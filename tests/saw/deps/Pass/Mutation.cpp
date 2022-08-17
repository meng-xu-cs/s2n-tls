#include <llvm/Pass.h>
#include <llvm/Support/CommandLine.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/raw_os_ostream.h>

#include "MutRules.h"

using namespace llvm;

static cl::opt<std::string> Action(cl::Positional, cl::desc("action to take"),
                                   cl::Required);
static cl::opt<std::string> Output("mutest-output",
                                   cl::desc("output for mutest"), cl::Optional,
                                   cl::ValueRequired);

namespace mutest {

struct MutationTestPass : public ModulePass {
  static char ID;

  MutationTestPass() : ModulePass(ID) {}

  bool runOnModule(Module &m) override {
    if (Action == "init") {
      auto result = collect_mutation_points(m);

      // dump the result
      if (Output.empty()) {
        outs() << result.dump(4) << '\n';
      } else {
        std::error_code ec;
        raw_fd_ostream stm(Output.getValue(), ec, llvm::sys::fs::F_RW);
        stm << result.dump(4);
      }

      // bitcode not changed
      return false;
    }

    llvm_unreachable("Unknown action command");
  }

protected:
  static json collect_mutation_points(const Module &m) {
    json mutation_points = json::array();

    const auto rules = mutest::all_mutation_rules();
    for (const auto &f : m) {
      auto func_name = f.getName();
      size_t inst_count = 0;
      for (const auto &bb : f) {
        for (const auto &i : bb) {
          for (const auto &rule : rules) {
            if (rule->can_mutate(i)) {
              json point = json::object();
              point["function"] = func_name.str();
              point["instruction"] = inst_count;
              point["rule"] = rule->name_;
              mutation_points.push_back(point);
            }
          }
          inst_count += 1;
        }
      }
    }

    return mutation_points;
  }
};

char MutationTestPass::ID = 0;

} // namespace mutest

// Automatically enable the pass.
static RegisterPass<mutest::MutationTestPass> X("mutest", "Mutation testing",
                                                false, false);