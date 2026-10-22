from pathlib import Path

import pytest
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from antismash_models import SyncJob as Job

from downloader import (
    config,
    core,
)

import downloader.core


def test_run_loop_target_queues(db, mocker, tmpdir):
    mocker.patch("downloader.core.download_job_files")
    upload_dir = tmpdir.mkdir("upload")
    cfg = config.Config(name="test", workdir=str(upload_dir))
    job = Job(db, "bacteria-123456")
    job.target_queues.append("jobs:special")
    job.commit()
    db.lpush("jobs:downloads", job.job_id)
    core.run_loop(cfg, db)

    job.fetch()

    assert job.target_queues == []
    assert db.rpop("jobs:special") == job.job_id


@pytest.mark.parametrize("source", ["pending", "recovery"])
@pytest.mark.parametrize("field, value", [
    pytest.param(None, None, id="missing-job"),
    pytest.param("trace", "not valid JSON", id="malformed-json"),
    pytest.param("from_pos", "not an integer", id="invalid-number"),
    pytest.param("sideload_simple", ":1-2", id="invalid-sideload-accession"),
])
def test_run_loop_skips_unfetchable_job_and_continues(
    db, mocker, tmp_path, caplog, source, field, value,
):
    cfg = config.Config(name="test", workdir=str(tmp_path), use_metrics=False)
    recovery_queue = f"{cfg.name}:downloading"
    bad_id = "bacteria-bad"
    download = mocker.patch("downloader.core.download_job_files")
    if field is not None:
        bad = Job(db, bad_id)
        bad.needs_download = True
        bad.download = "NC_000001.1"
        bad.commit()
        # Corrupt the stored record so the real model's fetch/parser is exercised.
        db.hset(f"job:{bad_id}", field, value)

    good = Job(db, "bacteria-good")
    good.target_queues = ["jobs:ready"]
    good.commit()
    db.lpush(cfg.download_queue, good.job_id)
    if source == "pending":
        db.rpush(cfg.download_queue, bad_id)
    else:
        db.lpush(recovery_queue, bad_id)

    core.run_loop(cfg, db)

    assert db.lrange(recovery_queue, 0, -1) == []
    assert db.lrange(cfg.download_queue, 0, -1) == [good.job_id]
    assert db.lrange("jobs:ready", 0, -1) == []
    assert bad_id in caplog.text
    download.assert_not_called()

    core.run_loop(cfg, db)

    assert db.lrange(recovery_queue, 0, -1) == []
    assert db.lrange(cfg.download_queue, 0, -1) == []
    assert db.lrange("jobs:ready", 0, -1) == [good.job_id]
    download.assert_not_called()


@pytest.mark.parametrize("source", ["pending", "recovery"])
@pytest.mark.parametrize("error_type", [RedisConnectionError, RedisTimeoutError])
def test_run_loop_preserves_job_after_redis_fetch_failure(
    db, mocker, tmp_path, source, error_type,
):
    cfg = config.Config(name="test", workdir=str(tmp_path), use_metrics=False)
    recovery_queue = f"{cfg.name}:downloading"
    job = Job(db, "bacteria-123456")
    job.target_queues = ["jobs:ready"]
    job.commit()
    record = db.hgetall(f"job:{job.job_id}")
    queue = cfg.download_queue if source == "pending" else recovery_queue
    db.lpush(queue, job.job_id)
    error = error_type("Redis unavailable during fetch")
    # EXISTS is the first Redis operation inside Job.fetch(), after claiming the ID.
    exists = mocker.patch.object(db, "exists", side_effect=error)

    with pytest.raises(error_type) as caught:
        core.run_loop(cfg, db)

    assert caught.value is error
    assert db.lrange(recovery_queue, 0, -1) == [job.job_id]
    assert db.lrange(cfg.download_queue, 0, -1) == []
    assert db.lrange("jobs:ready", 0, -1) == []
    assert db.lrange(cfg.failed_queue, 0, -1) == []
    assert db.hgetall(f"job:{job.job_id}") == record

    mocker.stop(exists)
    core.run_loop(cfg, db)

    assert db.lrange(recovery_queue, 0, -1) == []
    assert db.lrange("jobs:ready", 0, -1) == [job.job_id]
    assert Job(db, job.job_id).fetch().target_queues == []


def test_sanitize_filename():
    assert core.sanitize_filename("test") == "test"
    assert core.sanitize_filename("test/../test") == "test__test"
    assert core.sanitize_filename("test/../../test") == "test___test"
    assert core.sanitize_filename("test/..\\..\\test") == "test___test"
    assert core.sanitize_filename("test/..\\..\\..\\test") == "test____test"
    assert core.sanitize_filename("test/..\\..\\..\\..\\test") == "test_____test"
    assert core.sanitize_filename("test/..\\..\\..\\..\\..\\test") == "test______test"
    assert core.sanitize_filename("test/..\\..\\..\\..\\..\\..\\test") == "test_______test"


@pytest.fixture
def download_context(db, mocker, tmp_path):
    upload_dir = tmp_path / "upload"
    cfg = config.Config(name="test", workdir=str(upload_dir), use_metrics=False)
    job = Job(db, "bacteria-123456")
    job.download = "NC_000001.1"
    job.needs_download = True
    job.state = "waiting"
    job.trace = ["submitter"]
    job.commit()
    input_dir = upload_dir / job.job_id / "input"
    input_dir.mkdir(parents=True)
    download = mocker.patch("downloader.core.download_to_file")
    return cfg, job, input_dir, download


