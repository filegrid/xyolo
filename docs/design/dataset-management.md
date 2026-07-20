# 数据集管理与训练评估打通设计

## 1. 当前状态

目前仓库里已经有三块相邻设计，但“数据集”这一层还没有单独立起来：

1. `training-page.md` 已经定义了**训练目标 / root / 节点树 / 数据集只做加法**；
2. `evaluation-metrics.md` 已经定义了**多验证集 / 角色 / 综合评分 / best node**；
3. `toolchain-interface.md` 已经定义了**TrainRequest / EvaluationRequest / DatasetArtifact**。

但当前仍然缺一层关键抽象：

- 数据集本身如何建模；
- 数据集与原始来源、导入批次、标注结果之间是什么关系；
- 训练集、验证集、基准评估集如何复用同一套数据资产；
- 数据集版本如何追溯到“这批数据从哪来、谁标的、为什么产生”；
- 训练节点里的 `added_datasets` 到底加的是什么对象。

所以现在的问题不是“没有训练设计”或“没有评估设计”，而是**训练和评估中引用的数据对象还没有统一的数据集管理层**。

本文档用于补上这一层。

## 2. 设计目标

这套数据集管理方案要解决六件事：

1. 统一管理原始数据来源、导入批次、样本、标注结果和可训练数据集版本；
2. 让训练节点和评估节点都引用同一套可追溯的数据资产；
3. 支持数据集之间的父子关系、组合关系、派生关系和替换关系；
4. 支持“标注数据”和“训练数据”解耦，但又能精确关联；
5. 支持来源透明，能明确回答“这次训练到底用了哪些数据、这些数据从哪来”；
6. 保持与现有训练/评估设计兼容，最终仍落到统一 `TrainRequest / EvaluationRequest`。

## 3. 适用范围

适用于以下对象：

1. `detect`
2. `segment`
3. `pose`

适用于以下流程：

1. 原始数据导入；
2. 标注任务生成与回流；
3. 数据集版本发布；
4. 训练节点选数；
5. 评估基准集挂载；
6. 模型结果回溯到数据。

不在本文档范围内：

1. 具体标注平台产品选型；
2. 具体对象存储或 NAS 选型；
3. 具体数据库实现细节。

## 4. 基本原则

### 4.1 数据资产分层，不把所有东西都叫 dataset

“数据集”在这里不能同时指代原图、标注任务、训练 YAML、验证集和评估集。

至少要区分五层：

1. **来源层**：数据从哪来；
2. **样本层**：具体有哪些图片/视频帧；
3. **标注层**：这些样本上有哪些标注版本；
4. **切片层**：从样本和标注里挑出了哪一批可用样本；
5. **发布层**：一个可被训练/评估直接消费的数据集版本。

### 4.2 训练和评估都引用“已发布数据集版本”

训练页、评估页都不应该直接拿“某个目录”或“某个 YAML 路径”当业务主对象。

上层应统一引用：

- `dataset_version_id`
- `benchmark_id`
- `annotation_version_id`

而具体生成给 YOLO 的 `yaml`、未来给 Torch 的 manifest，由数据集发布层负责。

### 4.3 标注结果不是训练集本身

标注结果是样本上的一种解释结果，不等于训练集。

同一批标注结果可以派生出多个数据集版本，例如：

1. 全量训练集；
2. 去重后训练集；
3. 夜间专项集；
4. 只保留高质量样本的基准评估集。

也就是说：

- **annotation** 解决“怎么标”；
- **dataset version** 解决“拿哪些样本、以什么规则发布给训练或评估”。

### 4.4 所有可训练数据都必须可追溯

任何一个训练节点的有效数据，都必须能反查出：

1. 包含了哪些数据集版本；
2. 每个版本来自哪些来源；
3. 每个版本基于哪些样本；
4. 每个样本使用了哪一版标注；
5. 是否存在人工过滤、重采样、类别映射。

### 4.5 训练集和评估集都属于数据集体系，但角色不同

训练和评估都消费“发布后的数据集版本”，只是用途不同：

1. **train**：参与梯度更新；
2. **validation**：训练后即时验证；
3. **benchmark**：目标级长期稳定评估；
4. **observe**：只看不参与排序。

这样训练页和评估页可以共享一套数据底座。

## 5. 核心对象

## 5.1 SourceAsset

表示原始来源。

