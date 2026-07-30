"""Static/runtime contract for the production Gunicorn entrypoint."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = REPO_ROOT / "backend/docker/Dockerfile.prod"
ENTRYPOINT = REPO_ROOT / "backend/docker/start-production.sh"


def test_dockerfile_uses_configurable_production_entrypoint():
    dockerfile = DOCKERFILE.read_text()

    assert "COPY backend/docker/start-production.sh /usr/local/bin/" in dockerfile
    assert 'ENTRYPOINT ["start-production.sh"]' in dockerfile
    assert 'CMD ["gunicorn"' not in dockerfile


def test_entrypoint_passes_validated_worker_configuration(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "argv"
    gunicorn = fake_bin / "gunicorn"
    gunicorn.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_FILE"\n',
        encoding="utf-8",
    )
    gunicorn.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CAPTURE_FILE": str(capture),
        "GUNICORN_WORKERS": "3",
        "GUNICORN_THREADS": "4",
        "GUNICORN_TIMEOUT": "90",
        "GUNICORN_MAX_REQUESTS": "700",
        "GUNICORN_MAX_REQUESTS_JITTER": "50",
    }

    subprocess.run([str(ENTRYPOINT)], env=env, check=True)

    argv = capture.read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--workers") + 1] == "3"
    assert argv[argv.index("--threads") + 1] == "4"
    assert argv[argv.index("--timeout") + 1] == "90"
    assert argv[argv.index("--max-requests") + 1] == "700"
    assert argv[argv.index("--max-requests-jitter") + 1] == "50"


def test_entrypoint_rejects_non_numeric_configuration():
    result = subprocess.run(
        [str(ENTRYPOINT)],
        env={**os.environ, "GUNICORN_WORKERS": "two"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "GUNICORN_WORKERS" in result.stderr
