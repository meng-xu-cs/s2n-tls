# syntax=docker/dockerfile:1
FROM ubuntu:22.04

# pre-requisites
RUN apt-get update
RUN apt-get install -y \
    build-essential git curl cmake ninja-build python3 \
    flex bison bc cpio libncurses-dev libssl-dev libelf-dev libtinfo5

# prepare the project 
ADD . s2n-tls

# prepare environment
ENV DOCKER=1
