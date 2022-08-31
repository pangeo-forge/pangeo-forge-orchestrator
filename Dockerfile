# See: https://rakhesh.com/docker/building-a-docker-sops-image/
FROM golang:1.17-bullseye

ENV SOPS_VERSION 3.7.3

RUN apt-get update && apt-get -y install make

# Download the release; untar it; make it
ADD https://github.com/mozilla/sops/archive/v${SOPS_VERSION}.tar.gz /go/src/app/
RUN tar xzf /go/src/app/v${SOPS_VERSION}.tar.gz -C /go/src/app/
WORKDIR /go/src/app/sops-${SOPS_VERSION}
RUN make install

FROM ubuntu:22.04

COPY --from=0 /go/bin/sops /usr/local/bin/sops
# we need python3.9 because apache beam is not supported on 3.10
# is the best way to get 3.9 on ubuntu? https://askubuntu.com/a/682875
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get -y install tzdata software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get -y install python3.9-dev python3.9-distutils
RUN apt-get update && apt-get -y install curl apt-transport-https ca-certificates
# is this the best way to get pip for python 3.9? https://stackoverflow.com/a/65644846
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3.9 get-pip.py

# Install gcloud https://cloud.google.com/sdk/docs/install#installation_instructions
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt \
    cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | tee /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get -y install google-cloud-cli

# TODO: remove git + gcc, and revert python3.9-dev -> python3.9 above
# Only needed for now because installing unrealeased deps from github
RUN apt-get update && apt-get -y install git gcc
COPY requirements.txt ./
RUN python3.9 -m pip install -r requirements.txt

COPY . /opt/app
WORKDIR /opt/app

RUN chmod +x scripts.deploy/release.sh
