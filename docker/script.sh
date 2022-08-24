#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /project/tests/saw

# build the bitcode
./main.py bitcode --clean

# run the pass
./main.py pass init

# run the fuzzing
./main.py -v -l fuzz --clean

# wait for user input
bash
