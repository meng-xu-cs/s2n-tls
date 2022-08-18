"""
Fuzzing-related functionalities
"""

import os
import json
import logging
import shutil
import time
from dataclasses import asdict
from threading import Thread, Lock
from typing import List, Set

import config
from bitcode import mutation_init
from prover import VerificationError

#
# Global variable shared across the threads
#


GLOBAL_LOCK = Lock()
GLOBAL_COV: Set[VerificationError] = set()
GLOBAL_FLAG_HALT: bool = False


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
        jobj = [asdict(item) for item in sorted(GLOBAL_COV)]
        json.dump(jobj, f, indent=4)


def _fuzzing_thread(tid: int) -> None:
    global GLOBAL_LOCK
    global GLOBAL_COV
    global GLOBAL_FLAG_HALT

    logging.info("Thread-{}: started".format(tid))

    # preparation
    path_instance = os.path.join(config.PATH_WORK_FUZZ_THREAD_DIR, str(tid))
    path_saw = os.path.join(path_instance, "saw")
    os.makedirs(path_saw, exist_ok=True)

    # fuzzing loop
    while True:
        # decide whether to halt the process
        GLOBAL_LOCK.acquire()
        should_halt = GLOBAL_FLAG_HALT
        GLOBAL_LOCK.release()
        if should_halt:
            break

    # on halt
    logging.info("Thread-{}: stopped".format(tid))


def fuzz_start(clean: bool, num_threads: int) -> None:
    global GLOBAL_LOCK
    global GLOBAL_COV
    global GLOBAL_FLAG_HALT

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

    GLOBAL_COV.clear()
    for seed in os.listdir(config.PATH_WORK_FUZZ_SEED_DIR):
        for entry in _load_seed_cov(seed):
            GLOBAL_COV.add(entry)
    _dump_cov_global()
    logging.info(
        "Number of entries in the global coverage map: {}".format(len(GLOBAL_COV))
    )

    # prepare the threads
    GLOBAL_FLAG_HALT = False
    threads = [Thread(target=_fuzzing_thread, args=(i,)) for i in range(num_threads)]

    # start the fuzzing loop
    for t in threads:
        t.start()
    logging.info("All fuzzing threads started")

    # busy waiting
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        GLOBAL_LOCK.acquire()
        GLOBAL_FLAG_HALT = True
        GLOBAL_LOCK.release()
        logging.info("Halt signal sent, waiting for child threads to terminate")

    # stop all the threads
    for t in threads:
        t.join()

    # on halt
    logging.info("All fuzzing threads stopped")
