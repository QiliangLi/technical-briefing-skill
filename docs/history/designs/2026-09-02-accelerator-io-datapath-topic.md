# 加速器直连 I/O 与存储数据路径专题设计

- Status: implemented
- Created: 2026-09-02
- Last updated: 2026-09-02

## Problem and evidence

当前八个深度专题没有稳定承接“加速器与存储之间的 I/O 发起权和数据路径重构”。现有专题分别覆盖 DPU 随路卸载、内存语义与 DSA、AI 芯片内存层级、存储介质与控制器，但存在以下空缺：

- GPUDirect Storage 等方案的核心是存储与 GPU memory 之间的直接数据路径以及 Host DRAM bounce buffer 消除，不属于介质创新；
- SCADA、BaM、GIDS 等工作进一步讨论由 GPU 发起或编排存储访问，改变的不只是数据经过哪里，还包括谁拥有 I/O control path；
- 面向 GPU 高并发、细粒度请求重新设计 SSD controller、错误校正、队列和访问接口时，主要贡献既不是通用 SSD 指标提升，也不是 DPU 随路处理；
- 当前 AI Infra 横向 Radar 可以偶然发现这些信息，但没有稳定的专题判断边界、方向预算和长期 Roadmap 归属。

讨论底稿见 [完善 IO 直通专题](../../discussions/ChatGPT-完善IO直通专题-20260902-2315.md)。NVIDIA 官方将 GPUDirect Storage 描述为在存储与 GPU memory 之间建立直接数据路径并避免 CPU memory bounce buffer；2026 年公开的 Storage-Next 与 SCADA 又把关注点扩展到 GPU-driven storage、并行 GPU 直接访问存储以及受保护的直接访问。Marvell 已用 GPU-initiated 与 CPU-initiated 区分 AI 存储路径，并把小于 4 KB 的 I/O、controller 和 ECC 变化列为 GPU-initiated storage 的关键问题。Micron 已公开 BaM/GIDS、GDS 和小块 I/O 的设备测试。这些信号足以建立独立专题，但尚不足以把所有相关项目描述为一条严格的产品继承路线。

当前 Deep 事实候选和 `expanded_v2` 发布容量均按八个专题 × 每专题最多四条设置为 32。新增第九个专题而不调整总上限，会让“每个专题独立 Top4”的产品承诺与全局安全上限冲突。本设计采用用户指定的 36 条总上限，保持每专题 Top4 不变。

## Goals and non-goals

### Goals

- 新增一个稳定的第九个深度专题，追踪 AI/HPC 场景中加速器与本地或远端存储之间的直接 I/O、加速器主动发起 I/O、受约束的软件快路径和存储控制器协同。
- 用可执行的主题边界区分数据路径直通、control-path 转移、通用存储优化、DPU 卸载和介质创新。
- 优先追踪 NVIDIA、Marvell、Micron 的官方技术进展，同时允许其他厂商、研究团队、开源项目和标准组织凭同一证据标准进入专题。
- 保持每专题最多四条深度解读，并把 Deep 事实候选与 `expanded_v2` 总上限从 32 同步提高到 36。
- 保持 A 级原始来源、相关性评审、技术价值、Evidence Pack、Fact Check、专题补充和去重规则不变。

### Non-goals

- 不把所有 `direct I/O`、zero-copy、SPDK、io_uring、kernel bypass 或 NVMe 性能优化纳入本专题。
- 不把普通 SSD 容量、顺序带宽、PCIe 代际、NAND 密度或没有路径变化的 benchmark 纳入 Deep。
- 不重构来源等级、评分公式、60 天滚动窗口、Radar 分类或邮件版式。
- 不把 NVIDIA、Marvell、Micron 设为排他性白名单，也不因厂商名称命中而自动提高技术价值或绕过 A 级来源要求。
- 不在本设计阶段修改代码、配置、Prompt、Schema、归档或运行状态。

## Constraints and invariants

