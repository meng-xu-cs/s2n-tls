#ifndef LLVM_MUTEST_MUT_RULE_CMP_INT_REPLACE_H
#define LLVM_MUTEST_MUT_RULE_CMP_INT_REPLACE_H

#include "MutRule.h"
#include <fstream>
#include "json.hpp"
#include <vector>
using json = nlohmann::json;

namespace mutest {

class MutRuleCmpIntReplace : public MutRule {
public:
  static constexpr const char *NAME = "cmp-int-replace";
  static bool const second_mutation = true;

private:
  // map every predicate with the possible mutant
  std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>> repl_signed;
  std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>> repl_unsigned;

public:
  MutRuleCmpIntReplace()
      : MutRule(NAME), repl_signed(getReplacementsSigned()),
        repl_unsigned(getReplacementsUnsigned()) {}

public:
  bool can_second_mutation() const override{return second_mutation;}
  bool can_mutate(const Instruction &i) const override {
    if (!isa<ICmpInst>(i)) {
      return false;
    }

    const auto &cmp_inst = cast<ICmpInst>(i);
    const auto predicate = cmp_inst.getPredicate();
    return predicate >= CmpInst::FIRST_ICMP_PREDICATE &&
           predicate <= CmpInst::LAST_ICMP_PREDICATE;
  }

  std::string origin_mutate(const Instruction &i) const override {
    if (!isa<ICmpInst>(i)){
      return std::string("");
    }
    const auto &cmp_inst = cast<ICmpInst>(i);
    const auto predicate = cmp_inst.getPredicate();
    return intoPredicateName(predicate);
   }

  Optional<json> run_mutate(Instruction &i,std::string function_count, std::string inst_count) const override {
    
    auto &cmp_inst = cast<ICmpInst>(i);
    const auto predicate = cmp_inst.getPredicate();

    // Add: Also guarantee the mutated predicate won't show up in the future
    // Create a file if it doesn't exist
    std::string constant_file = std::string("predicate_history.json");

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

    }
    // If flag = false which means there is no history record in this file yet, 
    // append the original value in history  
    std::vector<uint64_t> v;
    if (flag == false){
      std::vector<uint64_t> v = {predicate};
      auto object = json::object();
      object["Function"] = function_count;
      object["Instruction"] = inst_count;
      object["history"] = v;	
      data.push_back(object);
    }
      
    // EQ/NE can be either signed or unsigned
    bool is_signed;
    switch (predicate) {
    case CmpInst::Predicate::ICMP_EQ:
    case CmpInst::Predicate::ICMP_NE:
      is_signed = random_bool();
      break;
    case CmpInst::Predicate::ICMP_SGT:
    case CmpInst::Predicate::ICMP_SGE:
    case CmpInst::Predicate::ICMP_SLT:
    case CmpInst::Predicate::ICMP_SLE:
      is_signed = true;
      break;
    case CmpInst::Predicate::ICMP_UGT:
    case CmpInst::Predicate::ICMP_UGE:
    case CmpInst::Predicate::ICMP_ULT:
    case CmpInst::Predicate::ICMP_ULE:
      is_signed = false;
      break;
    default:
      llvm_unreachable("Unknown predicate");
    }

    // randomize a replacement
    const auto &options =
        is_signed ? repl_signed.at(predicate) : repl_unsigned.at(predicate);

    
    auto repl= random_choice(options);
    while(true){
    repl = random_choice(options);

    if (flag == true){
    for(auto& element:data){
        if(element["Instruction"] == inst_count && element["Function"] == function_count) {

          if (std::find(element["history"].begin(), element["history"].end(), repl) != element["history"].end())
          {
            continue;
          }
      } 
      }
    }
    if (flag == true){
      for(auto& element:data){
        if(element["Instruction"] == inst_count && element["Function"] == function_count) {
          element["history"].push_back(repl);
      } 
      }
    }

    }
    // do the replacement
    cmp_inst.setPredicate(repl);


