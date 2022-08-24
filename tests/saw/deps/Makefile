# help
define cmdline
Please choose one of the following targets:
  - cmake-3.24.1
  - ninja-1.11.0
  - clang-13.0.0
  - llvm-3.9.1
  - saw-0.9
  - saw-nightly
  - pass
endef
export cmdline

help:
	@echo "$$cmdline"

#
# settings
#

CURRENT_DIR := $(shell pwd)
TARGET_DIR := $(CURRENT_DIR)/target
LOCAL_INST := /usr/local

#
# dependencies
#

cmake-3.24.1:
	@mkdir -p $(TARGET_DIR)
	@echo "Downloading binaries"
	@wget https://github.com/Kitware/CMake/releases/download/v3.24.1/cmake-3.24.1-linux-x86_64.tar.gz \
		-O $(TARGET_DIR)/cmake.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf cmake.tar.gz && \
		rm cmake.tar.gz && \
		rsync -r -a cmake-3.24.1-linux-x86_64/ $(LOCAL_INST) && \
		rm -rf cmake-3.24.1-linux-x86_64

ninja-1.11.0:
	@mkdir -p $(TARGET_DIR)
	@echo "Downloading binaries"
	@wget https://github.com/ninja-build/ninja/releases/download/v1.11.0/ninja-linux.zip \
		-O $(TARGET_DIR)/ninja.zip
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		unzip ninja.zip && \
		rm ninja.zip && \
		mv ninja $(LOCAL_INST)/bin

clang-13.0.0:
	@mkdir -p $(TARGET_DIR)
	@echo "Downloading binaries"
	@wget https://github.com/llvm/llvm-project/releases/download/llvmorg-13.0.0/clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-16.04.tar.xz \
		-O $(TARGET_DIR)/clang.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf clang.tar.gz && \
		rm clang.tar.gz && \
		rsync -r -a clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-16.04/ $(LOCAL_INST) && \
		rm -rf clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-16.04

#
# targets
#

llvm-3.9.1:
	@mkdir -p $(TARGET_DIR)
	@echo "Downloading binaries"
	@wget https://releases.llvm.org/3.9.1/clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04.tar.xz \
		-O $(TARGET_DIR)/llvm.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf llvm.tar.gz && \
		mv clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04 $@ && \
		rm llvm.tar.gz

saw-0.9:
	@mkdir -p $(TARGET_DIR)
	@echo "Downloading binaries"
	@wget https://github.com/GaloisInc/saw-script/releases/download/v0.9/saw-0.9-Linux-x86_64-with-solvers.tar.gz \
		-O $(TARGET_DIR)/saw.tar.gz
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf saw.tar.gz && \
		mv saw-0.9-Linux-x86_64-with-solvers $@ && \
		rm saw.tar.gz

saw-nightly:
	@mkdir -p $(TARGET_DIR)/$@
	@echo "Installing SAW"
	@curl --retry 3 \
		https://s2n-public-test-dependencies.s3.us-west-2.amazonaws.com/saw-0.9.0.99-Linux-x86_64.tar.gz \
		--output saw.tar.gz
	@mkdir saw/
	@tar xvf saw.tar.gz --strip-components=1 -C saw
	@rsync -r -a saw/ $(TARGET_DIR)/$@
	@rm -rf saw/ saw.tar.gz
	@echo "Installing solver: yices"
	@curl --retry 3 \
		https://s3-us-west-2.amazonaws.com/s2n-public-test-dependencies/yices-2.6.1-x86_64-pc-linux-gnu-static-gmp.tar.gz \
		--output yices.tar.gz
	@mkdir yices/
	@tar xvf yices.tar.gz --strip-components=1 -C yices
	@rsync -r -a yices/ $(TARGET_DIR)/$@
	@rm -rf yices/ yices.tar.gz
	@echo "Installing solver: z3"
	@curl --retry 3 \
		https://s3-us-west-2.amazonaws.com/s2n-public-test-dependencies/z3-4.8.8-x64-ubuntu-16.04.zip \
		--output z3.zip
	@unzip z3.zip
	@rsync -r -a z3-4.8.8-x64-ubuntu-16.04/ $(TARGET_DIR)/$@
	@rm -rf z3-4.8.8-x64-ubuntu-16.04/ z3.zip


pass:
	@rm -rf $(TARGET_DIR)/pass
	@mkdir -p $(TARGET_DIR)/pass
	@echo "Building pass"
	@cd $(TARGET_DIR)/pass && \
		cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ../../Pass && \
		ninja
