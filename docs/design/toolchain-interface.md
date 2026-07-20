# 训练与评估工具链接口设计

## 1. 目标

训练目标系统不应把执行层写死为单一框架。

需要引入**工具链（toolchain）**概念，把“训练 / 评估 / 模型产物解析 / 指标归一化”统一抽象成公共接口，上层页面、目标树、节点树都只依赖通用协议，不直接依赖 YOLO、Torch 或其他具体实现。

目标如下：

1. 支持多个工具链并存；
2. 当前先落地 `yolo`；
3. 未来可扩展 `torch`、自定义 trainer、其他推理/评估框架；
4. 训练页、评估页、任务记录都使用统一数据契约；
5. 工具链差异收敛到适配层，不扩散到业务层。

## 2. 当前支持范围

第一阶段工具链清单：

| toolchain | 状态 | 说明 |
|---|---|---|
| `yolo` | 支持 | 当前唯一落地实现 |
| `torch` | 预留 | 接口保留，暂不实现 |

这里的“支持多个工具链”指的是**架构上可扩展**，不是要求第一版同时实现多个后端。

## 3. 设计原则

### 3.1 业务层不直接调用具体框架

业务层不应出现这类绑定：

- `YOLO(...).train(...)`
- `YOLO(...).val(...)`
- 某个框架私有 `kwargs` 直接成为业务主协议

业务层只能面向：

- `toolchain`
- `operation`
- `request`
- `result`
- `artifact`

### 3.2 公共字段优先，私有字段下沉

公共协议中只保留跨工具链都成立的字段，例如：

- 任务类型；
- 数据集；
- 基础模型；
- 输出目录；
- 训练轮数；
- 验证集定义；
- 产物路径；
- 归一化指标。

YOLO、Torch 各自独有的参数不能污染公共顶层，统一放进：

- `provider_config`
- `provider_payload`
- `provider_result`

### 3.3 训练与评估分别抽象

训练和评估是两个独立操作：

1. `train`
2. `evaluate`

不能默认“训练完成就天然等于完成评估”，因为未来可能存在：

- 只评估历史模型；
- 重跑某个验证集；
- 用不同工具链做离线评估；
- 单独产出 benchmark 报告。

## 4. 核心对象

### 4.1 ToolchainDefinition

描述一个工具链能做什么。