```json
{
  "id": "source-site-a-camera-01",
  "type": "camera",
  "name": "Site A Camera 01",
  "owner": "factory-a",
  "provider": "internal",
  "description": "A 厂区东门固定摄像头",
  "task": "detect",
  "status": "active",
  "metadata": {
    "location": "gate-east",
    "device_model": "hikvision-xx"
  }
}
```

来源类型可以包括：

1. `camera`
2. `upload`
3. `customer_delivery`
4. `public_dataset`
5. `synthetic`
6. `third_party`

这个对象回答的是：**数据来自哪里**。

## 5.2 ImportBatch

表示一次实际导入动作。

```json
{
  "id": "import-20260718-site-a-001",
  "source_id": "source-site-a-camera-01",
  "kind": "image",
  "input_uri": "oss://raw/site-a/2026-07-18/",
  "import_reason": "补充早晚高峰样本",
  "created_by": "tommy",
  "stats": {
    "files": 12840
  },
  "status": "completed"
}
```

同一个来源可以产生多次导入批次。

这个对象回答的是：**这批数据是什么时候、因为什么原因进入系统的**。

## 5.3 Sample

表示被系统纳管的单个样本。

```json
{
  "id": "sample-000001",
  "import_batch_id": "import-20260718-site-a-001",
  "source_id": "source-site-a-camera-01",
  "content_type": "image",
  "uri": "oss://raw/site-a/2026-07-18/000001.jpg",
  "capture_time": "2026-07-18T08:30:01Z",
  "checksum": "sha256:xxx",
  "width": 1920,
  "height": 1080,
  "tags": [
    "daylight",
    "gate",
    "helmet-scene"
  ]
}
```

样本是后续标注、切片、发布的最小单位。

## 5.4 AnnotationProject

表示一类标注任务容器。

```json
{
  "id": "anno-person-helmet",
  "name": "Person Helmet Annotation",
  "task": "detect",
  "label_schema_id": "schema-person-helmet-v2",
  "description": "人员与安全帽检测标注项目"
}
```

标注项目和训练目标不必一一绑定，但通常会强相关。

## 5.5 AnnotationBatch

表示一次发出去的标注批次。

```json
{
  "id": "anno-batch-20260718-01",
  "project_id": "anno-person-helmet",
  "sample_ids": [
    "sample-000001",
    "sample-000002"
  ],
  "label_source": "manual",
  "vendor": "label-team-a",
  "status": "accepted"
}
```

这个对象回答的是：**哪些样本被送去标注、由谁标、结果是否验收**。

## 5.6 AnnotationVersion

表示一组经过验收、可复用的标注结果版本。

```json
{
  "id": "annotation-person-helmet-v12",
  "project_id": "anno-person-helmet",
  "label_schema_id": "schema-person-helmet-v2",
  "sample_count": 8420,
  "source_batches": [
    "anno-batch-20260718-01"
  ],
  "quality_status": "approved",
  "export_format": "yolo",
  "status": "published"
}
```

关键点：

1. `AnnotationBatch` 是过程对象；
2. `AnnotationVersion` 是可被后续切片/发布复用的稳定结果对象。

## 5.7 DatasetSlice

表示从样本 + 标注里根据某个规则切出来的一批候选数据。

```json
{
  "id": "slice-night-scenes-v1",
  "task": "detect",
  "annotation_version_id": "annotation-person-helmet-v12",
  "filter_spec": {
    "tags": ["night"],
    "quality_status": ["approved"]
  },
  "sample_count": 1320,
  "purpose": "scenario"
}
```

这个对象很重要，因为训练时经常不是直接吃整版标注，而是先切片。

## 5.8 DatasetVersion

表示最终发布给训练或评估直接使用的数据集版本。

```json
{
  "id": "dataset-person-helmet-base-v3",
  "name": "person-helmet-base",
  "version": 3,
  "task": "detect",
  "usage": "train",
  "status": "published",
  "class_schema_id": "schema-person-helmet-v2",
  "composition": [
    {
      "type": "slice",
      "ref_id": "slice-base-scenes-v3"
    },
    {
      "type": "slice",
      "ref_id": "slice-hard-negatives-v1"
    }
  ],
  "stats": {
    "images": 8420,
    "objects": 26100
  },
  "artifacts": {
    "yolo_yaml": "datasets/person-helmet-base-v3.yaml"
  }
}
```

