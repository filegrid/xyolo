#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import yaml


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class AppConfig:
    def __init__(self, project_root: Path, venv_dir: Path) -> None:
        self.project_root = project_root
        self.venv_dir = venv_dir
        self.models_dir = project_root / "models"
        self.datasets_dir = project_root / "datasets"
        self.runs_dir = project_root / "runs"
        self.web_dir = project_root / "web"
        self.tasks_dir = self.web_dir / "tasks"
        self.configs_dir = self.web_dir / "configs"
        self.worker_script = self.web_dir / "task_worker.py"
        self.xyolo_script = project_root / "xyolo"
        self.compatibility = self._build_compatibility()
        for path in (
            self.models_dir,
            self.datasets_dir,
            self.runs_dir,
            self.web_dir,
            self.tasks_dir,
            self.configs_dir,
        ):
            ensure_dir(path)

    def _build_compatibility(self) -> dict[str, str]:
        version = sys.version_info
        details = {
            "python": f"{version.major}.{version.minor}.{version.micro}",
            "dstack": "ready" if (3, 10) <= version[:2] < (3, 14) else "python_unsupported",
            "swanlab": "ready" if version[:2] < (3, 14) else "python_warning",
        }
        return details


def list_files(base: Path, suffixes: tuple[str, ...]) -> list[str]:
    if not base.exists():
        return []
    items: list[str] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        items.append(path.relative_to(base).as_posix())
    return items


def load_tasks(config: AppConfig) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in sorted(config.tasks_dir.glob("*.json"), reverse=True):
        try:
            tasks.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)
    return tasks


def parse_scalar(value: str) -> Any:
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError:
        return value


def parse_key_value_text(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for token in shlex.split(line):
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            parsed[key.strip()] = parse_scalar(value.strip())
    return parsed


def load_config_values(config: AppConfig, filename: str) -> tuple[dict[str, Any], str | None]:
    if not filename:
        return {}, None
    path = (config.configs_dir / filename).resolve()
    if config.configs_dir.resolve() not in path.parents or not path.is_file():
        raise ValueError("invalid config file")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text) or {}
    else:
        data = parse_key_value_text(text)
    if not isinstance(data, dict):
        raise ValueError("config file must contain a key/value mapping")
    return data, path.relative_to(config.project_root).as_posix()


def save_config_text(config: AppConfig, name: str, text: str, fmt: str) -> str:
    safe_name = Path(name).name.strip()
    if not safe_name:
        raise ValueError("missing config file name")
    if fmt == "json" and not safe_name.endswith(".json"):
        safe_name += ".json"
    elif fmt == "yaml" and not safe_name.endswith((".yaml", ".yml")):
        safe_name += ".yaml"
    elif fmt == "kv" and not safe_name.endswith(".txt"):
        safe_name += ".txt"
    path = config.configs_dir / safe_name
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path.relative_to(config.project_root).as_posix()


