# See: https://rakhesh.com/docker/building-a-docker-sops-image/
FROM golang:1.17-bullseye

ENV SOPS_VERSION 3.7.3

RUN apt-get -y install make

# Download the release; untar it; make it
ADD https://github.com/mozilla/sops/archive/v${SOPS_VERSION}.tar.gz /go/src/app/
RUN tar xzf /go/src/app/v${SOPS_VERSION}.tar.gz -C /go/src/app/
WORKDIR /go/src/app/sops-${SOPS_VERSION}
RUN make install

FROM ubuntu:22.04

COPY --from=0 /go/bin/sops /usr/local/bin/sops
