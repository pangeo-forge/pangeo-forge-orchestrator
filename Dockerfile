FROM golang:1.17-bullseye

# Build sops (see: https://rakhesh.com/docker/building-a-docker-sops-image/)
ENV SOPS_VERSION 3.7.3
RUN apt-get update && apt-get -y install make
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
RUN apt-get update && apt-get -y install curl wget unzip apt-transport-https ca-certificates
# is this the best way to get pip for python 3.9? https://stackoverflow.com/a/65644846
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3.9 get-pip.py

# Install terraform, which we need for release (could be a separate build stage in the future)\
ENV TF_VERSION 1.1.4
RUN wget --quiet https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip \
    && unzip terraform_${TF_VERSION}_linux_amd64.zip \
    && mv terraform /usr/local/bin/terraform \
    && rm terraform_${TF_VERSION}_linux_amd64.zip

# Install aws cli, for decrypting secrets via AWS KMS
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

# Install gcloud https://cloud.google.com/sdk/docs/install#installation_instructions
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt \
    cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | tee /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get -y install google-cloud-cli

# Install git, for fetching submodule contents in Dockerfile.heroku
RUN apt-get update && apt-get -y install git

# Install pip requirements, a time-consuming step!
COPY requirements.txt ./
RUN python3.9 -m pip install -r requirements.txt
