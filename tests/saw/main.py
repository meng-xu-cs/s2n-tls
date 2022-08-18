#!/usr/bin/env python3

import sys
import logging
import argparse
from typing import List

import config
from util import enable_coloring_in_logging
from bitcode import build_bitcode, mutation_init
from prover import verify_one, verify_all
from fuzzer import fuzz_start


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
    parser_fuzz.add_argument("-j", "--jobs", type=int, default=config.NUM_CORES)

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
            errors = verify_all(parallel=True)
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
        fuzz_start(args.clean, args.jobs)

    else:
        parser.print_help()
        return -1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
