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
RUN apt-get update && apt-get -y install curl python3 python3-pip apt-transport-https ca-certificates

# Install gcloud https://cloud.google.com/sdk/docs/install#installation_instructions
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt \
    cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | tee /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get -y install google-cloud-cli

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . /opt/app
WORKDIR /opt/app
