"""
SAW-related functionalities
"""

import os
import subprocess
import re
import shutil
import json
from typing import List, Dict, Union
from collections import OrderedDict
from dataclasses import asdict, dataclass

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
    details: Dict[str, Union[str, List[str]]]


def _search_for_error_subgoal_failed(
    wks: str, lines: List[str]
) -> List[Dict[str, Union[str, List[str]]]]:
    error_pattern = re.compile(
        r"^\[\d\d:\d\d:\d\d\.\d\d\d\] Subgoal failed: (.+?) (.+?): (.+?)$"
    )

    result: List[Dict[str, Union[str, List[str]]]] = []

    # scan for the stdout file for error patterns
    error_points = {}
    for i, line in enumerate(lines):
        match = error_pattern.match(line)
        if not match:
            continue

        goal = match.group(1)
        location = match.group(2)
        if location.startswith(wks):
            location = location[len(wks) :]
        message = match.group(3)

        # prepare base message
        error = OrderedDict()  # type: Dict[str, Union[str, List[str]]]
        error["type"] = "subgoal failed"
        error["goal"] = goal
        error["location"] = location
        error["message"] = message
        error_points[i] = error

    # proces the error
    for i, error in error_points.items():
        # look for extra details
        error["details"] = lines[i + 1].strip()
        extra = []

        if lines[i + 2] == "Details:":
            offset = 3
            while i + offset < len(lines):
                cursor = lines[i + offset]
                if not cursor.startswith(" "):
                    break
                extra.append(cursor.strip())
                offset += 1

        error["extra"] = extra

        # done with the error parsing
        result.append(error)

    return result


def __search_for_symexec_abort_assertion(
    wks: str, i: int, lines: List[str], error: Dict[str, Union[str, List[str]]]
) -> None:
    # base message
    error["location"] = lines[i + 1].strip()
    category = lines[i + 2].strip()
    error["category"] = category

    # look for extra details
    extra = []

    if category == "Global symbol not allocated":
        assert lines[i + 3].strip() == "Details:"
        indent = " " * (len(lines[i + 3]) - len(lines[i + 3].lstrip()) + 1)

        offset = 4
        while i + offset < len(lines):
            cursor = lines[i + offset]
            if not cursor.startswith(indent):
                break
            extra.append(cursor.strip())
            offset += 1

    elif category == "Arithmetic comparison on incompatible values":
        extra.append(lines[i + 3].strip())
        extra.append(lines[i + 4].strip())
        extra.append(lines[i + 5].strip())

    elif category == "Error during memory load":
        # no more information
        pass

    elif category.startswith("No override specification applies for"):
        offset = 3
        while i + offset < len(lines):
            cursor = lines[i + offset].strip()
            if (
                cursor == "The following overrides had some preconditions "
                "that failed concretely:"
            ):
                break
            offset += 1
        assert i + offset != len(lines)

        extra_name = lines[i + offset + 1].strip()
        match = re.compile(r"^- Name: (.*)$").match(extra_name)
        assert match
        extra_name = match.group(1)
        extra.append(extra_name)

        extra_location = lines[i + offset + 2].strip()
        match = re.compile(r"^Location: (.*)$").match(extra_location)
        assert match
        extra_location = match.group(1)
        if extra_location.startswith(wks):
            extra_location = extra_location[len(wks) :]
        extra.append(extra_location)

        offset = offset + 3
        while i + offset < len(lines):
            cursor = lines[i + offset].strip()
            if cursor.startswith("*"):
                break
            offset += 1
        assert i + offset != len(lines)

        match = re.compile(r"^\* (.*): error: (.*)$").match(lines[i + offset].strip())
        assert match

        extra_location = match.group(1)
        if extra_location.startswith(wks):
            extra_location = extra_location[len(wks) :]
        extra.append(extra_location)

        extra_error = match.group(2)
        extra.append(extra_error)

        extra_details = lines[i + offset + 1].strip()
        extra.append(extra_details)

    else:
        raise RuntimeError(
            "Unknown category for symexec assertion failure: {}".format(category)
        )

    error["extra"] = extra


def __search_for_symexec_abort_both_branch(
    wks: str, i: int, lines: List[str], error: Dict[str, Union[str, List[str]]]
) -> None:
    # base message
    error["location"] = lines[i + 1].strip() + lines[i + 2].strip()

    # true branch message
    assert lines[i + 3].strip() == "Message from the true branch:"
    assert lines[i + 4].strip() == "Abort due to assertion failure:"

    error_t: Dict[str, Union[str, List[str]]] = OrderedDict()
    __search_for_symexec_abort_assertion(wks, i + 4, lines, error_t)
    error_t["branch_t"] = ["{}: {}".format(k, v) for k, v in error_t.items()]

    # false branch messages
    j = None
    offset = 5
    while i + offset < len(lines):
        cursor = lines[i + offset]
        if cursor == "Message from the false branch:":
            j = i + offset
            break
        offset += 1

    # found the location
    assert j is not None
    assert lines[j + 1].strip() == "Abort due to assertion failure:"

    error_f: Dict[str, Union[str, List[str]]] = OrderedDict()
    __search_for_symexec_abort_assertion(wks, j + 1, lines, error_f)
    error_t["branch_f"] = ["{}: {}".format(k, v) for k, v in error_f.items()]


