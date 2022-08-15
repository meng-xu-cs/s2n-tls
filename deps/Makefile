# help
define cmdline
Please choose one of the following targets:
  - reset
  - llvm-3.9.1
  - llvm-14.0.6
  - saw-0.9
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
	@echo "Downloading binaries"
	@wget https://releases.llvm.org/3.9.1/clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04.tar.xz \
		-O $(TARGET_DIR)/llvm.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf llvm.tar.gz && \
		mv clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04 $@ && \
		rm llvm.tar.gz

llvm-14.0.6:
	@echo "Checking out the source code"
	@cd llvm && git checkout llvmorg-14.0.6
	###
	@echo "Configuring"
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
	@echo "Building"
	@cmake --build $(OBJECT_DIR)/$@
	###
	@echo "Installing"
	@cmake --install $(OBJECT_DIR)/$@

saw-0.9:
	@echo "Downloading binaries"
	@wget https://github.com/GaloisInc/saw-script/releases/download/v0.9/saw-0.9-Linux-x86_64-with-solvers.tar.gz \
		-O $(TARGET_DIR)/saw.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf saw.tar.gz && \
		mv saw-0.9-Linux-x86_64-with-solvers $@ && \
		rm saw.tar.gz
