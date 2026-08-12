lama3 vLLM local prefix 7.2311.72×larger
Llama3 SGLang prefix 7.311 1.73×larger
Llama3 KVCOMM 7.912 1.88×larger
Llama3 DistServe style 25.695 6.10×larger
At 25 Gbps and above, transfer wins at every tested context for
both models, measured HF prefill is already more expensive than
transferring the measured KV bytes across every tested context.
AAFLOW+, therefore, needs both the stateful operators and the cost
model: KVTransfer is not always correct, but it is usually correct
on high-bandwidth GPU clusters and can be selected explicitly by
the scheduler.
2
 4
 6
 8
 10
 12
 14
 16
Branch Factor
0
20
40
60
80
100
120Peak KV Memory (GiB)
KV Memory Footprint vs Branch Factor
AAFLOW+
aaﬂow_text
dense_preﬁll
distserve_style
kvcomm_preﬁx
sglang_preﬁx
vllm_local_preﬁx
Figure 10: Experiment-4: Mean peak KV memory with HF
backend and Mistral Model. AAFLOW+ reduces memory be-
cause it treats KV as a first-class object with lineage and
ownership.
6.9 Experiment 4: Memory Efficiency
The fourth experiment compares peak KV memory footprint across
baselines. The stateful design should avoid allocating redundant pre-
fix KV for every branch. AAFLOW+ stores one materialized prefix
10

## PDF Page 11

plus branch continuation state; dense and text baselines effectively
duplicate the prefix across branches. Table 4 and Figure 10 reports
mean peak KV memory across branch factors 1, 2, 4, 8, and 16. For
Mistral, AAFLOW+ averages 8.355 GiB peak KV memory. Dense,
AAFLOW-text, and DistServe-style average 49.987 GiB, or5.98× the
AAFLOW+ memory. vLLM-local and SGLang average 14.351 GiB
(1.72× AAFLOW+), and 14.591 GiB (1.74× AAFLOW+), while KV-
COMM averages 15.702 GiB (1.88×). The nearest competitor varies
with the branch factor. At branch factors 1, 2, and 4, KVCOMM
is closest to AAFLOW+. At branch factors 8 and 16, vLLM-local
becomes closest. Even then, AAFLOW+ uses less memory at every
branch factor.
Forked states initially share block references, so memory grows
with branch continuation rather than with full-context duplication.
The vLLM-local and SGLang profiles also reduce duplicate prefix
storage, but they are local-prefix baselines rather than distributed
state-object schedulers. SKVCOMM captures communication-oriented
prefix reuse but has a lower reuse fraction in this benchmark. The
result is that AAFLOW+ has the lowest peak memory in every
tested branch-factor setting.
6.10 Experiment 5: Throughput and Framework
Overhead
The fifth experiment measures effective throughput and frame-
work overhead Ω shown in Table 5. AAFLOW+ should improve
throughput by removing repeated prefill work and reducing text
serialization. In the benchmark schema, throughput is reported
as generated tokens per second, and Ω captures framework-side
scheduling, serialization, and orchestration overhead modeled by
the baseline adapters. AAFLOW+ achieves approximately 302 to-
kens/s on Mistral. The nearest throughput competitor is vLLM-
local/SGLang/DistServe-style at about 38–39 tokens/s. The resulting
throughput advantage is about7 .63×–8.04× against those nearest
competitors and roughly9 .47× against dense text prefill, although
dense text prefill has low overhead.
The throughput numbers are consistent with the aggregated com-
pute costs experiments. AAFLOW+ executes one measured prefill
and then reuses state; text baselines repeatedly pay the full context
construction and prefill cost. The explicit abstraction also keeps
framework overhead small in this simulation profile. KVCOMM
has a meaningful modeled communication overhead in these runs,
which explains the larger Ω values and lower throughput relative
to AAFLOW+.
7 RELATED WORK
Distributed Data Systems and Operator Abstractions:The de-
sign of AAFLOW [34] and our extension builds upon a long line of
work in distributed data systems, where computation is expressed
as compositions of operators over structured data. Systems such as
MapReduce [8], Spark [46], and Flink [5] demonstrate how declara-
tive data transformations can be compiled into efficient distributed
execution plans. More recent frameworks such as Modin [27] and
Cylon [40] extend this paradigm to high-performance dataframes,
emphasizing communication-aware execution and parallel process-
ing patterns [25, 26, 36]. AAFLOW adapts these ideas to agentic
Table 5: Experiment-5: Mean throughput and framework
overhead with fixed context grid and variation agents.
Model Baseline ThroughputΩ(s)
(tok/s)
Mistral AAFLOW+302.610.0075
Mistral dense prefill 31.940.0019
Mistral AAFLOW-text 31.84 11.1659
Mistral vLLM local prefix 38.81 0.0627
Mistral SGLang prefix 39.62 0.0657
Mistral KVCOMM 35.59 21.6770
Mistral DistServe style 37.62 0.0597
Llama3 AAFLOW+300.570.0075
Llama3 dense prefill 33.610.0019
Llama3 AAFLOW-text 33.54 6.7272
Llama3 vLLM local prefix 38.46 0.0627
Llama3 SGLang prefix 39.27 0.0657
Llama3 KVCOMM 36.16 13.0375
Llama3 DistServe style 37.46 0.0597
workflows by treating embedding, retrieval, reasoning, and mem-
ory operations as composable operators. Our work further extends
this abstraction by introducing stateful operators over KV cache,
effectively generalizing dataflow systems into stateflow systems.
Workflow Runtimes and Distributed Execution:A large
body of work has explored distributed workflow execution and
task scheduling. Systems such as Ray [24], Dask [30], and Parsl [4]
provide flexible task-based execution frameworks for parallel and
distributed workloads. HPC-oriented systems such as RADICAL-
Pilot [23, 31–33] and Pegasus [ 9] focus on large-scale scientific
workflows. While these systems provide powerful execution sub-
strates, they treat tasks as independent units and do not explicitly
model LLM-specific state such as KV cache. As a result, they cannot
exploit opportunities for state reuse across agents. Our work com-
plements these systems by introducing an abstraction that exposes
state dependencies and enables scheduling decisions based on both
data and model state.
LLM Programming and Agent Frameworks:Recent work on
LLM programming has focused on improving the expressiveness
and composability of language model applications. Frameworks
such as LangChain [7], LangGraph [10], and AutoGen [41] enable
multi-agent workflows, tool invocation, and iterative reasoning.
DSPy [16] further proposes a declarative programming model for
optimizing LLM pipelines. These systems treat orchestration as a
high-level programming problem but largely ignore the underlying
systems cost of data movement and state recomputation. In particu-
lar, they rely on text-based communication between agents, leading
to repeated prefill computation. Our work differs by introducing a
systems-level abstraction that allows agents to exchange execution
state directly.
11

