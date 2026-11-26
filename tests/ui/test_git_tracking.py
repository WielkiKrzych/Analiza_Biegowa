import logging


def test_git_check_failure_is_logged(monkeypatch, caplog, tmp_path):
    """Pre-fix: ``except (OSError, subprocess.SubprocessError): pass`` made the
    subject-data privacy warning vanish without a trace whenever git was missing."""
    from modules.frontend import git_tracking

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(git_tracking.subprocess, "run", _boom)

    with caplog.at_level(logging.WARNING, logger="modules.frontend.git_tracking"):
        git_tracking.check_git_tracking("reports/ramp_tests")

    message = caplog.text
    assert "tracked by git" in message
    assert "did not run" in message


def test_git_check_failure_reaches_the_interface(monkeypatch, caplog, tmp_path):
    """Pre-fix: the failure was logged to a console nobody reads in Streamlit, so the
    user was never told that the subject-data privacy check did not run."""
    import streamlit

    from modules.frontend import git_tracking

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise OSError("git not installed")

    warnings = []
    monkeypatch.setattr(git_tracking.subprocess, "run", _boom)
    monkeypatch.setattr(streamlit, "warning", lambda msg: warnings.append(msg))

    git_tracking.check_git_tracking("reports/ramp_tests")

    assert warnings, "the user was never told the privacy check failed"
    assert "Kontrola prywatności nie została wykonana" in warnings[0]


def test_git_check_reports_tracked_subject_data(monkeypatch, tmp_path):
    """The happy path still raises the Streamlit privacy warning."""
    import streamlit

    from modules.frontend import git_tracking

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    errors = []
    monkeypatch.setattr(streamlit, "error", lambda msg: errors.append(msg))

    class _Result:
        returncode = 0
        stdout = "reports/ramp_tests/2026/01/ramp_test_2026-01-15_abc.json\n"

    monkeypatch.setattr(git_tracking.subprocess, "run", lambda *a, **k: _Result())

    git_tracking.check_git_tracking("reports/ramp_tests")

    assert errors and "SECURITY WARNING" in errors[0]