```json
{
  "key": "yolo",
  "label": "Ultralytics YOLO",
  "version": "v1",
  "capabilities": {
    "train": true,
    "evaluate": true,
    "tasks": ["detect", "segment", "pose"]
  }
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `key` | 工具链唯一标识 |
| `label` | UI 展示名 |
| `version` | 当前接口版本 |
| `capabilities` | 声明支持的操作和任务类型 |

### 4.2 ModelArtifact

统一表示训练或导入后的模型产物。

```json
{
  "artifact_id": "model-node-002-best",
  "toolchain": "yolo",
  "task": "detect",
  "format": "checkpoint",
  "path": "runs/person-helmet/node-002/weights/best.pt",
  "source": {
    "goal_id": "goal-person-helmet",
    "node_id": "node-002",
    "task_id": "task-20260715-001"
  },
  "metadata": {
    "is_best": true
  }
}
```

说明：

- 上层只知道这是一个模型产物；
- 至于它是 `.pt`、`.ckpt`、`.safetensors` 还是别的格式，由工具链适配层解释。

### 4.3 DatasetArtifact

统一表示训练或评估输入数据。

```json
{
  "artifact_id": "dataset-effective-node-002",
  "kind": "dataset",
  "task": "detect",
  "path": "web/tasks/task-20260715-001/data.effective.yaml",
  "format": "yolo-yaml"
}
```

说明：

- 公共层只要求“这是一个可供某工具链读取的数据集描述”；
- 具体格式可以是 `yolo-yaml`、`torch-manifest` 等。

## 5. 公共操作接口

### 5.1 训练请求 TrainRequest

```json
{
  "toolchain": "yolo",
  "operation": "train",
  "task": "detect",
  "base_model": {
    "artifact_id": "model-node-001-best",
    "path": "runs/person-helmet/node-001/weights/best.pt"
  },
  "dataset": {
    "artifact_id": "dataset-effective-node-002",
    "path": "web/tasks/task-20260715-001/data.effective.yaml",
    "format": "yolo-yaml"
  },
  "runtime_config": {
    "output_dir": "runs/person-helmet/node-002",
    "run_name": "node-002"
  },
  "train_config": {
    "epochs": 60,
    "batch": 32,
    "imgsz": 640
  },
  "provider_payload": {
    "kwargs": {
      "model": "runs/person-helmet/node-001/weights/best.pt",
      "data": "web/tasks/task-20260715-001/data.effective.yaml",
      "epochs": 60,
      "batch": 32,
      "imgsz": 640,
      "lr0": 0.0005
    }
  }
}
```

设计要点：

1. 公共层只看 `toolchain + operation + task + artifacts + config`；
2. YOLO 现有 `train_kwargs` 仍可保留，但只能放到 `provider_payload.kwargs`；
3. 未来 `torch` 可以生成自己的 `provider_payload`，不影响上层。

### 5.2 训练结果 TrainResult

```json
{
  "toolchain": "yolo",
  "operation": "train",
  "status": "completed",
  "artifacts": {
    "best_model": {
      "artifact_id": "model-node-002-best",
      "path": "runs/person-helmet/node-002/weights/best.pt"
    },
    "last_model": {
      "artifact_id": "model-node-002-last",
      "path": "runs/person-helmet/node-002/weights/last.pt"
    }
  },
  "provider_result": {
    "run_dir": "runs/person-helmet/node-002"
  }
}
```

### 5.3 评估请求 EvaluationRequest

```json
{
  "toolchain": "yolo",
  "operation": "evaluate",
  "task": "detect",
  "model": {
    "artifact_id": "model-node-002-best",
    "path": "runs/person-helmet/node-002/weights/best.pt"
  },
  "validation": {
    "name": "night-val",
    "role": "scenario",
    "weight": 0.20,
    "dataset": {
      "artifact_id": "dataset-night-val",
      "path": "datasets/night-val.yaml",
      "format": "yolo-yaml"
    }
  },
  "runtime_config": {
    "output_dir": "runs/person-helmet/node-002/evals/night-val"
  },
  "provider_payload": {
    "kwargs": {
      "data": "datasets/night-val.yaml"
    }
  }
}
```

### 5.4 评估结果 EvaluationResult

```json
{
  "toolchain": "yolo",
  "operation": "evaluate",
  "status": "completed",
  "normalized_metrics": {
    "main_metric": 0.63,
    "map50_95": 0.63,
    "map50": 0.82,
    "precision": 0.84,
    "recall": 0.74
  },
  "provider_result": {
    "raw_metrics": {
      "map": 0.63
    }
  }
}
```

重点：

- 公共层消费 `normalized_metrics`；
- 工具链原始输出保留在 `provider_result.raw_metrics`；
- 评估指标体系文档中的 `dataset_score`、`node_score` 都基于归一化指标计算。

## 6. 适配层接口

工具链实现层建议统一暴露以下接口。

### 6.1 注册接口

```ts
interface ToolchainAdapter {
  key: string
  supports(task: string, operation: 'train' | 'evaluate'): boolean
  validateTrainRequest(request: TrainRequest): void
  validateEvaluationRequest(request: EvaluationRequest): void
  runTrain(request: TrainRequest): Promise<TrainResult>
  runEvaluation(request: EvaluationRequest): Promise<EvaluationResult>
  normalizeMetrics(result: EvaluationResult): NormalizedMetrics
}
```

说明：

1. 业务层按 `toolchain` 找 adapter；
2. 每个 adapter 自己校验自己的私有参数；
3. 每个 adapter 负责把原始输出转换成公共指标结构。

### 6.2 YoloAdapter

第一版只实现 `YoloAdapter`：

1. 读取 `provider_payload.kwargs`；
2. 调用当前 YOLO 训练/评估流程；
3. 解析产出的模型路径、日志、指标；
4. 转成公共 `TrainResult / EvaluationResult`。

### 6.3 TorchAdapter

后续如果接 `torch`，只需要新增 `TorchAdapter`，而不是改：

- 训练目标结构；
- 节点树结构；
- 最优模型规则；
- 页面交互协议。

## 7. 任务记录结构调整

现有执行任务不能再只保存某个框架私有 `train_kwargs`，应改成**公共任务协议 + provider 私有负载**。

推荐结构：

```json
{
  "id": "task-20260715-001",
  "goal_id": "goal-person-helmet",
  "node_id": "node-002",
  "toolchain": "yolo",
  "operation": "train",
  "request": {
    "task": "detect",
    "base_model": {
      "path": "runs/person-helmet/node-001/weights/best.pt"
    },
    "dataset": {
      "path": "web/tasks/task-20260715-001/data.effective.yaml",
      "format": "yolo-yaml"
    },
    "train_config": {
      "epochs": 60,
      "batch": 32,
      "imgsz": 640
    },
    "provider_payload": {
      "kwargs": {
        "lr0": 0.0005
      }
    }
  },
  "result": {
    "status": "completed"
  }
}
```

这样任务记录未来既能表达 YOLO，也能表达 Torch。

## 8. 与评估指标体系的关系

工具链负责**产出原始评估结果**，评估体系负责**做统一归一化和排序决策**。

职责边界如下：

| 层级 | 职责 |
|---|---|
| toolchain adapter | 跑训练、跑评估、解析原始结果 |
| metrics normalizer | 把不同工具链结果映射到统一指标 |
| evaluation policy | 计算 `dataset_score` / `node_score` / `best_node_id` |

也就是说：

- `yolo` 和未来 `torch` 的差异，主要由 adapter 处理；
- “哪个模型最好”不是工具链决定，而是上层评估策略决定。

## 9. Yolo 第一阶段落地方式

第一阶段不推翻当前实现，而是包一层适配：

1. 上层生成 `TrainRequest / EvaluationRequest`；
2. `toolchain = yolo` 时，交给 `YoloAdapter`；
3. `YoloAdapter` 内部继续复用现有训练 worker；
4. 现有 `train_kwargs` 下沉为 `provider_payload.kwargs`；
5. 现有评估输出解析后映射为 `normalized_metrics`。

这样既能快速兼容现状，也为后续多工具链扩展留好边界。

## 10. 需要同步调整的旧接口

此前文档里写死的接口需要统一改成以下原则：

1. 不再把 `train_kwargs` 当作公共顶层协议；
2. 不再把 `YOLO(...).train(...)` 作为系统执行接口描述；
3. 不再假设评估一定是 YOLO 原生输出格式；
4. 所有任务记录都显式带 `toolchain`；
5. 所有评估记录都保留 `normalized_metrics + provider_result` 双层结构。

## 11. 最终结论

这套工具链设计的核心是：

1. **公共层统一**：目标、节点、任务、评估都面向统一协议；
2. **私有层隔离**：YOLO/Torch 差异下沉到 adapter；
3. **当前可落地**：先只实现 `yolo`；
4. **未来可扩展**：后续增加 `torch` 不需要重写目标树和评估体系。
