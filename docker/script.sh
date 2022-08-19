#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /s2n-tls/tests/saw

# get llvm and the pass
cd deps
make llvm-3.9.1
make pass
cd -

# build the bitcode
./main.py bitcode

# run the pass
./main.py pass init

# run the fuzzing
./main.py -v fuzz --clean 