def test_download_job_files_success(db, download_context):
    cfg, job, input_dir, download = download_context
    destination = input_dir / "NC_000001.1.gbk"

    def perform_download(accession, nad_conf, prefix):
        # The in-progress state must be visible to other services before downloading.
        downloading = Job(db, job.job_id).fetch()
        assert downloading.state == "downloading"
        assert downloading.status == f"Downloading {accession} from NCBI"
        assert downloading.needs_download is True
        assert downloading.trace == ["submitter", cfg.name]
        assert nad_conf.format == "genbank"
        assert nad_conf.recursive is True
        assert prefix == str(input_dir / "NC_000001.1")
        Path(f"{prefix}.gbk").write_text("downloaded sequence")

    download.side_effect = perform_download

    core.download_job_files(cfg, job)

    download.assert_called_once()
    assert destination.read_text() == "downloaded sequence"
    saved = Job(db, job.job_id).fetch()
    assert saved.state == "queued"
    assert saved.status == "pending"
    assert saved.needs_download is False
    assert saved.filename == str(destination.resolve())
    assert saved.trace == ["submitter", cfg.name]
    assert saved.download == "NC_000001.1"


@pytest.mark.parametrize("accession, stem", [
    ("../outside", "_outside"),
    ("/tmp/outside", "_tmp_outside"),
    (r"..\outside", "_outside"),
    ("A" * 40, "A" * 32),
])
def test_download_job_files_contains_download_filename(db, download_context, accession, stem):
    cfg, job, input_dir, download = download_context
    job.download = accession

    core.download_job_files(cfg, job)

    download.assert_called_once()
    original_accession, _, prefix = download.call_args.args
    assert original_accession == accession
    assert prefix == str(input_dir / stem)
    destination = Path(f"{prefix}.gbk").resolve()
    assert destination.is_relative_to(input_dir.resolve())
    assert Job(db, job.job_id).fetch().filename == str(destination)


@pytest.mark.parametrize("job_id", [
    "", ".", "..", "../other-job", "/tmp/other-job", r"..\other-job", "bacteria-123/other",
])
def test_download_job_files_rejects_invalid_job_id(db, download_context, job_id):
    cfg, original, _, download = download_context
    job = Job(db, job_id)
    job.download = original.download
    job.needs_download = True

    with pytest.raises(ValueError, match="Invalid job ID"):
        core.download_job_files(cfg, job)

    download.assert_not_called()


@pytest.mark.parametrize("accession", ["", ".", ".."])
def test_download_job_files_rejects_empty_or_dot_filename(download_context, accession):
    cfg, job, _, download = download_context
    job.download = accession

    with pytest.raises(ValueError, match="Invalid download filename"):
        core.download_job_files(cfg, job)

    download.assert_not_called()


@pytest.mark.parametrize("component", ["job", "input"])
def test_download_job_files_rejects_redirected_directory(download_context, tmp_path, component):
    cfg, job, input_dir, download = download_context
    original = input_dir.parent if component == "job" else input_dir
    redirected = tmp_path / "redirected"
    original.rename(redirected)
    original.symlink_to(redirected, target_is_directory=True)

    with pytest.raises(ValueError, match="Job input directory is redirected"):
        core.download_job_files(cfg, job)

    download.assert_not_called()


@pytest.mark.parametrize("target_kind", ["outside-existing", "outside-missing", "other-job"])
def test_download_job_files_rejects_escaping_output_symlink(
    download_context, tmp_path, target_kind,
):
    cfg, job, input_dir, download = download_context
    if target_kind == "other-job":
        target = input_dir.parents[1] / "bacteria-other" / "input" / "sequence.gbk"
        target.parent.mkdir(parents=True)
    else:
        target = tmp_path / "outside.gbk"
    if target_kind != "outside-missing":
        target.write_text("existing sequence")
    (input_dir / f"{job.download}.gbk").symlink_to(target)

    with pytest.raises(ValueError, match="Download destination escapes job input directory"):
        core.download_job_files(cfg, job)

    download.assert_not_called()
    if target_kind == "outside-missing":
        assert not target.exists()
    else:
        assert target.read_text() == "existing sequence"


def test_download_job_files_requires_existing_input_directory(download_context):
    cfg, job, input_dir, download = download_context
    input_dir.rmdir()

    with pytest.raises(FileNotFoundError):
        core.download_job_files(cfg, job)

    download.assert_not_called()


@pytest.mark.parametrize("error", [
    pytest.param(core.DownloadError("download failed"), id="download"),
    pytest.param(core.InvalidIdError("invalid accession", "NC_000001.1", 400), id="invalid-id"),
    pytest.param(core.ValidationError("invalid record"), id="validation"),
    pytest.param(OSError("disk full"), id="filesystem"),
])
def test_download_job_files_propagates_failure_without_marking_success(db, download_context, error):
    cfg, job, _, download = download_context
    download.side_effect = error

    with pytest.raises(type(error)) as caught:
        core.download_job_files(cfg, job)

    assert caught.value is error
    download.assert_called_once()
    saved = Job(db, job.job_id).fetch()
    assert saved.state == "downloading"
    assert saved.status == f"Downloading {job.download} from NCBI"
    assert saved.needs_download is True
    assert saved.filename is None
