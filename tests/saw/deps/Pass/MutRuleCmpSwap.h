#ifndef LLVM_MUTEST_MUT_RULE_CMP_SWAP_H
#define LLVM_MUTEST_MUT_RULE_CMP_SWAP_H

#include "MutRule.h"

namespace mutest {

class MutRuleCmpSwap : public MutRule {
public:
  static constexpr const char *NAME = "cmp-swap";

public:
  MutRuleCmpSwap() : MutRule(NAME) {}

public:
  bool can_mutate(const Instruction &i) const override {
    if (!isa<CmpInst>(i)) {
      return false;
    }

    const auto &cmp_inst = cast<CmpInst>(i);
    return !cmp_inst.isCommutative();
  }

  Optional<json> run_mutate(Instruction &i) const override {
    auto &cmp_inst = cast<CmpInst>(i);
    cmp_inst.swapOperands();
    return json::object();
  }

  void run_replay(Instruction &i,
                  [[maybe_unused]] const json &info) const override {
    auto &cmp_inst = cast<CmpInst>(i);
    cmp_inst.swapOperands();
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_CMP_SWAP_H */
