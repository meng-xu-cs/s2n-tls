cmake_minimum_required(VERSION 3.16.3)
project(kernel-analyzer)

# load LLVM
find_package(LLVM REQUIRED
             PATHS ../target/llvm-3.9.1
             NO_DEFAULT_PATH)

list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)

add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS})

SET(CMAKE_CXX_FLAGS "-Wall -fno-rtti")

# add code for the pass
add_library(Mutation MODULE
            Mutation.cpp)