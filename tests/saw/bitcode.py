"""
LLVM-based functionalities
"""

import os
import shutil
import json
from dataclasses import dataclass
from typing import List, Dict, Any

import config
from util import cd, execute, envpaths
from prover import collect_verified_functions


def build_bitcode(clean: bool) -> None:
    if clean:
        with cd(config.PATH_BASE):
            execute(["make", "clean"])

    # run the target, with LLVM binaries
    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_LLVM, "bin")):
            execute(["make", "bitcode/all_llvm.bc"])

    # save a copy of the generated bitcode
    os.makedirs(config.PATH_WORK_BITCODE, exist_ok=True)
    shutil.copyfile(
        os.path.join(config.PATH_ORIG_BITCODE_ALL_LLVM),
        os.path.join(config.PATH_WORK_BITCODE_ALL_LLVM),
    )


@dataclass(frozen=True, eq=True, order=True)
class MutationPoint(object):
    rule: str
    function: str
    instruction: int


@dataclass(frozen=True, eq=True, order=True)
class MutationStep(object):
    rule: str
    function: str
    instruction: int
    package: Dict[str, Any]


def load_mutation_points() -> List[MutationPoint]:
    with open(config.PATH_WORK_FUZZ_MUTATION_POINTS) as f:
        jobj = json.load(f)
        return [MutationPoint(**item) for item in jobj]


def _run_mutation_pass(bc_from: str, bc_into: str, args: List[str]) -> None:
    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_LLVM, "bin")):
            execute(
                [
                    "opt",
                    "-load",
                    config.PATH_DEPS_PASS_LIB,
                    "-mutest",
                    "-o",
                    bc_into,
                    bc_from,
                    *args,
                ]
            )


def mutation_init() -> List[MutationPoint]:
    os.makedirs(config.PATH_WORK_FUZZ, exist_ok=True)

    # we need these high-level verified functions to build a call graph
    targets = collect_verified_functions()
    with open(config.PATH_WORK_FUZZ_ENTRY_TARGETS, "w") as f:
        json.dump(targets, f, indent=4)

    # now invoke the llvm pass to collect mutation points
    _run_mutation_pass(
        config.PATH_WORK_BITCODE_ALL_LLVM,
        config.PATH_ORIG_BITCODE_ALL_LLVM,
        [
            "init",
            "-mutest-input",
            config.PATH_WORK_FUZZ_ENTRY_TARGETS,
            "-mutest-output",
            config.PATH_WORK_FUZZ_MUTATION_POINTS,
        ],
    )

    # load the mutation points
    return load_mutation_points()


def mutation_pass_replay(trace: str) -> None:
    _run_mutation_pass(
        config.PATH_WORK_BITCODE_ALL_LLVM,
        config.PATH_ORIG_BITCODE_ALL_LLVM,
        [
            "replay",
            "-mutest-input",
            trace,
        ],
    )
