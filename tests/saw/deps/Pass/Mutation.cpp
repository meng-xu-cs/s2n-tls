#include <llvm/Pass.h>
#include <llvm/Support/CommandLine.h>

using namespace llvm;

namespace {

struct MutationTestPass : public ModulePass {
  static char ID;

  MutationTestPass() : ModulePass(ID) {}

  bool runOnModule(Module &M) override {
    // mark that we did not change anything
    return false;
  }
};

} // namespace

char MutationTestPass::ID = 0;

// Automatically enable the pass.
static RegisterPass<MutationTestPass> X("mutation-testing", "Mutation testing",
                                        false, false);