#!/usr/bin/env python3
import os
import sys
import logging
import argparse
from typing import List
from collections import OrderedDict

import config
from util import cd, enable_coloring_in_logging, execute, execute3, envpaths


def build_bitcode(clean: bool) -> None:
    if clean:
        with cd(config.PATH_BASE):
            execute(["make", "clean"])

    # run the target, with LLVM binaries
    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_LLVM, "bin")):
            execute(["make", "bitcode/all_llvm.bc"])


def verify_one(item: str) -> None:
    file_out = os.path.join(config.PATH_WORK_SAW, item + ".out")
    file_err = os.path.join(config.PATH_WORK_SAW, item + ".err")
    file_log = os.path.join(config.PATH_WORK_SAW, item + ".log")

    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_SAW, "bin")):
            execute3(
                ["saw", "-s", file_log, "-f", "json", item],
                pout=file_out,
                perr=file_err,
            )


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
        # collect all saw files
        all_saw_scripts = OrderedDict()
        for item in os.listdir(config.PATH_BASE):
            if item.endswith(".saw"):
                all_saw_scripts[item] = True  # this is a dummy

        if args.input == "ALL":
            for item in all_saw_scripts.keys():
                verify_one(item)
        else:
            assert args.input in all_saw_scripts
            verify_one(args.input)

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
