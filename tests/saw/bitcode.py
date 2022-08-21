"""
LLVM-based functionalities
"""
import logging
import os
import shutil
import json
from dataclasses import asdict, dataclass
from typing import List, Dict, Any, Optional

import config
from util import cd, execute
from prover import collect_verified_functions


def build_bitcode(clean: bool) -> None:
    if clean:
        with cd(config.PATH_BASE):
            execute(["make", "clean"])

    # run the target, with LLVM binaries
    with cd(config.PATH_BASE):
        execute(["make", "-j", str(config.NUM_CORES), "bitcode/all_llvm.bc"])

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

    # refresh the pass
    with cd(config.PATH_DEPS):
        execute(["make", "pass"])

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


def mutation_pass_replay(trace: str, bc_into: str) -> None:
    _run_mutation_pass(
        config.PATH_WORK_BITCODE_ALL_LLVM,
        bc_into,
        [
            "replay",
            "-mutest-input",
            trace,
        ],
    )


def mutation_pass_mutate(
    point: MutationPoint, output: str, bc_from: str, bc_into: str
) -> None:
    _run_mutation_pass(
        bc_from,
        bc_into,
        [
            "mutate",
            "-mutest-target-rule",
            point.rule,
            "-mutest-target-function",
            point.function,
            "-mutest-target-instruction",
            str(point.instruction),
            "-mutest-output",
            output,
        ],
    )


def mutation_pass_test(
    repetition: int,
    filter_rule: Optional[str],
    filter_function: Optional[str],
    filter_instruction: Optional[int],
) -> None:
    all_points = mutation_init()
    for point in all_points:
        if filter_rule is not None and filter_rule != point.rule:
            continue
        if filter_function is not None and filter_function != point.function:
            continue
        if filter_instruction is not None and filter_instruction != point.instruction:
            continue

        logging.info(
            "Testing: {} on {}::{}".format(
                point.rule, point.function, point.instruction
            )
        )

        for k in range(repetition):
            # test mutation
            mutation_pass_mutate(
                point,
                config.PATH_WORK_BITCODE_MUTATION,
                config.PATH_WORK_BITCODE_ALL_LLVM,
                config.PATH_ORIG_BITCODE_ALL_LLVM,
            )
            logging.debug("  [{}] mutation done".format(k))

            # test replay
            with open(config.PATH_WORK_BITCODE_MUTATION) as f1:
                result = json.load(f1)
                if not result["changed"]:
                    logging.warning("Mutation point results in no change")
                    continue

            step = MutationStep(
                point.rule, point.function, point.instruction, result["package"]
            )
            with open(config.PATH_WORK_BITCODE_MUTATION, "w") as f2:
                json.dump([asdict(step)], f2, indent=4)

            mutation_pass_replay(
                config.PATH_WORK_BITCODE_MUTATION, config.PATH_ORIG_BITCODE_ALL_LLVM
            )
            logging.debug("  [{}] replay done".format(k))
