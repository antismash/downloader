"""Core functionality for the antiSMASH download service."""

from pathlib import Path

from antismash_models import (
    SyncControl as Control,
    SyncJob as Job,
)
import logging
from ncbi_acc_download.core import Config as NadConfig
from ncbi_acc_download.core import download_to_file
from ncbi_acc_download.errors import (
    DownloadError,
    InvalidIdError,
    ValidationError,
)
import os
from prometheus_client import (
    Counter,
    start_http_server,
    Summary,
)
import redis
import time

from downloader.config import Config
from downloader.version import git_version

MAX_FILE_NAME_LENGTH = 32
DOWNLOAD_TIME = Summary("download_processing_seconds", "Time spent downloading files from NCBI")
INVALID_ID = Counter("download_invalid_id_total", "Number of downloads failed due to an invalid ID")
DOWNLOAD_ERROR = Counter("download_unknown_error_total", "Number of downloads failed due to an unknown errror")
VALIDATION_ERROR = Counter("download_validation_error_total", "Number of downloads failing validation")


def run(config: Config) -> None:
    """Run the antiSMASH download service."""

    db = create_db(config)
    control = Control(db, config.name, 1, git_version())
    control.commit()

    try:
        if config.use_metrics:
            start_http_server(config.metrics_port)
        while True:
            if control.fetch().stop_scheduled:
                logging.info("stop scheduled, exiting")
                break
            run_loop(config, db)
            control.alive()
            time.sleep(1)
    finally:
        logging.info("cleaning up")
        control.delete()


def run_loop(config: Config, db: redis.Redis) -> None:
    """Run one iteration of the main loop."""
    my_queue = "{}:downloading".format(config.name)
    uid = None
    queues_to_check = [config.download_queue]

    # First, try to pick up any left over jobs from before a crash
    uid = db.lindex(my_queue, -1)

    for queue in queues_to_check:
        if uid is not None:
            break
        uid = db.rpoplpush(queue, my_queue)

    if uid is None:
        return

    try:
        job = Job(db, uid).fetch()
    except ValueError:
        logging.error("Invalid job ID %s, skipping", uid)
        db.lrem(my_queue, 1, uid)
        return
    except IndexError:
        logging.error("Job %s failed to parse, skipping", uid)
        db.lrem(my_queue, 1, uid)
        return
    if job.needs_download and job.download:
        try:
            logging.info("Downloading files for %s", job.job_id)
            download_job_files(config, job)
            logging.info("Done with %s", job.job_id)
        except (DownloadError, InvalidIdError, ValidationError, ValueError) as err:
            job.state = "failed"
            job.status = "Failed to download file from NCBI"
            job.target_queues.append(config.failed_queue)
            if isinstance(err, ValidationError):
                VALIDATION_ERROR.inc()
            elif isinstance(err, InvalidIdError):
                INVALID_ID.inc()
            elif isinstance(err, DownloadError):
                DOWNLOAD_ERROR.inc()
            elif isinstance(err, ValueError):
                logging.error("ValueError raised when trying to download {j.job_id}:{j.download}".format(j=job))
                DOWNLOAD_ERROR.inc()

    move_job(job, db, my_queue)


@DOWNLOAD_TIME.time()
def download_job_files(config: Config, job: Job) -> None:
    """Download the files of an antiSMASH job."""
    job.state = 'downloading'
    job.status = "Downloading {} from NCBI".format(job.download)
    job.trace.append(config.name)
    job.commit()

    # Validate the original job ID before constructing its directory.
    job_id = job.job_id
    if job_id in {"", ".", ".."} or "/" in job_id or "\\" in job_id:
        raise ValueError("Invalid job ID")

    root = Path(config.workdir).resolve(strict=True)
    expected_input = root / job_id / "input"
    input_dir = expected_input.resolve(strict=True)

    # Reject symlinks that redirect the job directory elsewhere.
    if input_dir != expected_input:
        raise ValueError("Job input directory is redirected")

    dl_name = sanitize_filename(job.download[:MAX_FILE_NAME_LENGTH])
    if dl_name in {"", ".", ".."}:
        raise ValueError("Invalid download filename")

    destination = (input_dir / f"{dl_name}.gbk").resolve()

    if not destination.is_relative_to(input_dir):
        raise ValueError("Download destination escapes job input directory")

    # The library adds ".gbk" itself.
    dl_prefix = str(input_dir / dl_name)
    nad_conf = NadConfig(format="genbank", recursive=True)
    download_to_file(job.download, nad_conf, dl_prefix)

    # The dispatcher mounts the job's input directory at /input in its container.
    job.filename = destination.name
    job.state = 'queued'
    job.needs_download = False
    job.status = "pending"
    job.commit()


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to be safe for use in the filesystem."""
    # remove ../ sequences and any other potentially dangerous characters
    return filename.replace("..", "").replace("/", "_").replace("\\", "_")


def create_db(config: Config) -> redis.Redis:
    """Create a Redis database connection."""
    return redis.Redis(host=config.redis_host,
                       port=config.redis_port,
                       db=config.redis_db,
                       password=config.redis_pass,
                       encoding="utf-8",
                       decode_responses=True)


def move_job(job: Job, db: redis.Redis, source_queue: str, target_queue: str | None = None) -> None:
    """Move a job from one queue to another."""
    if target_queue is None and job.target_queues:
        target_queue = job.target_queues.pop()
        job.commit()
    if target_queue is None:
        target_queue = "jobs:queued"
    with db.pipeline(transaction=True) as pipe:
        pipe.lrem(source_queue, 1, job.job_id)
        pipe.lpush(target_queue, job.job_id)
        pipe.execute()
