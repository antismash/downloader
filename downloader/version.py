"""Version-related functionality."""
import os
import subprocess


__version__ = '0.1.0'

_GIT_VERSION = None


def version():
    """Get the full version string."""
    ver = __version__

    git_ver = git_version()
    if git_ver:
        ver = "{}-{}".format(ver, git_ver)

    return ver


def git_version():
    """Get the git version."""
    global _GIT_VERSION  # pylint: disable=global-statement
    if _GIT_VERSION is None:
        proc = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'],
                                cwd=os.path.dirname(__file__),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, _ = proc.communicate()
        if proc.returncode != 0:
            ver = ""
        else:
            ver = stdout.strip().decode('utf-8')
        _GIT_VERSION = ver

    return _GIT_VERSION
