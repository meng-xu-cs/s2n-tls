import multiprocessing
import os

# path
PATH_BASE = os.path.abspath(os.path.join(__file__, ".."))

PATH_ORIG_BITCODE = os.path.join(PATH_BASE, "bitcode")
PATH_ORIG_BITCODE_ALL_LLVM = os.path.join(PATH_ORIG_BITCODE, "all_llvm.bc")

PATH_DEPS = os.path.join(PATH_BASE, "deps")
PATH_DEPS_LLVM = os.path.join(PATH_DEPS, "target", "llvm-3.9.1")
PATH_DEPS_SAW = os.path.join(PATH_DEPS, "target", "saw-nightly")
PATH_DEPS_PASS = os.path.join(PATH_DEPS, "target", "pass")
PATH_DEPS_PASS_LIB = os.path.join(PATH_DEPS_PASS, "libMutation.so")

PATH_WORK = os.path.join(PATH_BASE, "work")
PATH_WORK_SAW = os.path.join(PATH_WORK, "saw")
PATH_WORK_FUZZ = os.path.join(PATH_WORK, "fuzz")
PATH_WORK_FUZZ_ENTRY_TARGETS = os.path.join(PATH_WORK_FUZZ, "entry-targets.json")
PATH_WORK_FUZZ_MUTATION_POINTS = os.path.join(PATH_WORK_FUZZ, "mutation-points.json")
PATH_WORK_FUZZ_SEED_DIR = os.path.join(PATH_WORK_FUZZ, "seeds")
PATH_WORK_FUZZ_SURVIVAL_DIR = os.path.join(PATH_WORK_FUZZ, "survival")
PATH_WORK_FUZZ_THREAD_DIR = os.path.join(PATH_WORK_FUZZ, "threads")
PATH_WORK_FUZZ_STATUS_DIR = os.path.join(PATH_WORK_FUZZ, "status")
PATH_WORK_BITCODE = os.path.join(PATH_WORK, "bitcode")
PATH_WORK_BITCODE_ALL_LLVM = os.path.join(PATH_WORK_BITCODE, "all_llvm.bc")
PATH_WORK_BITCODE_MUTATION = os.path.join(PATH_WORK_BITCODE, "mutation.json")

# misc
NUM_CORES = multiprocessing.cpu_count()
