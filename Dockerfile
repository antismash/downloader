# antiSMASH download service
# VERSION 0.1.0
FROM alpine:latest
MAINTAINER Kai Blin <kblin@biosustain.dtu.dk>

RUN apk --no-cache add python3 ca-certificates git gcc musl-dev python3-dev

# Make uids match the old Debian setup
RUN deluser $(getent passwd  | grep ":33:" | cut -d: -f1) && addgroup -S -g 33 www-data && adduser -S -g 33 -u 33 -H www-data

COPY . /downloader

WORKDIR /downloader

RUN pip3 install .

VOLUME ['/upload', '/config']

ENTRYPOINT ["/usr/bin/antismash-downloader"]
