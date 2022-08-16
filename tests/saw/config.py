import multiprocessing
import os

# path
PATH_BASE = os.path.abspath(os.path.join(__file__, ".."))
PATH_DEPS = os.path.join(PATH_BASE, "deps")
PATH_DEPS_LLVM = os.path.join(PATH_DEPS, "target", "llvm-3.9.1")
PATH_DEPS_SAW = os.path.join(PATH_DEPS, "target", "saw-nightly")

# misc
NUM_CORES = multiprocessing.cpu_count()
