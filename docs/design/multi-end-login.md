# 多端登录与统一身份设计

## 1. 当前状态

当前仓库已经有两个明确入口：

1. `xyolo` CLI；
2. `xyolo web` Web 页面。

从代码和 README 看，现阶段系统还是**单机工作目录 + 本地命令 + 本地 Web 服务**形态：

1. CLI 负责训练命令入口；
2. Web 负责页面操作与任务落盘；
3. `dataset / model / eval / deploy` 模块仍处于预留状态。

也就是说，现在还没有：

- 用户体系；
- 登录态；
- 多端身份打通；
- 组织/项目隔离；
- API token；
- 第三方系统联动身份。

但结合现有设计文档，后续系统已经明显不再只是单机训练脚本，而会逐步演进为一个完整平台：

1. `training-page.md` 定义了训练目标树；
2. `evaluation-metrics.md` 定义了评估体系；
3. `toolchain-interface.md` 定义了工具链接口；
4. `dataset-management.md` 定义了来源、样本、标注、数据集版本。

这意味着系统后续必然要支持：

1. 多人协作；
2. 多端访问；
3. 外部标注/数据/实验系统集成；
4. 任务、数据、模型的权限边界。

本文档用于定义这套多端登录和统一身份方案。

## 2. 设计目标

这套设计要解决七个问题：

1. Web、CLI、未来桌面端使用同一套账号体系；
2. 支持个人账号、组织账号、项目级权限；
3. 支持浏览器登录、CLI 登录、长期 API token；
4. 支持服务间调用与第三方系统联动；
5. 支持数据、训练目标、模型、评估结果的权限隔离；
6. 支持后续接入 CVAT、FiftyOne、ClearML 等外部系统；
7. 保持当前本地优先架构可平滑演进，不强行一步到位成重型 IAM 系统。

## 3. 适用范围

第一阶段需要覆盖的端：

1. **Web**
2. **CLI**
3. **Open API**

第二阶段预留：

1. **Desktop**
2. **内部 worker / agent**
3. **第三方集成回调**

这里的“多端”不要求第一版马上做 App，而是指**不同访问方式共用统一身份与授权体系**。

## 4. 基本原则

### 4.1 认证和业务解耦

训练、评估、数据集、标注、模型都不应自己维护散乱的登录逻辑。

统一由：

1. `Identity Service`
2. `Access Token`
3. `Session`
4. `Permission Model`

四部分承担。

### 4.2 Web 用会话，CLI 用令牌

浏览器和命令行的交互方式不同，不应强行统一成一种模式。

推荐：

1. **Web**：短期 session + refresh；
2. **CLI**：设备码登录或浏览器授权后换取长期 token；
3. **Open API / Worker**：服务账号 token。

### 4.3 先做统一账号，再做单点登录扩展

第一版不必一上来引入复杂企业 IAM，但模型上要预留：

1. 本地账号密码；
2. OAuth/OIDC；
3. 企业 SSO；
4. 第三方服务授权绑定。

### 4.4 权限边界按组织、项目、资源三层控制

因为现有设计已经有训练目标、数据集版本、评估基准、模型产物等对象，权限不能只停留在“能不能登录”。

至少要区分：

1. **组织级**
2. **项目级**
3. **资源级**

## 5. 核心对象

### 5.1 User

```json
{
  "id": "user-001",
  "username": "tommy",
  "display_name": "Tommy",
  "email": "tommy@example.com",
  "status": "active"
}
```

### 5.2 Organization

```json
{
  "id": "org-factory-a",
  "name": "Factory A",
  "status": "active"
}
```

### 5.3 Project

```json
{
  "id": "project-person-helmet",
  "org_id": "org-factory-a",
  "name": "Person Helmet",
  "status": "active"
}
```

这里的 `Project` 是多端登录里最关键的权限边界，因为现有设计里的：

1. 训练目标；
2. 数据集版本；
3. BenchmarkSet；
4. 模型产物；
5. 任务记录；

都建议挂在某个 `project_id` 下面。

### 5.4 IdentityProvider

```json
{
  "id": "idp-local",
  "type": "local",
  "name": "XYolo Local"
}
```

后续可扩展：

1. `local`
2. `oidc`
3. `github`
4. `feishu`
5. `ldap`

### 5.5 LoginSession

```json
{
  "id": "sess-001",
  "user_id": "user-001",
  "client_type": "web",
  "org_id": "org-factory-a",
  "project_id": "project-person-helmet",
  "expires_at": "2026-07-18T12:00:00Z"
}
```

