#!/bin/bash

# configs
BASE_DIR=$(dirname $(realpath "$0"))
DEPS_DIR=$(realpath ${BASE_DIR}/../../deps)

export PATH=$PATH:${DEPS_DIR}/target/llvm-3.9.1/bin:${DEPS_DIR}/target/saw-0.9/bin

cd ${BASE_DIR} && make
