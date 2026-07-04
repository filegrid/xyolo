#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_task(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_task(path: Path, task: dict[str, Any]) -> None:
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def build_xyolo_command(task: dict[str, Any], xyolo_path: Path) -> list[str]:
    command = [str(xyolo_path), "--mode", task["mode"]]
    if task["mode"] == "docker":
        command.append("--attach")
    command.extend(task["train_args"])
    return command


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    log(f"Running: {' '.join(shlex.quote(part) for part in command)}")
    process = subprocess.Popen(command, cwd=cwd, env=env)
    return process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--venv-dir", required=True)
    args = parser.parse_args()

    task_path = Path(args.task).resolve()
    project_root = Path(args.project_root).resolve()
    xyolo_path = project_root / "xyolo"

    task = load_task(task_path)
    task["status"] = "running"
    task["started_at"] = now_iso()
    save_task(task_path, task)

    try:
        command = build_xyolo_command(task, xyolo_path)
        return_code = run_command(command, project_root, os.environ.copy())
        task["status"] = "completed" if return_code == 0 else "failed"
        task["return_code"] = return_code
    except Exception as exc:  # noqa: BLE001
        log(f"Task failed with exception: {exc}")
        task["status"] = "failed"
        task["return_code"] = -1
        task["error"] = str(exc)
    finally:
        task["finished_at"] = now_iso()
        save_task(task_path, task)


if __name__ == "__main__":
    main()
