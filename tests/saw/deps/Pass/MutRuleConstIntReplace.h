#ifndef LLVM_MUTEST_MUT_RULE_CONST_INT_REPLACE_H
#define LLVM_MUTEST_MUT_RULE_CONST_INT_REPLACE_H

#include "MutRule.h"

namespace mutest {

class MutRuleConstIntReplace : public MutRule {
public:
  static constexpr const char *NAME = "const-replace";

private:
  std::vector<const char *> action_options;

public:
  MutRuleConstIntReplace() : MutRule(NAME) {
    // constants
    action_options.push_back("set-0");
    action_options.push_back("set-1");
    action_options.push_back("set-2");
    action_options.push_back("set-minus-1");
    action_options.push_back("set-minus-2");
    action_options.push_back("set-max-signed");
    action_options.push_back("set-max-unsigned");
    action_options.push_back("set-min");
    // arithmetics
    action_options.push_back("add-1");
    action_options.push_back("add-2");
    action_options.push_back("sub-1");
    action_options.push_back("sub-2");
    action_options.push_back("mul-2");
    action_options.push_back("mul-3");
    action_options.push_back("div-2");
    action_options.push_back("div-3");
    action_options.push_back("div-3");
    // bit ops
    action_options.push_back("flip");
  }

public:
  bool can_mutate(const Instruction &i) const override {
    for (const auto &u : i.operands()) {
      if (isa<ConstantInt>(u)) {
        return true;
      }
    }
    return false;
  }

  Optional<json> run_mutate(Instruction &i) const override {
    // collect the operand number
    std::vector<size_t> const_positions;

    size_t counter = 0;
    for (const auto &u : i.operands()) {
      if (isa<ConstantInt>(u)) {
        const_positions.push_back(counter);
      }
      counter++;
    }

    // pick an operand to mutate
    auto choice = random_choice(const_positions);
    const auto *operand = cast<ConstantInt>(i.getOperand(choice));

    // pick an action such that after the mutation, the new value is guaranteed
    // to be different
    const char *action;
    ConstantInt *new_val;
    do {
      action = random_choice(action_options);
      auto result = doReplace(operand->getValue(), action);
      if (!result) {
        // this action is not good, pick another one
        continue;
      }

      // now create the new constant
      new_val = ConstantInt::get(i.getContext(), result.getValue());

      // done with the mutation
      break;
    } while (true);

    // now set the operand to be a new value
    i.setOperand(choice, new_val);

    // save the info
    json info = json::object();
    info["operand"] = choice;
    info["action"] = action;
    return info;
  }

  void run_replay(Instruction &i, const json &info) const override {
    size_t choice = info["operand"];
    const auto *target = dyn_cast<ConstantInt>(i.getOperand(choice));
    assert(target != nullptr && "Operand is not a constant int");

    auto result = doReplace(target->getValue(), info["action"]);
    if (!result) {
      // technically, this shouldn't happen
      return;
    }

    // now create the new constant
    auto new_val = ConstantInt::get(i.getContext(), result.getValue());
    i.setOperand(choice, new_val);
  }

private:
  static Optional<APInt> tryNewConst(const APInt &old_val, int64_t new_val,
                                     bool is_signed) {
    if (old_val == new_val) {
      return Optional<APInt>();
    }
    return APInt(old_val.getBitWidth(), new_val, is_signed);
  }

  static Optional<APInt> tryMinMax(const APInt &old_val, bool is_max,
                                   bool is_signed) {
    auto nbits = old_val.getBitWidth();
    auto new_val = is_max ? (is_signed ? APInt::getSignedMaxValue(nbits)
                                       : APInt::getMaxValue(nbits))
                          : (is_signed ? APInt::getSignedMinValue(nbits)
                                       : APInt::getMinValue(nbits));
    if (new_val == old_val) {
      return Optional<APInt>();
    }
    return new_val;
  }

  static Optional<APInt> doReplace(const APInt &val,
                                   const std::string &action) {
    // constants
    if (action == "set-0") {
      return tryNewConst(val, 0, false);
    }
    if (action == "set-1") {
      return tryNewConst(val, 1, false);
    }
    if (action == "set-2") {
      return tryNewConst(val, 2, false);
    }
    if (action == "set-minus-1") {
      return tryNewConst(val, -1, true);
    }
    if (action == "set-minus-2") {
      return tryNewConst(val, -2, true);
    }
    if (action == "set-max-signed") {
      return tryMinMax(val, true, true);
    }
    if (action == "set-max-unsigned") {
      return tryMinMax(val, true, false);
    }
    if (action == "set-min") {
      return tryMinMax(val, false, true);
    }

    // arithmetics
    if (action == "add-1") {
      return val + 1;
    }
    if (action == "add-2") {
      return val + 2;
    }
    if (action == "sub-1") {
      return val - 1;
    }
    if (action == "sub-2") {
      return val - 2;
    }
    if (action == "mul-2") {
      return val * APInt(val.getBitWidth(), 2);
    }
    if (action == "mul-3") {
      return val * APInt(val.getBitWidth(), 3);
    }
    if (action == "div-2") {
      return val.sdiv(APInt(val.getBitWidth(), 2));
    }
    if (action == "div-3") {
      return val.sdiv(APInt(val.getBitWidth(), 3));
    }

    // bit ops
    if (action == "flip") {
      APInt new_val(val);
      new_val.flipAllBits();
      return new_val;
    }

    llvm_unreachable("Unknown constant int mutation action");
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_CONST_INT_REPLACE_H */
