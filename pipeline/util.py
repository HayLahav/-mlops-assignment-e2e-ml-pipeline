"""Small subprocess helper shared by the agent and evaluation steps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


def run_logged(
    cmd: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    check: bool = True,
) -> int:
    """Run ``cmd``, streaming combined stdout/stderr to console and ``log_path``.

    Returns the process exit code. Raises ``CalledProcessError`` when
    ``check`` is set and the command fails -- this lets Airflow mark the task
    as failed and trigger retries.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    printable = " ".join(str(c) for c in cmd)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {printable}\n(cwd={cwd})\n\n")
        log.flush()
        proc = subprocess.Popen(
            [str(c) for c in cmd],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, list(cmd))
    return proc.returncode
