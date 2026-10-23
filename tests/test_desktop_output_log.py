"""A detached launch must not let a dead stdout pipe kill audits.

When Scrawly is started from a shell that later goes away (an installer, a
script, an agent), stdout is a pipe nobody reads. The first structlog line
written during an audit — e.g. a `check_failed` warning — then raised
`BrokenPipeError`, and do_audit's catch-all marked the whole audit
"Failed: [Errno 32] Broken pipe" after the URLs were already saved, so the
crawl showed 0 issues and a perfect health score.
"""
import os
from pathlib import Path

import sentinelseo.desktop as desktop


def test_dead_pipe_is_rerouted_to_log_file(tmp_path: Path) -> None:
    r, w = os.pipe()
    stream = os.fdopen(w, "w", buffering=1)
    os.close(r)  # the reader is gone — writing now raises BrokenPipeError
    log_path = tmp_path / "scrawly.log"

    desktop._route_output_to_log(log_path, streams=(stream,))

    stream.write("check_failed check_id=R10\n")
    stream.flush()
    stream.close()
    assert "check_failed check_id=R10" in log_path.read_text()


def test_terminal_output_is_left_alone(tmp_path: Path) -> None:
    class Tty:
        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            raise AssertionError("a terminal must not be redirected")

    desktop._route_output_to_log(tmp_path / "scrawly.log", streams=(Tty(),))
