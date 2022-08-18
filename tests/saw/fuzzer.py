"""
Fuzzing-related functionalities
"""

import os
import json
import logging
import shutil
import time
import random
from dataclasses import asdict
from threading import Thread, Lock
from typing import List, Set, Dict

import config
from bitcode import (
    MutationStep,
    mutation_init,
    mutation_pass_replay,
    mutation_pass_mutate,
    load_mutation_points,
)
from prover import VerificationError, verify_all

#
# Global variable shared across the threads
#


GLOBAL_LOCK = Lock()
GLOBAL_COV: Set[VerificationError] = set()
GLOBAL_SEEDS: Dict[int, List[str]] = {}
GLOBAL_FLAG_HALT: bool = False


class Seed(object):
    def __init__(self, name: str):
        self.name = name
        self.path = os.path.join(config.PATH_WORK_FUZZ_SEED_DIR, name)
        self.path_cov = os.path.join(self.path, "cov.json")
        self.path_trace = os.path.join(self.path, "trace.json")
        self.path_score = os.path.join(self.path, "score.txt")

    def _save_cov(self, cov: List[VerificationError]) -> None:
        with open(self.path_cov, "w") as f:
            jobj = [asdict(item) for item in cov]
            json.dump(jobj, f, indent=4)

    def load_cov(self) -> List[VerificationError]:
        with open(self.path_cov) as f:
            jobj = json.load(f)
            return [VerificationError(**item) for item in jobj]

    def _save_trace(self, trace: List[MutationStep]) -> None:
        with open(self.path_trace, "w") as f:
            jobj = [asdict(item) for item in trace]
            json.dump(jobj, f, indent=4)

    def load_trace(self) -> List[MutationStep]:
        with open(self.path_trace) as f:
            jobj = json.load(f)
            return [MutationStep(**item) for item in jobj]

    def _init_score(self, delta: int) -> None:
        with open(self.path_score, "w") as f:
            f.write(str(100 + delta))

    def load_and_adjust_score(self, delta: int) -> int:
        with open(self.path_score) as f:
            old_score = int(f.readline().strip())

        if delta != 0:
            new_score = max(old_score + delta, 0)
            with open(self.path_score, "w") as f:
                f.write(str(new_score))

        return old_score

    def load_score(self) -> int:
        return self.load_and_adjust_score(0)

    @staticmethod
    def new_seed(
        trace: List[MutationStep], cov: List[VerificationError], delta: int
    ) -> "Seed":
        while True:
            count = len(os.listdir(config.PATH_WORK_FUZZ_SEED_DIR))
            try:
                os.makedirs(
                    os.path.join(config.PATH_WORK_FUZZ_SEED_DIR, str(count)),
                    exist_ok=False,
                )
                seed = Seed(str(count))
                seed._init_score(delta)
                seed._save_trace(trace)
                seed._save_cov(cov)
                return seed
            except FileExistsError:
                pass

    @staticmethod
    def new_survival(trace: List[MutationStep], cov: List[VerificationError]) -> "Seed":
        while True:
            count = len(os.listdir(config.PATH_WORK_FUZZ_SURVIVAL_DIR))
            try:
                os.makedirs(
                    os.path.join(config.PATH_WORK_FUZZ_SURVIVAL_DIR, str(count)),
                    exist_ok=False,
                )
                seed = Seed(str(count))
                seed._init_score(0)
                seed._save_trace(trace)
                seed._save_cov(cov)
                return seed
            except FileExistsError:
                pass


def _dump_cov_global() -> None:
    cov_path = os.path.join(config.PATH_WORK_FUZZ_STATUS_DIR, "cov.json")
    with open(cov_path, "w") as f:
        jobj = [asdict(item) for item in sorted(GLOBAL_COV)]
        json.dump(jobj, f, indent=4)


