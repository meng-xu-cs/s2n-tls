#ifndef LLVM_MUTEST_MUT_RULE_CONST_INT_REPLACE_H
#define LLVM_MUTEST_MUT_RULE_CONST_INT_REPLACE_H

#include "MutRule.h"
#include <fstream>
#include "json.hpp"
#include <vector>
using json = nlohmann::json;


namespace mutest {

class MutRuleConstIntReplace : public MutRule {
public:
  static constexpr const char *NAME = "const-replace";
  static bool const second_mutation = true;
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
  bool can_second_mutation() const override{return second_mutation;}
  bool can_mutate(const Instruction &i) const override {
    std::vector<size_t> const_positions;
    collectConstantOperands(&i, const_positions);
    return !const_positions.empty();
  }

  std::string origin_mutate(const Instruction &i) const override{
    // record the operand for all the operands
    std::vector<size_t> const_positions;
    collectConstantOperands(&i, const_positions);
    std::string origin_value = std::string("");
    for (auto & position: const_positions){
      const auto *operand = cast<ConstantInt>(i.getOperand(position));
      const auto &const_value = operand->getValue();
      origin_value.append(const_value.toString(10, true));
	    origin_value.append(" ");
    }
    return origin_value;
  }
  Optional<json> run_mutate(Instruction &i, std::string function_count, std::string inst_count) const override {
    // collect the operand number
    std::vector<size_t> const_positions;
    collectConstantOperands(&i, const_positions);

    // pick an operand to mutate
    auto choice = random_choice(const_positions);
    const auto *operand = cast<ConstantInt>(i.getOperand(choice));

    // pick an action such that after the mutation, the new value is guaranteed
    // to be different

    // Add: Also guarantee the mutated value has not shown up before
    // Create a file if it doesn't exist
    std::string constant_file = std::string("constant_history.json");

    const APInt &old_val = operand->getValue();

    std::ifstream f(constant_file);
    json data = json::array();
    if(!f.fail()){
      data = json::parse(f);
    }
    
    bool flag = false;
    // Iterate through the json object
    for(auto& element: data){
    // Use something that belongs to the instruction to identify it
    // Don't forget to allow for the empty one 
      if(element["Function"] ==function_count  && element["Instruction"] == inst_count && element["Operand"] == choice) {
        flag = true;
      } 

    }
    // If flag = false which means there is no history record in this file yet, 
    // append the original value in history  
    std::vector<uint64_t> v;
    if (flag == false){
      std::vector<uint64_t> v = {old_val.getZExtValue()};
      auto object = json::object();
      object["Function"] = function_count;
      object["Instruction"] = inst_count;
      object["Operand"] = choice;
      object["history"] = v;	
      data.push_back(object);
    }
    const char *action;
    ConstantInt *new_val;
    while (true) {
      if (old_val.getBitWidth() == 1) {
        // the only action for a single bit value is flip
        action = "flip";
      } else {
        action = random_choice(action_options);
      }

      auto result = run_action(operand->getValue(), action);
      if (old_val == result) {
        continue;
      }

      // Filter out flip case
      if (action != "flip"){
      // If the current result value is in the history vector, continue to regenerate a new one

      if (flag == true){
      for(auto& element:data){
        if(element["Instruction"] == inst_count && element["Function"] == function_count && element["Operand"] == choice) {
          element["history"].push_back(result.getZExtValue());
      } 
      }
    }

    }
    
      // now create the new constant
    new_val = ConstantInt::get(i.getContext(), result);
    // If flag == true, 
    

      // done with the mutation
      break;
    }
    std::ofstream o;
    o.open(constant_file, std::ofstream::out | std::ofstream::trunc);
    o << std::setw(4) << data << std::endl;
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

    // now create the new constant
    auto result = run_action(target->getValue(), info["action"]);
    auto new_val = ConstantInt::get(i.getContext(), result);
    i.setOperand(choice, new_val);
  }

private:
  static size_t probeOperandIndex(const Instruction *i, const Value *v) {
    for (unsigned int k = 0; k < i->getNumOperands(); k++) {
      if (i->getOperand(k) == v) {
        return k;
      }
    }
    llvm_unreachable("Unable to find the operand");
  }

