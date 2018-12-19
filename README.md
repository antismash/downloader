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
[redis]
url = redis_host
port = 6379
db = 0
```

#### `antismash` options

* **queues**: A list of queues to service. The input queue names are created by adding the `download_suffix`, see below.
* **download_suffix**: A suffix to append to an output queue name to get the download queue name.
* **failed_queue**: Queue to deposit failed jobs into.
* **workdir**: Path to directory holding all the antiSMASH job files.

Example:
```toml
[antismash]
queues = [ "jobs:fast", "jobs:queued", "jobs:development" ]
download_suffix = "downloads"
failed_queue = "jobs:failed"
workdir = "/path/to/antismash/upload/dir"
```


#### `metrics` options

* **port**: Port to expose Prometheus metrics on
* **use_metrics**: Turn metrics reporting on/off

Example:
```toml
[metrics]
port = 9151
use_metrics = true
```


License
-------

All code is available under the Apache License version 2,
see the [`LICENSE`](LICENSE) file for details.
