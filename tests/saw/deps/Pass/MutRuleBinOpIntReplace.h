#ifndef LLVM_MUTEST_MUT_RULE_BINOP_INT_REPLACE_H
#define LLVM_MUTEST_MUT_RULE_BINOP_INT_REPLACE_H

#include "MutRule.h"

namespace mutest {

class MutRuleBinOpIntReplace : public MutRule {
public:
  static constexpr const char *NAME = "binop-int-replace";
  static bool const second_mutation = true;

private:
  std::map<BinaryOperator::BinaryOps, std::vector<BinaryOperator::BinaryOps>>
      repl_options;

public:
  MutRuleBinOpIntReplace() : MutRule(NAME), repl_options(getReplacements()) {}

public:
  bool can_second_mutation() const override{return second_mutation;}
  bool can_mutate(const Instruction &i) const override {
    if (!isa<BinaryOperator>(i)) {
      return false;
    }

    const auto &bin_inst = cast<BinaryOperator>(i);
    switch (bin_inst.getOpcode()) {
      // arithmetics
    case BinaryOperator::BinaryOps::Add:
    case BinaryOperator::BinaryOps::Sub:
    case BinaryOperator::BinaryOps::Mul:
    case BinaryOperator::BinaryOps::UDiv:
    case BinaryOperator::BinaryOps::SDiv:
    case BinaryOperator::BinaryOps::URem:
    case BinaryOperator::BinaryOps::SRem:
      // bitwise
    case BinaryOperator::BinaryOps::Shl:
    case BinaryOperator::BinaryOps::LShr:
    case BinaryOperator::BinaryOps::AShr:
    case BinaryOperator::BinaryOps::And:
    case BinaryOperator::BinaryOps::Or:
    case BinaryOperator::BinaryOps::Xor:
      return true;
    default:
      return false;
    }
  }
  std::string origin_mutate(const Instruction &i) const override {
    if (!isa<BinaryOperator>(i)){
      return std::string("");
    }
    const auto &bin_inst = cast<BinaryOperator>(i);
    return intoOpcodeName(bin_inst.getOpcode());
  
  }

  Optional<json> run_mutate(Instruction &i, std::string function_count, std::string inst_count ) const override {
    auto &bin_inst = cast<BinaryOperator>(i);
    const auto opcode = bin_inst.getOpcode();

    // Add: Also guarantee the mutated predicate won't show up in the future
    // Create a file if it doesn't exist
    std::string constant_file = std::string("/home/r2ji/s2n-tls/tests/saw/binop_history.json");

    std::ifstream f(constant_file);
    json data = json::array();
    if(!f.fail()){
      data = json::parse(f);
    }

    bool flag = false;
    // Iterate through the json object
    for(auto& element: data){
    // Use something that belongs to the instruction to identify it
      if(element["Function"] ==function_count  && element["Instruction"] == inst_count) {
        flag = true;
      } 
      // If flag = false which means there is no history record in this file yet, 
      // append the original value in history  
      std::vector<uint64_t> v;
      if (flag == false){
        std::vector<uint64_t> v = {opcode};
        auto object = json::object();
        object["Function"] = function_count;
        object["Instruction"] = inst_count;
        object["history"] = v;	
        data.push_back(object);
      }
    }

    // randomize a replacement
    const auto &options = repl_options.at(opcode);
    BinaryOperator::BinaryOps repl;
    for (unsigned counter = 0; counter < 3; counter++) {
      repl = random_choice(options);
      // lower the chance of getting a remainder
      if (repl != BinaryOperator::BinaryOps::SRem &&
          repl != BinaryOperator::BinaryOps::URem) {
        break;
      }
    }

    // add a small chance of swapping the operands
    const bool swap = random_range(0, 10) >= 8;

    if (flag == true){
      for(auto& element:data){
        if(element["Instruction"] == inst_count && element["Function"] == function_count) {
          element["history"].push_back(repl);
      } 
      }
      std::ofstream o(constant_file);
      o << std::setw(4) << data << std::endl;
    }
    // do the replacement
    doReplace(bin_inst, swap, repl);

    // save the info
    json info = json::object();
    info["repl"] = intoOpcodeName(repl);
    info["swap"] = swap;
    return info;
  }

