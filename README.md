# XYolo

XYolo is an installable Python project for local YOLO training, Docker training, and web-based training workflows. It can be distributed as a wheel.

After installation, the Python environment provides the `xyolo` command:

```bash
xyolo --help
xyolo --version
```

For Chinese documentation, see [README-CN.md](./README-CN.md).

## Installation

Install from source:

```bash
python3 -m pip install .
```

Install in editable mode:

```bash
python3 -m pip install -e .
```

Install a built wheel:

```bash
python3 -m pip install dist/xyolo-0.1.0-py3-none-any.whl
```

`ultralytics` and `PyYAML` are installed as Python dependencies. XYolo no longer creates or manages a separate `venv/` inside the working directory.

## Building the wheel

Build the frontend assets first:

```bash
cd web/ui
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ../..
```

Then build the Python distributions:

```bash
python3 -m pip install build
python3 -m build
```

Artifacts are written to `dist/`. The frontend build writes to `src/xyolo/static/`; those files are included in the wheel, so Node.js and pnpm are not required when running the installed web service.

## Working directory

XYolo treats the current directory as the project workspace and automatically uses:

```text
models/          # model weights
datasets/        # dataset configs and related files
runs/            # training output
web/configs/     # YAML configs saved by the web UI
web/drafts/      # web drafts
web/templates/   # web templates
web/tasks/       # web tasks and logs
```

The installed package contains only application code and static web assets, not user training data.

## Local training

```bash
xyolo train model=yolov8s.pt data=dataset.yaml epochs=200 batch=8
```

`--mode venv` remains as a compatibility name and is still the default. It now means using the Python environment where XYolo is installed:

```bash
xyolo train --mode venv model=best.pt data=my_dataset.yaml epochs=100
```

Files found under `models/` and `datasets/` are resolved automatically, and `project=runs` is added unless explicitly supplied.

Print the resulting command without launching training:

```bash
xyolo train --dry-run model=yolov8s.pt data=dataset.yaml epochs=1
```

## Docker training

```bash
xyolo train --mode docker model=yolov8s.pt data=dataset.yaml epochs=200
```

Docker mode mounts the current workspace at `/ultralytics`. It uses `ultralytics/ultralytics:latest` and runs detached by default:

```bash
xyolo train --mode docker --attach model=yolov8s.pt data=dataset.yaml
xyolo train --mode docker --container-name train-01 model=yolov8s.pt data=dataset.yaml
```

## Command modules

The CLI modules follow the web UI sections:

```text
xyolo dataset    # reserved
xyolo train      # implemented
xyolo model      # reserved
xyolo eval       # reserved
xyolo deploy     # reserved
xyolo web        # implemented
```

Reserved modules are discoverable through `xyolo --help`. Invoking one currently returns a clear not-implemented message, and future commands can be added under the matching module.

## Web service

```bash
xyolo web
xyolo web --host 0.0.0.0 --port 8860
```

The server reads the bundled frontend assets from the installed wheel. Task metadata and training output remain in the current workspace.

## Frontend development

```bash
cd web/ui
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

The Vite development server proxies `/api` and `/logs` to `http://127.0.0.1:8860`.