`DatasetVersion` 是训练页里最核心的数据对象。

训练节点里的 `added_datasets` 应加的就是它，而不是原始目录。

## 5.9 BenchmarkSet

表示一个稳定评估基准。

```json
{
  "id": "benchmark-person-helmet-regression-v1",
  "name": "person-helmet-regression",
  "task": "detect",
  "role": "regression",
  "dataset_version_id": "dataset-person-helmet-regression-v1",
  "weight": 0.30,
  "is_required": true,
  "status": "active"
}
```

评估体系里挂的主验证集、回归集、专项集，建议都落成 `BenchmarkSet`。

## 6. 数据对象之间的关系

核心关系如下：

```text
SourceAsset
  └── ImportBatch
        └── Sample
              ├── AnnotationBatch
              │     └── AnnotationVersion
              └── DatasetSlice
                      └── DatasetVersion
                            ├── Train usage
                            └── BenchmarkSet / Eval usage
```

更完整地说：

1. 一个 `SourceAsset` 可以有多个 `ImportBatch`；
2. 一个 `ImportBatch` 可以导入多个 `Sample`；
3. 一个 `Sample` 可以被多个 `AnnotationBatch` 重复标注或复审；
4. 多个 `AnnotationBatch` 可汇总为一个稳定 `AnnotationVersion`；
5. 一个 `AnnotationVersion` 可以派生多个 `DatasetSlice`；
6. 多个 `DatasetSlice` 可以组合成一个 `DatasetVersion`；
7. 一个 `DatasetVersion` 可以同时用于训练集发布和评估基准发布；
8. 一个 `BenchmarkSet` 本质上是“带角色与权重的数据集版本引用”。

## 7. 数据集之间的关系模型

数据集不仅要有“版本号”，还要能表达相互关系。

建议支持以下关系：

| relation_type | 含义 | 示例 |
|---|---|---|
| `derived_from` | 从某个数据集版本派生 | `night-v2` derived from `base-v3` |
| `composed_of` | 由多个切片或子集组合 | `merged-v5` composed of `city-a-v2` + `city-b-v1` |
| `incremental_to` | 作为某个版本的增量包 | `rain-addon-v1` incremental to `base-v3` |
| `benchmark_of` | 作为某训练目标的评估基准 | `regression-v1` benchmark of `goal-person-helmet` |
| `relabels` | 对旧样本重标 | `annotation-v12` relabels `annotation-v10` |
| `replaces` | 新版本替代旧版本 | `base-v4` replaces `base-v3` |
| `subset_of` | 是某版本的子集 | `night-v1` subset of `base-v3` |
| `same_samples_as` | 样本相同但标注版本不同 | `base-v3-labelfix` same samples as `base-v3` |

建议单独维护 `dataset_relations`：

```json
{
  "from_dataset_id": "dataset-night-addon-v1",
  "to_dataset_id": "dataset-person-helmet-base-v3",
  "relation_type": "incremental_to",
  "description": "夜间数据增量包"
}
```

这样训练树里的“加法”就能精确表达成：

1. root 节点引用若干 `DatasetVersion`；
2. 子节点新增的 `DatasetVersion` 与父节点数据通常是 `incremental_to` 或 `subset_of` 关系；
3. 系统既能看树上的训练关系，也能看数据资产本身的派生关系。

## 8. 与标注数据的关系

### 8.1 一个数据集版本必须显式绑定标注版本

`DatasetVersion` 不能只知道图片从哪来，还必须知道标签从哪来。

建议至少记录：

1. `annotation_version_id`
2. `label_schema_id`
3. `class_schema_id`
4. `label_transform_spec`

例如：

```json
{
  "id": "dataset-person-helmet-base-v3",
  "annotation_version_id": "annotation-person-helmet-v12",
  "label_schema_id": "schema-person-helmet-v2",
  "label_transform_spec": {
    "drop_classes": [],
    "merge_classes": [],
    "remap": {}
  }
}
```

### 8.2 允许同样本不同标注版本并存

有时需要重标或修标。

这时不应覆盖旧训练记录，而应允许：

1. 相同 `sample_ids`；
2. 不同 `annotation_version_id`；
3. 派生出新的 `DatasetVersion`。

这样可以精确分析：

- 是新增样本带来的收益；
- 还是重标质量提升带来的收益。

### 8.3 类别体系是独立约束