  void run_replay(Instruction &i, const json &info) const override {
    auto &bin_inst = cast<BinaryOperator>(i);

    // retrieve the package
    const auto repl = fromOpcodeName(info["repl"]);
    const bool swap = info["swap"];

    // do the replacement
    doReplace(bin_inst, swap, repl);
  }

private:
  static std::map<BinaryOperator::BinaryOps,
                  std::vector<BinaryOperator::BinaryOps>>
  getReplacements() {
    const std::vector<BinaryOperator::BinaryOps> all_options = {
        // arithmetics
        BinaryOperator::BinaryOps::Add,
        BinaryOperator::BinaryOps::Sub,
        BinaryOperator::BinaryOps::Mul,
        BinaryOperator::BinaryOps::UDiv,
        BinaryOperator::BinaryOps::SDiv,
        BinaryOperator::BinaryOps::URem,
        BinaryOperator::BinaryOps::SRem,
        // bitwise
        BinaryOperator::BinaryOps::Shl,
        BinaryOperator::BinaryOps::LShr,
        BinaryOperator::BinaryOps::AShr,
        BinaryOperator::BinaryOps::And,
        BinaryOperator::BinaryOps::Or,
        BinaryOperator::BinaryOps::Xor,
    };

    std::map<BinaryOperator::BinaryOps, std::vector<BinaryOperator::BinaryOps>>
        result;
    for (const auto opcode : all_options) {
      std::vector<BinaryOperator::BinaryOps> replacements(all_options);
      replacements.erase(
          std::remove(replacements.begin(), replacements.end(), opcode),
          replacements.end());

      // further de-prioritize operations that are too similar
      switch (opcode) {
      case BinaryOperator::BinaryOps::UDiv:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::SDiv),
                           replacements.end());
        break;
      case BinaryOperator::BinaryOps::SDiv:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::UDiv),
                           replacements.end());
        break;
      case BinaryOperator::BinaryOps::URem:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::SRem),
                           replacements.end());
        break;
      case BinaryOperator::BinaryOps::SRem:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::URem),
                           replacements.end());
        break;
      case BinaryOperator::BinaryOps::AShr:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::LShr),
                           replacements.end());
        break;
      case BinaryOperator::BinaryOps::LShr:
        replacements.erase(std::remove(replacements.begin(), replacements.end(),
                                       BinaryOperator::BinaryOps::AShr),
                           replacements.end());
        break;
      default:
        break;
      }
      result[opcode] = replacements;
    }

    return result;
  }

  static const char *intoOpcodeName(const BinaryOperator::BinaryOps opcode) {
    switch (opcode) {
      // arithmetics
    case BinaryOperator::BinaryOps::Add:
      return "Add";
    case BinaryOperator::BinaryOps::Sub:
      return "Sub";
    case BinaryOperator::BinaryOps::Mul:
      return "Mul";
    case BinaryOperator::BinaryOps::UDiv:
      return "UDiv";
    case BinaryOperator::BinaryOps::SDiv:
      return "SDiv";
    case BinaryOperator::BinaryOps::URem:
      return "URem";
    case BinaryOperator::BinaryOps::SRem:
      return "SRem";
      // bitwise
    case BinaryOperator::BinaryOps::Shl:
      return "Shl";
    case BinaryOperator::BinaryOps::LShr:
      return "LShr";
    case BinaryOperator::BinaryOps::AShr:
      return "AShr";
    case BinaryOperator::BinaryOps::And:
      return "And";
    case BinaryOperator::BinaryOps::Or:
      return "Or";
    case BinaryOperator::BinaryOps::Xor:
      return "Xor";
    default:
      llvm_unreachable("Unknown predicate");
    }
  }

  static BinaryOperator::BinaryOps fromOpcodeName(const std::string &name) {
    if (name == "Add") {
      return BinaryOperator::BinaryOps::Add;
    }
    if (name == "Sub") {
      return BinaryOperator::BinaryOps::Sub;
    }
    if (name == "Mul") {
      return BinaryOperator::BinaryOps::Mul;
    }
    if (name == "UDiv") {
      return BinaryOperator::BinaryOps::UDiv;
    }
    if (name == "SDiv") {
      return BinaryOperator::BinaryOps::SDiv;
    }
    if (name == "URem") {
      return BinaryOperator::BinaryOps::URem;
    }
    if (name == "SRem") {
      return BinaryOperator::BinaryOps::SRem;
    }
    if (name == "Shl") {
      return BinaryOperator::BinaryOps::Shl;
    }
    if (name == "LShr") {
      return BinaryOperator::BinaryOps::LShr;
    }
    if (name == "AShr") {
      return BinaryOperator::BinaryOps::AShr;
    }
    if (name == "And") {
      return BinaryOperator::BinaryOps::And;
    }
    if (name == "Or") {
      return BinaryOperator::BinaryOps::Or;
    }
    if (name == "Xor") {
      return BinaryOperator::BinaryOps::Xor;
    }
    llvm_unreachable("Unknown opcode name");
  }

  static void doReplace(BinaryOperator &bin_inst, bool swap,
                        const BinaryOperator::BinaryOps target) {
    IRBuilder<> builder(&bin_inst);
    auto lhs = swap ? bin_inst.getOperand(0) : bin_inst.getOperand(1);
    auto rhs = swap ? bin_inst.getOperand(1) : bin_inst.getOperand(0);

    Value *new_inst = nullptr;
    switch (target) {
      // arithmetics
    case BinaryOperator::BinaryOps::Add:
      new_inst = builder.CreateAdd(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::Sub:
      new_inst = builder.CreateSub(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::Mul:
      new_inst = builder.CreateMul(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::UDiv:
      new_inst = builder.CreateUDiv(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::SDiv:
      new_inst = builder.CreateSDiv(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::URem:
      new_inst = builder.CreateURem(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::SRem:
      new_inst = builder.CreateSRem(lhs, rhs);
      break;
      // bitwise
    case BinaryOperator::BinaryOps::Shl:
      new_inst = builder.CreateShl(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::LShr:
      new_inst = builder.CreateLShr(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::AShr:
      new_inst = builder.CreateAShr(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::And:
      new_inst = builder.CreateAnd(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::Or:
      new_inst = builder.CreateOr(lhs, rhs);
      break;
    case BinaryOperator::BinaryOps::Xor:
      new_inst = builder.CreateXor(lhs, rhs);
      break;
    default:
      llvm_unreachable("Unknown binary operator");
    }

    assert(new_inst != nullptr && "New instruction not created");
    bin_inst.replaceAllUsesWith(new_inst);
    // NOTE: erasing is important to ensure that the instruction count is intact
    bin_inst.eraseFromParent();
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_BINOP_INT_REPLACE_H */
