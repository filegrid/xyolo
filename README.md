# xyolo

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
- `web/tasks/`: generated tasks, logs, and dstack specs

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

The web UI can:

1. Select models and datasets from `models/` and `datasets/`
2. Edit training parameters directly
3. Load an existing parameter file or save a new one from the page
4. Create tasks and start them automatically in the background
5. View task status and logs

Generated task artifacts:

- `web/tasks/<task-id>.json`: task definition
- `web/tasks/<task-id>.log`: training log
- `web/tasks/<task-id>.dstack.yml`: created when dstack is enabled

### Web parameter files

The page supports:

1. **Direct parameter editing**
2. **Parameter files**

Supported formats:

- `yaml`
- `json`
- `key=value` text

YAML example:

```yaml
epochs: 300
batch: 4
lr0: 0.005
close_mosaic: 10
```

`key=value` example:

```text
epochs=300
batch=4
lr0=0.005
close_mosaic=10
```

## SwanLab usage

The web UI can enable **SwanLab** directly.

Available fields:

- `SwanLab project`
- `SwanLab workspace`
- `SwanLab experiment`
- `SwanLab API key`
- `SwanLab description`

### SwanLab in venv mode

Web tasks switch to an `Ultralytics + SwanLab callback` flow:

```python
from ultralytics import YOLO
from swanlab.integration.ultralytics import add_swanlab_callback
```

Training metrics are then logged to SwanLab automatically.

### SwanLab in docker mode

For Docker tasks, the worker installs `swanlab` inside the container and then runs the integration script, so SwanLab can also be enabled directly from the UI for Docker-based jobs.

### SwanLab compatibility

The current local environment uses **Python 3.14**.

The web page already shows the compatibility status:

- **docker mode is recommended**
- **local SwanLab callbacks in venv mode may fail because of the Python version**

If you need reliable local SwanLab support, use **Python 3.10 - 3.13**.

## dstack usage

The web UI supports:

1. **Generating a dstack task file**
2. **Attempting automatic dstack submission**

When enabled, it creates:

```bash
web/tasks/<task-id>.dstack.yml
```

The generated spec includes:

- task name
- working directory
- GPU resource request
- the `./xyolo ...` launch command
- SwanLab API key if provided

If **auto submit dstack** is enabled, the worker runs:

```bash
python -m dstack apply -f web/tasks/<task-id>.dstack.yml -d -y
```

### dstack compatibility

The currently installed `dstack` package does **not** support Python 3.14. At the moment:

- generating `.dstack.yml` works
- local automatic submission may fail

If you need reliable automatic dstack submission, use a **Python 3.10 - 3.13** virtual environment.

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
