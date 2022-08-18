"""
Fuzzing-related functionalities
"""

import os
import json
import logging
import shutil
from dataclasses import asdict
from typing import List, Set

import config
from bitcode import mutation_init
from prover import VerificationError

#
# Global variable shared across the threads
#

COV_GLOBAL: Set[VerificationError] = set()


def _save_seed_cov(seed: str, cov: List[VerificationError]) -> None:
    cov_path = os.path.join(config.PATH_WORK_FUZZ_SEED_DIR, seed, "cov.json")
    with open(cov_path, "w") as f:
        jobj = [asdict(item) for item in cov]
        json.dump(jobj, f, indent=4)


def _load_seed_cov(seed: str) -> List[VerificationError]:
    cov_path = os.path.join(config.PATH_WORK_FUZZ_SEED_DIR, seed, "cov.json")
    with open(cov_path) as f:
        jobj = json.load(f)
        return [VerificationError(**item) for item in jobj]


def _dump_cov_global() -> None:
    cov_path = os.path.join(config.PATH_WORK_FUZZ_STATUS_DIR, "cov.json")
    with open(cov_path, "w") as f:
        jobj = [asdict(item) for item in sorted(COV_GLOBAL)]
        json.dump(jobj, f, indent=4)


def fuzz_start(clean: bool) -> None:
    if clean:
        shutil.rmtree(config.PATH_WORK_FUZZ)
        logging.info("Previous fuzzing work cleared out")

    # initialize the necessary information
    if not os.path.exists(config.PATH_WORK_FUZZ_MUTATION_POINTS):
        mutation_init()
        logging.info("Mutation points collected")

    # other preparations
    os.makedirs(config.PATH_WORK_FUZZ_SEED_DIR, exist_ok=True)
    os.makedirs(config.PATH_WORK_FUZZ_SURVIVAL_DIR, exist_ok=True)
    os.makedirs(config.PATH_WORK_FUZZ_STATUS_DIR, exist_ok=True)

    # prepare the coverage map based on existing seeds
    logging.info(
        "Processing existing fuzzing seeds: {}".format(
            len(os.listdir(config.PATH_WORK_FUZZ_SEED_DIR))
        )
    )

    COV_GLOBAL.clear()
    for seed in os.listdir(config.PATH_WORK_FUZZ_SEED_DIR):
        for entry in _load_seed_cov(seed):
            COV_GLOBAL.add(entry)
    _dump_cov_global()
    logging.info("Global coverage map contains {} entries".format(len(COV_GLOBAL)))

    # start the fuzzing loop
    logging.info("Fuzzing loop started")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logging.info("Fuzzing loop stopped")