### 5.6 AccessToken

```json
{
  "id": "token-001",
  "subject_type": "user",
  "subject_id": "user-001",
  "client_type": "cli",
  "scopes": [
    "project:read",
    "dataset:write",
    "train:run"
  ],
  "expires_at": "2026-08-18T12:00:00Z"
}
```

### 5.7 ServiceAccount

```json
{
  "id": "svc-cvat-sync",
  "org_id": "org-factory-a",
  "project_id": "project-person-helmet",
  "status": "active"
}
```

这个对象用于：

1. worker 拉任务；
2. CVAT 回调同步；
3. ClearML 任务回写；
4. 数据导入服务写入来源和样本。

## 6. 多端登录流程

### 6.1 Web 登录

推荐流程：

1. 用户访问 Web；
2. 未登录时跳转登录页；
3. 输入账号密码或进入 OIDC；
4. 服务端签发 `session + refresh`；
5. 浏览器保存 httpOnly cookie；
6. 前端通过 `/api/me` 获取当前用户与当前项目上下文。

Web 更适合 session，不建议长期把 access token 暴露给前端脚本。

### 6.2 CLI 登录

推荐两种模式：

#### 模式 A：设备码 / 浏览器授权

```bash
xyolo auth login
```

流程：

1. CLI 生成 `device_code`；
2. 用户在浏览器完成登录；
3. CLI 轮询换取 token；
4. token 本地安全保存；
5. 后续 `xyolo dataset/train/eval/model` 全部带 token 调 API。

#### 模式 B：个人访问令牌

```bash
xyolo auth login --token <PAT>
```

适用于：

1. CI；
2. 无浏览器环境；
3. 批处理脚本。

### 6.3 Open API / SDK

Open API 不走浏览器 session，统一用 Bearer Token。

适用于：

1. 外部自动导入数据；
2. 标注平台回调；
3. 第三方训练调度器；
4. 报表系统读取结果。

### 6.4 Worker / Agent

内部 worker 不应伪装成普通用户，建议使用 `ServiceAccount`：

1. worker 注册自己的 service identity；
2. 拉任务时携带服务令牌；
3. 所有落盘和回写动作可审计。

## 7. 权限模型

### 7.1 角色建议

| 角色 | 说明 |
|---|---|
| `org_owner` | 组织管理员 |
| `project_admin` | 项目管理员 |
| `data_manager` | 数据与标注负责人 |
| `trainer` | 训练与评估操作者 |
| `viewer` | 只读 |
| `service` | 服务账号 |

### 7.2 资源权限建议

| 资源 | 典型动作 |
|---|---|
| `source_asset` | read / write / import |
| `annotation_project` | read / write / review |
| `dataset_version` | read / publish / deprecate |
| `training_goal` | read / write / branch / run |
| `benchmark_set` | read / write |
| `model_artifact` | read / promote / export |
| `task` | read / run / cancel |

### 7.3 默认边界

建议所有核心资源默认都带：

1. `org_id`
2. `project_id`
3. `created_by`

这样数据集、训练节点、模型、评估结果才能天然纳入多租户权限控制。

## 8. 与现有设计的整合方式

### 8.1 与训练目标树整合

`training-page.md` 里的：

1. `goal`
2. `node`
3. `task`

建议全部增加：

1. `org_id`
2. `project_id`
3. `created_by`
4. `updated_by`

创建 root、创建分支、启动训练都要校验当前用户是否有对应项目权限。

### 8.2 与数据集管理整合

`dataset-management.md` 里的：

1. `SourceAsset`
2. `ImportBatch`
3. `Sample`
4. `AnnotationProject`
5. `AnnotationVersion`
6. `DatasetVersion`
7. `BenchmarkSet`

也都应带 `org_id / project_id`。

其中 `SourceAsset` 还需要额外支持：

1. 来源可见范围；
2. 敏感级别；
3. 可共享范围。

### 8.3 与评估体系整合

`evaluation-metrics.md` 里的：

1. `best_node_id`
2. `validation_results`
3. `ranking`

都应受项目权限控制。

否则只要知道任务 ID，就可能越权读到模型表现和业务数据分布。

### 8.4 与工具链接口整合

`toolchain-interface.md` 里的任务执行请求应增加身份上下文：

```json
{
  "actor": {
    "type": "user",
    "id": "user-001"
  },
  "project_id": "project-person-helmet",
  "toolchain": "yolo",
  "operation": "train"
}
```

这样训练和评估结果天然可审计。

## 9. 与参考系统的关系

