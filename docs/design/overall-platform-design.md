# XYolo 整体平台设计

## 1. 当前状态

当前 XYolo 已经具备两个实际入口：

1. `xyolo train`
2. `xyolo web`

仓库中已经形成了几份关键设计文档：

1. `training-page.md`
2. `evaluation-metrics.md`
3. `toolchain-interface.md`
4. `dataset-management.md`
5. `multi-end-login.md`

这些文档分别解决了训练、评估、工具链、数据集、身份的问题，但还缺一份**整体总览文档**，把它们收敛成统一平台架构。

本文档就是这份总览。

## 2. 平台目标

XYolo 后续不应只被定义为“一个 YOLO 启动器”。

更准确地说，它要逐步演进成一个围绕视觉模型训练闭环的平台，统一管理：

1. 数据来源；
2. 标注资产；
3. 数据集版本；
4. 训练目标与训练树；
5. 评估基准与最优模型；
6. 模型产物与发布；
7. 多端访问与权限。

## 3. 总体设计原则

### 3.1 业务对象优先于文件路径

平台上层不应该围绕：

1. 某个 YAML 文件；
2. 某个目录；
3. 某个训练命令；

组织系统。

上层应该围绕：

1. `DatasetVersion`
2. `TrainingGoal`
3. `TrainingNode`
4. `BenchmarkSet`
5. `ModelArtifact`
6. `Project`

组织系统。

### 3.2 训练、评估、数据、权限四条线统一建模

四条线分别解决不同问题：

1. **数据线**：数据从哪来，怎么标，如何发布；
2. **训练线**：模型如何从 root 持续分支演进；
3. **评估线**：模型如何被稳定比较和推荐；
4. **权限线**：谁能看、谁能改、谁能运行。

整体架构的价值就在于把这四条线打通。

### 3.3 工具链下沉，业务层稳定

YOLO 只是第一阶段工具链，不应成为整个系统的抽象中心。

业务层稳定对象应是：

1. 数据集版本；
2. 训练节点；
3. 评估结果；
4. 模型产物；

而不是某个具体框架的 `kwargs`。

## 4. 平台分层

整体建议拆成六层：

```text
┌─────────────────────────────────────────────┐
│ 1. Access Layer                             │
│    Web / CLI / Open API / Future Desktop    │
├─────────────────────────────────────────────┤
│ 2. Identity & Project Layer                 │
│    User / Org / Project / RBAC / Tokens     │
├─────────────────────────────────────────────┤
│ 3. Domain Layer                             │
│    Dataset / Annotation / Goal / Eval /     │
│    Model / Deploy                           │
├─────────────────────────────────────────────┤
│ 4. Orchestration Layer                      │
│    Task / Worker / Pipeline / Scheduling    │
├─────────────────────────────────────────────┤
│ 5. Toolchain & Integration Layer            │
│    YoloAdapter / CVAT / FiftyOne /          │
│    Datumaro / DVC / ClearML / lakeFS        │
├─────────────────────────────────────────────┤
│ 6. Artifact & Storage Layer                 │
│    Sources / Samples / Labels / Datasets /  │
│    Models / Logs / Metrics                  │
└─────────────────────────────────────────────┘
```

## 5. 业务主链路

平台最核心的主链路应是：

```text
SourceAsset
  -> ImportBatch
  -> Sample
  -> AnnotationVersion
  -> DatasetVersion
  -> TrainingGoal
  -> TrainingNode
  -> Task
  -> ModelArtifact
  -> BenchmarkSet
  -> EvaluationResult
  -> BestNode
```

这个链路把此前分散的设计文档串成了一条完整闭环。

## 6. 核心模块

### 6.1 身份与项目模块

由 `multi-end-login.md` 定义，负责：

1. 用户；
2. 组织；
3. 项目；
4. 登录态；
5. API token；
6. Service account；
7. 权限控制。

这是所有后续模块的横切基础。

### 6.2 数据集管理模块

由 `dataset-management.md` 定义，负责：

1. `SourceAsset`
2. `ImportBatch`
3. `Sample`
4. `AnnotationProject`
5. `AnnotationVersion`
6. `DatasetSlice`
7. `DatasetVersion`
8. `BenchmarkSet`

这是训练和评估的统一数据底座。

### 6.3 训练目标模块

由 `training-page.md` 定义，负责：

1. `TrainingGoal`
2. 多 root 管理；
3. 训练分支树；
4. `branch_reason`；
5. `root_dataset_version_ids / added_dataset_version_ids / effective_dataset_version_ids`；
6. 默认参数与节点覆盖参数。

