# xyolo

`xyolo` 是一个 YOLO 训练启动脚本，支持：

1. **venv 本地训练**
2. **docker 训练**
3. **web 页面建任务并启动训练**

默认训练模式是 **venv**。

## 目录约定

脚本会自动规整并使用这些目录：

- `venv/`：本地 Python 虚拟环境
- `models/`：本地模型权重
- `datasets/`：数据集配置
- `runs/`：训练输出
- `web/configs/`：Web 保存的参数文件
- `web/tasks/`：Web 生成的任务、日志和 dstack spec

这些目录默认都会自动创建，**不需要先手动建**。

如果模型和数据集文件放在默认目录里，启动时可以直接写文件名：

```bash
./xyolo model=best.pt data=my_dataset.yaml epochs=200 batch=8
```

脚本会优先解析为：

```bash
model=models/best.pt
data=datasets/my_dataset.yaml
project=runs
```

如果你传的是完整路径、相对路径，或者官方模型名（例如 `yolov8s.pt`），脚本不会强行改写。

## 自动安装

### venv 模式

启动时会自动检查：

- `venv/` 是否存在
- `ultralytics`
- `dstack`
- `swanlab`

如果缺失，会自动创建虚拟环境并安装这些包。

### docker 模式

启动时会自动检查：

- 系统是否安装了 `docker`
- Docker 服务是否启动
- 本地是否已有 `ultralytics/ultralytics:latest` 镜像

如果缺失，会自动尝试：

```bash
apt-get install docker.io
docker pull ultralytics/ultralytics:latest
```

当前自动安装 Docker 的逻辑面向 **Ubuntu / Debian 这类 apt 系 Linux**。

## 手动创建 venv

如果你想提前手动准备虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install ultralytics dstack swanlab
```

检查：

```bash
./venv/bin/yolo --help
./venv/bin/pip show dstack swanlab
```

## 训练用法

```bash
./xyolo [--mode venv|docker] [options] key=value [key=value ...]
```

脚本会把参数传给：

```bash
yolo train ...
```

例如：

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

等价于：

```bash
yolo train model=yolov8s.pt data=xxx.yaml epochs=200 batch=8 project=runs
```

## venv 模式

默认就是 `venv`，调用的是：

```bash
./venv/bin/yolo train ...
```

示例：

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
./xyolo --mode venv model=best.pt data=my_data.yaml imgsz=640 device=0
```

## docker 模式

使用镜像：

```bash
ultralytics/ultralytics:latest
```

并把当前目录挂载到容器内：

```bash
/ultralytics
```

示例：

```bash
./xyolo --mode docker model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
sudo ./xyolo --mode docker model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

默认参数：

- `--runtime=nvidia`
- `--shm-size=4g`
- `--ulimit memlock=-1`
- `--ulimit stack=67108864`

Docker 默认后台运行；如果要前台看日志：

```bash
./xyolo --mode docker --attach model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
```

## Web 服务

启动：

```bash
./xyolo web
```

自定义监听地址：

```bash
./xyolo web --host 0.0.0.0 --port 8860
```

启动后页面里可以：

1. 从 `models/` 和 `datasets/` 里选择模型、数据集
2. 直接填写训练参数
3. 选择已有参数文件，或者在页面里保存新的参数文件
4. 创建任务并自动后台启动
5. 查看任务状态和日志

Web 任务会生成：

- `web/tasks/<task-id>.json`：任务描述
- `web/tasks/<task-id>.log`：训练日志
- `web/tasks/<task-id>.dstack.yml`：启用 dstack 时生成

### Web 参数文件

页面支持两种方式：

1. **直接填写参数**
2. **使用参数文件**

参数文件支持：

- `yaml`
- `json`
- `key=value` 文本

示例 YAML：

```yaml
epochs: 300
batch: 4
lr0: 0.005
close_mosaic: 10
```

示例 key=value：

```text
epochs=300
batch=4
lr0=0.005
close_mosaic=10
```

## SwanLab 用法

Web 页面支持直接开启 **SwanLab**。

启用后可填写：

- `SwanLab project`
- `SwanLab workspace`
- `SwanLab experiment`
- `SwanLab API key`
- `SwanLab description`

### venv 模式下的 SwanLab

Web 任务会改为走 `Ultralytics + SwanLab callback`：

```python
from ultralytics import YOLO
from swanlab.integration.ultralytics import add_swanlab_callback
```

然后训练时自动把指标打到 SwanLab。

### docker 模式下的 SwanLab

Web 任务会在容器里先安装 `swanlab`，再运行集成脚本，所以 docker 任务也可以直接在页面里启用 SwanLab。

### SwanLab 兼容性说明

当前本地环境是 **Python 3.14**。  
Web 页面已经提示兼容性状态：

- **docker 模式更推荐**
- **venv 模式下本地 SwanLab 回调可能因为 Python 版本报错**

如果你要稳定使用本地 SwanLab，建议把本地 Python 切到 **3.10 - 3.13**。

## dstack 用法

Web 页面支持：

1. **生成 dstack 任务文件**
2. **尝试自动提交 dstack**

启用后会在 `web/tasks/` 下生成：

```bash
<task-id>.dstack.yml
```

生成内容会基于当前任务自动拼出：

- 任务名
- working_dir
- GPU 资源
- `./xyolo ...` 启动命令
- SwanLab API key（如果填了）

如果勾选了 **自动提交 dstack**，会执行：

```bash
python -m dstack apply -f web/tasks/<task-id>.dstack.yml -d -y
```

### dstack 兼容性说明

当前安装的 `dstack` 包本身 **不支持 Python 3.14**。所以目前：

- **生成 `.dstack.yml` 没问题**
- **本地自动提交可能失败**

如果要稳定自动提交 dstack，建议使用 **Python 3.10 - 3.13** 的虚拟环境。

## 可选参数

- `--mode venv|docker`：选择训练方式，默认 `venv`
- `--venv-dir PATH`：指定虚拟环境目录
- `--models-dir PATH`：指定模型目录
- `--datasets-dir PATH`：指定数据集目录
- `--docker-image IMAGE`：指定 Docker 镜像
- `--container-name NAME`：指定容器名
- `--attach`：Docker 前台运行
- `--detach`：Docker 后台运行
- `--dry-run`：只打印命令，不执行

Web 启动参数：

- `./xyolo web --host HOST --port PORT`

## 示例

```bash
./xyolo model=yolov8s.pt data=xxx.yaml epochs=200 batch=8
./xyolo --dry-run model=best.pt data=my_dataset.yaml epochs=100 batch=16
./xyolo --mode docker --container-name yolo_train_01 model=yolov8m.pt data=xxx.yaml epochs=300 batch=4
./xyolo --mode venv --models-dir ./checkpoints --datasets-dir ./yamls model=last.pt data=train.yaml epochs=50
./xyolo web --host 0.0.0.0 --port 8860
```

## 帮助

```bash
./xyolo --help
```