## PDF Page 12

LLM Serving and KV-Cache Optimization:A growing body
of work has focused on optimizing LLM inference through effi-
cient KV-cache management. vLLM [19] introduces PagedAttention,
which uses block-based memory allocation to improve throughput
and reduce fragmentation. SGLang [47] proposes RadixAttention,
enabling prefix sharing across structured programs. FlexGen [37]
explores memory-compute trade-offs through offloading strategies,
while DistServe [ 50] and LMCache [ 21] separate prefill and de-
code stages to improve resource utilization. These systems demon-
strate that KV cache is a critical performance factor in LLM serving.
However, their optimizations are confined to single-node or single-
request execution contexts with efficient storage, movement, and
management of KV cache across heterogeneous memory tiers and
serving backends. They do not expose KV cache as a distributed
systems object that can be shared across multiple agents. Our work
extends KV-cache optimization from local serving to distributed
multi-agent workflows rather than focusing solely on cache man-
agement.
Distributed and Multi-Tenant LLM Serving:Recent work
has explored scaling LLM serving across multiple tenants and dis-
tributed environments. Systems such as Orca [45] and Sarathi [1]
improve GPU utilization through scheduling and batching tech-
niques. Helix [14] focuses on multi-tenant inference with efficient
resource sharing. While these systems address throughput and
fairness, they do not explicitly consider KV-state reuse across inde-
pendent requests or agents. Our approach is orthogonal, focusing
on reducing redundant computation by reusing state rather than
improving scheduling alone.
Retrieval-Augmented Generation and Memory Systems:
Retrieval-Augmented Generation (RAG) systems integrate external
knowledge with LLM inference to improve factual accuracy [20].
Recent work has extended this paradigm with more sophisticated
memory and retrieval mechanisms, such as MemoRAG [28], Hip-
poRAG [13], and CueRAG [ 11]. These systems demonstrate the
importance of persistent memory for multi-step reasoning. How-
ever, most RAG systems treat memory as external data rather than
internal model state. They optimize retrieval and indexing but do
not address the cost of reprocessing retrieved context within the
model. Our work complements these approaches by enabling the
reuse of the internal KV representation of retrieved context.
Existing research has focused on two areas: improving LLM effi-
ciency via KV-cache optimization and enhancing workflow expres-
siveness with agent frameworks. We unify these by treating the KV
cache as a distributed state within an operator abstraction, enabling
optimizations like cross-agent state reuse, distributed KV transfer,
and state-aware scheduling. Extending AAFLOW’s operator-driven
model with stateflow lays the groundwork for scalable, efficient,
and reproducible multi-agent LLM systems.
8 LIMITATIONS AND FUTURE WORK
These results should be viewed within defined limits. The work-
loads use synthetic, deterministic prompts [17], so answer quality
is not evaluated against external datasets. The main output length
is 𝑌= 64tokens; longer outputs would reduce prefill reuse ben-
efits and place greater emphasis on decoding. AAFLOW+ targets
shared-prefix multi-agent workflows, not independent stateless
inference. Infrastructure assessments are based on controlled exper-
iments rather than production cluster data. We define architectural
objectives for eviction and memory-constrained scheduling, but
currently evaluate only unconstrained memory.
AAFLOW+ opens several directions for future research. First,
extending the workflow to supportheterogeneous model envi-
ronmentsremains an important challenge. Current compatibility
constraints assume identical model architectures and positional
encodings, but real-world systems may involve mixtures of models,
adapters, or fine-tuned variants. Generalizing state reuse across
heterogeneous settings would broaden applicability. Second,cost-
aware schedulingcan be further developed. While this work
demonstrates the tradeoff between KV transfer and recomputation,
future systems could incorporate dynamic bandwidth estimation,
workload prediction, and adaptive placement strategies to opti-
mize execution decisions in real time. Third, integratingstateful
execution with emerging model architecturesis a promising
direction. While this work focuses on transformer-based KV cache,
alternative architectures such as state space models introduce dif-
ferent notions of internal state. Extending the proposed abstraction
to support these models could enable a unified treatment of execu-
tion state beyond KV representations. Fourth,fault tolerance and
persistencefor stateful workflows require deeper investigation.
Although recomputation provides a fallback mechanism, efficient
checkpointing, partial state recovery, and durable storage of KV
state remain open problems for large-scale deployments. Finally,
future work can exploreprogramming abstractions and devel-
oper toolingfor state-aware workflows. Providing higher-level
interfaces, debugging tools, and visualization systems for stateflow
execution would make these capabilities accessible to a broader
class of applications.
9 CONCLUSION
We presentedAAFLOW+, a stateful extension of agentic workflow
abstraction that makes KV cache a first-class distributed systems
object in AI memory instead of just a local inference optimization.
AAFLOW+ presents astateflowabstraction that allows agents to di-
rectly interchange and reuse execution state, in contrast to current
multi-agent LLM systems that rely on text-based communication
and frequently recalculate shared context. Our method exposes
state reuse at the workflow level by defining operators for KV-state
materialization, transfer, fork, restricted composition, and eviction,
and assembling workflows into communication-aware graphs. The
runtime externalizes KV cache using explicit metadata descrip-
tors and zero-copy communication pathways, enabling efficient
state reuse across distributed agents while preserving correctness
through compatibility constraints. Experimental results on Mistral-
7B and Llama-3-8B show that AAFLOW+ significantly improves
efficiency, achieving up to50.2 × reduction in TTFT,7.63 × lower
multi-agent latency at 16-agent scale,1.72 ×–6.10× reduction in
peak KV memory, and over7.74 × improvement in throughput.
These findings show that duplicate computation and framework
overhead in multi-agent LLM execution can be significantly re-
duced by substituting explicit KV-state sharing for text forwarding
in AI memory.
12

