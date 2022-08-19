"""
SAW-related functionalities
"""

import os
import subprocess
import re
import shutil
from typing import List, Dict
from collections import OrderedDict
from dataclasses import dataclass

import config
from util import cd, execute3

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
    details: Dict[str, str]


def _search_for_error_subgoal_failed(
    wks: str, lines: List[str]
) -> List[Dict[str, str]]:
    error_pattern = re.compile(
        r"^\[\d\d:\d\d:\d\d\.\d\d\d\] Subgoal failed: (.+?) (.+?): (.+?)$"
    )

    result: List[Dict[str, str]] = []

    # scan for the stdout file for error patterns
    pending_error = None
    for line in lines:
        line = line.strip()

        # consume the next line after the error message
        if pending_error is not None:
            pending_error["details"] = line
            result.append(pending_error)
            pending_error = None
            continue

        # check for error message
        match = error_pattern.match(line)
        if not match:
            continue

        # this line represents an error
        goal = match.group(1)
        location = match.group(2)
        if location.startswith(wks):
            location = location[len(wks) :]
        message = match.group(3)

        # prepare the partial details
        pending_error = OrderedDict()
        pending_error["type"] = "subgoal failed"
        pending_error["goal"] = goal
        pending_error["location"] = location
        pending_error["message"] = message

    assert pending_error is None
    return result


def _search_for_symexec_failed(lines: List[str]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []

    # scan for the stdout file for error patterns
    error_points = []
    for i, line in enumerate(lines):
        if line == "Symbolic execution failed.":
            error_points.append(i)

    # parse each error points
    for i in error_points:
        error = OrderedDict()
        error["type"] = "symbolic execution failed"
        error["reason"] = lines[i + 1].strip()
        error["location"] = lines[i + 2].strip()
        error["details"] = lines[i + 3].strip()

        assert lines[i + 4].strip() == "Details:"
        extra = []

        offset = 5
        while True:
            if i + offset >= len(lines):
                break

            cursor = lines[i + offset]
            if not cursor.startswith(" "):
                break

            extra.append(cursor.strip())
            offset += 1

        error["extra"] = "\n".join(extra)
        result.append(error)

    return result


def _search_for_assertion_failed(lines: List[str]) -> List[Dict[str, str]]:
    error_pattern = re.compile(r"^\s\sAssertion made at: (.+?)$")

    result: List[Dict[str, str]] = []

    # scan for the stdout file for error patterns
    error_points = {}
    for i, line in enumerate(lines):
        match = error_pattern.match(line)
        if match:
            error_points[i] = match.group(1)

    # look up until reaching the error message
    for i, location in error_points.items():
        offset = 1
        while i >= offset:
            cursor = lines[i - offset]
            if cursor == "at " + location:
                message = lines[i - offset + 1]

                error = OrderedDict()
                error["type"] = "assertion failed"
                error["location"] = location
                error["message"] = message
                result.append(error)

                break
            offset += 1

    return result


def parse_failure_report(item: str, wks: str, workdir: str) -> List[VerificationError]:
    # load the output file
    file_out = os.path.join(workdir, item + ".out")
    with open(file_out) as f:
        lines = [line.rstrip() for line in f]

    # scan for the stdout file for error patterns
    details: List[Dict[str, str]] = []
    details.extend(_search_for_error_subgoal_failed(wks, lines))
    details.extend(_search_for_symexec_failed(lines))
    details.extend(_search_for_assertion_failed(lines))
    assert len(details) != 0

    # convert them into verification errors
    return [VerificationError(item, entry) for entry in details]


def verify_one(wks: str, item: str, result_dir: str) -> bool:
    os.makedirs(os.path.dirname(result_dir), exist_ok=True)
    file_out = os.path.join(result_dir, item + ".out")
    file_err = os.path.join(result_dir, item + ".err")
    file_log = os.path.join(result_dir, item + ".log")
    file_mark = os.path.join(result_dir, item + ".mark")

    with cd(wks):
        try:
            execute3(
                ["saw", "-v", "debug", "-s", file_log, "-f", "json", item],
                pout=file_out,
                perr=file_err,
            )
            result = True
            message = "success"

        except subprocess.SubprocessError as ex:
            result = False
            message = str(ex)

        # dump the execution status
        with open(file_mark, "w") as f:
            f.write(message)

        return result


def verify_all(wks: str, workdir: str) -> List[VerificationError]:
    # run the verification
    all_saw_scripts = _collect_saw_scripts()
    results = [verify_one(wks, script, workdir) for script in all_saw_scripts]

    # collect the failure cases
    errors = set()
    for result, script in zip(results, all_saw_scripts):
        if not result:
            for err in parse_failure_report(script, wks, workdir):
                errors.add(err)
    return sorted(errors)


def duplicate_workspace(wks: str) -> None:
    # create an empty bitcode dir
    os.makedirs(os.path.join(wks, "bitcode"), exist_ok=True)

    # copy over top-level SAW files
    for item in os.listdir(config.PATH_BASE):
        if item.endswith(".saw"):
            shutil.copyfile(
                os.path.join(config.PATH_BASE, item), os.path.join(wks, item)
            )

    # copy over important directories
    for item in ["spec", "HMAC"]:
        shutil.copytree(os.path.join(config.PATH_BASE, item), os.path.join(wks, item))