训练树里已经要求类别只能追加、不允许重排旧索引。

因此数据集管理层也要记录类别模式：

```json
{
  "id": "schema-person-helmet-v2",
  "task": "detect",
  "classes": [
    {"id": 0, "name": "person"},
    {"id": 1, "name": "helmet"}
  ]
}
```

数据集版本发布时必须校验：

1. 标注类别是否落在 schema 内；
2. 相对父训练节点是否只追加类别；
3. 是否存在旧类别索引重排。

## 9. 来源管理设计

来源管理至少要覆盖四个问题：

1. 数据从哪来；
2. 谁导入的；
3. 是否可商用/可训练；
4. 是否有使用限制。

建议 `SourceAsset` 增加以下字段：

| 字段 | 含义 |
|---|---|
| `owner` | 业务归属 |
| `provider` | 数据提供方 |
| `license` | 数据授权方式 |
| `retention_policy` | 保留策略 |
| `allowed_usages` | 允许训练/评估/展示/导出 |
| `sensitivity` | 是否敏感 |
| `region` | 数据区域 |

每个 `DatasetVersion` 都应能汇总展示其来源构成，例如：

| 来源 | 样本数 | 占比 | 最近导入批次 | 备注 |
|---|---:|---:|---|---|
| site-a-camera-01 | 5200 | 61.8% | import-20260718-site-a-001 | 主来源 |
| site-b-camera-02 | 2400 | 28.5% | import-20260710-site-b-003 | 补充逆光场景 |
| public-helmet-v1 | 820 | 9.7% | import-public-001 | 外部公开数据 |

这样用户在训练前就能看到这次数据构成。

## 10. 训练流程如何接入数据集管理

### 10.1 训练节点不再直接选 YAML 路径

训练页里原来的 `data=xxx.yaml`，在业务层不应再手工填写。

新流程应改成：

1. 用户在节点上选择 `added_dataset_version_ids`；
2. 系统根据父节点拿到 `effective_dataset_version_ids`；
3. 系统合并后生成当前节点的 `effective_dataset_manifest`；
4. 再落成工具链可消费的 `DatasetArtifact`。

### 10.2 与训练树的对齐方式

沿用 `training-page.md` 的约束：

1. root 节点配置 `root_dataset_version_ids`；
2. 子节点配置 `added_dataset_version_ids`；
3. `effective_dataset_version_ids = parent + added`；
4. 子节点不能移除父节点已有数据集版本。

节点数据建议改成：

```json
{
  "id": "node-002",
  "goal_id": "goal-person-helmet",
  "parent_id": "node-001",
  "added_dataset_version_ids": [
    "dataset-night-addon-v1"
  ],
  "effective_dataset_version_ids": [
    "dataset-person-helmet-base-v3",
    "dataset-night-addon-v1"
  ],
  "effective_dataset_artifact": {
    "artifact_id": "dataset-effective-node-002",
    "path": "web/tasks/task-20260718-001/data.effective.yaml",
    "format": "yolo-yaml"
  }
}
```

### 10.3 训练前校验

启动训练前至少要校验：

1. 所有数据集版本都处于 `published`；
2. 任务类型一致；
3. 类别 schema 兼容；
4. 数据来源授权允许训练；
5. 数据集版本对应的标注版本已验收；
6. 样本路径可访问；
7. 发布产物可生成目标 toolchain 所需格式。

### 10.4 训练后回写

训练完成后，应把结果回写到数据和模型关系中：

1. 该训练节点消费了哪些 `DatasetVersion`；
2. 每个版本贡献了多少样本；
3. 该节点模型在哪些 `BenchmarkSet` 上评估过；
4. 评估结果是否显示某个来源或某个切片有问题。

## 11. 评估流程如何接入数据集管理

### 11.1 验证集统一升级为 BenchmarkSet 引用

`evaluation-metrics.md` 里已经有 `primary / regression / scenario / observe`。

建议把这些从“裸 YAML 路径”升级成：

```json
{
  "benchmark_id": "benchmark-night-val-v1",
  "dataset_version_id": "dataset-night-benchmark-v1",
  "role": "scenario",
  "weight": 0.20,
  "is_required": true
}
```

这样评估页不只知道“在哪个 yaml 上评”，还能知道：

1. 这套基准是谁维护的；
2. 基于哪版标注；
3. 是否冻结；
4. 是否可参与最优模型排序。