def _fuzzing_thread(tid: int) -> None:
    global GLOBAL_LOCK
    global GLOBAL_COV
    global GLOBAL_FLAG_HALT

    # load the mutation points
    mutation_points = load_mutation_points()

    # workspace preparation
    path_instance = os.path.join(config.PATH_WORK_FUZZ_THREAD_DIR, str(tid))
    os.makedirs(path_instance, exist_ok=True)

    path_mutation_result = os.path.join(path_instance, "mutate_result.json")

    path_saw = os.path.join(path_instance, "saw")
    os.makedirs(path_saw, exist_ok=True)

    # fuzzing loop
    logging.info("[Thread-{}] Fuzzing started".format(tid))

    while True:
        # decide whether to halt the process
        GLOBAL_LOCK.acquire()
        should_halt = GLOBAL_FLAG_HALT
        GLOBAL_LOCK.release()
        if should_halt:
            break

        # populate a seed based on priority
        GLOBAL_LOCK.acquire()
        score = sorted(GLOBAL_SEEDS.keys(), reverse=True)[0]
        choice = random.choice(GLOBAL_SEEDS[score])
        base_seed = Seed(choice)

        # decrement the score after pulling it out from the pool
        base_seed.load_and_adjust_score(-1)
        GLOBAL_SEEDS[score].remove(choice)
        if (score - 1) not in GLOBAL_SEEDS:
            GLOBAL_SEEDS[score - 1] = []
        GLOBAL_SEEDS[score - 1].append(choice)

        GLOBAL_LOCK.release()

        logging.debug(
            "[Thread-{}] Mutating based on seed {} with score {}".format(
                tid, base_seed.name, score
            )
        )

        old_cov = base_seed.load_cov()
        old_trace = base_seed.load_trace()
        new_trace = [step for step in old_trace]

        # choose a mutation point that does not appear in previous trace
        while True:
            mutation_point = random.choice(mutation_points)

            # step 1: mutation point never appears in the trace
            valid = True
            for step in old_trace:
                if (
                    step.function == mutation_point.function
                    and step.instruction == mutation_point.instruction
                ):
                    valid = False
                    break

            if not valid:
                continue

            logging.debug(
                "[Thread-{}]   next mutation: {} on {}::{}".format(
                    tid,
                    mutation_point.rule,
                    mutation_point.function,
                    mutation_point.instruction,
                )
            )

            # step 2: actually produce the new mutant
            mutation_pass_replay(base_seed.path_trace)
            logging.debug("[Thread-{}]   trace replayed".format(tid))

            mutation_pass_mutate(mutation_point, path_mutation_result)
            with open(path_mutation_result) as f:
                mutate_result = json.load(f)

            # this might be just paranoid, but just ensure that the mutation is applied
            if not mutate_result["changed"]:
                continue

            new_trace.append(
                MutationStep(
                    mutation_point.rule,
                    mutation_point.function,
                    mutation_point.instruction,
                    mutate_result["package"],
                )
            )
            logging.debug("[Thread-{}]   mutation applied".format(tid))
            break

        # done with the new test case generation
        assert len(new_trace) - len(old_trace) == 1

        # run the verification
        new_cov = verify_all(path_saw)

        # test for novelty of the seed
        novelty_marks = 0
        for entry in old_cov:
            if entry not in new_cov:
                # reward the seed for each error eliminated
                novelty_marks += 1

        GLOBAL_LOCK.acquire()
        for entry in new_cov:
            if entry not in GLOBAL_COV:
                # reward the seed for each new error discovered
                GLOBAL_COV.add(entry)
                novelty_marks += 1
        GLOBAL_LOCK.release()

        # this is a boring case, ignore it
        if novelty_marks == 0:
            continue

        # adjust the score for the base seed
        GLOBAL_LOCK.acquire()

        # add 2 because we previously deducted one point from it
        prev_score = base_seed.load_and_adjust_score(2)
        GLOBAL_SEEDS[prev_score].remove(base_seed.name)
        if (prev_score + 2) not in GLOBAL_SEEDS:
            GLOBAL_SEEDS[prev_score + 2] = []
        GLOBAL_SEEDS[prev_score + 2].append(base_seed.name)

        GLOBAL_LOCK.release()

        # in case we found a surviving mutant
        if len(new_cov) == 0:
            logging.warning("Surviving mutant found")
            Seed.new_survival(new_trace, new_cov)
            continue

        # create a new seed
        new_seed = Seed.new_seed(new_trace, new_cov, novelty_marks)
        new_score = new_seed.load_score()

        # add the new seed to queue
        GLOBAL_LOCK.acquire()
        if new_score not in GLOBAL_SEEDS:
            GLOBAL_SEEDS[new_score] = []
        GLOBAL_SEEDS[new_score].append(new_seed.name)
        GLOBAL_LOCK.release()

    # on halt
    logging.info("[Thread-{}] Fuzzing stopped".format(tid))


def fuzz_start(clean: bool, num_threads: int) -> None:
    global GLOBAL_LOCK
    global GLOBAL_COV
    global GLOBAL_FLAG_HALT

    # do a clean-up if requested
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

    # deposit the base seed if needed
    path_seed_zero = os.path.join(config.PATH_WORK_FUZZ_SEED_DIR, "0")
    if not os.path.exists(path_seed_zero):
        # base seed has no errors and no mutation trace
        Seed.new_seed([], [], 0)

    # prepare the seed queue and coverage map based on existing seeds
    logging.info(
        "Processing existing fuzzing seeds: {}".format(
            len(os.listdir(config.PATH_WORK_FUZZ_SEED_DIR))
        )
    )

    GLOBAL_COV.clear()
    GLOBAL_SEEDS.clear()
    for item in os.listdir(config.PATH_WORK_FUZZ_SEED_DIR):
        seed = Seed(item)
        score = seed.load_score()
        if score not in GLOBAL_SEEDS:
            GLOBAL_SEEDS[score] = []
        GLOBAL_SEEDS[score].append(seed.name)
        for entry in seed.load_cov():
            GLOBAL_COV.add(entry)

    _dump_cov_global()
    logging.info(
        "Number of entries in the global coverage map: {}".format(len(GLOBAL_COV))
    )

    # prepare the threads
    GLOBAL_FLAG_HALT = False
    threads = [
        Thread(target=_fuzzing_thread, args=(i,), daemon=True)
        for i in range(num_threads)
    ]

    # start the fuzzing loop
    for t in threads:
        t.start()
    logging.info("All fuzzing threads started")

    # busy waiting
    try:
        while True:
            time.sleep(60)
            # periodically refresh the coverage map
            GLOBAL_LOCK.acquire()
            _dump_cov_global()
            GLOBAL_LOCK.release()
            logging.info("Global coverage dump refreshed")
    except KeyboardInterrupt:
        # halt all threads
        GLOBAL_LOCK.acquire()
        GLOBAL_FLAG_HALT = True
        GLOBAL_LOCK.release()
        logging.info("Halt signal sent, waiting for child threads to terminate")

    # stop all the threads
    for t in threads:
        t.join()

    # on halt
    logging.info("All fuzzing threads stopped")
