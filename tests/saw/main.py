#!/usr/bin/env python3
import os
import sys
import logging
import argparse
from typing import List

import config
from util import enable_coloring_in_logging, envpaths
from bitcode import (
    build_bitcode,
    mutation_init,
    mutation_pass_replay,
    mutation_pass_test,
)
from prover import verify_one, verify_all, dump_verification_output
from fuzzer import fuzz_start


def main(argv: List[str]) -> int:
    # setup argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=1)
    parser.add_argument("-l", "--log", action="store_true")
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

    parser_pass_subs_replay = parser_pass_subs.add_parser("replay")
    parser_pass_subs_replay.add_argument("input")

    parser_pass_subs_test = parser_pass_subs.add_parser("test")
    parser_pass_subs_test.add_argument("--filter-rule", default="*")
    parser_pass_subs_test.add_argument("--filter-function", default="*")
    parser_pass_subs_test.add_argument("--filter-instruction", default="*")
    parser_pass_subs_test.add_argument("--repetition", type=int, default=10)

    # args: fuzzing
    parser_fuzz = parser_subs.add_parser("fuzz", help="fuzzily mutation testing")
    parser_fuzz.add_argument("--clean", action="store_true")
    parser_fuzz.add_argument(
        "-j", "--jobs", type=int, default=int(config.NUM_CORES / 2)
    )

    # args: misc
    parser_misc = parser_subs.add_parser("misc", help="miscellaneous work items")
    parser_misc_subs = parser_misc.add_subparsers(dest="cmd_misc")

    parser_misc_subs_parse_verification_report = parser_misc_subs.add_parser(
        "parse_verification_output"
    )
    parser_misc_subs_parse_verification_report.add_argument("base")

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
    if args.log:
        logging.getLogger().addHandler(
            logging.FileHandler(config.PATH_WORK_FUZZ_LOG, mode="w")
        )

    # handle commands
    if args.cmd == "bitcode":
        build_bitcode(args.clean)

    elif args.cmd == "verify":
        if args.input == "ALL":
            errors = verify_all(config.PATH_BASE, config.PATH_WORK_SAW)
            if errors is not None:
                for entry in errors:
                    logging.warning("Verification failed with error\n{}".format(entry))
        else:
            if not verify_one(config.PATH_BASE, args.input, config.PATH_WORK_SAW):
                logging.warning("Verification failed with error\n{}".format(args.input))

    elif args.cmd == "pass":
        if args.cmd_pass == "init":
            mutation_points = mutation_init()
            logging.info("Mutation points collected: {}".format(len(mutation_points)))

        elif args.cmd_pass == "replay":
            mutation_pass_replay(args.input, config.PATH_ORIG_BITCODE_ALL_LLVM)

        elif args.cmd_pass == "test":
            mutation_pass_test(
                args.repetition,
                None if args.filter_rule == "*" else args.filter_rule,
                None if args.filter_function == "*" else args.filter_function,
                None
                if args.filter_instruction == "*"
                else int(args.filter_instruction),
            )

        else:
            parser_pass.print_help()
            return -1

    elif args.cmd == "fuzz":
        fuzz_start(args.clean, args.jobs)

    elif args.cmd == "misc":
        if args.cmd_misc == "parse_verification_output":
            if args.base == "BASE":
                wks = config.PATH_BASE
                workdir = config.PATH_WORK_SAW
                dump_verification_output(wks, workdir)
            elif args.base == "ALL":
                for instance in sorted(os.listdir(config.PATH_WORK_FUZZ_THREAD_DIR)):
                    wks = os.path.join(
                        config.PATH_WORK_FUZZ_THREAD_DIR, instance, "wks"
                    )
                    workdir = os.path.join(
                        config.PATH_WORK_FUZZ_THREAD_DIR, instance, "saw"
                    )
                    dump_verification_output(wks, workdir)
            elif args.base == "SEED":
                for instance in sorted(os.listdir(config.PATH_WORK_FUZZ_SEED_DIR)):
                    if instance == "0":
                        continue

                    workdir = os.path.join(
                        config.PATH_WORK_FUZZ_SEED_DIR, instance, "output"
                    )
                    dump_verification_output(config.PATH_WORK_FUZZ_THREAD_DIR, workdir)
            else:
                wks = os.path.join(config.PATH_WORK_FUZZ_THREAD_DIR, args.base, "wks")
                workdir = os.path.join(
                    config.PATH_WORK_FUZZ_THREAD_DIR, args.base, "saw"
                )
                dump_verification_output(wks, workdir)

        else:
            parser_misc.print_help()
            return -1

    else:
        parser.print_help()
        return -1

    return 0


if __name__ == "__main__":
    with envpaths(
        os.path.join(config.PATH_DEPS_SAW, "bin"),
        os.path.join(config.PATH_DEPS_LLVM, "bin"),
    ):
        sys.exit(main(sys.argv[1:]))
