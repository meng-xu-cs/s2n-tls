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
from typing import List, Dict, Tuple

import config
from bitcode import (
    MutationStep,
    mutation_init,
    mutation_pass_replay,
    mutation_pass_mutate,
    load_mutation_points,
)
from prover import VerificationError, verify_all, duplicate_workspace


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


class GlobalState(object):
    def __init__(self) -> None:
        self.lock = Lock()
        # R/W accesses to the rest requires lock
        self.cov: List[VerificationError] = []
        self.seeds: Dict[int, List[str]] = {}
        self.flag_halt = False

    # Check whether the halt flag is set
    def get_flag_halt(self) -> bool:
        self.lock.acquire()
        flag = self.flag_halt
        self.lock.release()
        return flag

    def set_flag_halt(self) -> None:
        self.lock.acquire()
        self.flag_halt = True
        self.lock.release()

    # This function must be called under lock
    def _update_seed_score(self, seed: Seed, delta: int) -> None:
        old_score = seed.load_and_adjust_score(delta)
        self.seeds[old_score].remove(seed.name)
        if len(self.seeds[old_score]) == 0:
            del self.seeds[old_score]

        new_score = old_score + delta
        if new_score not in self.seeds:
            self.seeds[new_score] = []
        self.seeds[new_score].append(seed.name)

    # Generate the next seed based on priority
    def next_seed(self) -> Tuple[Seed, int]:
        self.lock.acquire()

        # grab the seed
        top_score = sorted(self.seeds.keys(), reverse=True)[0]
        choice = random.choice(self.seeds[top_score])
        seed = Seed(choice)

        # lower its score
        self._update_seed_score(seed, -1)

        self.lock.release()
        return seed, top_score

    # Update the coverage map, return number of new entries added
    def update_coverage(self, new_cov: List[VerificationError]) -> int:
        self.lock.acquire()

        addition = 0
        for entry in new_cov:
            if entry not in self.cov:
                self.cov.append(entry)
                addition += 1

        if addition != 0:
            self.cov.sort()

        self.lock.release()
        return addition

    # Update the seed score in the priority queue
    def update_seed_score(self, seed: Seed, delta: int) -> None:
        self.lock.acquire()
        self._update_seed_score(seed, delta)
        self.lock.release()

    # Add a new seed to the priority queue
    def add_seed(self, seed: Seed) -> None:
        self.lock.acquire()
        score = seed.load_score()
        if score not in self.seeds:
            self.seeds[score] = []
        self.seeds[score].append(seed.name)
        self.lock.release()

    # Dump the global coverage map
    def dump_cov(self) -> None:
        self.lock.acquire()

        cov_path = os.path.join(config.PATH_WORK_FUZZ_STATUS_DIR, "cov.json")
        with open(cov_path, "w") as f:
            jobj = [asdict(item) for item in sorted(self.cov)]
            json.dump(jobj, f, indent=4)

        self.lock.release()


#
# Global variable shared across the threads
#

GLOBAL_STATE = GlobalState()


def _fuzzing_thread(tid: int) -> None:
    global GLOBAL_STATE

    # load the mutation points
    mutation_points = load_mutation_points()

    # workspace preparation
    path_instance = os.path.join(config.PATH_WORK_FUZZ_THREAD_DIR, str(tid))
    os.makedirs(path_instance, exist_ok=True)

    path_saw = os.path.join(path_instance, "saw")
    os.makedirs(path_saw, exist_ok=True)

    # copy over the related files for verification
    path_wks = os.path.join(path_instance, "wks")
    os.makedirs(path_saw, exist_ok=True)
    duplicate_workspace(path_wks)

    # other important files
    path_all_llvm_bc = os.path.join(path_wks, "bitcode", "all_llvm.bc")
    path_mutation_result = os.path.join(path_instance, "mutate_result.json")

    # fuzzing loop
    logging.info("[Thread-{}] Fuzzing started".format(tid))

    while True:
        # decide whether to halt the process
        if GLOBAL_STATE.get_flag_halt():
            break

        # populate a seed based on priority
        base_seed, base_score = GLOBAL_STATE.next_seed()

        old_cov = base_seed.load_cov()
        old_trace = base_seed.load_trace()
        logging.debug(
            "[Thread-{}] Mutating based on seed {} with score {}".format(
                tid, base_seed.name, base_score
            )
        )

        # prepare for the new trace to be the same as old trace
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
            mutation_pass_replay(
                base_seed.path_trace,
                path_all_llvm_bc,
            )
            logging.debug("[Thread-{}]   trace replayed".format(tid))

            mutation_pass_mutate(
                mutation_point,
                path_mutation_result,
                path_all_llvm_bc,
                path_all_llvm_bc,
            )
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
        new_cov = verify_all(path_wks, path_saw)
        logging.debug(
            "[Thread-{}]   verification completed with {} errors".format(
                tid, len(new_cov)
            )
        )

        # test for novelty of the seed
        novelty_marks = 0
        for entry in old_cov:
            if entry not in new_cov:
                # reward the seed for each error eliminated
                novelty_marks += 1
        logging.debug(
            "[Thread-{}]   previous errors removed: {}".format(tid, novelty_marks)
        )

        # reward the seed for each new error discovered
        cov_addition = GLOBAL_STATE.update_coverage(new_cov)
        logging.debug(
            "[Thread-{}]   new errors discovered: {}".format(tid, cov_addition)
        )
        novelty_marks += cov_addition

        # this is a boring case, ignore it
        if novelty_marks == 0:
            continue

        # adjust the score for the base seed
        # add 2 because we previously deducted one point from it
        GLOBAL_STATE.update_seed_score(base_seed, 2)

        # in case we found a surviving mutant
        if len(new_cov) == 0:
            logging.warning("Surviving mutant found")
            Seed.new_survival(new_trace, new_cov)
            continue

        # create a new seed and register it to the seed queue
        new_seed = Seed.new_seed(new_trace, new_cov, novelty_marks)
        GLOBAL_STATE.add_seed(new_seed)
        logging.debug("[Thread-{}]   a new seed is added to the seed pool".format(tid))

    # on halt
    logging.info("[Thread-{}] Fuzzing stopped".format(tid))


def fuzz_start(clean: bool, num_threads: int) -> None:
    global GLOBAL_STATE

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

    num_cov_entries = 0
    for item in os.listdir(config.PATH_WORK_FUZZ_SEED_DIR):
        seed = Seed(item)
        GLOBAL_STATE.add_seed(seed)
        num_cov_entries += GLOBAL_STATE.update_coverage(seed.load_cov())

    GLOBAL_STATE.dump_cov()
    logging.info(
        "Number of entries in the global coverage map: {}".format(num_cov_entries)
    )

    # prepare the threads
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
            GLOBAL_STATE.dump_cov()
            logging.info("Global coverage dump refreshed")
    except KeyboardInterrupt:
        # halt all threads
        GLOBAL_STATE.set_flag_halt()
        logging.info("Halt signal sent, waiting for child threads to terminate")

    # stop all the threads
    for t in threads:
        t.join()

    # on halt
    logging.info("All fuzzing threads stopped")
