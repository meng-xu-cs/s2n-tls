#ifndef LLVM_MUTEST_MUT_RULE_H
#define LLVM_MUTEST_MUT_RULE_H

#include "json.hpp"
using json = nlohmann::json;

#include <llvm/ADT/Optional.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Module.h>
#include <llvm/Support/Casting.h>
using namespace llvm;

namespace mutest {

class MutRule {
public:
  const char *name_;

public:
  explicit MutRule(const char *name) : name_(name) {}
  virtual ~MutRule() = default;

public:
  /// Check whether this can be a mutation point
  virtual bool can_mutate(const Instruction &i) const { return false; }

  /// Perform the mutation
  virtual Optional<json> run_mutate(Instruction *i) const {
    return Optional<json>();
  }

  /// Replay the mutation
  virtual void run_replay(Instruction *i, const json &info) const {}
};

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_H */