- **单一主归属**：一条候选只能按主要技术贡献进入一个稳定 Topic；共享关键词不能造成跨专题证据复制。
- **路径变化是准入前提**：候选必须明确改变以下至少一项：I/O 发起者、control path、data path、Host DRAM/CPU 参与方式、数据复制次数、加速器与存储的连接或访问语义。
- **加速器—存储约束**：通用软件快路径只有在明确服务 GPU/NPU/其他加速器与存储之间的访问时才直接相关。
- **证据不降级**：Deep 条目仍要求解析后的 A 级原始来源和现有事实、价值、去重及多样性门槛；厂商博客中的计划指标必须与实测、送样、量产和部署事实区分。
- **指标带条件**：IOPS、带宽和时延必须尽量绑定 I/O 大小、队列深度、并发线程、设备数量、互连、baseline 和工作负载；单个峰值不能自动代表端到端收益。
- **运行隔离**：新增 Topic 不重写历史归档或旧 Roadmap，不把新分类追溯应用到已发布条目。
- **容量一致**：`max_fact_candidates_total`、`max_fact_candidates_hard_cap`、`expanded_v2.core_max`、`expanded_v2.observation_max` 和 `expanded_v2.total_max` 必须共同变为 36；`max_fact_candidates_per_topic`、`expanded_v2.max_per_topic` 和 `topic_target` 保持 4。
- **外部效果不变**：本设计不改变邮件确认、发送、归档或发布行为。

## Proposed design

### 1. Topic identity

新增 Topic：

```yaml
id: accelerator_io_datapath
name: 加速器直连I/O与存储数据路径
max_items_per_issue: 4
aihot_priority: high
```

专题定义：

> 追踪 AI/HPC 场景下 GPU、NPU 或其他加速器与本地或远端持久化存储之间的 I/O 架构变化。核心包括直接数据路径、由加速器发起或控制的存储访问、专用于加速器—存储路径的软件栈，以及面向细粒度高并发加速器访问的存储控制器协同。

专题名称保留“I/O”和“存储数据路径”，不使用宽泛的“数据路径优化”作为独立名称，避免把网络、数据库、文件系统和通用 CPU I/O 优化全部吸入。

### 2. Directions

| Direction ID | 名称 | 直接相关的主要贡献 | 默认排除 |
| --- | --- | --- | --- |
| `direct_storage_path` | 加速器—存储直接数据路径 | 存储与 accelerator memory 之间的 DMA/P2P 路径，消除 Host DRAM bounce buffer 或减少复制 | 仅有网络 GPU P2P、普通 RDMA、普通 zero-copy |
| `accelerator_initiated_io` | 加速器主动发起与控制 I/O | GPU/NPU/device 直接提交、调度或控制存储请求，或把关键 control path 从 CPU 转移给加速器 | CPU 仍按普通路径发起、仅数据落入 GPU memory 的方案 |
| `accelerator_storage_stack` | 加速器存储软件快路径 | cuFile、driver/filesystem/userspace stack 等明确为 accelerator-to-storage I/O 缩短软件路径或提供安全隔离 | 通用 O_DIRECT、SPDK、io_uring、异步 I/O 和文件系统优化 |
| `accelerator_storage_controller` | 细粒度 I/O 与控制器协同 | 为 GPU 高线程并发、亚 4 KB/小块请求、P2P 或 GPU-initiated I/O 改变 controller、queue、ECC、firmware 或 device interface | 仅提升容量、顺序带宽、NAND 层数或普通随机 IOPS |

每个 Direction 使用合取式查询，不把高歧义词作为独立 query。例如：

```text
"GPUDirect Storage" OR (GPU storage "direct data path")
"GPU-initiated storage" OR "GPU-initiated I/O" OR (GPU NVMe control path)
(cuFile OR "storage stack") AND (GPU OR accelerator) AND storage
(SSD controller OR NVMe controller) AND (GPU-initiated OR fine-grained OR small-block) AND storage
```

品牌与项目词 `SCADA`、`Storage-Next`、`BaM`、`GIDS`、`GPUDirect Storage` 和 `cuFile` 用于召回，但不能替代机制判断。`GPUDirect RDMA` 只有在来源明确落到存储访问路径时才进入本专题；纯网络通信归入网络相关专题或 Radar。

### 3. Deep entry contract

在 `DEEP_ENTRY_CONTRACTS` 中新增：

```text
allowed_core_contributions:
  - accelerator_storage_direct_path
  - accelerator_initiated_io
  - accelerator_storage_stack
  - accelerator_storage_controller_codesign
min_relevance_score: 65
min_technology_value_score: 12
```

