#ifndef LLVM_MUTEST_MUT_RULE_H
#define LLVM_MUTEST_MUT_RULE_H

#include <map>
#include <random>
#include <vector>

#include "json.hpp"
using json = nlohmann::json;

#include <llvm/ADT/Optional.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/IntrinsicInst.h>
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
  virtual Optional<json> run_mutate(Instruction &i) const {
    return Optional<json>();
  }

  /// Replay the mutation
  virtual void run_replay(Instruction &i, const json &info) const {}
};

//
// utilities functions
//

size_t random_range(size_t min, size_t max) {
  std::random_device rd;
  std::mt19937_64 gen(rd());
  std::uniform_int_distribution<size_t> dist(min, max);
  return dist(gen);
}

bool random_bool() { return random_range(0, 1) == 0; }

template <typename T> const T &random_choice(const std::vector<T> &items) {
  return items.at(random_range(0, items.size() - 1));
}

} // namespace mutest

#endif /* LLVM_MUTEST_MUT_RULE_H */
