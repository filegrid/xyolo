# 训练页面重新设计方案

## 1. 核心改动

训练页不再以“新建一次训练任务”为中心，而只保留“新建训练目标”这一种入口。

每个训练目标不是只能有一个起点，而是可以维护多个 root，整体表现为一片瀑布流演进森林：

1. 每个 root 表示该目标的一条初始训练基线。
2. 后续每个分支节点都来自某个已有节点。
3. 分支必须说明“为什么要分支”。
4. 子节点的数据集只能在父节点数据集基础上做加法，不能减法替换。
5. 每次实际训练都继承目标默认参数，只允许局部覆盖。
6. 每次训练可以挂多个验证集，分别评估效果。

训练执行方式仍然沿用现有方法：最终还是生成统一的 `train_request`，再由具体 `toolchain` 转成对应执行负载，不另起一套训练引擎。

## 2. 页面模型从“任务”改成“目标”

当前页面偏向一次性表单：

- 选 `model`
- 选 `data`
- 填参数
- 启动一次训练

新方案改成：

- 先创建训练目标；
- 在目标下维护默认参数、默认模型来源、默认验证集；
- 以瀑布流方式持续增加训练节点；
- 每个节点只描述“相对父节点新增了什么”；
- 每次训练都是“目标默认值 + 父节点继承值 + 本节点局部调整”。

也就是说，页面主对象从 `task` 变成 `goal`，`task` 退化为目标树上的一次实际训练执行记录。

## 3. 信息架构

顶部导航仍保持：

`数据集 / 训练 / 模型 / 评估 / 部署`

其中“训练”只保留一个主入口：**训练目标**。

训练页面分成左右两块：

```text
┌──────────────────────────────┬──────────────────────────────────────┐
│ 左侧：训练目标列表            │ 右侧：当前训练目标详情               │
│                              │                                      │
│ - 目标 A                     │ 1. 目标概览                          │
│ - 目标 B                     │ 2. 瀑布流训练树                      │
│ - 目标 C                     │ 3. 当前节点详情                      │
│                              │ 4. 训练参数继承/覆盖                 │
│                              │ 5. 验证集与评估结果                  │
└──────────────────────────────┴──────────────────────────────────────┘
```

右侧核心不是普通表单，而是 **目标 + 树 + 节点** 三层结构。

## 4. 训练目标结构

每个训练目标包含四类稳定信息：

### 4.1 目标元信息

- 目标名称
- 任务类型：detect / segment / pose
- 目标说明
- 创建时间
- 当前推荐主干分支
- 当前最佳节点

### 4.2 默认训练配置

这是整个目标的基础配置，不是某一次训练的临时参数。

包括：

- 默认模型来源
- 默认训练参数
- 默认输出目录规则
- 默认验证集列表
- 默认评估指标

这些默认值定义的是“这个目标通常怎么训练”，不是立刻执行一次训练。

### 4.3 Root 层

每个目标必须至少有一个 root，但可以同时存在多个 root。

这样可以支持一个训练目标从多个源头数据集或多个初始模型并行起步，而不是被限制成单一起点。

每个 root 都表示一条可继续分支演进的初始基线。root 可以来自：

1. 官方预训练权重；
2. 自定义模型结构 YAML + 初始化权重；
3. 已有历史模型导入。

每个 root 节点本身也允许直接配置多个初始数据集，作为该条分支的源头训练集合。

### 4.4 节点树

后续所有训练节点都必须挂在某个 root 或某个已有父节点下面，不允许孤立创建。

## 5. 瀑布流设计

### 5.1 展示形式

目标内部采用“多 root + 每个 root 向下瀑布流演进”的展示形式，而不是平铺表格。

示意：