  static void collectConstantOperandsNaive(const Instruction *i,
                                           std::vector<size_t> &indices) {
    for (unsigned int k = 0; k < i->getNumOperands(); k++) {
      if (isa<ConstantInt>(i->getOperand(k))) {
        indices.push_back(k);
      }
    }
  }

  static void collectConstantOperands(const Instruction *i,
                                      std::vector<size_t> &indices) {
    if (const auto *i_call = dyn_cast<CallInst>(i)) {
      // ignore some intrinsic functions as they have special requirements on
      // the format of the constant value
      if (const auto *i_intrinsic = dyn_cast<IntrinsicInst>(i_call)) {
        switch (i_intrinsic->getIntrinsicID()) {
        case Intrinsic::ID::memset:
        case Intrinsic::ID::memcpy:
        case Intrinsic::ID::memmove:
          return;
        default:
          break;
        }
      }

      for (unsigned int k = 0; k < i_call->getNumArgOperands(); k++) {
        const auto *v = i_call->getArgOperand(k);
        if (isa<ConstantInt>(v)) {
          indices.push_back(probeOperandIndex(i, v));
        }
      }
    } else if (const auto *i_store = dyn_cast<StoreInst>(i)) {
      const auto *v = i_store->getValueOperand();
      if (isa<ConstantInt>(v)) {
        indices.push_back(probeOperandIndex(i, v));
      }
    } else if (const auto *i_unary = dyn_cast<UnaryInstruction>(i)) {
      // do not mutate the alloca constant
      if (isa<AllocaInst>(i_unary)) {
        return;
      }
      collectConstantOperandsNaive(i_unary, indices);
    } else if (const auto *i_cmp = dyn_cast<CmpInst>(i)) {
      collectConstantOperandsNaive(i_cmp, indices);
    } else if (const auto *i_bin = dyn_cast<BinaryOperator>(i)) {
      collectConstantOperandsNaive(i_bin, indices);
    } else if (const auto *i_phi = dyn_cast<PHINode>(i)) {
      collectConstantOperandsNaive(i_phi, indices);
    } else if (const auto *i_return = dyn_cast<ReturnInst>(i)) {
      collectConstantOperandsNaive(i_return, indices);
    } else if (const auto *i_select = dyn_cast<SelectInst>(i)) {
      collectConstantOperandsNaive(i_select, indices);
    }
  }

  static APInt newConst(const APInt &old_val, int64_t new_val, bool is_signed) {
    return {old_val.getBitWidth(), static_cast<uint64_t>(new_val), is_signed};
  }

  static APInt newMinMax(const APInt &old_val, bool is_max, bool is_signed) {
    auto nbits = old_val.getBitWidth();
    auto new_val = is_max ? (is_signed ? APInt::getSignedMaxValue(nbits)
                                       : APInt::getMaxValue(nbits))
                          : (is_signed ? APInt::getSignedMinValue(nbits)
                                       : APInt::getMinValue(nbits));
    return new_val;
  }

  static APInt run_action(const APInt &val, const std::string &action) {
    // constants
    if (action == "set-0") {
      return newConst(val, 0, false);
    }
    if (action == "set-1") {
      return newConst(val, 1, false);
    }
    if (action == "set-2") {
      return newConst(val, 2, false);
    }
    if (action == "set-minus-1") {
      return newConst(val, -1, true);
    }
    if (action == "set-minus-2") {
      return newConst(val, -2, true);
    }
    if (action == "set-max-signed") {
      return newMinMax(val, true, true);
    }
    if (action == "set-max-unsigned") {
      return newMinMax(val, true, false);
    }
    if (action == "set-min") {
      return newMinMax(val, false, true);
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
