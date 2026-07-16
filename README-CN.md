# XYolo

XYolo 是一个可安装、可打包为 wheel 的 Python 项目，提供本地 YOLO 训练、Docker 训练和 Web 训练界面。

安装完成后，Python 环境会自动生成系统命令：

```bash
xyolo --help
xyolo --version
```

## 安装

从源码安装：

```bash
python3 -m pip install .
```

开发模式安装：

```bash
python3 -m pip install -e .
```

安装 wheel：

```bash
python3 -m pip install dist/xyolo-0.1.0-py3-none-any.whl
```

`ultralytics` 和 `PyYAML` 会作为 Python 依赖一并安装。XYolo 不再在项目目录中创建或维护自己的 `venv/`。

## 构建 wheel

先构建并打包前端静态资源：

```bash
cd web/ui
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ../..
```

然后构建 Python 包：

```bash
python3 -m pip install build
python3 -m build
```

生成文件位于 `dist/`。Web 前端构建产物会写入 `src/xyolo/static/`，并随 wheel 一起安装，运行 Web 服务时不再需要 Node.js 或 pnpm。

## 工作目录

XYolo 把执行命令时的当前目录作为项目工作目录，并自动使用：

```text
models/          # 模型权重
datasets/        # 数据集配置和相关文件
runs/            # 训练输出
web/configs/     # Web 保存的 YAML 参数
web/drafts/      # Web 草稿
web/templates/   # Web 模板
web/tasks/       # Web 任务和日志
```

安装包目录只保存程序代码和 Web 静态资源，不保存用户训练数据。

## 本地训练

```bash
xyolo train model=yolov8s.pt data=dataset.yaml epochs=200 batch=8
```

`--mode venv` 为兼容原命令保留，也是默认模式；它现在表示直接使用安装 XYolo 的当前 Python 环境：

```bash
xyolo train --mode venv model=best.pt data=my_dataset.yaml epochs=100
```

如果 `best.pt` 位于 `models/`、`my_dataset.yaml` 位于 `datasets/`，XYolo 会自动解析为对应相对路径，并默认补充 `project=runs`。

只查看最终命令：

```bash
xyolo train --dry-run model=yolov8s.pt data=dataset.yaml epochs=1
```

## Docker 训练

```bash
xyolo train --mode docker model=yolov8s.pt data=dataset.yaml epochs=200
```

Docker 模式会把当前工作目录挂载到容器内的 `/ultralytics`。默认镜像为 `ultralytics/ultralytics:latest`，默认后台运行：

```bash
xyolo train --mode docker --attach model=yolov8s.pt data=dataset.yaml
xyolo train --mode docker --container-name train-01 model=yolov8s.pt data=dataset.yaml
```

## 命令模块

CLI 模块与 Web 页面模块保持一致：

```text
xyolo dataset    # 数据集，预留
xyolo train      # 训练，已实现
xyolo model      # 模型，预留
xyolo eval       # 评估，预留
xyolo deploy     # 部署，预留
xyolo web        # Web 服务，已实现
```

预留模块已经出现在 `xyolo --help` 中。当前直接执行时会明确提示尚未实现，后续功能将在对应模块下扩展。

## Web 服务

```bash
xyolo web
xyolo web --host 0.0.0.0 --port 8860
```

Web 服务直接读取 wheel 内置的前端静态资源，任务数据和训练输出仍写入当前工作目录。

## 前端开发

```bash
cd web/ui
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Vite 开发服务器会把 `/api` 和 `/logs` 代理到 `http://127.0.0.1:8860`。
