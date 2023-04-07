# Branch explanation

We splited into several different branches here, mainly to approach a higher-order mutant of different types within shortest among of time. In the future, it might be interesting to explore the distribution (time/percentage) of multi-location mutant / multi-trial mutant.

- Multi-step mutation : multi-location mutant
- mutation-testing-add: multi-trial mutant
- mutation-testing-multi-loc: multi-location (under different function) mutant


# Setup


## Docker usage

Under root/docker:
`make build` to build the docker
`make once` to probe once into the docker image and discard the changes
`make script` to run the script over the docker image, this directly start the fuzzing process.

## Setup Environment First

Go into deps dir, make build all the dependencies. (SAW verification is quite fragile in terms of version requirement. The deps listed in this dir are most stable)

In order to match the script with in FAST on parsing the error messages returned from SAW verification, replace executable file saw in saw-nightly built from `make saw-nightly` with the one from:

![Workable saw nightly build, not available on their page anymore](tests/saw/deps/Linux-bins.zip)

# Replay

(Have to be in docker first)

Under test/saw

`python3 main.py replay addr_to_trace`. This will mutate and link the all_llvm.bc file into `tests/saw/bitcode/all_llvm.bc`.

In order to test it, simplest way is to directly run `absolute_path_to_saw/saw verify_xxxx.saw`


