import multiprocessing
import os

# path
PATH_BASE = os.path.abspath(os.path.join(__file__, ".."))

PATH_DEPS = os.path.join(PATH_BASE, "deps")
PATH_DEPS_LLVM = os.path.join(PATH_DEPS, "target", "llvm-3.9.1")
PATH_DEPS_SAW = os.path.join(PATH_DEPS, "target", "saw-nightly")

PATH_WORK = os.path.join(PATH_BASE, "work")
PATH_WORK_SAW = os.path.join(PATH_WORK, "saw")
PATH_WORK_FUZZ = os.path.join(PATH_WORK, "fuzz")

# misc
NUM_CORES = multiprocessing.cpu_count()
