from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_daily_shell_does_not_start_runner_when_batch_intent_publish_fails(tmp_path: Path) -> None:
    project = tmp_path / "TOP10new"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    (project / "logs").mkdir()
    shell = scripts / "run_daily_research_quota.sh"
    shell.write_text(
        (PROJECT_ROOT / "scripts/run_daily_research_quota.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    fake_python = project / "fake_python.py"
    calls = project / "runner_calls.txt"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os, pathlib, sys",
                "target = sys.argv[1] if len(sys.argv) > 1 else ''",
                "if target == 'scripts/fog_runtime_time_authority.py':",
                "    if '--field' in sys.argv:",
                "        print('2026-08-14')",
                "    raise SystemExit(0)",
                "if target == 'scripts/publish_research_batch_intent.py':",
                "    raise SystemExit(int(os.environ.get('PUBLISH_EXIT', '0')))",
                "if target == 'scripts/run_autonomous_research.py':",
                "    pathlib.Path(os.environ['RUNNER_CALLS']).write_text('called')",
                "    raise SystemExit(0)",
                "raise SystemExit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        ["bash", str(shell)],
        cwd=project,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(project),
            "TOP10_RESEARCH_PYTHON": str(fake_python),
            "TOP10_FOG_RUN_CONTEXT": "fixture",
            "PUBLISH_EXIT": "7",
            "RUNNER_CALLS": str(calls),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 7
    assert not calls.exists()
