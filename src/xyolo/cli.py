from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn


DEFAULT_DOCKER_IMAGE = "ultralytics/ultralytics:latest"
RESERVED_MODULES = {
    "dataset": "Dataset management",
    "model": "Model management",
    "eval": "Model evaluation",
    "deploy": "Model deployment",
}
MODULE_ORDER = ("dataset", "train", "model", "eval", "deploy")


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def run_privileged(command: list[str]) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        subprocess.run(command, check=True)
        return
    sudo = shutil.which("sudo")
    if not sudo:
        fail("Need root or sudo privileges to install system packages.")
    subprocess.run([sudo, *command], check=True)


def ensure_docker_ready() -> str:
    docker = shutil.which("docker")
    if not docker:
        apt_get = shutil.which("apt-get")
        if not apt_get:
            fail("Docker is not installed. Automatic installation only supports apt-based Linux.")
        print("Docker not found, installing docker.io")
        run_privileged([apt_get, "update"])
        run_privileged([apt_get, "install", "-y", "docker.io"])
        docker = shutil.which("docker")
    if not docker:
        fail("Docker installation completed but the docker command is unavailable.")

    systemctl = shutil.which("systemctl")
    if systemctl:
        active = subprocess.run([systemctl, "is-active", "--quiet", "docker"], check=False)
        if active.returncode != 0:
            print("Starting Docker service")
            run_privileged([systemctl, "enable", "--now", "docker"])
    return docker


def ensure_docker_image(docker: str, image: str) -> None:
    result = subprocess.run(
        [docker, "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        print(f"Docker image not found locally, pulling: {image}")
        subprocess.run([docker, "pull", image], check=True)


def resolve_input_path(project_root: Path, directory: Path, value: str) -> str:
    if "/" in value or value.startswith("."):
        return value
    candidate = directory / value
    if candidate.exists():
        try:
            return candidate.relative_to(project_root).as_posix()
        except ValueError:
            return candidate.as_posix()
    return value


def normalize_train_args(
    project_root: Path,
    models_dir: Path,
    datasets_dir: Path,
    train_args: list[str],
) -> list[str]:
    normalized: list[str] = []
    has_project = False
    for argument in train_args:
        key, value = argument.split("=", 1)
        if key == "model":
            value = resolve_input_path(project_root, models_dir, value)
        elif key == "data":
            value = resolve_input_path(project_root, datasets_dir, value)
        elif key == "project":
            has_project = True
        normalized.append(f"{key}={value}")
    if not has_project:
        normalized.append("project=runs")
    return normalized


def print_command(command: list[str]) -> None:
    print("Running:", shlex.join(command))


def run_local(train_args: list[str], dry_run: bool) -> None:
    yolo = shutil.which("yolo")
    if not yolo:
        if dry_run:
            print_command(["yolo", "train", *train_args])
            return
        fail(
            "The yolo executable is unavailable. Install XYolo with its dependencies "
            "in the active Python environment."
        )
    command = [yolo, "train", *train_args]
    print_command(command)
    if dry_run:
        return
    os.execv(yolo, command)


def run_docker(
    project_root: Path,
    train_args: list[str],
    image: str,
    container_name: str,
    detach: bool,
    dry_run: bool,
) -> None:
    docker = shutil.which("docker")
    if not dry_run:
        docker = ensure_docker_ready()
        ensure_docker_image(docker, image)
    if not docker:
        fail("Docker is not installed or not in PATH.")

    command = [docker, "run", "--rm", "--runtime=nvidia"]
    if detach:
        command.append("-d")
    command.extend(
        [
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
    )
    if container_name:
        command.extend(["--name", container_name])
    command.extend([image, "yolo", "train", *train_args])
    print_command(command)
    if dry_run:
        return
    os.execv(docker, command)


def add_train_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "train",
        help="launch YOLO training",
        description="Launch YOLO training locally or with Docker.",
    )
    parser.set_defaults(module="train")
    parser.add_argument("--mode", choices=("venv", "docker"), default="venv")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--datasets-dir", default="datasets")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--container-name", default="")
    attach_group = parser.add_mutually_exclusive_group()
    attach_group.add_argument("--attach", action="store_true")
    attach_group.add_argument("--detach", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("train_args", nargs="*", metavar="key=value")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xyolo",
        description="Manage XYolo datasets, training, models, evaluation, and deployment.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="module", required=True, metavar="MODULE")

    for name in MODULE_ORDER:
        if name == "train":
            add_train_parser(subparsers)
            continue
        description = RESERVED_MODULES[name]
        reserved = subparsers.add_parser(
            name,
            help=f"{description.lower()} (reserved)",
            description=f"{description} commands are reserved for a future release.",
        )
        reserved.set_defaults(module=name)

    web = subparsers.add_parser(
        "web",
        help="start the web UI",
        description="Start the XYolo web UI.",
    )
    web.set_defaults(module="web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8860)
    return parser


def run_train(args: argparse.Namespace, project_root: Path) -> None:
    invalid = [argument for argument in args.train_args if "=" not in argument]
    if invalid:
        fail(f"Unsupported training argument: {invalid[0]}. Use key=value arguments.")
    if not args.train_args:
        fail("No training arguments provided. Run 'xyolo train --help' for usage.")

    models_dir = (project_root / args.models_dir).resolve()
    datasets_dir = (project_root / args.datasets_dir).resolve()
    for path in (models_dir, datasets_dir, project_root / "runs"):
        path.mkdir(parents=True, exist_ok=True)
    normalized = normalize_train_args(
        project_root,
        models_dir,
        datasets_dir,
        args.train_args,
    )

    if args.mode == "docker":
        run_docker(
            project_root=project_root,
            train_args=normalized,
            image=args.docker_image,
            container_name=args.container_name,
            detach=not args.attach,
            dry_run=args.dry_run,
        )
        return
    run_local(normalized, args.dry_run)


def main() -> None:
    args = build_parser().parse_args()
    project_root = Path.cwd().resolve()
    if args.module == "web":
        from .web import serve

        serve(host=args.host, port=args.port, project_root=project_root)
        return
    if args.module == "train":
        run_train(args, project_root)
        return
    fail(f"The '{args.module}' module is reserved and is not implemented yet.")
