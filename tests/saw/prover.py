"""
SAW-related functionalities
"""
import logging
import os
import subprocess
import re
import shutil
import json
from typing import List, Dict, Union, Optional, Any
from collections import OrderedDict
from dataclasses import asdict, dataclass

import config
from util import cd, execute3

#
# Preparation
#

ErrorRecord = Union[str, List[str], Dict[str, Union[str, List[str], Dict[str, Any]]]]

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
    details: ErrorRecord


def _search_for_error_subgoal_failed(wks: str, lines: List[str]) -> List[ErrorRecord]:
    error_pattern = re.compile(
        r"^\[\d\d:\d\d:\d\d\.\d\d\d\] Subgoal failed: (.+?) (.+?):$"
    )

    result: List[ErrorRecord] = []

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
        #message = match.group(3)

        # prepare base message
        error = OrderedDict()  # type: Dict[str, ErrorRecord]
        error["type"] = "subgoal failed"
        error["goal"] = goal
        error["location"] = location
        error["message"] = "message"
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
    wks: str, i: int, lines: List[str], error: Dict[str, ErrorRecord]
) -> int:
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

        result = i + offset

    elif category == "Arithmetic comparison on incompatible values":
        extra.append(lines[i + 3].strip())
        extra.append(lines[i + 4].strip())
        extra.append(lines[i + 5].strip())
        result = i + 6

    elif category == "Error during memory load":
        # no more information
        result = i + 3

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

        result = i + offset + 2

    else:
        raise RuntimeError(
            "Unknown category for symexec assertion failure: {}".format(category)
        )

    error["extra"] = extra
    return result


def __search_for_symexec_abort_both_branch(
    wks: str, i: int, lines: List[str], error: Dict[str, ErrorRecord]
) -> int:
    # base message
    error["location"] = lines[i + 1].strip() + lines[i + 2].strip()

    # true branch message
    assert lines[i + 3].strip() == "Message from the true branch:"
    reason = lines[i + 4].strip()

    # look for fine-grained details
    error_t: Dict[str, ErrorRecord] = OrderedDict()

    if reason == "Abort due to assertion failure:":
        pos = __search_for_symexec_abort_assertion(wks, i + 4, lines, error_t)

    elif reason == "Both branches aborted after a symbolic branch.":
        pos = __search_for_symexec_abort_both_branch(wks, i + 4, lines, error_t)

    else:
        raise RuntimeError(
            "Unknown reasons for symbolic execution failure: {}".format(reason)
        )

    error["branch_t"] = error_t

    # false branch messages
    j = None
    while pos < len(lines):
        cursor = lines[pos].strip()
        if cursor == "Message from the false branch:":
            j = pos
            break
        pos += 1

    # found the location
    assert j is not None
    reason = lines[j + 1].strip()

    # look for fine-grained details
    error_f: Dict[str, ErrorRecord] = OrderedDict()

    if reason == "Abort due to assertion failure:":
        pos = __search_for_symexec_abort_assertion(wks, j + 1, lines, error_f)

    elif reason == "Both branches aborted after a symbolic branch.":
        pos = __search_for_symexec_abort_both_branch(wks, j + 1, lines, error_f)

    else:
        raise RuntimeError(
            "Unknown reasons for symbolic execution failure: {}".format(reason)
        )

    error["branch_f"] = error_f

    # return the cursor position for the next round
    return pos


def _search_for_symexec_failed(wks: str, lines: List[str]) -> List[ErrorRecord]:
    result: List[ErrorRecord] = []

    # scan for the stdout file for error patterns
    error_points = []
    for i, line in enumerate(lines):
        if line == "Symbolic execution failed.":
            error_points.append(i)

    # parse each error points
    for i in error_points:
        # base message
        error = OrderedDict()  # type: Dict[str, ErrorRecord]
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


def _search_for_assertion_failed(wks: str, lines: List[str]) -> List[ErrorRecord]:
    error_pattern = re.compile(r"^\s\sAssertion made at: (.+?)$")

    result: List[ErrorRecord] = []

    # scan for the stdout file for error patterns
    error_points = {}
    for i, line in enumerate(lines):
        match = error_pattern.match(line)
        if not match:
            continue
        error_points[i] = match.group(1)

    # look up until reaching the error message
    for i, location in error_points.items():
        error = OrderedDict()  # type: Dict[str, ErrorRecord]
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


def _search_for_prover_unknown(wks: str, lines: List[str]) -> List[ErrorRecord]:
    trace_pattern = re.compile(r"^\"(.*?)\" \((.*?)\)$")

    result: List[ErrorRecord] = []

    # scan for the stdout file for error patterns
    error_points = []
    for i, line in enumerate(lines):
        if line == "Prover returned Unknown":
            error_points.append(i)

    # parse each error points
    for i in error_points:
        error = OrderedDict()  # type: Dict[str, ErrorRecord]
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


def _parse_failure_report(
    item: str, wks: str, workdir: str
) -> Optional[List[VerificationError]]:
    # load the output file
    file_out = os.path.join(workdir, item + ".out")
    with open(file_out) as f:
        lines = [line.rstrip() for line in f]

    # scan for the stdout file for error patterns
    details: List[ErrorRecord] = []
    details.extend(_search_for_error_subgoal_failed(wks, lines))
    details.extend(_search_for_symexec_failed(wks, lines))
    details.extend(_search_for_assertion_failed(wks, lines))
    details.extend(_search_for_prover_unknown(wks, lines))

    if len(details) == 0:
        file_err = os.path.join(workdir, item + ".err")
        if os.stat(file_err).st_size == 0:
            raise RuntimeError("No errors found in file {}".format(file_out))
        else:
            with open(file_err) as f:
                lines = [line.rstrip() for line in f]
                logging.info(
                    "Observed error in file: {}\n{}".format(file_err, "\n".join(lines))
                )
                return None

    # convert them into verification errors
    return [VerificationError(item, entry) for entry in details]


def dump_verification_output(wks: str, workdir: str):
    print("Analyzing: {}".format(workdir))
    for entry in os.listdir(workdir):
        if not entry.endswith(".mark"):
            continue

        path_mark = os.path.join(workdir, entry)
        with open(path_mark) as f:
            if f.readline().strip() == "success":
                continue

        # found a potential failure case
        item, _ = os.path.splitext(entry)

        # check whether this out is in next round of mutation
        time_mark = os.path.getmtime(path_mark)
        path_out = os.path.join(workdir, item + ".out")
        time_out = os.path.getmtime(path_out)
        if time_out > time_mark:
            continue

        # now confirmed that this is definitely a failure case
        print("  Case failed: {}".format(item))
        errors = _parse_failure_report(item, wks, workdir)
        if errors is None:
            continue

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


def verify_all(wks: str, workdir: str) -> Optional[List[VerificationError]]:
    # run the verification
    all_saw_scripts = _collect_saw_scripts()
    results = [verify_one(wks, script, workdir) for script in all_saw_scripts]

    # collect the failure cases
    errors = []
    has_exception = False
    for result, script in zip(results, all_saw_scripts):
        if result:
            continue

        reports = _parse_failure_report(script, wks, workdir)
        if reports is None:
            has_exception = True
            continue

        for err in reports:
            if err not in errors:
                errors.append(err)

    if has_exception:
        return None

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
