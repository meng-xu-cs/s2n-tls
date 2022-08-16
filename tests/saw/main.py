#!/usr/bin/env python3
import os
import sys
import logging
import argparse
import shutil
from multiprocessing import Pool
from typing import List
from collections import OrderedDict

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


def _get_verification_targets() -> List[str]:
    all_saw_scripts = OrderedDict()
    for item in os.listdir(config.PATH_BASE):
        if item.endswith(".saw"):
            all_saw_scripts[item] = True  # this is a dummy value entry
    return [item for item in all_saw_scripts]


def verify_one(item: str) -> None:
    file_out = os.path.join(config.PATH_WORK_SAW, item + ".out")
    file_err = os.path.join(config.PATH_WORK_SAW, item + ".err")
    file_log = os.path.join(config.PATH_WORK_SAW, item + ".log")
    os.makedirs(os.path.dirname(file_log), exist_ok=True)

    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_SAW, "bin")):
            execute3(
                ["saw", "-s", file_log, "-f", "json", item],
                pout=file_out,
                perr=file_err,
            )


def verify_all_parallel() -> None:
    all_saw_scripts = _get_verification_targets()
    pool = Pool(config.NUM_CORES)
    pool.map(verify_one, all_saw_scripts)


def _run_mutation_pass(args: List[str]) -> None:
    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_LLVM, "bin")):
            execute(
                [
                    "opt",
                    "-load",
                    config.PATH_DEPS_PASS_LIB,
                    "-o",
                    config.PATH_ORIG_BITCODE_ALL_LLVM,
                    config.PATH_WORK_BITCODE_ALL_LLVM,
                    *args,
                ]
            )


def mutation_init() -> None:
    _run_mutation_pass([])


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
            verify_all_parallel()
        else:
            verify_one(args.input)

    elif args.cmd == "pass":
        if args.cmd_pass == "init":
            mutation_init()

        else:
            parser_pass.print_help()
            return -1

    else:
        parser.print_help()
        return -1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