```text
目标：person-helmet

[R0/N0] 初始基线-A
  模型：yolov8s.pt
  初始数据：dataset-base-v1 + dataset-site-a-v1
  指标：mAP50-95=0.61
  │
  ├── [N1] 增加夜间数据
  │     分支原因：夜间漏检明显
  │     数据增量：night-v1
  │     参数调整：lr0 0.001 -> 0.0005
  │     指标：old-val / night-val / merged-val
  │
  │   └── [N2] 增加安全帽类别
  │         分支原因：新增 helmet 类别
  │         数据增量：helmet-v1
  │         参数调整：freeze 10, epochs 80
  │         指标：old-val / helmet-val / merged-val
  │
  └── [N3] 增加逆光场景
        分支原因：逆光场景误检高
        数据增量：backlight-v1
        参数调整：仅调整 augment
        指标：old-val / backlight-val / merged-val

[R1/N0] 初始基线-B
  模型：history/best-site-b.pt
  初始数据：dataset-base-v1 + dataset-site-b-v1
  指标：mAP50-95=0.59
  │
  └── [N4] 增加雨天数据
        分支原因：雨天场景 recall 偏低
        数据增量：rain-v1
        参数调整：epochs 100
        指标：old-val / rain-val / merged-val
```

### 5.2 每个分支必须记录原因

分支不是为了“多训一次”，而是为了表达一次明确的优化意图。

因此从父节点创建子节点时，`branch_reason` 必填，例如：

- 夜间场景漏检
- 新增类别 helmet
- 旧数据 recall 下降，需要回滚策略
- 小目标效果不足，补充高分辨率样本

这个字段必须在 UI 中显式显示，不能藏在备注里。

### 5.3 子节点数据集只能做加法

这是本次设计的核心约束。

父节点已经使用的数据集集合记为：

`base_datasets`

子节点只能声明：

`added_datasets`

最终训练实际使用的数据集为：

`effective_datasets = parent.effective_datasets + added_datasets`

不允许：

- 删除父节点已有数据集；
- 用新数据集替换旧数据集；
- 只保留新增数据单独训练；
- 在子节点偷偷改掉父节点的数据定义。

如果当前节点是 root，那么它没有父节点，此时：

`effective_datasets = root_datasets`

其中 `root_datasets` 本身允许包含多个源头数据集。

这样每个节点都天然满足“对子节点的数据集做加法”，同时不会把源头数据集限制成只能有一个。

## 6. 节点的数据模型

每个训练节点建议包含以下结构：

```json
{
  "id": "node-002",
  "goal_id": "goal-person-helmet",
  "parent_id": "node-001",
  "name": "增加夜间数据",
  "branch_reason": "夜间场景漏检明显，需要补充夜间样本继续训练",
  "added_datasets": [
    "datasets/night-v1.yaml"
  ],
  "effective_datasets": [
    "datasets/base-v1.yaml",
    "datasets/night-v1.yaml"
  ],
  "override_params": {
    "lr0": 0.0005,
    "epochs": 60
  },
  "validation_sets": [
    "datasets/base-val.yaml",
    "datasets/night-val.yaml",
    "datasets/merged-val.yaml"
  ],
  "status": "completed",
  "result_model": "runs/person-helmet/node-002/weights/best.pt"
}
```

这里最重要的是区分三种东西：

1. `added_datasets`：本节点新增的数据；
2. `effective_datasets`：从根到当前节点累计后的训练数据；
3. `override_params`：只写本节点相对默认值或父节点的差异。

对于 root 节点，建议再补充三个字段：

1. `is_root`：标记该节点是 root；
2. `root_key`：标识该目标下的第几个 root；
3. `root_datasets`：该 root 自身的初始数据集集合。

## 7. 参数继承模型

### 7.1 参数来源优先级

每次实际训练使用的参数按以下顺序生成：

1. 系统默认参数；
2. 训练目标默认参数；
3. 父节点生效参数；
4. 当前节点覆盖参数；
5. 运行时系统补充项，例如 `project`、`name`。

最终结果生成一个可执行的 `train_kwargs`，继续走当前训练逻辑。

### 7.2 页面上只编辑“默认值”和“覆盖值”

不再让用户每次都重新填完整参数表。

页面分成两层：

1. **目标默认参数**
   - 定义整个目标的基线训练策略；
2. **节点覆盖参数**
   - 只写这一次训练与默认值/父节点不同的内容。

例如：

目标默认参数：

```yaml
imgsz: 640
batch: 32
epochs: 80
lr0: 0.001
close_mosaic: 10
freeze: 10
```

节点覆盖参数：

```yaml
lr0: 0.0005
epochs: 60
```

最终界面需同时显示：

- 默认值
- 继承值
- 当前覆盖值
- 最终生效值

避免用户不知道参数到底从哪里来的。