这里不要求 XYolo 直接照搬这些系统，但可以吸收它们成熟的边界划分。

| 系统 | GitHub | 借鉴点 |
|---|---|---|
| FiftyOne | https://github.com/voxel51/fiftyone | 数据集浏览、样本级视图、评估结果可视化 |
| CVAT | https://github.com/cvat-ai/cvat | 标注任务、团队协作、项目与成员管理 |
| Datumaro | https://github.com/open-edge-platform/datumaro | 数据集版本、格式转换、merge/split/QA |
| DVC | https://github.com/iterative/dvc | 数据版本与谱系引用 |
| ClearML | https://github.com/allegroai/clearml | 任务、实验、模型与 agent 闭环 |
| lakeFS | https://github.com/treeverse/lakeFS | 对象存储级数据版本控制 |
| Label Studio | https://github.com/HumanSignal/label-studio | 通用标注平台与可嵌入标注体验 |

对多端登录最相关的借鉴点有两个：

1. **项目级协作边界**：CVAT、ClearML 都不是只做“用户登录”，而是围绕 workspace/project 组织权限；
2. **服务账号与 API token**：这类系统都会区分人用登录和机器用 token。

## 10. 推荐登录架构

### 10.1 第一阶段

先做轻量内建身份系统：

1. 本地账号密码；
2. Web session；
3. CLI token；
4. 项目级 RBAC；
5. Service account。

优点：

1. 贴合当前本地部署现状；
2. 实现成本低；
3. 足够支撑数据、训练、评估闭环。

### 10.2 第二阶段

增加 OIDC / 企业 SSO：

1. 统一接企业身份源；
2. 支持组织自动开通；
3. 支持 SCIM/目录同步可后置。

### 10.3 第三阶段

增加外部系统账号绑定：

1. 绑定 CVAT 项目；
2. 绑定 ClearML workspace；
3. 绑定对象存储凭证；
4. 绑定 Git 仓库或 CI token。

## 11. API 契约建议

### 11.1 当前用户

```json
{
  "user": {
    "id": "user-001",
    "display_name": "Tommy"
  },
  "current_org": {
    "id": "org-factory-a",
    "name": "Factory A"
  },
  "current_project": {
    "id": "project-person-helmet",
    "name": "Person Helmet"
  },
  "permissions": [
    "dataset:publish",
    "train:run",
    "eval:read"
  ]
}
```

### 11.2 CLI token 元信息

```json
{
  "token_id": "token-001",
  "subject_type": "user",
  "subject_id": "user-001",
  "project_id": "project-person-helmet",
  "scopes": [
    "dataset:read",
    "train:run"
  ]
}
```

### 11.3 审计日志

```json
{
  "event_id": "audit-001",
  "actor_type": "user",
  "actor_id": "user-001",
  "action": "dataset.publish",
  "resource_type": "dataset_version",
  "resource_id": "dataset-person-helmet-base-v3",
  "project_id": "project-person-helmet"
}
```

## 12. 约束与风险

### 12.1 第一版不要做的事

1. 不要把权限散落到每个模块自行判断；
2. 不要让 CLI 直接复用浏览器 cookie；
3. 不要让 worker 使用个人账号 token；
4. 不要把项目边界只做在前端；
5. 不要把数据集路径当作权限控制单位。

### 12.2 重点风险

1. 本地部署和多人协作模式差异大；
2. 模型、数据、日志都可能含敏感信息；
3. 外部标注平台回调如果没有服务账号，会造成审计断裂；
4. 如果不先确定 `org/project` 边界，后面很难给已有对象补权限。

## 13. 推荐实施顺序

### P0

1. 增加 `User / Organization / Project`；
2. Web 登录；
3. CLI token；
4. 项目级 RBAC；
5. 核心对象增加 `org_id / project_id`。

### P1

1. Service account；
2. 审计日志；
3. Open API；
4. 标注/训练/评估任务权限收口。

### P2

1. OIDC / 企业 SSO；
2. 第三方系统绑定；
3. 细粒度共享与临时授权。

## 14. 最终结论

这套多端登录方案的核心不是“加一个登录页”，而是给 XYolo 后续的平台化演进补上统一身份底座：

1. **Web 可用 session**；
2. **CLI 可用 token**；
3. **Worker 可用 service account**；
4. **资源统一挂在 org/project 下**；
5. **训练、评估、数据集、模型全部接入同一权限体系**。

这样后续不管是继续扩展 `dataset / eval / model / deploy` 模块，还是接入 CVAT、FiftyOne、ClearML 这类外部系统，身份与权限边界都不会散掉。