def resolve_default_path(config: AppConfig, directory: Path, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return stripped
    if "/" in stripped or stripped.startswith("."):
        return stripped
    candidate = directory / stripped
    if candidate.exists():
        return candidate.relative_to(config.project_root).as_posix()
    return stripped


def stringify_cli_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def task_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def build_task(form: dict[str, str], config: AppConfig) -> dict[str, Any]:
    config_values, config_source = load_config_values(config, form.get("config_file", ""))
    save_source = None
    config_text = form.get("config_text", "").strip()
    if config_text:
        save_source = save_config_text(
            config,
            form.get("config_name", ""),
            config_text,
            form.get("config_format", "yaml"),
        )
        if form.get("config_format", "yaml") == "json":
            inline_values = json.loads(config_text)
        elif form.get("config_format", "yaml") == "yaml":
            inline_values = yaml.safe_load(config_text) or {}
        else:
            inline_values = parse_key_value_text(config_text)
        if not isinstance(inline_values, dict):
            raise ValueError("inline config must contain key/value pairs")
        config_values.update(inline_values)
        config_source = save_source

    model_input = (form.get("model_custom") or form.get("model_select") or "").strip()
    dataset_input = (form.get("dataset_custom") or form.get("dataset_select") or "").strip()
    if not model_input:
        raise ValueError("model is required")
    if not dataset_input:
        raise ValueError("dataset is required")

    params: dict[str, Any] = {}
    params.update(config_values)
    params["model"] = resolve_default_path(config, config.models_dir, model_input)
    params["data"] = resolve_default_path(config, config.datasets_dir, dataset_input)

    for key in ("epochs", "batch", "imgsz", "workers", "patience"):
        value = form.get(key, "").strip()
        if value:
            params[key] = parse_scalar(value)
    for key in ("device", "optimizer", "resume", "cache"):
        value = form.get(key, "").strip()
        if value:
            params[key] = parse_scalar(value)

    run_name = form.get("run_name", "").strip() or f"task-{datetime.now().strftime('%m%d-%H%M%S')}"
    params["name"] = run_name
    params["project"] = "runs"
    params.update(parse_key_value_text(form.get("extra_args", "")))
    params["model"] = resolve_default_path(config, config.models_dir, params["model"])
    params["data"] = resolve_default_path(config, config.datasets_dir, params["data"])

    train_args = [f"{key}={stringify_cli_value(value)}" for key, value in params.items() if value not in ("", None)]
    task_name = form.get("task_name", "").strip() or run_name
    mode = form.get("mode", "venv").strip() or "venv"
    if mode not in {"venv", "docker"}:
        raise ValueError("mode must be venv or docker")

    return {
        "id": task_id(),
        "task_name": task_name,
        "created_at": now_iso(),
        "status": "queued",
        "mode": mode,
        "train_kwargs": params,
        "train_args": train_args,
        "config_source": config_source,
        "notes": form.get("notes", "").strip(),
        "log_path": "",
        "worker_pid": None,
        "swanlab": {
            "enabled": form.get("swanlab_enabled") == "on",
            "project": form.get("swanlab_project", "").strip(),
            "workspace": form.get("swanlab_workspace", "").strip(),
            "experiment_name": form.get("swanlab_experiment", "").strip() or run_name,
            "description": form.get("swanlab_description", "").strip(),
            "api_key": form.get("swanlab_api_key", "").strip(),
        },
        "dstack": {
            "enabled": form.get("dstack_enabled") == "on",
            "auto_submit": form.get("dstack_auto_submit") == "on",
            "project_name": form.get("dstack_project", "").strip(),
            "task_name": form.get("dstack_task_name", "").strip() or task_name,
            "gpu": form.get("dstack_gpu", "").strip(),
            "working_dir": form.get("dstack_working_dir", "").strip() or ".",
        },
    }


def save_task(config: AppConfig, task: dict[str, Any]) -> Path:
    path = config.tasks_dir / f"{task['id']}.json"
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def start_task_worker(config: AppConfig, task_path: Path) -> None:
    log_path = config.tasks_dir / f"{task_path.stem}.log"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["log_path"] = log_path.relative_to(config.project_root).as_posix()
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log_handle = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(config.worker_script), "--task", str(task_path), "--project-root", str(config.project_root), "--venv-dir", str(config.venv_dir)],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=config.project_root,
        start_new_session=True,
    )
    log_handle.close()

    task["worker_pid"] = process.pid
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def html_page(config: AppConfig, message: str = "", error: str = "") -> str:
    models = list_files(config.models_dir, (".pt", ".onnx", ".engine", ".pth"))
    datasets = list_files(config.datasets_dir, (".yaml", ".yml", ".json"))
    configs = list_files(config.configs_dir, (".yaml", ".yml", ".json", ".txt"))
    tasks = load_tasks(config)

    def option_list(items: list[str], placeholder: str) -> str:
        options = [f'<option value="">{html.escape(placeholder)}</option>']
        options.extend(f'<option value="{html.escape(item)}">{html.escape(item)}</option>' for item in items)
        return "\n".join(options)

    rows: list[str] = []
    for task in tasks[:30]:
        log_link = ""
        if task.get("log_path"):
            log_link = f'<a href="/logs?id={html.escape(task["id"])}" target="_blank">log</a>'
        dstack_note = ""
        dstack_info = task.get("dstack", {})
        if dstack_info.get("enabled"):
            status = task.get("dstack_submit_status", "spec only")
            dstack_note = f" / dstack: {html.escape(status)}"
        swanlab_note = " / swanlab" if task.get("swanlab", {}).get("enabled") else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(task['id'])}</td>"
            f"<td>{html.escape(task['task_name'])}</td>"
            f"<td>{html.escape(task['mode'])}{swanlab_note}{dstack_note}</td>"
            f"<td>{html.escape(task.get('status', 'unknown'))}</td>"
            f"<td>{html.escape(task.get('created_at', ''))}</td>"
            f"<td>{log_link}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="6">No tasks yet.</td></tr>')

    compatibility_lines = [
        f"Python: {html.escape(config.compatibility['python'])}",
        "Dstack local submit: ready" if config.compatibility["dstack"] == "ready" else "Dstack local submit: current Python unsupported, spec generation still works",
        "SwanLab local callback: ready" if config.compatibility["swanlab"] == "ready" else "SwanLab local callback: current Python may fail in local venv, docker mode is recommended",
    ]

    notice = ""
    if message:
        notice = f'<p style="color:#1a7f37;"><strong>{html.escape(message)}</strong></p>'
    if error:
        notice += f'<p style="color:#cf222e;"><strong>{html.escape(error)}</strong></p>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>xyolo web</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; background: #f6f8fa; color: #24292f; }}
    h1, h2 {{ margin-bottom: 12px; }}
    form, .panel {{ background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }}
    label {{ display: block; font-weight: 600; margin-bottom: 4px; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #d0d7de; border-radius: 6px; }}
    textarea {{ min-height: 110px; }}
    button {{ padding: 10px 16px; border: 0; border-radius: 6px; background: #0969da; color: #fff; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border: 1px solid #d0d7de; padding: 8px; text-align: left; vertical-align: top; }}
    .hint {{ color: #57606a; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>xyolo web</h1>
  <div class="panel">
    <div>{"<br>".join(html.escape(line) for line in compatibility_lines)}</div>
    <div class="hint" style="margin-top:8px;">默认会从 models/ 和 datasets/ 读取候选项；也可以直接输入官方模型名或完整路径。</div>
  </div>
  {notice}
  <form method="post" action="/tasks">
    <h2>新建训练任务</h2>
    <div class="grid">
      <div><label>任务名</label><input name="task_name" placeholder="web-train-01"></div>
      <div><label>运行名(name)</label><input name="run_name" placeholder="exp-web-01"></div>
      <div><label>模式</label><select name="mode"><option value="venv">venv</option><option value="docker">docker</option></select></div>
      <div><label>模型</label><select name="model_select">{option_list(models, "选择 models/ 下模型")}</select></div>
      <div><label>自定义模型</label><input name="model_custom" placeholder="yolov8s.pt 或 ./other/model.pt"></div>
      <div><label>数据集</label><select name="dataset_select">{option_list(datasets, "选择 datasets/ 下配置")}</select></div>
      <div><label>自定义数据集</label><input name="dataset_custom" placeholder="my_data.yaml 或 ./other/data.yaml"></div>
      <div><label>epochs</label><input name="epochs" value="200"></div>
      <div><label>batch</label><input name="batch" value="8"></div>
      <div><label>imgsz</label><input name="imgsz" value="640"></div>
      <div><label>device</label><input name="device" placeholder="0 或 cpu"></div>
      <div><label>workers</label><input name="workers" placeholder="8"></div>
    </div>
    <div class="grid" style="margin-top:12px;">
      <div><label>optimizer</label><input name="optimizer" placeholder="auto/SGD/AdamW"></div>
      <div><label>resume</label><input name="resume" placeholder="true 或 checkpoint.pt"></div>
      <div><label>cache</label><input name="cache" placeholder="true/ram/disk"></div>
      <div><label>patience</label><input name="patience" placeholder="50"></div>
      <div><label>已保存参数文件</label><select name="config_file">{option_list(configs, "不使用参数文件")}</select></div>
    </div>
    <p class="hint">额外参数支持 key=value，按空格或换行分隔，例如：lr0=0.01 hsv_h=0.015</p>
    <div><label>额外参数</label><textarea name="extra_args" placeholder="lr0=0.01&#10;close_mosaic=10"></textarea></div>
    <div class="grid" style="margin-top:12px;">
      <div><label>保存参数文件名</label><input name="config_name" placeholder="train-defaults.yaml"></div>
      <div><label>参数文件格式</label><select name="config_format"><option value="yaml">yaml</option><option value="json">json</option><option value="kv">key=value</option></select></div>
    </div>
    <div><label>参数文件内容（可选）</label><textarea name="config_text" placeholder="epochs: 300&#10;batch: 4&#10;lr0: 0.005"></textarea></div>
    <div class="grid" style="margin-top:12px;">
      <div>
        <label><input type="checkbox" name="swanlab_enabled"> 启用 SwanLab</label>
        <div class="hint">venv 模式使用 Ultralytics 回调；docker 模式会在容器内安装 swanlab 后运行。</div>
      </div>
      <div><label>SwanLab project</label><input name="swanlab_project" placeholder="yolo-train"></div>
      <div><label>SwanLab workspace</label><input name="swanlab_workspace" placeholder="team-or-user"></div>
      <div><label>SwanLab experiment</label><input name="swanlab_experiment" placeholder="exp-001"></div>
      <div><label>SwanLab API key</label><input name="swanlab_api_key" placeholder="可选"></div>
      <div><label>SwanLab description</label><input name="swanlab_description" placeholder="experiment notes"></div>
    </div>
    <div class="grid" style="margin-top:12px;">
      <div>
        <label><input type="checkbox" name="dstack_enabled"> 生成 dstack 任务</label>
        <div class="hint">会在 web/tasks/ 下生成 .dstack.yml。</div>
      </div>
      <div><label><input type="checkbox" name="dstack_auto_submit"> 自动提交 dstack</label></div>
      <div><label>dstack project</label><input name="dstack_project" placeholder="my-project"></div>
      <div><label>dstack task name</label><input name="dstack_task_name" placeholder="remote-yolo-train"></div>
      <div><label>dstack GPU</label><input name="dstack_gpu" placeholder="24GB / A100 / H100"></div>
      <div><label>dstack working dir</label><input name="dstack_working_dir" value="."></div>
    </div>
    <div style="margin-top:12px;"><label>备注</label><textarea name="notes" placeholder="这次实验的说明"></textarea></div>
    <div style="margin-top:16px;"><button type="submit">创建并启动任务</button></div>
  </form>

  <h2>最近任务</h2>
  <table>
    <thead><tr><th>ID</th><th>任务</th><th>模式</th><th>状态</th><th>创建时间</th><th>日志</th></tr></thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    config: AppConfig

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/logs":
            task_id_value = parse_qs(parsed.query).get("id", [""])[0]
            self.serve_log(task_id_value)
            return
        message = parse_qs(parsed.query).get("message", [""])[0]
        error = parse_qs(parsed.query).get("error", [""])[0]
        body = html_page(self.config, message=message, error=error).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/tasks":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        form = {key: values[-1] for key, values in parse_qs(payload, keep_blank_values=True).items()}
        try:
            task = build_task(form, self.config)
            path = save_task(self.config, task)
            start_task_worker(self.config, path)
            self.redirect("/?message=task%20created")
        except Exception as exc:  # noqa: BLE001
            self.redirect(f"/?error={quote(str(exc))}")

    def serve_log(self, task_id_value: str) -> None:
        path = self.config.tasks_dir / f"{task_id_value}.log"
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "log not found")
            return
        body = path.read_text(encoding="utf-8", errors="replace").encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8860)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--venv-dir", required=True)
    args = parser.parse_args()

    config = AppConfig(Path(args.project_root).resolve(), Path(args.venv_dir).resolve())
    Handler.config = config
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"xyolo web listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
