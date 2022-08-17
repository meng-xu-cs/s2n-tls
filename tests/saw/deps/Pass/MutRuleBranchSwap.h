#ifndef LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H
#define LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H

#include "MutRule.h"

namespace mutest {

class MutRuleBranchSwap : MutRule {
public:
  static constexpr const char *NAME = "branch-swap";

public:
  MutRuleBranchSwap() : MutRule(NAME) {}
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_BRANCH_SWAP_H */