### 7.3 训练方法保持现有实现

虽然页面模型改了，但训练执行不要重写。

后端仍应产出统一执行结构，例如：

```json
{
  "toolchain": "yolo",
  "operation": "train",
  "train_request": {
    "task": "detect",
    "base_model": {
      "path": "models/previous-best.pt"
    },
    "dataset": {
      "path": "web/tasks/task-001/data.effective.yaml",
      "format": "yolo-yaml"
    },
    "train_config": {
      "epochs": 60,
      "imgsz": 640,
      "batch": 32
    },
    "provider_payload": {
      "kwargs": {
        "lr0": 0.0005
      }
    }
  }
}
```

也就是说，新的“目标树”只是更高层的组织方式，底层仍通过 `toolchain adapter` 复用现有执行流程。当前先实现 `yolo`，后续可接 `torch` 或其他工具链。

## 8. 数据集加法规则

### 8.1 训练数据

节点不能直接选一个独立的 `data` 覆盖父节点。

正确流程是：

1. 如果是普通分支节点，则继承父节点的 `effective_datasets`；
2. 如果是普通分支节点，则再选择当前 `added_datasets`；
3. 如果是 root 节点，则直接配置 `root_datasets` 作为初始集合；
4. 后端生成当前节点的合并训练 YAML；
5. 实际训练使用这个合并 YAML。

例如：

```yaml
train:
  - datasets/base/images/train
  - datasets/night/images/train
  - datasets/helmet/images/train
val:
  - datasets/base/images/val
names:
  0: person
  1: helmet
```

### 8.2 类别约束

因为子节点只能做加法，所以类别规则也必须按树递增：

- 同类别扩充：`names` 不变；
- 新增类别：只能在父节点类别集基础上追加；
- 不允许删除旧类别；
- 不允许重排旧类别索引。

页面需要在创建分支时显示：

- 父节点类别列表；
- 本节点新增类别；
- 最终生效类别列表；
- 是否兼容。

### 8.3 数据来源透明

在节点详情里必须能看到：

- 本节点新增了哪些数据集；
- 从根节点累计后最终参与训练的是哪些数据集；
- 每个数据集贡献了多少 train/val 样本；
- 是否包含旧数据；
- 是否包含新类别数据。

这样用户能直接看出训练是不是仍然保留了历史数据。

## 9. 验证集设计

### 9.1 一次训练可以挂多个验证集

每个节点都允许配置多个验证集，而不是只依赖一个 `val`。

验证集分为两类：

1. **目标默认验证集**
   - 所有节点默认都会跑；
2. **节点附加验证集**
   - 只针对这次分支新增。

例如某个目标默认有：

- `base-val`
- `regression-val`

某个夜间分支再增加：

- `night-val`

那么该节点训练后要评估：

- `base-val`
- `regression-val`
- `night-val`

### 9.2 验证集不是训练数据集的替代品

这里要严格区分：

- 训练数据：只能做加法继承；
- 验证数据：可以独立增加多个视角；
- 验证集不会反向改变父节点训练数据。

### 9.3 结果展示方式

每个节点结果不能只显示一个总 mAP，而应按验证集展开：

| 验证集 | 用途 | mAP50-95 | Precision | Recall | 备注 |
|---|---|---:|---:|---:|---|
| base-val | 老能力回归 | 0.60 | 0.82 | 0.70 | 相比父节点 -0.01 |
| regression-val | 通用回归 | 0.58 | 0.80 | 0.68 | 持平 |
| night-val | 夜间专项 | 0.63 | 0.84 | 0.74 | 提升明显 |

节点卡片上至少要显示：

- 默认主验证集指标；
- 与父节点对比变化；
- 最差验证集告警。

### 9.4 验证结论

每个节点训练完成后输出一个评估结论：

- 通过
- 有提升但旧集退化
- 新场景提升不明显
- 新类别有效，旧类别稳定
- 整体回归失败

这样训练树不只是日志树，而是决策树。

## 10. 页面交互流程

### 10.1 创建训练目标

用户创建目标时填写：

- 目标名称
- 任务类型
- root 模型来源
- root 初始数据集
- 目标默认参数
- 目标默认验证集

保存后进入 root 管理流程，允许用户先创建一个或多个 root 节点配置页。

### 10.2 在节点上创建分支

