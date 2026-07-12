from __future__ import annotations

import os
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    """Wait for the parent Job assignment, then launch Grok inside that Job."""

    args = argv if argv is not None else sys.argv[1:]
    if not args:
        raise SystemExit("missing Grok argument vector")
    if sys.stdin.buffer.read(1) != b"1":
        raise SystemExit("launcher was not released by its controller")
    child = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
        shell=False,
        close_fds=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
