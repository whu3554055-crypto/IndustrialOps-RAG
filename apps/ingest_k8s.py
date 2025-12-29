"""K8s 上触发 Ingest CronJob 一次性 Job."""

from __future__ import annotations

import subprocess
import time
from typing import Any


def trigger_ingest_cronjob(
    *,
    namespace: str,
    cronjob_name: str,
) -> dict[str, Any]:
    job_name = f"ingest-manual-{int(time.time())}"
    cmd = [
        "kubectl",
        "create",
        "job",
        job_name,
        f"--from=cronjob/{cronjob_name}",
        "-n",
        namespace,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "kubectl failed")
    return {"ok": True, "job": job_name, "namespace": namespace, "cronjob": cronjob_name}
