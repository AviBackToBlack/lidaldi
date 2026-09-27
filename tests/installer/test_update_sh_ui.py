"""update.sh console output: plain unless a terminal asks for fancy.

Plain output is a contract (these installer tests and operators' log greps
rely on the "TOKEN  message" lines), so fancy mode must never leak into
pipes, and forcing it must not change what the installer does.
"""

from conftest import run_update

ANSI = "\x1b["


def test_output_is_plain_when_not_a_terminal(sandbox):
    proc = run_update(sandbox)
    assert ANSI not in proc.stdout
    assert "✔" not in proc.stdout
    assert "PLAN  create directory" in proc.stdout
    assert "APPLY create directory" in proc.stdout


def test_fancy_mode_does_the_same_work(sandbox):
    proc = run_update(sandbox, env={"LIDALDI_FANCY": "1"})
    assert ANSI in proc.stdout
    assert "◆ LidAldi" in proc.stdout
    assert "BACKUP" in proc.stdout and "DONE" in proc.stdout
    assert (sandbox["WEB_ROOT"] / "index.html").is_file()
    # Same end state as a plain run: the next run has nothing to do.
    assert "NOOP" in run_update(sandbox).stdout


def test_plain_flag_beats_forced_fancy(sandbox):
    proc = run_update(sandbox, "--plain", env={"LIDALDI_FANCY": "1"})
    assert ANSI not in proc.stdout
    assert "APPLY create directory" in proc.stdout


def test_no_color_is_respected(sandbox):
    proc = run_update(sandbox, env={"NO_COLOR": "1"})
    assert ANSI not in proc.stdout


def test_help_documents_plain_flag(sandbox):
    proc = run_update(sandbox, "--help")
    assert "--plain" in proc.stdout