## PDF Page 13

REFERENCES
[1] Amey Agrawal, Ashish Panwar, Jayashree Mohan, Nipun Kwatra, Bhargav S
Gulavani, and Ramachandran Ramjee. 2023. Sarathi: Efficient llm inference by
piggybacking decodes with chunked prefills.arXiv preprint arXiv:2308.16369
(2023).
[2] Apache Arrow Project. 2025. Apache Arrow. Project website. https://arrow.
apache.org/ Language-independent columnar memory format with zero-copy
reads.
[3] Apache Software Foundation. 2016. Apache Arrow: A cross-language develop-
ment platform for in-memory data. https://arrow.apache.org
[4] Yadu Babuji, Anna Woodard, Zhuozhao Li, Daniel S. Katz, Ben Clifford, Rohan
Kumar, Lukasz Lacinski, Ryan Chard, Justin M. Wozniak, Ian Foster, Michael
Wilde, and Kyle Chard. 2019. Parsl: Pervasive Parallel Programming in Python.
InProceedings of the 28th International Symposium on High-Performance Parallel
and Distributed Computing(Phoenix, AZ, USA)(HPDC ’19). Association for
Computing Machinery, New York, NY, USA, 25–36. https://doi.org/10.1145/33
07681.3325400
[5] Paris Carbone, Asterios Katsifodimos, Stephan Ewen, Volker Markl, Seif Haridi,
and Kostas Tzoumas. 2015. Apache flink: Stream and batch processing in a single
engine.The Bulletin of the Technical Committee on Data Engineering38, 4 (2015).
https://asterios.katsifodimos.com/assets/publications/flink-deb.pdf
[6] Lisandro Dalcin, Rodrigo Paz, and Mario Storti. 2005. MPI for Python.J. Parallel
and Distrib. Comput.65, 9 (1 Sept. 2005), 1108–1115. https://doi.org/10.1016/j.jp
dc.2005.03.010
[7] Emily Davis. 2024. Building Custom AI Workflows Using LangChain Tools.
ThinkTide Global Research Journal5, 4 (2024), 54–62. https://thinktidejournal.c
om/index.php/TGRJ/article/view/53/63
[8] Jeffrey Dean and Sanjay Ghemawat. 2008. MapReduce: simplified data processing
on large clusters.Commun. ACM51, 1 (Jan. 2008), 107–113. https://doi.org/10.1
145/1327452.1327492
[9] Ewa Deelman, Karan Vahi, Gideon Juve, Mats Rynge, Scott Callaghan, Philip J.
Maechling, Rajiv Mayani, Weiwei Chen, Rafael Ferreira da Silva, Miron Livny,
and Kent Wenger. 2015. Pegasus, a workflow management system for science
automation.Future Generation Computer Systems46 (2015), 17–35. https:
//doi.org/10.1016/j.future.2014.10.008
[10] LangChain Developer. 2024.LangGraph: Stateful Multi-Agent Workflows. Techni-
cal Report. LangChain Inc. https://blog.langchain.com/langgraph-multi-agent-
workflows
[11] Yuanshuang Fu, Dan Liu, Bonan Zhang, Zhuotong Jiang, Haibo Mei, and Jiajin
Guan. 2025. Cue RAG: Dynamic multi-output cue memory under H framework
for retrieval-augmented generation.Neurocomputing639 (2025), 130235. https:
//doi.org/10.1016/j.neucom.2025.130235
[12] Yingsheng Geng, Yuchong Gao, Weihong Wu, Guyue Liu, and Jiang Liu. 2026.
RelayCaching: Accelerating LLM Collaboration via Decoding KV Cache Reuse.
arXiv preprint arXiv:2603.13289(2026).
[13] Bernal J Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, and Yu Su. 2024.
Hipporag: Neurobiologically inspired long-term memory for large language
models.Advances in neural information processing systems37 (2024), 59532–
59569.
[14] Bodun Hu, Jiamin Li, Le Xu, Myungjin Lee, Akshay Jajoo, Geon-Woo Kim, Hong
Xu, and Aditya Akella. 2024. Blockllm: Multi-tenant finer-grained serving for
large language models.arXiv preprint arXiv:2404.18322(2024).
[15] Cunchen Hu, Heyang Huang, Junhao Hu, Jiang Xu, Xusheng Chen, Tao Xie,
Chenxi Wang, Sa Wang, Yungang Bao, Ninghui Sun, and Yizhou Shan. 2024. Mem-
Serve: Context Caching for Disaggregated LLM Serving with Elastic Memory
Pool.arXiv preprint arXiv:2406.17565(2024). https://arxiv.org/pdf/2406.17565
[16] Omar Khattab, Arnav Singhvi, Paridhi Maheshwari, Zhiyuan Zhang, Keshav San-
thanam, Sri Vardhamanan, Saiful Haq, Ashutosh Sharma, Thomas T. Joshi, Hanna
Moazam, Heather Miller, Matei Zaharia, and Christopher Potts. 2023. DSPy: Com-
piling Declarative Language Model Calls into Self-Improving Pipelines.arXiv
preprint arXiv:2310.03714(2023). https://arxiv.org/pdf/2310.03714
[17] Tom Kwiatkowski, Jennimaria Palomaki, Olivia Redfield, Michael Collins, Ankur
Parikh, Chris Alberti, Danielle Epstein, Illia Polosukhin, Jacob Devlin, Kenton
Lee, et al. 2019. Natural questions: a benchmark for question answering research.
Transactions of the Association for Computational Linguistics7 (2019), 453–466.
[18] Woosuk Kwon et al. 2023. vLLM: Easy, Fast, and Cheap LLM Serving. https:
//github.com/vllm-project/vllm
[19] Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng,
Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica. 2023. Efficient
Memory Management for Large Language Model Serving with PagedAttention.
InProceedings of the 29th Symposium on Operating Systems Principles(Koblenz,
Germany)(SOSP ’23). Association for Computing Machinery, New York, NY,
USA, 611–626. https://doi.org/10.1145/3600006.3613165
[20] Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir
Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim
Rocktäschel, Sebastian Riedel, and Douwe Kiela. 2020. Retrieval-augmented
generation for knowledge-intensive NLP tasks. InProceedings of the 34th Inter-
national Conference on Neural Information Processing Systems(Vancouver, BC,
Canada)(NIPS ’20). Curran Associates Inc., Red Hook, NY, USA, Article 793,
16 pages. https://dl.acm.org/doi/abs/10.5555/3495724.3496517
[21] Yuhan Liu, Jiayi Yao, Yihua Cheng, Yuwei An, Xiaokun Chen, Shaoting Feng, et al.
2025. LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference.
arXiv preprint arXiv:2510.09665(2025). https://arxiv.org/pdf/2510.09665
[22] LLMS3. 2026. When AI Memory Became an Architecture: KV-Cache Persistence,
MCP, and the Night S3 Got Its Memory Tier. Project website. https://llms3.
com/blog/when-ai-memory-became-an-architecture-may-2026 KV-Cache
Persistence, MCP, and the Night S3 Got Its Memory Tier.
[23] A. Merzky, M. Turilli, M. Titov, A. Al-Saadi, and S. Jha. 2022. Design and Perfor-
mance Characterization of RADICAL-Pilot on Leadership-Class Platforms.IEEE
Transactions on Parallel and amp; Distributed Systems33, 04 (apr 2022), 818–829.
https://doi.org/10.1109/TPDS.2021.3105994
[24] Philipp Moritz, Robert Nishihara, Stephanie Wang, Alexey Tumanov, Richard
Liaw, Eric Liang, Melih Elibol, Zongheng Yang, William Paul, Michael I Jordan,
et al. 2018. Ray: A distributed framework for emerging {AI} applications. In
13th USENIX Symposium on Operating Systems Design and Implementation (OSDI
18). 561–577. https://www.usenix.org/system/files/osdi18-moritz.pdf
[25] Niranda Perera, Arup Kumar Sarker, Kaiying Shan, Alex Fetea, Supun Kambu-
rugamuve, Thejaka Amila Kanewala, Chathura Widanage, Mills Staylor, Tianle
Zhong, Vibhatha Abeykoon, Gregor von Laszewski, and Geoffrey Fox. 2024.
Supercharging distributed computing environments for high-performance data
engineering.Frontiers in High Performance ComputingVolume 2 - 2024 (2024).
https://doi.org/10.3389/fhpcp.2024.1384619
[26] Niranda Perera, Arup Kumar Sarker, Mills Staylor, Gregor von Laszewski, Kaiy-
ing Shan, Supun Kamburugamuve, Chathura Widanage, Vibhatha Abeykoon,
Thejaka Amila Kanewela, and Geoffrey Fox. 2023. In-depth analysis on parallel
processing patterns for high-performance Dataframes.Future Generation Com-
puter Systems149 (2023), 250–264. https://doi.org/10.1016/j.future.2023.07.007
[27] Maximilian Petersohn, Stephen Macke, Doris Xin, William Ma, J. K. Wittenauer,
Stephen Hoyer, Ryan Marcus, Matei Zaharia, and Benjamin Recht. 2020. Towards
Scalable Dataframe Systems.Proceedings of the VLDB Endowment (PVLDB)13,
12 (2020), 2033–2046. https://doi.org/10.14778/3407790.3407807
[28] Hongjin Qian, Zheng Liu, Peitian Zhang, Kelong Mao, Defu Lian, Zhicheng Dou,
and Tiejun Huang. 2025. MemoRAG: Boosting Long Context Processing with
Global Memory-Enhanced Retrieval Augmentation. InProceedings of the ACM
on Web Conference 2025(Sydney NSW, Australia)(WWW ’25). Association for
Computing Machinery, New York, NY, USA, 2366–2377. https://doi.org/10.114
5/3696410.3714805
[29] Ruoyu Qin, Zheming Li, Weiran He, Jialei Cui, Heyi Tang, Feng Ren, Teng Ma,
Shangming Cai, Yineng Zhang, Mingxing Zhang, Yongwei Wu, Weimin Zheng,
and Xinran Xu. 2025. Mooncake: A KVCache-centric Disaggregated Architecture
for LLM Serving.ACM Trans. Storage(Nov. 2025). https://doi.org/10.1145/3773
772 Just Accepted.
[30] Matthew Rocklin. 2015. Dask: Parallel computation with blocked algorithms and
task scheduling. InProceedings of the 14th python in science conference, Vol. 130.
Citeseer, 136. https://proceedings.scipy.org/articles/Majora-7b98e3ed-013.pdf
[31] Arup Kumar Sarker, Aymen Alsaadi, Alexander James Halpern, Prabhath Tan-
gella, Mikhail Titov, Niranda Perera, Mills Staylor, Gregor von Laszewski,
Shantenu Jha, and Geoffrey Fox. 2025. Deep RC: A Scalable Data Engineering
and Deep Learning Pipeline. InJob Scheduling Strategies for Parallel Process-
ing: 28th International Workshop, JSSPP 2025, Milan, Italy, June 3–4, 2025, Re-
vised Selected Papers(Milan, Italy). Springer-Verlag, Berlin, Heidelberg, 205–223.
https://doi.org/10.1007/978-3-032-10507-3_11
[32] Arup Kumar Sarker, Aymen Alsaadi, Niranda Perera, Mills Staylor, Gregor
von Laszewski, Matteo Turilli, Ozgur Ozan Kilic, Mikhail Titov, Andre Merzky,
Shantenu Jha, et al. 2024. Design and implementation of an analysis pipeline for
heterogeneous data.arXiv preprint arXiv:2403.15721(2024).
[33] Arup Kumar Sarker, Aymen Alsaadi, Niranda Perera, Mills Staylor, Gregor
von Laszewski, Matteo Turilli, Ozgur Ozan Kilic, Mikhail Titov, Andre Merzky,
Shantenu Jha, et al. 2024. Radical-Cylon: A Heterogeneous Data Pipeline for
Scientific Computing. InJob Scheduling Strategies for Parallel Processing. Springer
Nature Switzerland, 84–102. https://doi.org/10.1007/978-3-031-74430-3_5
[34] Arup Kumar Sarker, Mills Staylor, Aymen Alsaadi, Gregor von Laszewski,
Shantenu Jha, and Geoffrey Fox. 2026. AAFLOW: Scalable Patterns for Agentic
AI Workflows.arXiv preprint arXiv:2605.02162(2026). Under Submission to
SC2026.
[35] Pavel Shamis, Manjunath Gorentla Venkata, M. Graham Lopez, Matthew B.
Baker, Oscar Hernandez, Yossi Itigin, Mike Dubman, Gilad Shainer, Richard L.
Graham, Liran Liss, Yiftah Shahar, Sreeram Potluri, Davide Rossetti, Donald
Becker, Duncan Poole, Christopher Lamb, Sameer Kumar, Craig Stunkel, George
Bosilca, and Aurelien Bouteiller. 2015. UCX: An Open Source Framework for
HPC Network APIs and Beyond. In2015 IEEE 23rd Annual Symposium on High-
Performance Interconnects. 40–43. https://doi.org/10.1109/HOTI.2015.13
13

## PDF Page 14