Boundary：主要贡献必须直接改变加速器与持久化存储之间的 I/O 发起、控制、数据路径、复制、隔离或设备协同。仅使用 GPU 跑普通存储 benchmark、仅出现 NVMe/PCIe/CXL/RDMA 关键词、或只改进介质和通用软件栈的候选不能进入 Deep。

### 4. Project context and valuable evidence

新项目判断卡至少包含以下问题：

1. 方案改变了谁发起 I/O、谁负责控制、数据经过谁以及发生几次复制中的哪一项？
2. CPU/Host DRAM/OS/driver 是否真正退出关键路径，仍保留哪些 setup、权限、错误恢复和完成通知职责？
3. 收益来自路径缩短、并发模型、请求粒度、控制器重构还是增加设备并行度？
4. IOPS、时延、带宽和功耗收益能否传导到 GPU 利用率、训练/推理/RAG/GNN/checkpoint/data-loading 的端到端指标？
5. 隔离、权限、故障恢复、多租户和部署成熟度是否足以支持生产使用？

优先证据包括：

- 路径图、发起者、control/data path 和复制次数；
- I/O size distribution、queue depth、GPU thread/request 并发、设备数量和拓扑；
- IOPS、吞吐、平均及尾时延、CPU 占用、Host DRAM 流量、GPU 利用率；
- IOPS/W、系统功耗与成本，但必须给出计算口径和 baseline；
- 端到端 workload 结果及 compute-bound/storage-bound 边界；
- prototype、开源、集成、送样、量产和部署状态；
- 权限配置、隔离、错误处理、fallback 和恢复路径。

### 5. Cross-topic ownership

按主要贡献执行以下归属：

| 主要贡献 | Topic |
| --- | --- |
| GPU/NPU 与存储之间的直接访问、主动发起 I/O 或专用存储栈 | `accelerator_io_datapath` |
| DPU/SmartNIC/IPU 执行协议、元数据、安全、缓存或存储卸载 | `dpu_inline` |
| CXL 内存池化、共享、一致性或远程内存语义 | `memory_dsa` |
| GPU/NPU 芯片内部访存、HBM、片上/封装互连或计算架构 | `ai_chip_accelerator` |
| NAND/HBF/NVM/HDD 介质、FTL、耐久或介质主导的 controller 协同 | `storage_media` |
| 无法证明加速器—存储路径变化但仍有强 AI Infra 信号 | `ai_infra_horizontal` Radar |

当 controller 同时涉及介质与 GPU-initiated I/O 时，以论文或产品的主问题、主要对照实验和核心收益来源决定归属，不复制到两个 Deep Topic。

### 6. Vendor tracking and source routing

NVIDIA、Marvell、Micron 是优先观察对象而不是准入条件：

- NVIDIA：GPUDirect Storage、cuFile、SCADA、Storage-Next 及相关安全/隔离机制；
- Marvell：GPU-initiated storage、SSD/NVMe controller、small-payload ECC、PCIe/CXL 与存储加速器；
- Micron：BaM/GIDS、GDS、细粒度 I/O、AI SSD 工作负载与 controller/media 要求。

实施时：

- 为 AI HOT 和适用的 Builder/日报线索源增加该 Topic 的适度 boost；
- 将 `nvidia.com`、`marvell.com`、`micron.com`、`arxiv.org`、`dl.acm.org`、`usenix.org` 等加入该 Topic 的 coverage-gap preferred domains；
- 对已有 `topic_allowlist` 逐项判断，不全局追加；只有确实覆盖系统、存储或 AI 基础设施的来源才加入；
- 保持 `agent_web_search_max_queries: 4` 不变。该 Topic 通过 `high` 优先级参与现有缺口排序，不获得绕过全局预算的专用搜索任务；若上线后的 coverage telemetry 显示持续漏报，再单独提出搜索预算变更。

### 7. Capacity and publication behavior

新增第九个 Deep Topic 后：

```yaml
efficiency:
  deep_topics:
    # existing eight topics
    - accelerator_io_datapath
  max_fact_candidates_total: 36
  max_fact_candidates_hard_cap: 36
  max_fact_candidates_per_topic: 4

expanded_v2:
  core_max: 36
  observation_max: 36
  total_max: 36
  max_per_topic: 4
  topic_target: 4
```

