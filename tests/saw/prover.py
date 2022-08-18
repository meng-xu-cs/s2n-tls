"""
SAW-related functionalities
"""

import os
import subprocess
import re
from typing import List
from dataclasses import dataclass

import config
from util import cd, execute3, envpaths

#
# Preparation
#


# TODO: ideally we should not ignore any SAW scripts.
IGNORED_TOP_LEVEL_SAW_SCRIPTS = [
    # ignored because of lengthy and nondeterministic verification
    "verify_imperative_cryptol_spec.saw"
]


def _collect_saw_scripts() -> List[str]:
    all_saw_scripts = set()
    for item in os.listdir(config.PATH_BASE):
        if item.endswith(".saw") and item not in IGNORED_TOP_LEVEL_SAW_SCRIPTS:
            all_saw_scripts.add(item)
    return sorted(all_saw_scripts)


def collect_verified_functions() -> List[str]:
    # collect SAW files
    saw_scripts = _collect_saw_scripts()
    for base, _, files in os.walk(os.path.join(config.PATH_BASE, "spec")):
        for item in files:
            if item.endswith(".saw"):
                saw_scripts.append(os.path.join(base, item))

    # extract verified functions
    verified_functions = set()
    for script in saw_scripts:
        with open(script) as f:
            for line in f:
                tokens = line.strip().split()
                for i, tok in enumerate(tokens):
                    if tok == "crucible_llvm_verify":
                        target = tokens[i + 2]
                        assert target.startswith('"')
                        assert target.endswith('"')
                        verified_functions.add(target[1:-1])

    return sorted(verified_functions)


#
# Verification
#


@dataclass(frozen=True, eq=True, order=True)
class VerificationError(object):
    item: str
    goal: str
    location: str
    message: str
    details: str


@dataclass
class VerificationErrorBuilder(object):
    item: str
    goal: str
    location: str
    message: str
    details: str

    def build(self) -> VerificationError:
        return VerificationError(
            self.item, self.goal, self.location, self.message, self.details
        )


def _parse_failure_report(item: str, workdir: str) -> List[VerificationError]:
    error_pattern = re.compile(
        r"^\[\d\d:\d\d:\d\d\.\d\d\d\] Subgoal failed: (.+?) (.+?): (.+?)$"
    )

    result: List[VerificationError] = []

    # scan for the stdout file for error patterns
    file_out = os.path.join(workdir, item + ".out")
    with open(file_out) as f:
        pending_error = None
        for line in f:
            line = line.strip()

            # consume the next line after the error message
            if pending_error is not None:
                pending_error.details = line
                result.append(pending_error.build())
                pending_error = None
                continue

            # check for error message
            match = error_pattern.match(line)
            if not match:
                continue

            # this line represents an error
            pending_error = VerificationErrorBuilder(
                item, match.group(1), match.group(2), match.group(3), ""
            )

    assert len(result) != 0
    return result


def verify_one(item: str, workdir: str) -> bool:
    os.makedirs(os.path.dirname(workdir), exist_ok=True)
    file_out = os.path.join(workdir, item + ".out")
    file_err = os.path.join(workdir, item + ".err")
    file_log = os.path.join(workdir, item + ".log")

    with cd(config.PATH_BASE):
        with envpaths(os.path.join(config.PATH_DEPS_SAW, "bin")):
            try:
                execute3(
                    ["saw", "-v", "debug", "-s", file_log, "-f", "json", item],
                    pout=file_out,
                    perr=file_err,
                )
                return True
            except subprocess.SubprocessError:
                return False


def verify_all(workdir: str) -> List[VerificationError]:
    # run the verification
    all_saw_scripts = _collect_saw_scripts()
    results = [verify_one(script, workdir) for script in all_saw_scripts]

    # collect the failure cases
    errors = set()
    for result, script in zip(results, all_saw_scripts):
        if not result:
            for err in _parse_failure_report(script, workdir):
                errors.add(err)
    return sorted(errors)
