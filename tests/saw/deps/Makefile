# help
define cmdline
Please choose one of the following targets:
  - llvm-3.9.1
  - saw-0.9
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

#
# targets
#

llvm-3.9.1:
	@mkdir -p $(TARGET_DIR)
	###
	@echo "Downloading binaries"
	@wget https://releases.llvm.org/3.9.1/clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04.tar.xz \
		-O $(TARGET_DIR)/llvm.tar.gz
	###
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf llvm.tar.gz && \
		mv clang+llvm-3.9.1-x86_64-linux-gnu-ubuntu-16.04 $@ && \
		rm llvm.tar.gz

saw-0.9:
	@mkdir -p $(TARGET_DIR)
	###
	@echo "Downloading binaries"
	@wget https://github.com/GaloisInc/saw-script/releases/download/v0.9/saw-0.9-Linux-x86_64-with-solvers.tar.gz \
		-O $(TARGET_DIR)/saw.tar.gz
	###
	@echo "Unpacking binaries"
	@cd $(TARGET_DIR) && \
		tar xvf saw.tar.gz && \
		mv saw-0.9-Linux-x86_64-with-solvers $@ && \
		rm saw.tar.gz

pass:
	@mkdir -p $(TARGET_DIR)/pass
	###
	@echo "Building pass"
	@cd $(TARGET_DIR)/pass && \
		cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ../../Pass && \
		ninja