36 是九个专题各自最多四条时的安全上限，不是要求每期生成 36 条。来源不足、相关性不足、证据不足、已发布去重或多样性约束仍可让任一专题少于四条。专题补充每专题上限继续沿用现有配置，不因总上限提高而扩大。

## Compatibility and migration

- 新 Topic 只对配置启用后的新 run 生效；历史 archive、已发布条目的 Topic ID、Roadmap 和 Idea 证据不回填、不重分类。
- 当前配置在每次命令启动时重新加载，缺少可证明的完整 run 配置快照。因此上线应选择没有待恢复非终态 run 的边界；若存在旧配置创建的未完成 run，应先按旧代码/配置完成或明确终止，不能用新九专题配置继续解释旧任务图。
- 新 Direction 和项目判断卡会进入 evaluator/extractor version，原有 Topic 的 relevance/facts cache 不受影响；新 Topic 没有旧 cache 可复用。同一来源若曾在其他 Topic 评审过，不得跨 Topic 直接复用判断。
- 数据库和 Schema 不新增字段，不需要数据迁移。Topic、Direction 与任务 envelope 继续使用现有通用结构。
- `expanded_v2` 容量提高不改变旧 archive 校验；旧期少于或等于 32 条仍然合法。
- 新 Roadmap 在该 Topic 首次产生已发布 Machine evidence 后按现有知识物化流程创建；不得用本讨论文档或未发布候选作为 Roadmap 证据。

## Failure, recovery, and rollback

### Expected failures

- 高歧义查询导致普通存储、数据库或网络候选大量误入；
- 新 Topic 与 DPU、AI 芯片、存储介质重复路由；
- 某处仍保留八专题/32 条硬编码，造成 selection、render 或 validation 上限不一致；
- 官方厂商线索主要是产品计划或营销指标，缺少可核验条件；
- 四条全局 coverage-gap 搜索预算不足以持续覆盖新增方向。

### Recovery

- 误召回优先收紧 Direction query、include/exclude terms 和项目判断卡，不降低相关性阈值；
- 重复归属通过 `boundary_conflict`、Deep entry contract 和跨专题回归 fixture 修复；
- 容量不一致必须 fail closed，不得静默截断第九个专题；
- 无 A 级可解析证据的厂商线索保留为 discovery-only 或 Radar，不进入 Deep；
- 搜索覆盖不足先通过 telemetry 证明具体缺口，再设计查询预算调整。

### Rollback

- 从新 run 的 `deep_topics` 中移除 `accelerator_io_datapath`，恢复容量 32，并恢复 `expanded_v2` 的三个 32 上限；
- 保留已经合法发布的历史条目和 Topic 身份，不改写 archive；前端和知识读取必须继续容忍历史中存在已停用 Topic ID；
- 停用新增来源 boost、preferred domains 和项目判断卡路由前，先确认没有引用这些输入的待执行任务；
- 回滚不删除 cache、归档或知识历史；不可达的新 Topic 数据保留用于审计。

## Verification

### Configuration and routing

- 配置加载后共有九个 Deep Topic，新增 Topic 位于横向 Radar 之前并有四个唯一 Direction ID；
- 新 Topic 有非空 `current_questions`、`valuable_evidence`、项目判断卡和 Deep entry contract；
- `ConfigBundle.context_path()` 能解析新判断卡；
- coverage-gap 搜索为新 Topic 返回官方厂商与学术 preferred domains，且总 lane 上限仍为 4；
- 所有来源 allowlist 和 boost 引用的 Topic ID 均可解析。

### Semantic fixtures

至少增加以下正例：

- GDS 类存储到 GPU memory 的 direct path 和 bounce-buffer elimination；
- GPU 发起存储请求的 SCADA/BaM/GIDS 类架构；
- 专为 GPU 细粒度请求改变 queue/controller/ECC 的设备协同；
- 明确绑定 accelerator storage path 的 cuFile/driver/security fast path。

至少增加以下反例及预期归属：

- 普通 `O_DIRECT`、io_uring 或 SPDK benchmark → off-topic/Radar；
- 仅 PCIe Gen6 顺序带宽翻倍的 SSD → `storage_media` 或非 Deep；
- BlueField 执行 NVMe-oF、压缩或元数据卸载 → `dpu_inline`；
- CXL memory pooling → `memory_dsa`；
- HBM/片上 memory hierarchy → `ai_chip_accelerator`；
- 仅有 GPUDirect RDMA 网络通信、没有存储路径 → 非本 Topic。

