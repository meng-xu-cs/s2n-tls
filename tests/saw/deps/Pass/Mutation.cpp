#include <llvm/Pass.h>
#include <llvm/Support/CommandLine.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/raw_os_ostream.h>

#include "MutRules.h"

using namespace llvm;

static cl::opt<std::string> Action(cl::Positional, cl::desc("action to take"),
                                   cl::Required);

static cl::opt<std::string> Input("mutest-input", cl::desc("input for mutest"),
                                  cl::Optional, cl::ValueRequired);
static cl::opt<std::string> Output("mutest-output",
                                   cl::desc("output for mutest"), cl::Optional,
                                   cl::ValueRequired);

static cl::opt<std::string>
    TargetFunction("mutest-target-function",
                   cl::desc("name of the mutated function"), cl::Optional,
                   cl::ValueRequired);
static cl::opt<size_t>
    TargetInstruction("mutest-target-instruction",
                      cl::desc("count of the mutation instruction"),
                      cl::Optional, cl::ValueRequired);
static cl::opt<std::string> TargetRule("mutest-target-rule",
                                       cl::desc("name of the mutation rule"),
                                       cl::Optional, cl::ValueRequired);

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

    if (Action == "mutate") {
      // sanity check the arguments
      assert(!TargetFunction.getValue().empty() &&
             "-mutest-target-function not set");
      assert(TargetInstruction.getValue() != 0 &&
             "-mutest-target-instruction not set");
      assert(TargetRule.getValue().empty() && "-mutest-target-rule not set");

      // do the mutation
      const auto rules = all_mutation_rules();
      auto [rule, i] = find_rule_and_mutation_point(
          rules, m, TargetRule, TargetFunction, TargetInstruction);
      auto mutated = rule.run_mutate(i);

      json result = json::object();
      if (mutated) {
        result["changed"] = true;
        result["package"] = mutated.getValue();
      } else {
        result["changed"] = false;
      }

      // dump the result
      if (Output.empty()) {
        outs() << result.dump(4) << '\n';
      } else {
        std::error_code ec;
        raw_fd_ostream stm(Output.getValue(), ec, llvm::sys::fs::F_RW);
        stm << result.dump(4);
      }

      // may or may not change
      return mutated.hasValue();
    }

    if (Action == "replay") {
      assert(!Input.getValue().empty() && "-mutest-input not set");

      // load the trace file
      auto buffer = MemoryBuffer::getFile(Input);
      assert(buffer && "Unable to load the trace file");
      json trace = json::parse((*buffer)->getBuffer());

      // replay the trace
      for (const auto &entry : trace) {
        auto [rule, i] = find_rule_and_mutation_point(
            all_mutation_rules(), m, entry["rule"].get<std::string>(),
            entry["function"].get<std::string>(),
            entry["instruction"].get<size_t>());
        rule.run_replay(i, entry["package"]);
      }

      // may or may not change
      return !trace.empty();
    }

    // abort if we see an unknown command
    llvm_unreachable(
        (std::string("Unknown action command: ") + Action).c_str());
  }

protected:
  static json collect_mutation_points(const Module &m) {
    json mutation_points = json::array();

    const auto rules = all_mutation_rules();
    for (const auto &f : m) {
      auto func_name = f.getName();
      size_t inst_count = 0;
      for (const auto &bb : f) {
        for (const auto &i : bb) {
          inst_count += 1; // inst_count can never be 0
          for (const auto &rule : rules) {
            if (rule->can_mutate(i)) {
              json point = json::object();
              point["function"] = func_name.str();
              point["instruction"] = inst_count;
              point["rule"] = rule->name_;
              mutation_points.push_back(point);
            }
          }
        }
      }
    }

    return mutation_points;
  }

  static std::pair<const MutRule &, Instruction &> find_rule_and_mutation_point(
      const std::vector<std::unique_ptr<MutRule>> &rules, Module &m,
      const std::string &target_rule, const std::string &target_function,
      const size_t target_instruction) {
    for (const auto &rule : rules) {
      if (rule->name_ != target_rule) {
        continue;
      }

      // found the rule
      for (auto &f : m) {
        if (f.getName() != target_function) {
          continue;
        }

        // found the function
        size_t inst_count = 0;
        for (auto &bb : f) {
          for (auto &i : bb) {
            inst_count += 1; // inst_count can never be 0
            if (inst_count != TargetInstruction) {
              continue;
            }

            // found the instruction
            assert(rule->can_mutate(i));
            return {*rule, i};
          }
        }
        llvm_unreachable((std::string("No such instruction in function: ") +
                          target_function +
                          "::" + std::to_string(target_instruction))
                             .c_str());
      }
      llvm_unreachable(
          (std::string("No such function: ") + target_function).c_str());
    }
    llvm_unreachable(
        (std::string("No such mutation rule: ") + target_rule).c_str());
  }
};

char MutationTestPass::ID = 0;

} // namespace mutest

// Automatically enable the pass.
static RegisterPass<mutest::MutationTestPass> X("mutest", "Mutation testing",
                                                false, false);