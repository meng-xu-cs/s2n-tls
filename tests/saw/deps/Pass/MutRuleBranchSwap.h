#ifndef LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H
#define LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H

#include "MutRule.h"

namespace mutest {

class MutRuleBranchSwap : public MutRule {
public:
  static constexpr const char *NAME = "branch-swap";

public:
  MutRuleBranchSwap() : MutRule(NAME) {}

public:
  bool can_mutate(const Instruction &i) const override {
    if (!isa<BranchInst>(i)) {
      return false;
    }

    const auto &branch_inst = cast<BranchInst>(i);
    return branch_inst.isConditional();
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H */
