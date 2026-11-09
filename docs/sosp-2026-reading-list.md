# SOSP 2026 精读候选清单

- 会议：第 32 届 ACM SOSP，2026-09-28 至 10-02，布拉格；62/390 录取（15.9%）。
- 筛选方法：以 `config/topics.yaml` 与 `config/topics-{chip,frontier,io,media}.yaml` 中的专题关键词、`aihot_priority` 与 `current_questions` 为准，对官方 62 篇入选论文逐篇匹配。
- 分级：P0 = 与专题 `current_questions` 直接对位，全文精读；P1 = 机制相关或提供关键生产/评测视角，选读核心章节；P2 = 边界探索候选，读摘要与图表即可。
- 整理日期：2026-11-09。本文件是一次性人工精选快照，不随日报自动更新。

## P0：优先全文精读（10 篇）

| # | 论文 | 命中专题 | 团队 | 机制与证据 | 精读关注点 |
| --- | --- | --- | --- | --- | --- |
| 1 | [Skill VM: Write Once, Run Everywhere Efficiently](https://arxiv.org/abs/2604.03088) | `agent_acceleration` | 上海交大（陈海波组） | 把 agent skill 当"代码"、LLM 当异构处理器：能力分解、按模型-harness 对做能力 profile、编译期绑定与并发抽取、运行期 JIT 代码固化与自适应重编译。8 个 LLM × 3 个 harness × SkillsBench：token 至多 -40%，并行加速至多 3.2×，代码固化带来 19–50× 时延降低；基于 11.8 万个 skill 的实证研究。 | 能力 profile 的度量方法能否迁移到 coding agent 的工具链评估；JIT 固化对 `agent_harness` 方向（长任务状态、验收门）的启发。 |
| 2 | [Don't Let AI Agents YOLO Your Files（YoloFS）](https://arxiv.org/abs/2604.13536) | `agent_acceleration` / agent 运行环境 | UW-Madison + Microsoft Research + Iowa State | 面向 agent 的原生文件系统，把信息与控制从 agent 下移到 FS 层，兼顾安全与自主性。290 起公开的 agent 误用文件事件中 40% 损害不可恢复；11 个"隐性损害"任务中的 8 个上，agent 借助 FS 支持自行撤销了自己造成的损害。 | 信息/控制下移后与现有 agent 工作流的集成成本；可否与 harness 验收门、状态 checkpoint 机制组合。 |
| 3 | [StreamEP: Straggler-Tolerant MoE Decoding without Communication Barriers](https://arxiv.org/abs/2606.26607) | `tpn` | USC + Google DeepMind + UT Austin + SNU | MoE 解码消除同步 barrier、容忍 straggler；preprint（早期版本名为 Moebius）展示运行时在 EP/TP 间切换——利用两种并行是同一模型的不同布局，只需迁移 rank 归属变化的专家权重与 KVCache 分片，用融合 GPU-to-GPU 传输核在 decode 步间完成。8×H200 上服务 Qwen3-235B-A22B：每个工作点都追平更优的静态并行，RL rollout 场景 1.16–1.25×，切换耗时 215–434 ms，显存开销仅 2.4%。 | 对齐 TPN 的核心问题——通信是否感知解码阶段与 KVCache 位置；切换时 KVCache 分片迁移的真实带宽/时延成本，以及收益是否传导到端到端。 |
| 4 | [Janus: Multi-LLM Serving at Production Scale](https://yangtonghome.github.io/uploads/Janus_SOSP2026.pdf)（[ACM DL](https://dl.acm.org/doi/10.1145/3830418.3843867)） | `kv_management` + `ai_infra_horizontal` | 北大 + 京东 + UCAS/USTC/SJTU | 生产级多模型 serving——单集群复用数百个异构模型，请求按模型归属为主、设备占用为次；服务层与引擎层协同设计，处理 prefill 相互干扰与跨模型资源利用率。 | 多模型间显存/KVCache 放置与驱逐策略；真实生产负载下的干扰与利用率数据（`valuable_evidence`：命中率、GPU 显存利用率、端到端 P95）。 |
| 5 | [SANDHI: Fine-grained Merging for Memory Efficient Multi-Model Serving](https://dl.acm.org/doi/abs/10.1145/3830418.3843911)（[artifact](https://zenodo.org/records/22108093)） | `kv_management` / 内存 | Georgia Tech + Microsoft | 对多个相关/微调模型做细粒度合并，让它们共享 GPU 显存，降低多模型驻留成本。吞吐至多 2.93×，并给出显著显存节省。 | 合并粒度与"复用率/命中率"的量化关系；与 TensorDex 的张量级 delta 压缩互为参照——同是跨模型冗余消除，一个在显存、一个在存储。 |
| 6 | [Scalable Context Orchestration for Serving LLMs Over Voice（llmovoice）](https://arxiv.org/abs/2609.04288) | `context_building` / `ai_infra_horizontal` | 上海交大 + AgenticSys（Silvery Fu） | 语音场景的上下文编排中间件——显式建模副语言与环境状态（语速、丢包等），每轮构造有界上下文，由 serving LLM 生成运行时指令。语速对齐误差 -52.4%，丢包下误打断率 46.0%→0.9%，模型使用成本 -79.2%；长会话每轮成本至多降 24.9×，答案质量保持 98.7%。注意报告成本/质量指标，不含 TTFT/TPOT。 | 有界上下文构建与裁剪策略——正是日报 `context_building` 方向的机制样本；成本-质量权衡曲线的形状。 |
| 7 | [TensorDex: A Compact, Tensor-Centric Storage System for Modern AI Models](https://arxiv.org/abs/2604.17104) | `accelerator_io_datapath` / 存储 | UVA + Harvard | 张量级（而非模型级）无损 delta 压缩：比特级指纹预测张量对可压缩性，多中心聚类选参考基，不依赖不可靠的 lineage 元数据。2,890 个 Hugging Face 模型样本上存储占用 -70.5%（比 SOTA 再好 37%），压缩 22.9 GB/s、解压 28.4 GB/s。 | 模型仓库→集群分发路径上的数据量削减；对跨域权重/模型传输（`cross_region`）带宽成本的间接价值。 |
| 8 | MeshRT: Compile-Time Governed Wafer-Scale Runtime for Low-Latency High-Throughput Inference | `ai_chip_accelerator` | Edinburgh + Microsoft Research（无公开 preprint，截至整理日） | 晶圆级加速器上的推理运行时，编译期治理资源与通信，面向低时延高吞吐推理。 | 晶圆级互连拓扑如何影响 kernel 放置与通信调度；与配套编译论文 Wavel（见 P1）合读构成完整的晶圆级软件栈样本。 |
| 9 | [TensorHub: Scalable and Elastic Weight Transfer for LLM RL Training](https://arxiv.org/abs/2604.09107) | `cross_region` / `ai_infra_horizontal` | UW-Madison + ByteDance Seed | RL 训练集群间可扩展、弹性的权重传输；字节内部真实集群规模数据是稀缺证据。 | 虽是权重而非 KVCache，传输/放置/带宽问题与 `cross_region` 的 `transfer_placement` 方向同构，可与 KVCache 跨域迁移机制对照。 |
| 10 | [LLM-42: Enabling Determinism in LLM Inference with Verified Speculation](https://arxiv.org/abs/2601.17768) | `ai_infra_horizontal` | Microsoft Research | 不放弃动态 batching、不改写 GPU kernel 的推理确定性：快路径非确定性解码 + 轻量 verify-rollback 回放（固定 shape 归约序）提交一致 token，仅为需要确定性的流量付费。 | 浮点非结合性与 batching 交互的失效模型分析；verify-rollback 开销占比与对尾延迟的影响。 |

## P1：机制相关，选读核心章节

### Agent 与边界探索（`agent_acceleration` / `frontier_exploration`）

| 论文 | 团队 | 一句话理由 |
| --- | --- | --- |
| [Ave: Guiding Agentic GPU Optimization Using Data-Flow Invariants](https://arxiv.org/abs/2604.18616) | HKUST 等 | 用数据流不变量约束 agent 试错式 kernel 优化——"不变量作为验收门"可迁移到其他 agent 领域 |
| [Ahead-of-time Analysis of Shell Program Effects](https://atlas.cs.brown.edu/pdf/sash:sosp:2026.pdf) | Brown 等 | shell 程序副作用的提前静态分析，天然适配 agent 执行命令前的安全预测 |
| [AgileLog: A Forkable Shared Log for Agents on Data Streams](https://arxiv.org/abs/2604.14590) | UIUC | 数据流上 agent 的可 fork 共享日志——agent 状态管理与回放的基础设施样本 |
| [TuxBot: Semantic-Aware Online OS Tuning with LLMs](https://arxiv.org/abs/2605.15026) | Columbia + IBM | LLM 语义感知的在线 OS 调参，`frontier_exploration` 的"LLM×OS"代表 |

### AI Infra 横向（`ai_infra_horizontal`）

| 论文 | 团队 | 一句话理由 |
| --- | --- | --- |
| [A Few GPUs, A Whole Lotta Scale（CrystalLLM）](https://arxiv.org/abs/2605.15617) | 阿里 + Minlan Yu 等 | 小规模 GPU 上忠实模拟大规模 LLM 训练——集群研究的低成本方法论，阿里生产背景 |
| [Batched in Back（ACDC）](https://sigops.org/s/conferences/sosp/2026/accepted.html) | 上海交大 + 阿里 | 生产离线 batched 推理的特征化与优化，补齐日报偏在线 serving 的视角 |
| [LMTracer](https://sigops.org/s/conferences/sosp/2026/accepted.html) | 清华 | 生产 LLM 系统的细粒度实时性能剖析——`valuable_evidence` 观测工具直接对口 |
| Anchor: Mitigating GPU Shallow Disruptions with Decoupled Memory | 清华 + 上交 | 解耦内存缓解 GPU 短时故障，训练/推理可用性的内存侧手段 |
| [Beyond Utilization: Energy-Conscious GPU Sharing](https://sigops.org/s/conferences/sosp/2026/accepted.html) | UT Austin | 推理 serving 的能耗感知 GPU 共享，能效维度稀缺 |
| [Efficient GPU Multitasking with Morphable Kernels](https://sigops.org/s/conferences/sosp/2026/accepted.html) | 清华 | 可变形 kernel 支撑 GPU 多任务，kernel 级复用机制 |
| [Taming Dynamism on GPUs: Cross-SM Kernel Fusion](https://sigops.org/s/conferences/sosp/2026/accepted.html) | 上交 | 跨 SM 即时融合，GPU 内动态性治理 |
| [Linux AGX](https://sigops.org/s/conferences/sosp/2026/accepted.html) | UC Riverside | Linux 公平调度器扩展 GPU 调度，物理 AI/机器人场景 |
| [DiFlow](https://arxiv.org/abs/2604.08123) | 腾讯等 | 文生图扩散工作流的 micro-serving——多阶段生成式工作流与 agent 工作流同构 |
| [Taming Inference Workloads at Global Scale（Amazon Bedrock）](https://sigops.org/s/conferences/sosp/2026/accepted.html) | AWS | 全球规模 FM serving 的生产视角，跨区路由/放置的工业证据 |

### 内存语义（`memory_dsa`）

| 论文 | 团队 | 一句话理由 |
| --- | --- | --- |
| [StarfishOS](https://github.com/starfishos-org/starfishos/blob/main/docs/starfish.pdf) | 上交 | CXL 上重访单系统映像：状态分区微内核——池化语义的系统级答卷 |
| Borges: CXL Memory/SSD Hybrid 共享日志 | UT Austin + UIUC + Anthropic | CXL 内存/SSD 混合层上的低时延分布式共享日志 |
| [Disk-Based LSMs（Prism）](https://kstark007.github.io/assets/papers/Prism/paper.pdf) | UIUC + NVIDIA | 部分一致 CXL 内存下 LSM 意外地是好索引——反直觉结果，`frontier` 口味 |
| XTRA: CXL Pod 内一致性与并发控制统一 | HUST | 分布式事务中缓存一致性与并发控制的统一，CXL 语义边界样本 |
| [Tierce](https://huaicheng.github.io/p/sosp26-tierce.pdf) | Virginia Tech | 可观测性驱动的分层内存管理，混合部署场景 |

### 芯片与介质（`ai_chip_accelerator` / `storage_media`）

| 论文 | 团队 | 一句话理由 |
| --- | --- | --- |
| Wavel: Wafer-Scale 编译系统 | Edinburgh + MSR | 与 MeshRT 配套的晶圆级编译栈，合读看软硬件接口 |
| [Scheduling Linux Threads under I/O Chiplet Wall（cSwitch）](https://sigops.org/s/conferences/sosp/2026/accepted.html) | UW-Madison | I/O chiplet 墙下的线程调度——chiplet 化对 OS 调度的直接影响 |
| GAZE: ZNS 闪存上的 LFS 垃圾回收 | KAIST（元在燮组） | ZNS 盘上重架构日志结构文件系统的 GC，`storage_media` 专题对口 |
| ProbeFS: DNA 文件系统 | 上交 | 生化内容寻址的 DNA 存储文件系统——介质侧远期探索 |

### OS/运行时边界探索（`frontier_exploration`）

| 论文 | 团队 | 一句话理由 |
| --- | --- | --- |
| Turning Linux into a High-Performance Library OS with Flux | 清华 | Linux 变库 OS，运行时边界重画 |
| You Can Always Get What You Want: CPU Virtualization Made Fast and Free | 上交 + 阿里 | 又快又免费的 CPU 虚拟化 |
| [It's the Kernel's Fault!（bpf_fault）](https://github.com/bpf-fault/bpf-fault/blob/main/bpf_fault_draft.pdf) | Columbia | BPF 自定义缺页处理——用户态接管页错误的新接口 |
| VoliStorM: 两内核一份 I/O 缓存 | Inria | 崩溃一致性 I/O 缓存的新切分方式 |
| [QProf](https://storage.googleapis.com/gweb-research2023-media/pubtools/1044643.pdf) | Google | 机群级传递性成本剖析，仓库级观测方法可迁移 |
| Computation is Fast, Use Threadlet! | 北大等 | 轻量线程/异步执行路径的取舍再评估 |

## P2：边界探索泛读（分组）

以下论文与当前专题关键词无直接交集，但属于 `frontier_exploration` 的可选扫描范围，读摘要与结论即可：

- 验证与形式化：Sockeye（平台配置/硬件验证）、I3DP（分布式协议不变量）、Lion（异步 runtime 活性）、Welder（集群控制面活性）、M2K（CUDA kernel 验证）、Validating Rust Compilers（Trait 约束图）、Verifying Distributed Transactions（MIT）、Validating a Production Cloud Object Store（AWS）、Testing Custom Control Planes Without the Cluster（UCSC）。
- 安全与隐私：Cerium（TB 级加密推理，[arXiv:2512.11269](https://arxiv.org/abs/2512.11269)，若关注 TEE 推理可升级为 P1）、PirateShip（TEE 追加日志）、Sintr（拜占庭客户端下的事务）、Cohort（去中心化 PIR）、DISCO*（ oblivious join）、CryptDough（MPC 分析引擎）、Big Bird（跨域隐私预算）、Smaran（认证时间旅行查询）。
- 调试与可靠性：DDB（分布式源级交互调试）、CLODS（非投机失败诊断）、RPCShield（微服务级联失效防御）、MCon（Android 弹性云）、State-Aware Fuzzing of JavaScript Engines（LLM 引导插桩）。

## 与日报专题的空缺观察

- `dpu_inline`：62 篇中无 DPU/SmartNIC 随路卸载直接命中（Cerium 走 TEE 路线，非随路卸载）。
- `optical_network`：无光交换/OCS 论文，符合预期——该方向主阵地在 SIGCOMM/NSDI。
- `tpn`：无"网络侧"（交换机/传输层）论文，最接近的是 StreamEP 的通信调度；推理网络调度在系统会议仍缺位，可作为选题差异化的佐证。
- `storage_media`：GAZE（ZNS）与 ProbeFS（DNA）两篇间接命中，无 HBF/HAMR 内容。
- 总体印象：LLM serving/agent 是本届绝对主线（62 篇中约三分之一），CXL 内存语义论文密度显著，验证类论文体量大但与专题无交集。

## 来源

- [SOSP 2026 官方录取论文列表](https://sigops.org/s/conferences/sosp/2026/accepted.html)
- [SOSP '26 papers & preprints（pchaigno 社区整理）](https://pchaigno.github.io/academic/2026/08/03/sosp-2026-papers.html)
- 各论文 arXiv/机构 preprint 链接（见上文）
