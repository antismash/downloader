"""Configuration handling for the antiSMASH download service."""

import os
import toml
from typing import Sequence

class Config:
    """Central configuration class for the antiSMASH download service."""

    __slots__ = (
        "download_suffix",
        "failed_queue",
        "name",
        "queues",
        "redis_db",
        "redis_host",
        "redis_port",
        "workdir",
    )

    def __init__(self,
                 name: str,
                 download_suffix: str = "downloads",
                 failed_queue: str = "jobs:failed",
                 queues: Sequence[str] = ["jobs:queued"],
                 redis_db: int = 0,
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 workdir: str = "upload",
                ) -> None:
        """Initialise the Config."""

        self.name = "{}-downloader".format(name)
        self.workdir = os.path.abspath(workdir)

        self.failed_queue = failed_queue
        self.queues = queues
        self.download_suffix = download_suffix

        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db

    def __str__(self) -> str:
        return (
            "Config(n={c.name}, "
            "redis=redis://{c.redis_host}:{c.redis_port}/{c.redis_db}, "
            "q={c.queues}, s={c.download_suffix}, f={c.failed_queue}, "
            "w={c.workdir})".format(c=self))

    @classmethod
    def from_configfile(cls, name: str, filename: str) -> "Config":
        if not os.path.isfile(filename):
            return cls(name)

        config = toml.load(filename)
        params = {}  #  type: dict
        if 'redis' in config:
            if 'host' in config['redis']:
                params['redis_host'] = config['redis']['host']
            if 'db' in config['redis']:
                params['redis_db'] = config['redis']['db']
            if 'port' in config['redis']:
                params['redis_port'] = config['redis']['port']
        if 'antismash' in config:
            if 'failed_queue' in config['antismash']:
                params['failed_queue'] = config['antismash']['failed_queue']
            if 'queues' in config['antismash']:
                params['queues'] = config['antismash']['queues']
            if 'download_suffix' in config['antismash']:
                params['download_suffix'] = config['antismash']['download_suffix']
            if 'workdir' in config['antismash']:
                params['workdir'] = config['antismash']['workdir']
        return cls(name, **params)
