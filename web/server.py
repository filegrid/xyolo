#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, urlparse

import yaml


TOOL_SPECS = {
    "dstack": {
        "display_name": "dstack",
        "url": "http://127.0.0.1:3000",
        "container_name": "xyolo-dstack",
        "docker_command": [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            "xyolo-dstack",
            "-p",
            "127.0.0.1:3000:3000",
            "dstackai/dstack:latest",
            "server",
            "--host",
            "0.0.0.0",
            "-p",
            "3000",
        ],
        "help_message": "Requires a working Docker daemon with current-user access.",
    },
    "swanlab": {
        "display_name": "SwanLab",
        "url": "http://127.0.0.1:5092",
        "container_name": "xyolo-swanlab",
        "docker_command": [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            "xyolo-swanlab",
            "-p",
            "127.0.0.1:5092:5092",
            "-v",
            "{RUNS_DIR}:/app/runs",
            "python:3.12-slim",
            "bash",
            "-lc",
            "pip install -q 'swanlab[dashboard]' && mkdir -p /app/runs/swanlab && swanlab watch /app/runs/swanlab -h 0.0.0.0 -p 5092",
        ],
        "help_message": "Requires a working Docker daemon with current-user access.",
    },
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


DOCKER_BASE_COMMAND = ["docker"]
DEFAULT_TRAIN_DOCKER_IMAGE = "ultralytics/ultralytics:latest"
PRIMARY_PACKAGE_NAMES = (
    "ultralytics",
    "torch",
    "torchvision",
    "torchaudio",
    "opencv-python",
    "opencv-python-headless",
    "numpy",
    "pandas",
    "matplotlib",
    "PyYAML",
    "dstack",
    "swanlab",
)


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
        self.drafts_dir = self.web_dir / "drafts"
        self.templates_dir = self.web_dir / "templates"
        self.ui_dist_dir = self.web_dir / "ui" / "dist"
        self.worker_script = self.web_dir / "task_worker.py"
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        for path in (
            self.models_dir,
            self.datasets_dir,
            self.runs_dir,
            self.web_dir,
            self.tasks_dir,
            self.configs_dir,
            self.drafts_dir,
            self.templates_dir,
        ):
            ensure_dir(path)

    def environment(self) -> list[dict[str, str]]:
        return [
            {"label": "Project root", "value": self.project_root.as_posix()},
            {"label": "Python", "value": self.python_version},
            {"label": "Models dir", "value": self.models_dir.as_posix()},
            {"label": "Datasets dir", "value": self.datasets_dir.as_posix()},
            {"label": "Runs dir", "value": self.runs_dir.as_posix()},
        ]


def format_tree_line(name: str, prefix: str, is_last: bool) -> str:
    branch = "└── " if is_last else "├── "
    return f"{prefix}{branch}{name}"


def project_tree(config: AppConfig) -> str:
    root_name = config.project_root.name
    lines = [f"{root_name}/  # XYolo project root"]
    top_level = [
        ("datasets/  # dataset YAML files and related assets", []),
        ("models/  # model weights and checkpoints", []),
        ("runs/  # training outputs", []),
        ("venv/  # local Python environment", []),
        (
            "web/  # web backend and frontend",
            [
                ("configs/  # saved YAML parameter files", []),
                ("drafts/  # saved drafts", []),
                ("tasks/  # task metadata and logs", []),
                ("templates/  # reusable templates", []),
                (
                    "ui/  # Vite React frontend",
                    [
                        ("src/  # frontend source files", []),
                        ("dist/  # built static assets", []),
                    ],
                ),
            ],
        ),
    ]

    def append_nodes(nodes: list[tuple[str, list[Any]]], prefix: str) -> None:
        for index, (name, children) in enumerate(nodes):
            is_last = index == len(nodes) - 1
            lines.append(format_tree_line(name, prefix, is_last))
            if children:
                child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
                append_nodes(children, child_prefix)

    append_nodes(top_level, "")
    return "\n".join(lines)


def installed_packages(config: AppConfig) -> list[dict[str, str]]:
    python_executable = config.venv_dir / "bin" / "python"
    executable = python_executable if python_executable.exists() else Path(sys.executable)
    try:
        result = subprocess.run(
            [str(executable), "-m", "pip", "list", "--format=json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout or "[]")
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return []
    packages = [
        {
            "name": str(item.get("name", "")),
            "version": str(item.get("version", "")),
        }
        for item in payload
        if item.get("name")
    ]
    primary = [item for item in packages if item["name"] in PRIMARY_PACKAGE_NAMES]
    primary.sort(key=lambda item: PRIMARY_PACKAGE_NAMES.index(item["name"]))
    return primary


def docker_image_status(image_name: str) -> str:
    accessible, reason = docker_accessible()
    if not accessible:
        return reason or "Docker unavailable"
    result = subprocess.run(
        [*current_docker_base(), "image", "inspect", image_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return "local" if result.returncode == 0 else "missing"


def docker_images_overview() -> list[dict[str, str]]:
    images = [
        {"purpose": "training", "image": DEFAULT_TRAIN_DOCKER_IMAGE},
        {"purpose": "dstack", "image": "dstackai/dstack:latest"},
        {"purpose": "swanlab", "image": "python:3.12-slim"},
    ]
    return [
        {
            "purpose": item["purpose"],
            "image": item["image"],
            "status": docker_image_status(item["image"]),
        }
        for item in images
    ]


def environment_details(config: AppConfig) -> dict[str, Any]:
    return {
        "python_version": config.python_version,
        "project_tree": project_tree(config),
        "docker_images": docker_images_overview(),
        "packages": installed_packages(config),
    }


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


def make_generated_name(prefix: str = "xyolo") -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if prefix == "xyolo":
        return f"{prefix}-{timestamp}"
    return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:4]}"


def load_record_list(base: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json"), reverse=True):
        try:
            records.append(read_json(path))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
    return records


def summarize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "name": record["name"],
        "created_at": record.get("created_at", ""),
        "updated_at": record.get("updated_at", record.get("created_at", "")),
        "mode": record.get("form", {}).get("mode", "venv"),
        "model": record.get("form", {}).get("model", ""),
        "data": record.get("form", {}).get("data", ""),
        "status": record.get("status", ""),
    }


def load_config_values(config: AppConfig, filename: str) -> tuple[dict[str, Any], str | None]:
    if not filename:
        return {}, None
    path = (config.configs_dir / filename).resolve()
    if config.configs_dir.resolve() not in path.parents or not path.is_file():
        raise ValueError("invalid config file")
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("only yaml config files are supported")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config file must contain a key/value mapping")
    return data, path.relative_to(config.project_root).as_posix()


def save_yaml_config(config: AppConfig, name: str, text: str) -> str:
    path = config.configs_dir / f"{name}.yaml"
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


def normalize_form(raw: dict[str, Any]) -> dict[str, str]:
    fields = {
        "name": "",
        "mode": "venv",
        "model": "",
        "data": "",
        "epochs": "200",
        "batch": "8",
        "imgsz": "640",
        "device": "",
        "workers": "",
        "optimizer": "",
        "resume": "",
        "cache": "",
        "patience": "",
        "config_file": "",
        "config_text": "",
        "extra_args": "",
        "notes": "",
    }
    normalized = {key: str(raw.get(key, default) or default) for key, default in fields.items()}
    mode = normalized["mode"].strip() or "venv"
    if mode not in {"venv", "docker"}:
        raise ValueError("mode must be venv or docker")
    normalized["mode"] = mode
    normalized["name"] = normalized["name"].strip() or make_generated_name()
    if not normalized["model"].strip():
        raise ValueError("model is required")
    if not normalized["data"].strip():
        raise ValueError("dataset is required")
    return normalized


def create_launch_task(config: AppConfig, form: dict[str, str]) -> dict[str, Any]:
    name = form["name"].strip() or make_generated_name()
    config_values, config_source = load_config_values(config, form.get("config_file", "").strip())
    config_text = form.get("config_text", "").strip()
    if config_text:
        inline_values = yaml.safe_load(config_text) or {}
        if not isinstance(inline_values, dict):
            raise ValueError("yaml config must contain a key/value mapping")
        config_values.update(inline_values)
        config_source = save_yaml_config(config, name, config_text)

    params: dict[str, Any] = {}
    params.update(config_values)
    params["model"] = resolve_default_path(config, config.models_dir, form["model"].strip())
    params["data"] = resolve_default_path(config, config.datasets_dir, form["data"].strip())

    for key in ("epochs", "batch", "imgsz", "workers", "patience"):
        value = form.get(key, "").strip()
        if value:
            params[key] = parse_scalar(value)
    for key in ("device", "optimizer", "resume", "cache"):
        value = form.get(key, "").strip()
        if value:
            params[key] = parse_scalar(value)

    params["name"] = name
    params["project"] = "runs"
    params.update(parse_key_value_text(form.get("extra_args", "")))
    params["model"] = resolve_default_path(config, config.models_dir, params["model"])
    params["data"] = resolve_default_path(config, config.datasets_dir, params["data"])

    return {
        "id": make_generated_name("task"),
        "task_name": name,
        "name": name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "queued",
        "mode": form["mode"],
        "train_kwargs": params,
        "train_args": [f"{key}={stringify_cli_value(value)}" for key, value in params.items() if value not in ("", None)],
        "config_source": config_source,
        "notes": form.get("notes", "").strip(),
        "log_path": "",
        "worker_pid": None,
    }


def save_record(base: Path, payload: dict[str, Any]) -> Path:
    path = base / f"{payload['id']}.json"
    write_json(path, payload)
    return path


def save_form_record(base: Path, form: dict[str, str]) -> dict[str, Any]:
    name = form["name"].strip() or make_generated_name()
    record = {
        "id": make_generated_name(base.name[:-1] if base.name.endswith("s") else base.name),
        "name": name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": base.name[:-1] if base.name.endswith("s") else base.name,
        "form": form,
    }
    save_record(base, record)
    return record


def start_task_worker(config: AppConfig, task_path: Path) -> None:
    log_path = config.tasks_dir / f"{task_path.stem}.log"
    task = read_json(task_path)
    task["log_path"] = log_path.relative_to(config.project_root).as_posix()
    write_json(task_path, task)

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
    task["updated_at"] = now_iso()
    write_json(task_path, task)


def docker_accessible() -> tuple[bool, str]:
    global DOCKER_BASE_COMMAND
    candidates = (
        ["docker", "ps"],
        ["sudo", "-n", "docker", "ps"],
    )
    for command in candidates:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            DOCKER_BASE_COMMAND = command[:-1]
            return True, ""

    try:
        result = subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        return False, "Docker is not installed."
    message = result.stderr.strip() or "Docker is unavailable."
    return False, message

def current_docker_base() -> list[str]:
    return DOCKER_BASE_COMMAND


def http_ready(url: str) -> bool:
    try:
        with urllib_request.urlopen(url, timeout=3) as response:
            return response.status < 500
    except urllib_error.HTTPError as exc:
        return exc.code < 500
    except (urllib_error.URLError, TimeoutError, ConnectionResetError, OSError):
        return False


def container_running(tool_name: str) -> bool:
    spec = TOOL_SPECS[tool_name]
    inspect = subprocess.run(
        [*current_docker_base(), "inspect", "-f", "{{.State.Running}}", spec["container_name"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return inspect.returncode == 0 and inspect.stdout.strip() == "true"


def container_logs(tool_name: str) -> str:
    spec = TOOL_SPECS[tool_name]
    result = subprocess.run(
        [*current_docker_base(), "logs", "--tail", "80", spec["container_name"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout.strip()


def wait_for_tool_ready(tool_name: str, timeout_seconds: int = 60) -> tuple[bool, str]:
    spec = TOOL_SPECS[tool_name]
    deadline = time.time() + timeout_seconds
    last_logs = ""
    while time.time() < deadline:
        if http_ready(spec["url"]):
            return True, ""
        if not container_running(tool_name):
            last_logs = container_logs(tool_name)
            break
        time.sleep(1)
    if http_ready(spec["url"]):
        return True, ""
    return False, last_logs or f"{spec['display_name']} did not become ready in time."


def ensure_tool_running(config: AppConfig, tool_name: str) -> tuple[bool, str, str]:
    spec = TOOL_SPECS[tool_name]
    accessible, reason = docker_accessible()
    if not accessible:
        return False, "", reason

    if container_running(tool_name):
        ready, details = wait_for_tool_ready(tool_name, timeout_seconds=15)
        if ready:
            return True, spec["url"], ""
        return False, "", details

    command = [part.replace("{RUNS_DIR}", config.runs_dir.as_posix()) for part in spec["docker_command"]]
    if command and command[0] == "docker":
        command = [*current_docker_base(), *command[1:]]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or spec["help_message"]
        return False, "", message
    ready, details = wait_for_tool_ready(tool_name)
    if ready:
        return True, spec["url"], ""
    return False, "", details


def tool_status(config: AppConfig, tool_name: str) -> dict[str, Any]:
    accessible, reason = docker_accessible()
    return {
        "name": tool_name,
        "display_name": TOOL_SPECS[tool_name]["display_name"],
        "available": accessible,
        "url": TOOL_SPECS[tool_name]["url"],
        "reason": "" if accessible else reason,
    }


def bootstrap_payload(config: AppConfig) -> dict[str, Any]:
    drafts = load_record_list(config.drafts_dir)
    templates = load_record_list(config.templates_dir)
    tasks = load_record_list(config.tasks_dir)
    return {
        "models": list_files(config.models_dir, (".pt", ".onnx", ".engine", ".pth")),
        "datasets": list_files(config.datasets_dir, (".yaml", ".yml", ".json")),
        "configs": list_files(config.configs_dir, (".yaml", ".yml")),
        "environment": config.environment(),
        "tools": [tool_status(config, name) for name in TOOL_SPECS],
        "drafts": [summarize_record(item) for item in drafts],
        "templates": [summarize_record(item) for item in templates],
        "tasks": [
            {
                "id": item["id"],
                "name": item.get("task_name", item.get("name", "")),
                "mode": item.get("mode", ""),
                "status": item.get("status", ""),
                "created_at": item.get("created_at", ""),
                "log_path": item.get("log_path", ""),
            }
            for item in tasks
        ],
    }


class Handler(BaseHTTPRequestHandler):
    config: AppConfig

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self.send_json(bootstrap_payload(self.config))
            return
        if parsed.path == "/api/environment":
            self.send_json(environment_details(self.config))
            return
        if parsed.path.startswith("/api/records/"):
            parts = parsed.path.split("/")
            if len(parts) != 5:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            _, _, _, kind, record_id = parts
            self.serve_record(kind, record_id)
            return
        if parsed.path == "/logs":
            task_id_value = parse_qs(parsed.query).get("id", [""])[0]
            self.serve_log(task_id_value)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/actions":
            payload = self.read_json_body()
            action = str(payload.get("action", ""))
            raw_form = payload.get("form", {})
            if not isinstance(raw_form, dict):
                self.send_json({"ok": False, "message": "invalid form payload"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                form = normalize_form(raw_form)
                if action == "launch":
                    task = create_launch_task(self.config, form)
                    path = save_record(self.config.tasks_dir, task)
                    start_task_worker(self.config, path)
                    self.send_json({"ok": True, "message": "Task launched.", "item": {"id": task["id"], "name": task["task_name"]}})
                    return
                if action == "save_draft":
                    record = save_form_record(self.config.drafts_dir, form)
                    self.send_json({"ok": True, "message": "Draft saved.", "item": summarize_record(record)})
                    return
                if action == "save_template":
                    record = save_form_record(self.config.templates_dir, form)
                    self.send_json({"ok": True, "message": "Template saved.", "item": summarize_record(record)})
                    return
                self.send_json({"ok": False, "message": "unsupported action"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"ok": False, "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path.startswith("/api/tools/") and parsed.path.endswith("/open"):
            parts = parsed.path.split("/")
            if len(parts) != 5:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            _, _, _, tool_name, _ = parts
            if tool_name not in TOOL_SPECS:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            ok, url, reason = ensure_tool_running(self.config, tool_name)
            if ok:
                self.send_json({"ok": True, "url": url, "message": f"{TOOL_SPECS[tool_name]['display_name']} is ready."})
            else:
                self.send_json({"ok": False, "message": reason}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def serve_record(self, kind: str, record_id: str) -> None:
        mapping = {
            "drafts": self.config.drafts_dir,
            "templates": self.config.templates_dir,
        }
        if kind not in mapping:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = mapping[kind] / f"{record_id}.json"
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        record = read_json(path)
        self.send_json({"ok": True, "item": record})

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

    def serve_static(self, request_path: str) -> None:
        dist = self.config.ui_dist_dir
        target = (dist / request_path.lstrip("/")).resolve()
        if target.is_file() and dist.resolve() in target.parents:
            self.send_file(target)
            return
        self.send_file(dist / "index.html")

    def send_file(self, path: Path) -> None:
        body = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime_type or 'application/octet-stream'}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

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
    print(f"XYolo web listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
