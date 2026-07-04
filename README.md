# XYolo

`xyolo` is a YOLO training launcher with support for:

1. **Local training with venv**
2. **Docker-based training**
3. **A web UI for creating and launching training tasks**

The default training mode is **venv**.

For the Chinese documentation, see [README-CN.md](./README-CN.md).

## Directory layout

The script automatically manages these directories:

- `venv/`: local Python virtual environment
- `models/`: local model weights
- `datasets/`: dataset configs
- `runs/`: training outputs
- `web/configs/`: parameter files saved by the web UI
- `web/tasks/`: generated tasks and logs

All of them are created automatically, so you do **not** need to create them by hand.

If your model and dataset files are placed in the default directories, you can use file names directly:

```bash
./xyolo model=best.pt data=my_dataset.yaml epochs=200 batch=8
```

The script resolves them as:

```bash
model=models/best.pt
data=datasets/my_dataset.yaml
project=runs
```

If you pass a full path, a relative path, or an official model name such as `yolov8s.pt`, `xyolo` leaves it unchanged.

## Automatic installation

### venv mode

At startup, `xyolo` checks:

- whether `venv/` exists
- `ultralytics`
- `dstack`
- `swanlab`

If anything is missing, it creates the virtual environment and installs the required packages automatically.

### docker mode

At startup, `xyolo` checks:

- whether `docker` is installed
- whether the Docker service is running
- whether `ultralytics/ultralytics:latest` exists locally

If needed, it attempts to run:

```bash
apt-get install docker.io
docker pull ultralytics/ultralytics:latest
```

The automatic Docker installation path currently targets **apt-based Linux distributions** such as Ubuntu and Debian.

## Manual venv setup

If you want to prepare the environment manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install ultralytics dstack swanlab
```

Verify the installation:

```bash
./venv/bin/yolo --help
./venv/bin/pip show dstack swanlab
```

## Training usage

```bash
./xyolo [--mode venv|docker] [options] key=value [key=value ...]
```

The arguments are forwarded to:

```bash
yolo train ...
```

For example:

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

Equivalent command:

```bash
yolo train model=yolov8s.pt data=xxx.yaml epochs=200 batch=8 project=runs
```

## venv mode

This is the default mode and it runs:

```bash
./venv/bin/yolo train ...
```

Examples:

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
./xyolo --mode venv model=best.pt data=my_data.yaml imgsz=640 device=0
```

## docker mode

The default image is:

```bash
ultralytics/ultralytics:latest
```

The current project directory is mounted into the container as:

```bash
/ultralytics
```

Examples:

```bash
./xyolo --mode docker model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
sudo ./xyolo --mode docker model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

Default Docker runtime options:

- `--runtime=nvidia`
- `--shm-size=4g`
- `--ulimit memlock=-1`
- `--ulimit stack=67108864`

Docker runs in the background by default. To keep it in the foreground:

```bash
./xyolo --mode docker --attach model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

## Web service

Start it with:

```bash
./xyolo web
```

Custom bind address:

```bash
./xyolo web --host 0.0.0.0 --port 8860
```

The web frontend uses:

- **Vite**
- **React**
- **pnpm**
- **shadcn/ui**

`xyolo web` installs the frontend dependencies if needed and rebuilds the frontend before starting the backend service.

The web UI is a **single training page**.

Top-right controls:

- **Environment** entry
- **dstack** entry
- **SwanLab** entry
- **language** switch between Chinese and English
- **theme** switch with `system`, `light`, and `dark`

Language and theme selections are stored in cookies.

The theme switch really follows the system preference when `system` is selected.

Inside the training page, the UI is split into:

1. **New**
2. **List**

The **New** section contains:

- **Basic settings**
- **Advanced settings** (collapsed by default)

The **List** section shows:

- launched tasks
- saved templates
- saved drafts

The model and dataset fields each use a **single input** with local suggestions from `models/` and `datasets/`, while still allowing official model names or custom paths.

Only **one task name** is used. It is generated automatically for each action and reused for the launched training run and related metadata.

Generated task artifacts:

- `web/tasks/<task-id>.json`: task definition
- `web/tasks/<task-id>.log`: training log
- `web/drafts/<draft-id>.json`: saved draft
- `web/templates/<template-id>.json`: saved template

### Web parameter files

The page supports:

1. **Direct parameter editing**
2. **Optional YAML parameter files**

Only **YAML** is supported for saved parameter files.

YAML example:

```yaml
epochs: 300
batch: 4
lr0: 0.005
close_mosaic: 10
```

## SwanLab usage

The page keeps a **SwanLab entry** in the top-right area.

Clicking it asks the backend to try launching SwanLab through Docker and then opens the service URL if successful.

### SwanLab compatibility

The current local Python environment uses **Python 3.14**, so the local Python package path is not used for the entry anymore.

The current implementation uses the Docker path instead. If direct Docker access fails, the backend also retries with `sudo -n docker`. If startup still fails, the UI surfaces that error directly.

## dstack usage

The page keeps a **dstack entry** in the top-right area.

Clicking it asks the backend to try launching dstack through Docker and then opens the service URL if successful.

### dstack compatibility

The installed Python package still does **not** support Python 3.14, so the entry uses the Docker path instead of the local Python package.

If direct Docker access fails, the backend also retries with `sudo -n docker`. If startup still fails, the UI shows the exact failure reason.

## Options

- `--mode venv|docker`: training mode, default `venv`
- `--venv-dir PATH`: virtual environment directory
- `--models-dir PATH`: model directory
- `--datasets-dir PATH`: dataset directory
- `--docker-image IMAGE`: Docker image
- `--container-name NAME`: container name
- `--attach`: run Docker in the foreground
- `--detach`: run Docker in the background
- `--dry-run`: print the command without executing it

Web startup:

- `./xyolo web --host HOST --port PORT`

## Examples

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
./xyolo --dry-run model=best.pt data=my_dataset.yaml epochs=100 batch=16
./xyolo --mode docker --container-name yolo_train_01 model=yolov8m.pt data=xxx.yaml epochs=300 batch=4
./xyolo --mode venv --models-dir ./checkpoints --datasets-dir ./yamls model=last.pt data=train.yaml epochs=50
./xyolo web --host 0.0.0.0 --port 8860
```

## Help

```bash
./xyolo --help
```