从某个节点点击“创建分支”时，页面弹出分支面板，要求填写：

- 分支名称
- 分支原因
- 新增数据集
- 新增验证集（可选）
- 节点参数覆盖（可选）

系统自动继承：

- 父节点模型权重
- 父节点已有数据集；如果父节点是 root，则这里包含该 root 的全部源头数据集
- 父节点已生效参数
- 目标默认验证集

### 10.3 启动训练

点击启动时，后端执行：

1. 读取目标默认参数；
2. 解析父节点生效参数；
3. 合并本节点覆盖参数；
4. 生成当前节点生效训练 YAML；
5. 调用现有训练方法；
6. 训练完成后，对本节点全部验证集逐个评估；
7. 保存模型、指标和结论。

## 11. 列表页与详情页

### 11.1 训练目标列表

列表应展示目标级摘要，而不是任务级碎片：

| 列 | 内容 |
|---|---|
| 目标名称 | 例如 person-helmet |
| 任务类型 | detect / pose |
| 当前最佳节点 | 当前推荐模型分支 |
| Root 数 | 当前目标下的 root 数量 |
| 最早 root 时间 | 初始时间 |
| 最近训练 | 最近一次节点训练时间 |
| 节点数 | 当前树的节点总数 |
| 状态 | 正常 / 有告警 / 有失败节点 |

### 11.2 目标详情

目标详情包含三块：

1. 目标配置
2. 瀑布流训练树
3. 节点评估详情

用户切换节点后，右侧详情区刷新：

- 节点来源
- 分支原因
- 数据集加法结果
- 参数继承结果
- 验证集结果
- 产出模型路径

### 11.3 实际训练记录

底层仍保留当前 `tasks` 作为执行记录，但它不再是主要导航入口。

`task` 更适合挂在节点详情内，例如：

- 本节点最新一次执行
- 历史重跑记录
- 日志
- SwanLab 链接

## 12. 前后端数据契约建议

### 12.1 训练目标

```json
{
  "id": "goal-person-helmet",
  "name": "person-helmet",
  "task": "detect",
  "description": "人员与安全帽检测目标",
  "toolchain": "yolo",
  "default_params": {
    "imgsz": 640,
    "batch": 32,
    "epochs": 80,
    "lr0": 0.001,
    "freeze": 10
  },
  "default_validations": [
    "datasets/base-val.yaml",
    "datasets/regression-val.yaml"
  ],
  "root_node_ids": ["node-000", "node-100"],
  "best_node_id": "node-002"
}
```

### 12.2 训练节点

```json
{
  "id": "node-002",
  "goal_id": "goal-person-helmet",
  "parent_id": "node-001",
  "name": "增加夜间数据",
  "branch_reason": "夜间漏检明显",
  "base_model": "runs/person-helmet/node-001/weights/best.pt",
  "added_datasets": [
    "datasets/night-v1.yaml"
  ],
  "effective_datasets": [
    "datasets/base-v1.yaml",
    "datasets/night-v1.yaml"
  ],
  "override_params": {
    "lr0": 0.0005,
    "epochs": 60
  },
  "effective_params": {
    "imgsz": 640,
    "batch": 32,
    "epochs": 60,
    "lr0": 0.0005,
    "freeze": 10
  },
  "validations": [
    "datasets/base-val.yaml",
    "datasets/regression-val.yaml",
    "datasets/night-val.yaml"
  ],
  "latest_task_id": "task-20260715-001",
  "result_model": "runs/person-helmet/node-002/weights/best.pt"
}
```

一个 root 节点可以是：

```json
{
  "id": "node-000",
  "goal_id": "goal-person-helmet",
  "parent_id": null,
  "is_root": true,
  "root_key": "root-a",
  "name": "初始基线-A",
  "toolchain": "yolo",
  "base_model": "yolov8s.pt",
  "root_datasets": [
    "datasets/base-v1.yaml",
    "datasets/site-a-v1.yaml"
  ],
  "effective_datasets": [
    "datasets/base-v1.yaml",
    "datasets/site-a-v1.yaml"
  ],
  "override_params": {},
  "validations": [
    "datasets/base-val.yaml",
    "datasets/regression-val.yaml"
  ]
}
```

### 12.3 训练执行任务

