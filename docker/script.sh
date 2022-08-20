#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /s2n-tls/tests/saw

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
./main.py -v fuzz --clean

# wait for user input
bash
