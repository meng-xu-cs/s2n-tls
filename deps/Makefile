# help
define cmdline
Please choose one of the following targets:
  - reset
  - llvm-3.9.1
  - llvm-14.0.6
endef
export cmdline

help:
	@echo "$$cmdline"

#
# settings
#

CURRENT_DIR := $(shell pwd)

OBJECT_DIR := $(CURRENT_DIR)/object
TARGET_DIR := $(CURRENT_DIR)/target

#
# targets
#

reset:
	@echo "Resetting LLVM repo"
	@cd llvm && git checkout main

llvm-3.9.1:
	@echo "Checking out LLVM 3.9.1"
	@cd llvm && git checkout llvmorg-3.9.1
	###
	@echo "Configuring the LLVM build"
	@mkdir -p $(OBJECT_DIR)/$@
	@cd $(OBJECT_DIR)/$@ && \
		cmake \
			-G Ninja \
			-DLLVM_ENABLE_PROJECTS="clang;compiler-rt" \
			-DBUILD_SHARED_LIBS=On \
			-DCMAKE_BUILD_TYPE=Debug \
			-DCMAKE_INSTALL_PREFIX=$(TARGET_DIR)/$@ \
			$(CURRENT_DIR)/llvm/llvm
	###
	@echo "Building LLVM"
	@cmake --build $(OBJECT_DIR)/$@
	###
	@echo "Installing LLVM"
	@cmake --install $(OBJECT_DIR)/$@

llvm-14.0.6:
	@echo "Checking out LLVM 14.0.6"
	@cd llvm && git checkout llvmorg-14.0.6
	###
	@echo "Configuring the LLVM build"
	@mkdir -p $(OBJECT_DIR)/$@
	@cd $(OBJECT_DIR)/$@ && \
		cmake \
			-G Ninja \
			-DLLVM_ENABLE_PROJECTS="clang;compiler-rt" \
			-DBUILD_SHARED_LIBS=On \
			-DCMAKE_BUILD_TYPE=Debug \
			-DCMAKE_INSTALL_PREFIX=$(TARGET_DIR)/$@ \
			$(CURRENT_DIR)/llvm/llvm
	###
	@echo "Building LLVM"
	@cmake --build $(OBJECT_DIR)/$@
	###
	@echo "Installing LLVM"
	@cmake --install $(OBJECT_DIR)/$@
