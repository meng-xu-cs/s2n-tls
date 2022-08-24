#!/bin/bash

# exit when any command fails
set -e

# prepare
source $HOME/.profile
cd /project/tests/saw

# build the bitcode
python3.9 main.py bitcode --clean

# run the pass
python3.9 main.py pass init

# run the fuzzing
python3.9 main.py -v -l fuzz --clean

# wait for user input
bash