现有任务结构继续保留，但改成“公共请求 + toolchain 私有负载”的形式：

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
      "imgsz": 640,
      "batch": 32
    },
    "provider_payload": {
      "kwargs": {
        "lr0": 0.0005
      }
    }
  },
  "validation_runs": [
    {
      "name": "base-val",
      "toolchain": "yolo",
      "request": {
        "dataset": {
          "path": "datasets/base-val.yaml",
          "format": "yolo-yaml"
        }
      }
    },
    {
      "name": "night-val",
      "toolchain": "yolo",
      "request": {
        "dataset": {
          "path": "datasets/night-val.yaml",
          "format": "yolo-yaml"
        }
      }
    }
  ]
}
```

## 13. 与现有实现的对应关系

### 13.1 可复用部分

现有这些能力可以继续用：

- 本地 / Docker 训练模式；
- 现有训练配置生成逻辑；
- 现有 worker 执行流程；
- 现有 SwanLab 集成；
- 现有日志与任务文件落盘方式。

### 13.2 需要上移抽象层

当前 `App.tsx` 的核心是单次训练表单，需要改成：

- 目标列表；
- 目标默认参数面板；
- 瀑布流节点树；
- 节点覆盖参数面板；
- 多验证集评估面板。

也就是把“完整参数输入”从首页操作，变成“默认值 + 差异值”的编辑方式。

### 13.3 后端新增职责

当前后端主要做一次性任务创建。新方案下要新增：

1. 训练目标存储；
2. 多 root + 节点树存储；
3. 父子节点继承计算；
4. 数据集累积加法计算；
5. 节点有效参数计算；
6. toolchain 适配层与请求分发；
7. 多验证集评估调度；
8. 节点评估摘要生成。

但最终执行训练时，仍然可以通过 `yolo` adapter 调用现有训练代码，不需要推翻现有 worker。

## 14. 约束与校验

### 14.1 创建分支时的阻断项

- 未填写分支原因；
- 未选择父节点，且当前也不是在创建新 root；
- 新增数据集为空；
- 新增数据集与父节点已有集合完全重复；
- 试图删除父节点已有数据；
- 新类别破坏旧类别索引；
- 模型任务类型与新增数据集不匹配。

创建 root 时额外阻断：

- 首个 root 未配置初始数据集；
- 新 root 与现有 root 的模型来源和数据来源完全重复；
- root 初始数据集为空。

### 14.2 启动训练时的阻断项

- 父节点没有可用权重；
- 生效训练数据为空；
- 生成后的数据 YAML 无法解析；
- 覆盖参数非法；
- 多验证集配置无效；
- 当前节点已在训练中。

### 14.3 风险提示

- 本节点只增加了很少数据，可能收益有限；
- 新类别数据比例过高，旧类别可能退化；
- 覆盖参数偏离目标默认值过大；
- 没有附加专项验证集，难以证明本次分支价值；
- 当前节点指标低于父节点。

## 15. 推荐实施顺序

### P0

- 新增训练目标概念；
- 允许一个目标下维护多个 root；
- 新增节点树与父子关系；
- 分支原因必填；
- 子节点数据集只允许加法；
- 目标默认参数 + 节点覆盖参数；
- toolchain 公共接口 + `yolo` 适配；
- 保持现有训练方法执行。

### P1

- 多验证集配置；
- 节点训练后逐个验证集评估；
- 节点详情展示参数继承链；
- 目标详情展示瀑布流树。

### P2

- 自动推荐最佳节点；
- 节点评估结论与风险提示；
- 分支间指标对比；
- 更完整的回归报告。

## 16. 最终结论

新的训练页面不再服务于“一次性发起训练”，而是服务于“围绕一个训练目标持续演进模型”。

最关键的六个约束是：

1. 只保留训练目标入口；
2. 一个目标可以有多个 root，所有训练节点都挂在某个 root 或父节点下；
3. 每个分支必须说明分支原因；
4. 子节点只允许对父节点数据集做加法；
5. 每次训练只做默认参数继承或局部调整；
6. 每次训练都可以挂多个验证集做独立评估。

底层训练仍然走现有方式，但会先经过统一 toolchain 接口；上层组织模型从“单任务表单”升级为“目标树 + 分支演进 + 多验证集评估”。