def _search_for_symexec_failed(
    wks: str,
    lines: List[str],
) -> List[Dict[str, Union[str, List[str]]]]:
    result: List[Dict[str, Union[str, List[str]]]] = []

    # scan for the stdout file for error patterns
    error_points = []
    for i, line in enumerate(lines):
        if line == "Symbolic execution failed.":
            error_points.append(i)

    # parse each error points
    for i in error_points:
        # base message
        error = OrderedDict()  # type: Dict[str, Union[str, List[str]]]
        error["type"] = "symbolic execution failed"
        reason = lines[i + 1].strip()
        error["reason"] = reason

        # look for fine-grained details
        if reason == "Abort due to assertion failure:":
            __search_for_symexec_abort_assertion(wks, i + 1, lines, error)

        elif reason == "Both branches aborted after a symbolic branch.":
            __search_for_symexec_abort_both_branch(wks, i + 1, lines, error)

        else:
            raise RuntimeError(
                "Unknown reasons for symbolic execution failure: {}".format(reason)
            )

        result.append(error)

    return result


def _search_for_assertion_failed(
    wks: str,
    lines: List[str],
) -> List[Dict[str, Union[str, List[str]]]]:
    error_pattern = re.compile(r"^\s\sAssertion made at: (.+?)$")

    result: List[Dict[str, Union[str, List[str]]]] = []

    # scan for the stdout file for error patterns
    error_points = {}
    for i, line in enumerate(lines):
        match = error_pattern.match(line)
        if not match:
            continue
        error_points[i] = match.group(1)

    # look up until reaching the error message
    for i, location in error_points.items():
        error = OrderedDict()  # type: Dict[str, Union[str, List[str]]]
        error["type"] = "assertion failed"

        offset = 1
        while i >= offset:
            cursor = lines[i - offset]
            if cursor == "at " + location:
                message = lines[i - offset + 1]
                error["message"] = message

                # strip out the prefix of the location
                if location.startswith(wks):
                    location = location[len(wks) :]
                error["location"] = location
                break

            offset += 1

        assert i != offset
        result.append(error)

    return result


def _search_for_prover_unknown(
    wks: str, lines: List[str]
) -> List[Dict[str, Union[str, List[str]]]]:
    trace_pattern = re.compile(r"^\"(.*?)\" \((.*?)\)$")

    result: List[Dict[str, Union[str, List[str]]]] = []

    # scan for the stdout file for error patterns
    error_points = []
    for i, line in enumerate(lines):
        if line == "Prover returned Unknown":
            error_points.append(i)

    # parse each error points
    for i in error_points:
        error = OrderedDict()  # type: Dict[str, Union[str, List[str]]]
        error["type"] = "prover unknown"

        trace = []
        offset = 1
        while i >= offset:
            cursor = lines[i - offset].strip()
            if cursor.endswith("Stack trace:"):
                break

            match = trace_pattern.match(cursor)
            assert match
            function = match.group(1)
            location = match.group(2)
            if location.startswith(wks):
                location = location[len(wks) :]

            trace.append("{} @ {}".format(function, location))
            offset += 1

        assert i != offset
        error["trace"] = trace
        result.append(error)

    return result


def _parse_failure_report(item: str, wks: str, workdir: str) -> List[VerificationError]:
    # load the output file
    file_out = os.path.join(workdir, item + ".out")
    with open(file_out) as f:
        lines = [line.rstrip() for line in f]

    # scan for the stdout file for error patterns
    details: List[Dict[str, Union[str, List[str]]]] = []
    details.extend(_search_for_error_subgoal_failed(wks, lines))
    details.extend(_search_for_symexec_failed(wks, lines))
    details.extend(_search_for_assertion_failed(wks, lines))
    details.extend(_search_for_prover_unknown(wks, lines))
    assert len(details) != 0

    # convert them into verification errors
    return [VerificationError(item, entry) for entry in details]


def dump_verification_output(wks: str, workdir: str):
    print("Analyzing: {}".format(workdir))
    for entry in os.listdir(workdir):
        if not entry.endswith(".mark"):
            continue

        with open(os.path.join(workdir, entry)) as f:
            if f.readline().strip() == "success":
                continue

        # found a failure case
        item, _ = os.path.splitext(entry)
        print("  Case failed: {}".format(item))

        errors = _parse_failure_report(item, wks, workdir)
        for error in errors:
            print("    {}".format(json.dumps(asdict(error), indent=4)))


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
    errors = []
    for result, script in zip(results, all_saw_scripts):
        if not result:
            for err in _parse_failure_report(script, wks, workdir):
                if err not in errors:
                    errors.append(err)
    return errors


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
