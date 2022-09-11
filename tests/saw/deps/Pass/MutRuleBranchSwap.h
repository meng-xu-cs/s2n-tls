#ifndef LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H
#define LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H

#include "MutRule.h"

namespace mutest {

class MutRuleBranchSwap : public MutRule {
public:
  static constexpr const char *NAME = "branch-swap";
  static bool const second_mutation = false;

public:
  MutRuleBranchSwap() : MutRule(NAME) {}

public:
  bool can_second_mutation() const override{return second_mutation;}
  bool can_mutate(const Instruction &i) const override {
    if (!isa<BranchInst>(i)) {
      return false;
    }

    const auto &branch_inst = cast<BranchInst>(i);
    return branch_inst.isConditional();
  }

  Optional<json> run_mutate(Instruction &i) const override {
    auto &branch_inst = cast<BranchInst>(i);
    branch_inst.swapSuccessors();
    return json::object();
  }

  void run_replay(Instruction &i,
                  [[maybe_unused]] const json &info) const override {
    auto &branch_inst = cast<BranchInst>(i);
    branch_inst.swapSuccessors();
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H */
