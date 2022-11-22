#ifndef LLVM_MUTEST_MUT_RULE_SELECT_SWAP_H
#define LLVM_MUTEST_MUT_RULE_SELECT_SWAP_H

#include "MutRule.h"

namespace mutest {

class MutRuleSelectSwap : public MutRule {
public:
  static constexpr const char *NAME = "select-swap";
  static bool const second_mutation = false;
public:
  MutRuleSelectSwap() : MutRule(NAME) {}

public:
  bool can_second_mutation() const override{return second_mutation;}
  bool can_mutate(const Instruction &i) const override {
    return isa<SelectInst>(i);
  }

  Optional<json> run_mutate(Instruction &i, std::string function_count, std::string inst_count) const override {
    auto &sel_inst = cast<SelectInst>(i);
    swapValues(sel_inst);
    return json::object();
  }

  void run_replay(Instruction &i,
                  [[maybe_unused]] const json &info) const override {
    auto &sel_inst = cast<SelectInst>(i);
    swapValues(sel_inst);
  }

private:
  static void swapValues(SelectInst &inst) {
    auto *temp_f = inst.getFalseValue();
    auto *temp_t = inst.getTrueValue();
    inst.setFalseValue(temp_t);
    inst.setTrueValue(temp_f);
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_SELECT_SWAP_H */
