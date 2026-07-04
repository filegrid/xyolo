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

import yaml


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_task(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_task(path: Path, task: dict[str, Any]) -> None:
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def stringify_cli_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def build_xyolo_command(task: dict[str, Any], xyolo_path: Path) -> list[str]:
    command = [str(xyolo_path), "--mode", task["mode"]]
    if task["mode"] == "docker":
        command.append("--attach")
    command.extend(task["train_args"])
    return command


def build_docker_swanlab_command(task: dict[str, Any], project_root: Path) -> list[str]:
    docker_image = "ultralytics/ultralytics:latest"
    task_rel = f"web/tasks/{task['id']}.json"
    inner_parts = [
        "pip install -q swanlab",
        f"python web/swanlab_train.py --task {shlex.quote(task_rel)} --project-root /ultralytics",
    ]
    command = [
        "docker",
        "run",
        "--rm",
        "--runtime=nvidia",
        "--shm-size=4g",
        "--ulimit",
        "memlock=-1",
        "--ulimit",
        "stack=67108864",
        "-v",
        f"{project_root}:/ultralytics",
        "-w",
        "/ultralytics",
    ]
    api_key = task.get("swanlab", {}).get("api_key", "")
    if api_key:
        command.extend(["-e", f"SWANLAB_API_KEY={api_key}"])
    command.extend([docker_image, "bash", "-lc", " && ".join(inner_parts)])
    return command


def generate_dstack_spec(task: dict[str, Any], project_root: Path, xyolo_path: Path, venv_dir: Path) -> Path:
    dstack_path = project_root / "web" / "tasks" / f"{task['id']}.dstack.yml"
    spec: dict[str, Any] = {
        "type": "task",
        "name": task["dstack"]["task_name"],
        "working_dir": task["dstack"]["working_dir"],
        "commands": [
            "chmod +x ./xyolo",
            " ".join(shlex.quote(part) for part in build_xyolo_command(task, xyolo_path)),
        ],
    }
    if task["dstack"].get("project_name"):
        spec["project"] = task["dstack"]["project_name"]
    if task["dstack"].get("gpu"):
        spec["resources"] = {"gpu": task["dstack"]["gpu"]}
    env_map = {}
    if task.get("swanlab", {}).get("api_key"):
        env_map["SWANLAB_API_KEY"] = task["swanlab"]["api_key"]
    if env_map:
        spec["env"] = env_map
    dstack_path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    task["dstack_spec"] = dstack_path.relative_to(project_root).as_posix()
    if task["dstack"].get("auto_submit"):
        submit_command = [str(venv_dir / "bin" / "python"), "-m", "dstack", "apply", "-f", str(dstack_path), "-d", "-y"]
        log(f"Submitting dstack task: {' '.join(shlex.quote(part) for part in submit_command)}")
        result = subprocess.run(submit_command, cwd=project_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, end="", flush=True)
        task["dstack_submit_status"] = "submitted" if result.returncode == 0 else f"submit_failed({result.returncode})"
    else:
        task["dstack_submit_status"] = "spec_generated"
    return dstack_path


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
    venv_dir = Path(args.venv_dir).resolve()
    xyolo_path = project_root / "xyolo"

    task = load_task(task_path)
    task["status"] = "running"
    task["started_at"] = now_iso()
    save_task(task_path, task)

    try:
        if task.get("dstack", {}).get("enabled"):
            generate_dstack_spec(task, project_root, xyolo_path, venv_dir)
            save_task(task_path, task)

        env = os.environ.copy()
        swanlab = task.get("swanlab", {})
        if swanlab.get("api_key"):
            env["SWANLAB_API_KEY"] = swanlab["api_key"]

        if swanlab.get("enabled"):
            if task["mode"] == "docker":
                command = build_docker_swanlab_command(task, project_root)
            else:
                command = [
                    str(venv_dir / "bin" / "python"),
                    str(project_root / "web" / "swanlab_train.py"),
                    "--task",
                    str(task_path),
                    "--project-root",
                    str(project_root),
                ]
        else:
            command = build_xyolo_command(task, xyolo_path)

        return_code = run_command(command, project_root, env)
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
