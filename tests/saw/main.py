#!/usr/bin/env python3

import os
import subprocess
import sys
import logging
import argparse
import shutil
import json
import re
from multiprocessing import Pool
from typing import List
from collections import OrderedDict
from dataclasses import dataclass

import config
from util import cd, enable_coloring_in_logging, execute, execute3, envpaths


#
# Preparation
#


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


#
# Verification
#

# TODO: ideally we should not ignore any SAW scripts.
IGNORED_TOP_LEVEL_SAW_SCRIPTS = [
    # ignored because of lengthy and nondeterministic verification
    "verify_imperative_cryptol_spec.saw"
]


def _get_verification_targets() -> List[str]:
    all_saw_scripts = OrderedDict()
    for item in os.listdir(config.PATH_BASE):
        if item.endswith(".saw") and item not in IGNORED_TOP_LEVEL_SAW_SCRIPTS:
            all_saw_scripts[item] = True  # this is a dummy value entry
    return [item for item in all_saw_scripts]


@dataclass(frozen=True, eq=True, order=True)
class VerificationError(object):
    goal: str
    location: str
    message: str
    details: str


@dataclass
class VerificationErrorBuilder(object):
    goal: str
    location: str
    message: str
    details: str

    def build(self) -> VerificationError:
        return VerificationError(self.goal, self.location, self.message, self.details)


def _parse_failure_report(item: str) -> List[VerificationError]:
    error_pattern = re.compile(
        r"^\[\d\d:\d\d:\d\d\.\d\d\d\] Subgoal failed: (.+?) (.+?): (.+?)$"
    )

    result: List[VerificationError] = []

    # scan for the stdout file for error patterns
    file_out = os.path.join(config.PATH_WORK_SAW, item + ".out")
    with open(file_out) as f:
        pending_error = None
        for line in f:
            line = line.strip()

            # consume the next line after the error message
            if pending_error is not None:
                pending_error.details = line
                result.append(pending_error.build())
                pending_error = None
                continue

            # check for error message
            match = error_pattern.match(line)
            if not match:
                continue

            # this line represents an error
            pending_error = VerificationErrorBuilder(
                match.group(1), match.group(2), match.group(3), ""
            )

    assert len(result) != 0
    return result


def verify_one(item: str) -> bool:
    file_out = os.path.join(config.PATH_WORK_SAW, item + ".out")
    file_err = os.path.join(config.PATH_WORK_SAW, item + ".err")
    file_log = os.path.join(config.PATH_WORK_SAW, item + ".log")
    os.makedirs(os.path.dirname(file_log), exist_ok=True)

    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_SAW, "bin")):
            try:
                execute3(
                    ["saw", "-s", file_log, "-f", "json", item],
                    pout=file_out,
                    perr=file_err,
                )
                return True
            except subprocess.SubprocessError:
                return False


def verify_all_sequential() -> List[VerificationError]:
    all_saw_scripts = _get_verification_targets()
    errors = set()
    for script in all_saw_scripts:
        if not verify_one(script):
            for err in _parse_failure_report(script):
                errors.add(err)
    return sorted(errors)


def verify_all_parallel() -> List[VerificationError]:
    all_saw_scripts = _get_verification_targets()
    pool = Pool(config.NUM_CORES)
    results = pool.map(verify_one, all_saw_scripts)

    # collect the failure cases
    errors = set()
    for result, script in zip(results, all_saw_scripts):
        if not result:
            for err in _parse_failure_report(script):
                errors.add(err)
    return sorted(errors)


def _collect_verified_functions() -> List[str]:
    # collect SAW files
    saw_scripts = _get_verification_targets()
    for base, _, files in os.walk(os.path.join(config.PATH_BASE, "spec")):
        for item in files:
            if item.endswith(".saw"):
                saw_scripts.append(os.path.join(base, item))

    # extract verified functions
    verified_functions = set()
    for script in saw_scripts:
        with open(script) as f:
            for line in f:
                tokens = line.strip().split()
                for i, tok in enumerate(tokens):
                    if tok == "crucible_llvm_verify":
                        target = tokens[i + 2]
                        assert target.startswith('"')
                        assert target.endswith('"')
                        verified_functions.add(target[1:-1])

    return sorted(verified_functions)


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


def mutation_init() -> None:
    os.makedirs(config.PATH_WORK_FUZZ, exist_ok=True)

    # we need these high-level verified functions to build a call graph
    targets = _collect_verified_functions()
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


def mutation_pass_replay(seed: str) -> None:
    _run_mutation_pass(
        config.PATH_WORK_BITCODE_ALL_LLVM,
        config.PATH_ORIG_BITCODE_ALL_LLVM,
        [
            "replay",
            "-mutest-input",
            seed,
        ],
    )


def fuzz_start(clean: bool) -> None:
    if clean:
        shutil.rmtree(config.PATH_WORK_FUZZ)
        logging.info("Previous fuzzing work cleared out")

    # initialize the necessary information
    if not os.path.exists(config.PATH_WORK_FUZZ_MUTATION_POINTS):
        mutation_init()
        logging.info("Mutation points collected")

    # load the seeds
    os.makedirs(config.PATH_WORK_FUZZ_SEED_DIR, exist_ok=True)
    logging.info(
        "Processing existing fuzzing seeds: {}".format(
            len(os.listdir(config.PATH_WORK_FUZZ_SEED_DIR))
        )
    )


#
# Entrypoint
#


def main(argv: List[str]) -> int:
    # setup argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=1)
    parser_subs = parser.add_subparsers(dest="cmd")

    # args: bitcode
    parser_bitcode = parser_subs.add_parser(
        "bitcode", help="build the all_llvm.bc file"
    )
    parser_bitcode.add_argument("--clean", action="store_true")

    # args: verify
    parser_verify = parser_subs.add_parser("verify", help="verify a single saw script")
    parser_verify.add_argument("input")

    # args: mutation pass
    parser_pass = parser_subs.add_parser(
        "pass", help="invoke a single action on the mutation pass"
    )
    parser_pass_subs = parser_pass.add_subparsers(dest="cmd_pass")
    parser_pass_subs_init = parser_pass_subs.add_parser("init")
    parser_pass_subs_init.add_argument("-o", "--output")

    # args: fuzzing
    parser_fuzz = parser_subs.add_parser("fuzz", help="fuzzily mutation testing")
    parser_fuzz.add_argument("--clean", action="store_true")

    # parse arguments
    args = parser.parse_args(argv)

    # prepare logs
    LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
    LOG_LEVEL = (
        logging.WARNING
        if args.verbose == 0
        else logging.INFO
        if args.verbose == 1
        else logging.DEBUG
    )
    enable_coloring_in_logging()
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)

    # handle commands
    if args.cmd == "bitcode":
        build_bitcode(args.clean)

    elif args.cmd == "verify":
        if args.input == "ALL":
            errors = verify_all_parallel()
            for item in errors:
                logging.warning("Verification failed with error\n{}".format(item))
        else:
            if not verify_one(args.input):
                logging.warning("Verification failed with error\n{}".format(args.input))

    elif args.cmd == "pass":
        if args.cmd_pass == "init":
            mutation_init()

        else:
            parser_pass.print_help()
            return -1

    elif args.cmd == "fuzz":
        fuzz_start(args.clean)

    else:
        parser.print_help()
        return -1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
