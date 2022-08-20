# syntax=docker/dockerfile:1
FROM ubuntu:20.04

# pre-requisites
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential cmake ninja-build python3 wget \
    libssl-dev libtinfo5

# prepare mount point
VOLUME /project

# prepare environment
ENV DOCKER=1
