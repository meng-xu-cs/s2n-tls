import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from typing import IO, Iterator, List, Optional


# with statements
@contextmanager
def cd(pn: str) -> Iterator[None]:
    """
    change directory
    """

    cur = os.getcwd()
    os.chdir(os.path.expanduser(pn))
    try:
        yield
    finally:
        os.chdir(cur)


@contextmanager
def environ(
    key: str, value: Optional[str], concat: Optional[str] = None, prepend: bool = True
) -> Iterator[None]:
    """
    Temporarily change the environment variable.
    If value is None, the environment variable is removed.
    If prepend is True, the environment variable is prepended.
    """

    def _set_env(key: str, value: Optional[str]) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    old_value = os.environ.get(key, None)

    if value is None or concat is None or old_value is None:
        new_value = value
    elif prepend:
        new_value = value + concat + old_value
    else:
        new_value = old_value + concat + value

    _set_env(key, new_value)

    try:
        yield
    finally:
        _set_env(key, old_value)


@contextmanager
def envpaths(*path: str) -> Iterator[None]:
    """
    Prepend the PATH variable
    """

    with environ("PATH", value=":".join(path), concat=":", prepend=True):
        yield


@contextmanager
def envldpaths(*path: str) -> Iterator[None]:
    """
    Prepend the LD_LIBRARY_PATH variable
    """

    with environ("LD_LIBRARY_PATH", value=":".join(path), concat=":", prepend=True):
        yield


@contextmanager
def envpreload(path: str) -> Iterator[None]:
    """
    Assign the LD_PRELOAD variable
    """

    with environ("LD_PRELOAD", value=path):
        yield


# command execution
def execute(
    cmd: List[str],
    stdout: IO = sys.stdout,
    stderr: IO = sys.stderr,
    timeout: Optional[int] = None,
) -> None:
    """
    Execute command and return whether the command finished successfully.
    If stdout/stderr is not None, use the file object specified.
    If tee is True, also print the stdout/stderr to console.
    """

    with subprocess.Popen(
        cmd,
        bufsize=1,
        universal_newlines=True,
        stdout=stdout,
        stderr=stderr,
    ) as p:
        while True:
            try:
                rc = p.wait(timeout=timeout)
                if rc != 0:
                    raise subprocess.SubprocessError(
                        "Failed to execute {}: exit code {}".format(" ".join(cmd), rc)
                    )
                return
            except subprocess.TimeoutExpired:
                p.kill()
                raise subprocess.SubprocessError(
                    "Failed to execute {}: timed out".format(" ".join(cmd))
                )


def execute1(cmd: List[str], timeout: Optional[int] = None) -> None:
    """
    Same as execute, but direct all outputs to /dev/null
    """

    with open(os.devnull, "w") as fout:
        with open(os.devnull, "w") as ferr:
            execute(cmd, fout, ferr, timeout)


def execute2(cmd: List[str], path_log: str, timeout: Optional[int] = None) -> None:
    """
    Same as execute, but allows specification of path_log.
    """

    path_out = path_log + ".out"
    path_err = path_log + ".err"
    with open(path_out, "w") as stdout:
        with open(path_err, "w") as stderr:
            execute(cmd, stdout, stderr, timeout)


def execute3(
    cmd: List[str], pout: str, perr: str, timeout: Optional[int] = None
) -> None:
    """
    Same as execute, but allows specification of both pout and perr.
    """

    with open(pout, "w") as stdout:
        with open(perr, "w") as stderr:
            execute(cmd, stdout, stderr, timeout)


# logging
def enable_coloring_in_logging() -> None:
    logging.addLevelName(
        logging.CRITICAL,
        "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.CRITICAL),
    )
    logging.addLevelName(
        logging.ERROR,
        "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR),
    )
    logging.addLevelName(
        logging.WARNING,
        "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING),
    )
    logging.addLevelName(
        logging.INFO,
        "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.INFO),
    )
    logging.addLevelName(
        logging.DEBUG,
        "\033[1;35m%s\033[1;0m" % logging.getLevelName(logging.DEBUG),
    )