### 11.2 训练后即时评估

每个训练节点训练完成后：

1. 产出模型产物；
2. 遍历该节点挂载的 `BenchmarkSet`；
3. 为每个 `BenchmarkSet` 生成 `EvaluationRequest`；
4. 保存原始指标、归一化指标、基准引用关系。

### 11.3 长期基准与临时验证集分离

建议把评估数据分两类：

1. **benchmark**：目标级长期稳定，不轻易改；
2. **ad hoc validation**：节点临时附加，用于专项试验。

二者都走统一结构，但只有 benchmark 会进入长期比较和 `best_node_id` 计算的默认候选。

## 12. 发布层设计

数据集管理层需要一个明确的“发布”动作。

原因是：

1. 原始样本可能还没清洗；
2. 标注版本可能还没验收；
3. 切片规则可能还在变；
4. 训练和评估必须引用稳定快照。

建议引入发布态：

| 状态 | 含义 |
|---|---|
| `draft` | 草稿，规则可改 |
| `reviewing` | 待审核 |
| `published` | 可供训练/评估使用 |
| `deprecated` | 不建议新任务继续使用 |
| `archived` | 冻结，只保留历史追溯 |

只有 `published` 状态能挂到训练节点或评估基准上。

## 13. 前后端数据契约建议

### 13.1 数据集版本

```json
{
  "id": "dataset-person-helmet-base-v3",
  "name": "person-helmet-base",
  "version": 3,
  "task": "detect",
  "usage": "train",
  "status": "published",
  "annotation_version_id": "annotation-person-helmet-v12",
  "class_schema_id": "schema-person-helmet-v2",
  "source_summary": [
    {
      "source_id": "source-site-a-camera-01",
      "sample_count": 5200
    }
  ],
  "composition": [
    {
      "type": "slice",
      "ref_id": "slice-base-scenes-v3"
    }
  ],
  "artifacts": {
    "yolo_yaml": "datasets/person-helmet-base-v3.yaml"
  }
}
```

### 13.2 基准集

```json
{
  "id": "benchmark-person-helmet-regression-v1",
  "goal_id": "goal-person-helmet",
  "dataset_version_id": "dataset-person-helmet-regression-v1",
  "role": "regression",
  "weight": 0.30,
  "is_required": true,
  "status": "active"
}
```

### 13.3 训练节点

```json
{
  "id": "node-002",
  "goal_id": "goal-person-helmet",
  "parent_id": "node-001",
  "added_dataset_version_ids": [
    "dataset-night-addon-v1"
  ],
  "effective_dataset_version_ids": [
    "dataset-person-helmet-base-v3",
    "dataset-night-addon-v1"
  ],
  "benchmark_ids": [
    "benchmark-person-helmet-primary-v1",
    "benchmark-person-helmet-regression-v1",
    "benchmark-night-val-v1"
  ]
}
```

### 13.4 发布后的训练请求

最终训练仍落到工具链接口：

```json
{
  "toolchain": "yolo",
  "operation": "train",
  "task": "detect",
  "dataset": {
    "artifact_id": "dataset-effective-node-002",
    "path": "web/tasks/task-20260718-001/data.effective.yaml",
    "format": "yolo-yaml"
  }
}
```

也就是说：

1. 上层业务引用 `DatasetVersion`；
2. 发布层生成 `DatasetArtifact`；
3. 工具链继续消费 `DatasetArtifact`。

## 14. 页面信息架构建议

顶部导航仍保持：

`数据集 / 训练 / 模型 / 评估 / 部署`

其中“数据集”建议拆成四块：

1. **来源**
2. **标注**
3. **数据集版本**
4. **评估基准**

### 14.1 数据集列表页

| 列 | 内容 |
|---|---|
| 数据集名称 | `person-helmet-base` |
| 版本 | `v3` |
| 用途 | train / benchmark |
| 任务类型 | detect / segment / pose |
| 标注版本 | `annotation-v12` |
| 来源数 | 3 |
| 样本数 | 8420 |
| 状态 | published / deprecated |

### 14.2 数据集详情页

至少展示：

1. 基本信息；
2. 来源构成；
3. 标注版本；
4. 样本筛选规则；
5. 派生关系图；
6. 被哪些训练节点引用；
7. 被哪些基准集引用。

### 14.3 来源详情页

