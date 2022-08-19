#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /s2n-tls/tests/saw

# build the pass 
cd deps
make pass
cd -

# run the pass
./main.py pass init

# run the fuzzing
./main.py -v fuzz --clean 
