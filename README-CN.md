# XYolo

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
- `web/tasks/`：Web 生成的任务和日志

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

前端技术栈使用：

- **Vite**
- **React**
- **pnpm**
- **shadcn/ui**

执行 `xyolo web` 时，如果前端依赖还没装好，会自动安装并重新构建前端。

启动后页面是 **单页训练界面**。

右上角提供：

- **环境信息** 入口
- **dstack** 入口
- **SwanLab** 入口
- **中英文切换**
- **主题切换**：跟随系统 / 浅色 / 深色

语言和主题选择会写入 cookie。

当主题选择为 **跟随系统** 时，会真正跟随系统深浅色变化。

训练页面内部再分成两类：

1. **新建**
2. **列表**

训练表单分成：

- **基础设置**
- **高级设置**（默认隐藏）

模型和数据集各自都是 **一个输入框**：既能从本地候选里下拉，也能直接输入官方模型名或自定义路径。

整个流程只保留 **一个名字**。创建任务时自动生成，并同步复用到训练输出和相关任务元数据里。

Web 任务会生成：

- `web/tasks/<task-id>.json`：任务描述
- `web/tasks/<task-id>.log`：训练日志
- `web/drafts/<draft-id>.json`：暂存
- `web/templates/<template-id>.json`：模板

### Web 参数文件

页面支持两种方式：

1. **直接填写参数**
2. **使用 YAML 参数文件**

参数文件固定只支持 **YAML**。

示例 YAML：

```yaml
epochs: 300
batch: 4
lr0: 0.005
close_mosaic: 10
```

## SwanLab 用法

页面右上角保留了 **SwanLab** 入口。

点击时，后端会尝试通过 Docker 拉起 SwanLab，并在成功后打开对应地址。

### SwanLab 兼容性说明

当前本地环境是 **Python 3.14**，所以这里不再走本地 Python 包路径。

当前实现改成优先走 Docker。  
如果直接访问 Docker 失败，后端还会再尝试 `sudo -n docker`。如果还是失败，页面会直接把失败原因显示出来。

## dstack 用法

页面右上角保留了 **dstack** 入口。

点击时，后端会尝试通过 Docker 拉起 dstack，并在成功后打开对应地址。

### dstack 兼容性说明

当前安装的 `dstack` Python 包本身 **不支持 Python 3.14**，所以入口改成优先走 Docker 路径。

如果直接访问 Docker 失败，后端还会再尝试 `sudo -n docker`。如果还是失败，页面会直接显示具体错误。

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
