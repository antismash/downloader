
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
