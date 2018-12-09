antiSMASH web infrastructure NCBI download service
==================================================

A service to download sequences from NCBI for the antiSMASH web service.

Installation
------------

Run the following (in a virtualenv):

```
git clone https://github.com/antismash/downloader
pip install downloader
```


Usage
-----

All important runtime configuration is kept in a configuration
file in [TOML](https://github.com/toml-lang/toml) format.

### Configuration Options

#### `redis` options

* **url**: URL to the redis database host
* **port**: Port the Redis database is listening on
* **db**: Database number of the Redis database

Example:
```toml
redis.url = redis_host
redis.port = 6379
redis.db = 0
```

#### `antismash` options

For now, there are two main options: the queues to listen on, and the queues to
push jobs into. The number of input and output queues need to be the same, jobs
collected from the input queue at index *i* will be deposited at index *i* of
the output queue list.

Additionally, you can configure the queue failed jobs will be dumped into. All
failed jobs end up in the same queue.

Example:
```toml
antismash.input_queues = [ "jobs:download-fast", "jobs:download", "jobs:download-dev" ]
antismash.output_queues = [ "jobs:minimal", "jobs:queued", "jobs:development" ]
antismash.failed_queue = "jobs:failed"
```

License
-------

All code is available under the Apache License version 2,
see the [`LICENSE`](LICENSE) file for details.
