"""Core functionality for the antiSMASH download service."""

from antismash_models import (
    SyncControl as Control,
    SyncJob as Job,
)
from ncbi_acc_download.core import Config as NadConfig
from ncbi_acc_download.core import download_to_file
from ncbi_acc_download.errors import DownloadError
import os
import redis
import time

from downloader.config import Config


def run(config: Config) -> None:
    """Run the antiSMASH download service."""

    db = create_db(config)
    control = Control(db, config.name, 1)
    control.commit()

    try:
        while True:
            if control.fetch().stop_scheduled:
                print("stop scheduled, exiting")
                break
            run_loop(config, db)
            time.sleep(5)
    finally:
        print("cleaning up")
        control.delete()


def run_loop(config: Config, db: redis.Redis) -> None:
    """Run one iteration of the main loop."""
    my_queue = "{}:downloading".format(config.name)
    uid = None
    for queue_name in config.queues:
        dl_queue = "{}:{}".format(queue_name, config.download_suffix)
        uid = db.rpoplpush(dl_queue, my_queue)
        if uid is not None:
            break

    if uid is None:
        return

    job = Job(db, uid).fetch()
    if job.needs_download and job.download:
        try:
            download_job_files(config, job)
        except DownloadError:
            job.state = "failed"
            job.status = "Failed to download file form NCBI"
            job.commit()
            queue_name = config.failed_queue

    db.lrem(my_queue, 1, job.job_id)
    db.lpush(queue_name, job.job_id)


def download_job_files(config: Config, job: Job) -> None:
    """Download the files of an antiSMASH job."""
    job.state = 'downloading'
    job.commit()

    dl_prefix = os.path.join(config.workdir, job.job_id, 'input', job.download)
    nad_conf = NadConfig(format="genbank", recursive=True)

    download_to_file(job.download, nad_conf, dl_prefix)

    job.state = 'queued'
    job.needs_download = False
    job.filename = '{}.gbk'.format(job.download)
    job.commit()


def create_db(config: Config) -> redis.Redis:
    """Create a Redis database connection."""
    return redis.Redis(host=config.redis_host,
                       port=config.redis_port,
                       db=config.redis_db,
                       encoding="utf-8",
                       decode_responses=True)
