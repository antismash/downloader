# Copyright 2018 Kai Blin
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""antiSMASH web infrastructure NCBI download service."""

import argparse
import os
import platform
import sys

from downloader.config import Config
from downloader.core import run

def main() -> None:
    """Start up the antiSMASH download service."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--configfile',
                        default=os.path.join(os.getcwd(), 'downloader.toml'),
                        help="Configuration file to load settings from (default: %(default)s).")
    parser.add_argument('-n', '--name',
                        default=platform.node(),
                        help="Host-specific name of the downloader (default: %(default)s).")
    parser.add_argument('-p', '--print-config',
                        action="store_true", default=False,
                        help="Print the configuration and exit.")
    args = parser.parse_args()

    conf = Config.from_configfile(args.name, args.configfile)

    if args.print_config:
        print(conf)
        sys.exit(0)

    run(conf)


if __name__ == "__main__":
    main()