至少展示：

1. 来源元信息；
2. 导入历史；
3. 样本增长趋势；
4. 已进入哪些数据集版本；
5. 相关训练效果摘要。

### 14.4 标注详情页

至少展示：

1. 标注项目；
2. 标注批次；
3. 验收状态；
4. 类别 schema；
5. 标注版本派生出的数据集版本。

## 15. 关键查询能力

这套系统至少要能支持以下查询：

1. 某个训练节点到底用了哪些数据集版本；
2. 某个数据集版本来自哪些来源；
3. 某个来源被哪些训练节点使用过；
4. 某个样本使用的是哪版标注；
5. 某个 benchmark 最近一次何时更新；
6. 某个模型退化是否只发生在某个来源或某个场景切片；
7. 某个新数据集上线后是否确实带来了专项提升。

这也是为什么数据关系必须显式建模，而不能只靠目录结构。

## 16. 约束与校验

### 16.1 发布数据集版本时

- 未绑定标注版本；
- 样本为空；
- 类别 schema 非法；
- 来源授权不允许训练或评估；
- 同一版本既声明为 benchmark 冻结集，又允许继续增删样本；
- 生成产物失败。

### 16.2 训练节点引用数据集时

- 数据集版本未发布；
- 与父节点任务类型不一致；
- 类别 schema 不兼容；
- 试图移除父节点已生效数据集；
- 新增数据集与父节点完全重复且无新增价值。

### 16.3 创建 benchmark 时

- 数据集版本不是冻结快照；
- 缺少角色；
- 权重非法；
- 与目标任务类型不一致；
- 标注版本未验收。

## 17. 推荐实施顺序

### P0

1. 补齐 `DatasetVersion` 概念；
2. 训练节点从 YAML 路径切到 `dataset_version_id`；
3. 增加 `BenchmarkSet`；
4. 训练后评估统一引用 `BenchmarkSet`；
5. 发布层负责生成 `DatasetArtifact`；
6. 保持现有 `yolo` 执行流程不变。

### P1

1. 增加 `SourceAsset / ImportBatch / Sample`；
2. 增加 `AnnotationProject / AnnotationVersion`；
3. 数据集详情页展示来源与标注链路；
4. 训练和评估页面可回溯来源构成。

### P2

1. 增加 `DatasetSlice` 与切片规则管理；
2. 增加数据集关系图；
3. 增加按来源/场景/类别的评估对比；
4. 增加“某批数据是否提升模型”的闭环分析。

## 18. 与现有设计文档的对应关系

### 18.1 对 `training-page.md` 的补充

`training-page.md` 里提到的：

- `root_datasets`
- `added_datasets`
- `effective_datasets`

建议都升级成：

- `root_dataset_version_ids`
- `added_dataset_version_ids`
- `effective_dataset_version_ids`

也就是说，训练树的“数据集加法”不再是文件路径加法，而是**已发布数据集版本**的加法。

### 18.2 对 `evaluation-metrics.md` 的补充

`evaluation-metrics.md` 里的验证集角色继续保留，但落地对象改成 `BenchmarkSet`。

这样 `primary / regression / scenario / observe` 不只是展示字段，而是有稳定数据集快照支撑。

### 18.3 对 `toolchain-interface.md` 的补充

`toolchain-interface.md` 里的 `DatasetArtifact` 继续保留，不需要推翻。

只是其上游从手工 YAML 改成：

`DatasetVersion -> publish -> DatasetArtifact`

这样业务层和工具链层边界会更清晰。

## 19. 最终结论

这套方案的核心不是“再加一个数据集页面”，而是把数据真正变成系统里的一级对象：

1. **来源可管**：知道数据从哪来、谁导入、能不能用；
2. **标注可追**：知道每个数据集版本绑定哪版标签；
3. **关系可算**：知道数据集之间是增量、派生、替换还是子集关系；
4. **训练可接**：训练节点直接引用数据集版本，而不是手工 YAML；
5. **评估可接**：基准集直接引用冻结数据集版本，而不是散落路径；
6. **结果可回溯**：可以从模型一路追到训练数据、标注版本和原始来源。

落地后，训练、评估、数据集三块就不再是三套平行配置，而是统一围绕：

`来源 -> 样本 -> 标注 -> 数据集版本 -> 训练节点 / 评估基准 -> 模型结果`

这条主链路协同工作。
