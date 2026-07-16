#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def load_task(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    task_path = Path(args.task).resolve()
    project_root = Path(args.project_root).resolve()
    task = load_task(task_path)

    from ultralytics import YOLO
    from swanlab.integration.ultralytics import add_swanlab_callback

    train_kwargs = dict(task["train_kwargs"])
    model_path = train_kwargs.pop("model")

    swanlab_kwargs = {
        "project": task["swanlab"].get("project") or None,
        "workspace": task["swanlab"].get("workspace") or None,
        "experiment_name": task["swanlab"].get("experiment_name") or None,
        "description": task["swanlab"].get("description") or None,
        "logdir": str(project_root / "runs" / "swanlab"),
    }
    if task["swanlab"].get("api_key"):
        os.environ["SWANLAB_API_KEY"] = task["swanlab"]["api_key"]

    model = YOLO(model_path)
    add_swanlab_callback(model, **swanlab_kwargs)
    model.train(**train_kwargs)


if __name__ == "__main__":
    main()
