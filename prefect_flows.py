from __future__ import annotations

import subprocess
from pathlib import Path

from prefect import flow, task

ROOT = Path(__file__).resolve().parent


@task(name="kroger-extract-load", log_prints=True)
def task_extract_load() -> None:
    """Kroger API -> staging Parquet -> DuckDB raw (calls main.main)."""
    import main as kroger_main

    kroger_main.main()


@task(name="dbt-run", log_prints=True)
def task_dbt_run() -> None:
    """Run dbt against the local DuckDB profile."""
    subprocess.run(
        [
            "uv",
            "run",
            "dbt",
            "run",
            "--project-dir",
            str(ROOT / "kroger_analysis"),
            "--profiles-dir",
            str(ROOT / "kroger_analysis"),
        ],
        cwd=ROOT,
        check=True,
    )


@flow(name="kroger-daily-pipeline", log_prints=True)
def kroger_daily_flow() -> None:
    """
    Extract and load, then optionally run dbt.
    """
    task_extract_load()
    task_dbt_run()


@flow(name="kroger-extract-load-only", log_prints=True)
def kroger_extract_load_only_flow() -> None:
    """Extract and load only; does not run dbt."""
    task_extract_load()


if __name__ == "__main__":
    kroger_daily_flow()
