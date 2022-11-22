#include <llvm/ADT/StringSet.h>
#include <llvm/Analysis/CallGraph.h>
#include <llvm/Pass.h>
#include <llvm/Support/CommandLine.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/raw_os_ostream.h>
#include "llvm/IR/DebugInfo.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/Metadata.h"
#include "llvm/IR/Instruction.h"
#include "llvm/IR/DebugLoc.h"
#include "llvm/IR/Module.h"
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
static cl::opt<std::string>
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
      assert(!Input.getValue().empty() && "-mutest-input not set");

      // load the top-level verification targets
      auto buffer = MemoryBuffer::getFile(Input);
      assert(buffer && "Unable to load the entry target list");
      json targets = json::parse((*buffer)->getBuffer());

      // collect the transitive closure from the call graph
      StringSet todo_set;
      StringSet done_set;
      for (const auto &target : targets) {
        todo_set.insert(target.get<std::string>());
      }

      CallGraph cg(m);
      while (!todo_set.empty()) {
        collect_verification_scope(cg, todo_set, done_set);
      }
      errs() << "[mutest] "
             << "verification scope contains " << done_set.size() << " function"
             << '\n';

      // collect mutation points
      auto result = collect_mutation_points(m, done_set);

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
      assert(!TargetInstruction.getValue().empty() &&
             "-mutest-target-instruction not set");
      assert(TargetRule.getValue().empty() && "-mutest-target-rule not set");

      // do the mutation
      const auto rules = all_mutation_rules();
      auto [rule, i] = find_rule_and_mutation_point(
          rules, m, TargetRule, TargetFunction, std::stol(TargetInstruction));
      auto mutated = rule.run_mutate(i, TargetFunction, TargetInstruction);

      json result = json::object();
      if (mutated) {
        result["changed"] = true;
        result["package"] = mutated.getValue();
         result["additional_information"] = additional_information(i);
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
      const auto rules = all_mutation_rules();
      for (const auto &entry : trace) {
        auto [rule, i] = find_rule_and_mutation_point(
            rules, m, entry["rule"].get<std::string>(),
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
  static void collect_verification_scope(const CallGraph &cg,
                                         StringSet<MallocAllocator> &todo,
                                         StringSet<MallocAllocator> &done) {
    auto external_callee = cg.getCallsExternalNode();
    auto external_caller = cg.getExternalCallingNode();

    for (const auto &[f, caller_node] : cg) {
      // ignore theoretical nodes
      if (caller_node.get() == external_caller ||
          caller_node.get() == external_callee) {
        continue;
      }

      auto caller = f->getName();

      // ignore processed nodes
      if (done.find(caller) != done.end()) {
        continue;
      }
      // ignore nodes that are not even in the work list
      if (todo.find(caller) == todo.end()) {
        continue;
      }

      // now we need to process this function
      for (const auto &[_, callee_node] : *caller_node) {
        if (callee_node == nullptr) {
          continue;
        }
        if (callee_node == external_callee) {
          continue;
        }

        auto callee = callee_node->getFunction()->getName();
        if (done.find(callee) != done.end()) {
          continue;
        }
        todo.insert(callee);
      }

      // move the processed function from work list to done list
      todo.erase(caller);
      done.insert(caller);
    }
  }

  static json additional_information(Instruction &i)
  {
    json additional_information = json::object();
    MDNode *metadata = i.getMetadata("dbg");
    if(metadata == 0x0){
        return additional_information["null"] = std::string("null");
    }
    const DILocation *debugLocation = dyn_cast<DILocation>(metadata);
    const DebugLoc &debugLoc = DebugLoc(debugLocation);
    additional_information["file_name"] = debugLocation->getFilename();
    additional_information["instruction_line"] = debugLocation->getLine();
    additional_information["instruction_col"] = debugLoc.getCol();
    return additional_information;
  }
  static json collect_mutation_points(const Module &m,
                                      const StringSet<MallocAllocator> &scope) {
    json mutation_points = json::array();

    const auto rules = all_mutation_rules();
    for (const auto &f : m) {
      auto func_name = f.getName();
      // only mutate within the verification scope
      if (scope.find(func_name) == scope.end()) {
        continue;
      }
      
      
      // assign each instruction a unique counter value
      size_t inst_count = 0;
      for (const auto &bb : f) {
        for (const auto &i : bb) {
          inst_count += 1; // inst_count can never be 0
          MDNode *metadata = i.getMetadata("dbg");
          
          for (const auto &rule : rules) {
            if (rule->can_mutate(i)) {
              json point = json::object();
              point["second_mutation"] = rule->can_second_mutation();
	            point["origin_mutate"] = rule->origin_mutate(i);
              point["rule"] = rule->name_;
              point["function"] = func_name.str();
              point["instruction"] = inst_count;
              if (point["function"] ==std::string("s2n_drbg_instantiate") && point["instruction"] == 102){
                  errs() << "instruction here !!" << i << "\n";
              }
              if (metadata != 0x0){
                  DILocation *debugLocation = dyn_cast<DILocation>(metadata);
                  const DebugLoc &debugLoc = DebugLoc(debugLocation);
                  point["instruction_line"] = debugLocation->getLine();
              }
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
            if (inst_count != target_instruction) {
              continue;
            }
            // found the instruction
            assert(rule->can_mutate(i) &&
                   "Rule cannot actually mutate the instruction");
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
