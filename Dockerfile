# syntax=docker/dockerfile:1
FROM ubuntu:18.04
# pre-requisites
RUN apt-get update
RUN apt-get -y --fix-missing upgrade
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    software-properties-common
RUN add-apt-repository -y \
    ppa:sri-csl/formal-methods
RUN add-apt-repository -y \
    ppa:deadsnakes/ppa
RUN apt-get update --fix-missing
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential cmake ninja-build python3.9 wget rsync unzip \
    yices2 z3  libssl-dev libtinfo5 vim curl python3-pip

# install pip dependencies
RUN pip3 install dataclasses

# install the cmakes
ADD tests/saw/deps/Makefile Makefile
RUN make cmake-3.24.1
RUN make ninja-1.11.0
RUN make llvm-3.9.1
RUN make saw-nightly
# prepare for data exchange
VOLUME /project

# prepare environment
ENV DOCKER=1