    std::ofstream o;
    o.open(constant_file, std::ofstream::out | std::ofstream::trunc);
    o << std::setw(4) << data << std::endl;
    o.close();
    // save the info
    json info = json::object();
    info["repl"] = intoPredicateName(repl);
    return info;
  }

  void run_replay(Instruction &i, const json &info) const override {
    auto &cmp_inst = cast<ICmpInst>(i);

    // retrieve the package
    const auto repl = fromPredicateName(info["repl"]);

    // do the replacement
    cmp_inst.setPredicate(repl);
  }

private:
  static std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>>
  getReplacementsSigned() {
    const std::vector<CmpInst::Predicate> all_options = {
        CmpInst::Predicate::ICMP_EQ,  CmpInst::Predicate::ICMP_NE,
        CmpInst::Predicate::ICMP_SGT, CmpInst::Predicate::ICMP_SGE,
        CmpInst::Predicate::ICMP_SLT, CmpInst::Predicate::ICMP_SLE,
    };

    std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>> result;
    for (const auto pred : all_options) {
      std::vector<CmpInst::Predicate> replacements(all_options);
      replacements.erase(
          std::remove(replacements.begin(), replacements.end(), pred),
          replacements.end());
      result[pred] = replacements;
    }

    return result;
  }

  static std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>>
  getReplacementsUnsigned() {
    const std::vector<CmpInst::Predicate> all_options = {
        CmpInst::Predicate::ICMP_EQ,  CmpInst::Predicate::ICMP_NE,
        CmpInst::Predicate::ICMP_UGT, CmpInst::Predicate::ICMP_UGE,
        CmpInst::Predicate::ICMP_ULT, CmpInst::Predicate::ICMP_ULE,
    };

    std::map<CmpInst::Predicate, std::vector<CmpInst::Predicate>> result;
    for (const auto pred : all_options) {
      std::vector<CmpInst::Predicate> replacements(all_options);
      replacements.erase(
          std::remove(replacements.begin(), replacements.end(), pred),
          replacements.end());
      result[pred] = replacements;
    }

    return result;
  }

  static const char *intoPredicateName(const CmpInst::Predicate pred) {
    switch (pred) {
    case CmpInst::Predicate::ICMP_EQ:
      return "EQ";
    case CmpInst::Predicate::ICMP_NE:
      return "NE";
    case CmpInst::Predicate::ICMP_SGT:
      return "SGT";
    case CmpInst::Predicate::ICMP_SGE:
      return "SGE";
    case CmpInst::Predicate::ICMP_SLT:
      return "SLT";
    case CmpInst::Predicate::ICMP_SLE:
      return "SLE";
    case CmpInst::Predicate::ICMP_UGT:
      return "UGT";
    case CmpInst::Predicate::ICMP_UGE:
      return "UGE";
    case CmpInst::Predicate::ICMP_ULT:
      return "ULT";
    case CmpInst::Predicate::ICMP_ULE:
      return "ULE";
    default:
      llvm_unreachable("Unknown predicate");
    }
  }

  static CmpInst::Predicate fromPredicateName(const std::string &name) {
    if (name == "EQ") {
      return CmpInst::Predicate::ICMP_EQ;
    }
    if (name == "NE") {
      return CmpInst::Predicate::ICMP_NE;
    }
    if (name == "SGT") {
      return CmpInst::Predicate::ICMP_SGT;
    }
    if (name == "SGE") {
      return CmpInst::Predicate::ICMP_SGE;
    }
    if (name == "SLT") {
      return CmpInst::Predicate::ICMP_SLT;
    }
    if (name == "SLE") {
      return CmpInst::Predicate::ICMP_SLE;
    }
    if (name == "UGT") {
      return CmpInst::Predicate::ICMP_UGT;
    }
    if (name == "UGE") {
      return CmpInst::Predicate::ICMP_UGE;
    }
    if (name == "ULT") {
      return CmpInst::Predicate::ICMP_ULT;
    }
    if (name == "ULE") {
      return CmpInst::Predicate::ICMP_ULE;
    }
    llvm_unreachable("Unknown predicate name");
  }
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_CMP_INT_REPLACE_H */