这是平台的模型迭代主轴。

### 6.4 评估模块

由 `evaluation-metrics.md` 定义，负责：

1. 多验证集角色；
2. 原始指标归一化；
3. `dataset_score`；
4. `node_score`；
5. `best_node_id`；
6. 风险和结论。

这是平台的自动决策层。

### 6.5 工具链模块

由 `toolchain-interface.md` 定义，负责：

1. `ToolchainDefinition`
2. `TrainRequest`
3. `EvaluationRequest`
4. `TrainResult`
5. `EvaluationResult`
6. `ModelArtifact`
7. `DatasetArtifact`

这是平台与 YOLO、未来 Torch 等执行引擎的边界。

## 7. 各模块之间的关系

### 7.1 数据与训练

训练节点不直接引用 YAML，而是引用 `DatasetVersion`。

流程：

1. root 节点指定 `root_dataset_version_ids`；
2. 子节点指定 `added_dataset_version_ids`；
3. 系统计算 `effective_dataset_version_ids`；
4. 发布层生成 `DatasetArtifact`；
5. 工具链消费 `DatasetArtifact`。

### 7.2 训练与评估

训练完成不等于评估完成，但两者天然相邻：

1. 训练产出 `ModelArtifact`；
2. 节点挂载 `BenchmarkSet`；
3. 系统生成多个 `EvaluationRequest`；
4. 评估结果写回节点；
5. 系统重新计算 `best_node_id`。

### 7.3 权限与业务对象

所有核心对象都应挂：

1. `org_id`
2. `project_id`
3. `created_by`

这样：

1. 数据集不会越权可见；
2. 训练任务不会跨项目串用；
3. 评估结果不会被其他租户读取；
4. 模型产物可以审计来源。

## 8. 多端形态

### 8.1 Web

Web 是最完整的平台操作端，负责：

1. 数据集管理；
2. 训练目标树管理；
3. 评估结果浏览；
4. 模型选择与发布；
5. 系统配置。

### 8.2 CLI

CLI 不只是训练命令入口，未来应逐步补齐：

```text
xyolo auth
xyolo dataset
xyolo train
xyolo eval
xyolo model
xyolo deploy
```

CLI 更适合：

1. 自动化；
2. CI/CD；
3. 批处理；
4. 离线环境。

### 8.3 Open API

Open API 是系统与外部生态打通的关键：

1. 数据导入；
2. 标注回调；
3. 任务触发；
4. 报表读取；
5. 外部调度集成。

## 9. 参考系统与借鉴点

以下开源项目与 XYolo 未来形态最契合：

| 系统 | GitHub | 最值得借鉴的部分 |
|---|---|---|
| FiftyOne | https://github.com/voxel51/fiftyone | 样本级浏览、数据集视图、评估可视化、错误分析 |
| CVAT | https://github.com/cvat-ai/cvat | 标注项目、协作流程、任务分发、质量控制 |
| Datumaro | https://github.com/open-edge-platform/datumaro | 数据集变换、版本派生、格式转换、QA |
| DVC | https://github.com/iterative/dvc | 数据版本、实验绑定、可复现性 |
| ClearML | https://github.com/allegroai/clearml | 实验/任务/agent/模型闭环 |
| lakeFS | https://github.com/treeverse/lakeFS | 数据湖级版本控制、branch/commit/merge |
| Label Studio | https://github.com/HumanSignal/label-studio | 通用标注与可嵌入标注体验 |

## 10. 这些参考系统如何映射到 XYolo

### 10.1 数据与标注侧

最接近的组合是：

1. **CVAT / Label Studio**：标注入口；
2. **Datumaro**：标注结果转换、merge/split、版本发布；
3. **FiftyOne**：样本浏览、错误分析、数据观察。

映射到 XYolo：

| XYolo 概念 | 更像哪类参考系统能力 |
|---|---|
| `AnnotationProject / AnnotationBatch` | CVAT / Label Studio |
| `AnnotationVersion / DatasetSlice / DatasetVersion` | Datumaro |
| `Sample view / 评估可视化 / 数据巡检` | FiftyOne |

### 10.2 训练与实验侧

最接近的组合是：

1. **ClearML**：任务、agent、实验对比；
2. **DVC**：数据版本绑定实验；
3. **FiftyOne**：评估结果可视分析。

映射到 XYolo：

