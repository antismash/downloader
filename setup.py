import os
import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

long_description = read('README.md')

install_requires = [
    'antismash-models >= 0.1.23',
    'biopython',
    'hiredis',
    'ncbi-acc-download >= 0.2.5',
    'prometheus_client',
    'redis',
    'toml',
]

tests_require = [
    'coverage',
    'fakeredis',
    'pytest',
    'pytest-cov',
    'pytest-mock',
]


def read_version():
    for line in open(os.path.join('downloader', 'version.py'), 'r'):
        if line.startswith('__version__'):
            return line.split('=')[-1].strip().strip("'")


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)


setup(
    name='antismash-downloader',
    version=read_version(),
    author='Kai Blin',
    author_email='kblin@biosustain.dtu.dk',
    description='antiSMASH web infrastructure NCBI download service',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=install_requires,
    tests_require=tests_require,
    cmdclass={'test': PyTest},
    entry_points={
        'console_scripts': [
            'antismash-downloader=downloader.__main__:main',
        ],
    },
    packages=['downloader'],
    url='https://github.com/antismash/downloader/',
    license='Apache Software License',
    classifiers=[
        'Programming Language :: Python',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    extras_require={
        'testing': tests_require,
    },
)
