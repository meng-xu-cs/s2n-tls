#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /project/tests/saw

# get the pass
cd deps
make pass
cd -

# build the bitcode
./main.py bitcode

# run the pass
./main.py pass init

# run the fuzzing
./main.py -v fuzz --clean 
