#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /project/tests/saw

# get the pass
cd deps
rm -rf target/Pass
make pass
cd -

# build the bitcode
./main.py bitcode --clean

# run the pass
./main.py pass init

# run the fuzzing
./main.py -v fuzz --jobs 16 --clean

# wait for user input
bash