| XYolo 概念 | 更像哪类参考系统能力 |
|---|---|
| `Task / Worker / ModelArtifact` | ClearML |
| `DatasetVersion lineage` | DVC / lakeFS |
| `BenchmarkSet / EvaluationResult` | FiftyOne + 自定义评估策略 |

### 10.3 XYolo 不应直接照搬的部分

这些项目都很强，但 XYolo 不应原样拼接：

1. 不应把实验系统直接当业务主模型；
2. 不应把标注平台直接当数据资产主存储；
3. 不应把数据版本工具直接当训练目标树；
4. 不应把 YOLO 私有参数上浮成平台公共协议。

XYolo 应做的是**统一业务抽象，然后在边界层集成这些能力**。

## 11. 推荐目标架构

### 11.1 第一阶段目标

以当前仓库现状为基础，先完成平台骨架：

1. 用户/项目体系；
2. 数据集版本与 BenchmarkSet；
3. 训练目标树；
4. 评估指标体系；
5. YoloAdapter；
6. Web 主操作端；
7. CLI 基础自动化能力。

这一阶段重点是把文档里已经定义的对象真正打通。

### 11.2 第二阶段目标

在不推翻第一阶段的前提下，增加外部集成：

1. 接 CVAT / Label Studio；
2. 接 Datumaro；
3. 接 FiftyOne；
4. 接 DVC 或 lakeFS；
5. 接 ClearML 或保留自主任务体系并做桥接。

### 11.3 第三阶段目标

扩展成完整平台：

1. 多工具链；
2. 更完整的部署链路；
3. 更强的报表和观测；
4. 更完整的组织协同与审计。

## 12. 页面与信息架构

顶部导航建议保持：

`数据集 / 训练 / 模型 / 评估 / 部署`

并按以下方式展开：

### 12.1 数据集

1. 来源
2. 标注
3. 数据集版本
4. Benchmark

### 12.2 训练

1. 训练目标列表
2. 目标详情
3. 瀑布流训练树
4. 节点执行记录

### 12.3 模型

1. 当前推荐模型
2. 历史模型
3. 模型对比
4. 模型发布记录

### 12.4 评估

1. Benchmark 列表
2. 节点评估结果
3. 排行榜
4. 回归告警

### 12.5 部署

1. 发布目标
2. 版本记录
3. 回滚记录
4. 线上反馈闭环

## 13. 数据契约总览

核心对象建议形成以下骨架：

```json
{
  "project": {},
  "dataset_version": {},
  "training_goal": {},
  "training_node": {},
  "benchmark_set": {},
  "task": {},
  "model_artifact": {},
  "evaluation_result": {}
}
```

这些对象之间至少应满足：

1. `dataset_version.project_id = training_goal.project_id`
2. `training_node.goal_id -> training_goal.id`
3. `task.node_id -> training_node.id`
4. `model_artifact.source.node_id -> training_node.id`
5. `benchmark_set.project_id = training_goal.project_id`
6. `evaluation_result.node_id -> training_node.id`

## 14. 推荐实施顺序

### P0

1. 完成身份与项目边界；
2. 数据集版本和 BenchmarkSet；
3. 训练目标树切到 `dataset_version_id`；
4. 评估体系切到 `BenchmarkSet`；
5. 保持当前 YOLO 执行方式不变。

### P1

1. 引入标注项目与标注版本；
2. 增加样本与来源管理；
3. 增加外部集成适配层；
4. 增加 CLI 登录与 Open API。

### P2

1. 接入外部参考系统；
2. 增加更强的可视分析；
3. 增加模型发布与部署闭环；
4. 增加多工具链。

## 15. 最终结论

XYolo 的整体方向可以总结成一句话：

**以项目为边界，以数据集版本为底座，以训练目标树为主轴，以 Benchmark 评估为决策层，以工具链适配为执行边界。**

这也是把现有几份设计文档和参考系统整合后的统一结论：

1. **数据集管理** 负责把来源、标注、版本整理成稳定资产；
2. **训练目标树** 负责把模型迭代表达成可追溯的演进过程；
3. **评估体系** 负责把多验证集结果转成可比较、可推荐的结论；
4. **多端登录** 负责把 Web、CLI、Open API 与项目权限统一起来；
5. **工具链接口** 负责让 YOLO 先落地，同时为未来多工具链扩展留边界。

落地后，XYolo 就不再只是“训练一个模型”，而是变成一套完整的视觉数据与模型演进平台。