### Capacity and regressions

- 九个 Topic 各四条合法候选时，Deep 选择保留 36 条且每 Topic 不超过 4；
- 九个已配置 Topic 各四条时正好达到 36；若配置错误导致十个 Topic 都产生 Top4，选择必须因超过 hard cap 而 fail closed，不能静默饿死某个 Topic；
- `expanded_v2` 允许 `core + observations <= 36`，任一类别和总数超过配置时 fail closed；
- Topic 不足四条时不使用弱来源、重复事件或普通性能新闻补齐；
- 旧八专题 fixture、去重、同项目上限、同方向上限、cache 隔离、Evidence Gate、Fact Check、render 和 archive 测试继续通过。

### Operational checks

- 运行配置/Skill 校验器；
- 运行与 topic loading、Deep eligibility、coverage gap、topic-local selection、expanded publication、project insight、knowledge materialization 相关的定向测试，再运行完整测试套件；
- 检查本地 Markdown 链接、`git diff --check` 和 `git status --short`；
- 使用一次不发送邮件的新 run 或 fixture dry run 检查九专题任务图、36 上限、统计与最终校验；
- 不以真实邮件发送作为本设计的验收步骤。

## Documentation impact

实施已同步更新：

- `config/topics-io.yaml`：新增 Topic、Directions、queries、include/exclude terms、问题和证据字段；
- `config/settings.yaml`：新增 Deep Topic，两个事实候选上限改为 36；
- `config/scoring.yaml`：`expanded_v2.core_max`、`observation_max`、`total_max` 改为 36；
- `config/sources.yaml`：新增经过逐源判断的 boost/allowlist；
- `config/project-context/accelerator-io-datapath.md`：新增判断卡；
- `briefing_skill/config.py`：加载新 extension、增加判断卡路由并消除或更新八专题文案兼容逻辑；
- `briefing_skill/deep_eligibility.py`：新增 Deep entry contract；
- `briefing_skill/discovery_stage.py`：新增 preferred domains；
- 任何按 Topic ID 硬编码质量检查、横向补位或知识别名的代码；若无需新增 special case，应以回归测试证明通用路径可用；
- `SKILL.md`：补齐第九个深度专题、配置文件位置及 36 条安全上限；
- `docs/contracts/project-insight-layer.md`：修正专题覆盖和 Deep budget；`docs/architecture.md` 未陈述固定专题数量且数据流未变，无需修改；
- topic count、32 上限、Topic 顺序、判断卡覆盖、Deep contract 覆盖、quality guard、expanded_v2 和 knowledge coverage 相关测试。

Prompt 与 JSON Schema 使用通用 Topic/Direction envelope，本设计不要求修改；实施验证若发现硬编码枚举或旧容量，必须作为同一变更修复并记录在设计中。

## Decision log

- **2026-09-02**：用户要求为 IO 直通新增设计方案，并明确将总上限提高到 36。
- **2026-09-02**：选择新增第九个 Deep Topic，不并入 `storage_media`、`dpu_inline` 或 `ai_chip_accelerator`，因为其稳定主问题是加速器—存储 I/O 的发起权、控制和路径。
- **2026-09-02**：Topic 名称定为“加速器直连I/O与存储数据路径”；“数据路径优化”只作为描述词，不作为无边界的收录条件。
- **2026-09-02**：保留四个方向，但将软件栈方向限定为 accelerator-to-storage 路径；通用 SPDK/io_uring/O_DIRECT 默认排除。
- **2026-09-02**：NVIDIA、Marvell、Micron 作为优先追踪对象和来源路由信号，不作为白名单或自动 Deep 条件。
- **2026-09-02**：将 Deep 事实候选与 `expanded_v2` 的对应总容量同步从 32 调至 36；每 Topic Top4、每 Direction 和每 Project 多样性限制保持不变。
- **2026-09-02**：用户要求开始实施，设计状态由 `draft` 变为 `accepted`。
- **2026-09-02**：专题配置、判断卡、Deep 准入、来源与搜索路由、36 条容量、当前文档和回归测试全部完成；554 项测试、Skill validator、CLI 启动、Python 编译和仓库自检通过，设计状态变为 `implemented` 并归档。
