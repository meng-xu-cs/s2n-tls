"""
Fuzzing-related functionalities
"""

import os
import logging
import shutil

import config
from bitcode import mutation_init


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
