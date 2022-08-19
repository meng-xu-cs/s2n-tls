#ifndef LLVM_MUTEST_MUT_RULES_H
#define LLVM_MUTEST_MUT_RULES_H

#include "MutRule.h"
#include "MutRuleBranchSwap.h"
#include "MutRuleCmpSwap.h"

namespace mutest {

std::vector<std::unique_ptr<MutRule>> all_mutation_rules() {
  std::vector<std::unique_ptr<MutRule>> rules;
  rules.push_back(std::unique_ptr<MutRule>(new MutRuleBranchSwap()));
  rules.push_back(std::unique_ptr<MutRule>(new MutRuleCmpSwap()));
  return rules;
}

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULES_H */