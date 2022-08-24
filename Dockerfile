# syntax=docker/dockerfile:1
FROM ubuntu:18.04

# pre-requisites
RUN apt-get update
RUN apt-get -y upgrade
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
    software-properties-common
RUN add-apt-repository -y \
    ppa:sri-csl/formal-methods
RUN add-apt-repository -y \
    ppa:deadsnakes/ppa
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential cmake ninja-build python3.9 wget rsync unzip \
    yices2 libssl-dev libtinfo5

# install the cmakes
ADD tests/saw/deps/Makefile Makefile
RUN make cmake-3.24.1
RUN make ninja-1.11.0

# prepare for data exchange
VOLUME /project

# prepare environment
ENV DOCKER=1
