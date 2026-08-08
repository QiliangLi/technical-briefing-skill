d profiling optimal distributed KV eviction policies
remains future work.
4.5 Stateful Workflow Composition
A stateful workflow composes data operators and state operators
into a single graph. A typical branching workflow can be written as
𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 →𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 →
{𝑂𝑝 (1)
𝑟𝑒𝑎𝑠𝑜𝑛 , . . . , 𝑂𝑝(𝑘)
𝑟𝑒𝑎𝑠𝑜𝑛 } →𝑂𝑝 𝑘𝑣_𝑚𝑒𝑟𝑔𝑒 .(26)
This expression models a workflow where shared context is pro-
cessed once, branched into multiple reasoning paths, and later
merged under specific policies. As illustrated in Figure 5, dashed
edges indicate KV state flow and solid edges denote standard op-
erator outputs. Explicitly distinguishing state from data depen-
dencies enables the compiler to schedule reasoning branches effi-
ciently, avoiding redundant prefill computation for each branch.
Currently, restricted merge supports strictly non-overlapping se-
quential concatenation of independent branch outputs, avoiding
arbitrary tensor-blending of divergent attention states, which would
violate positional encoding semantics.
4.6 State-Aware Scheduling
The scheduler plays a central role in determining how state is man-
aged during execution. For each operator, the scheduler evaluates
5

## PDF Page 6

Figure 5: Stateful operator abstraction composes conven-
tional reasoning operators with KV-state operators. Dashed
edges represent state dependencies.
whether to transfer existing state or recompute it from scratch. This
decision is guided by a cost model:
𝜋(𝑆)=
(
transfer,if𝑇 𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 <𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙
recompute,otherwise (27)
Here, 𝑇𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 represents the cost of recomputing the state from
input text. When transfer is cheaper, the system reuses existing
state; otherwise, it falls back to recomputation. More generally, the
scheduler optimizes the objective: min Í
𝑖 𝑇𝑖 +𝜆·𝑀𝑒𝑚 𝑖 where 𝑇𝑖
is the execution time of operator 𝑖, 𝑀𝑒𝑚𝑖 is its memory footprint,
and 𝜆 controls the trade-off between latency and memory usage.
This formulation allows the system to adapt to different workloads
and resource constraints. For example, in memory-constrained
environments, the scheduler may choose to recompute state rather
than store and transfer it.
4.7 Runtime Integration
The runtime extends the capabilities of existing LLM serving sys-
tems like vLLM [18] and SGLang [48], which already manage KV
caches efficiently on single nodes, to distributed workflows. Exe-
cution involves four key stages: generating the stateful execution
graph 𝐺𝑠, scheduling operators and state placement, executing op-
erators with KV reuse when possible, and dynamically updating
the state graph as states are created or consumed. This approach
maintains compatibility with current model-serving infrastructure
while supporting advanced distributed optimization.
5 IMPLEMENTATION
5.1 Overview
We implement the proposed stateful agentic abstraction as a dis-
tributed runtime that extends AAFLOW with explicit support for
KV-state orchestration. The implementation builds on the operator-
driven execution model introduced in AAFLOW, where workflows
are compiled into communication-aware execution graphs over
distributed resources. In contrast to existing agent frameworks,
which treat model execution as a black box, our system externalizes
KV cache as a manipulable distributed state object. The system
consists of four tightly integrated layers: a state-aware compiler,
a KV-state manager, a transport subsystem, and an execution run-
time (Figure 6). These components collectively enable the system
to materialize, transfer, reuse, and evict KV state while preserving
compatibility with existing LLM serving infrastructures such as
vLLM [19] and SGLang [47].
Figure 6: System architecture illustrating the interaction be-
tween compiler, runtime, KV state layer, and transport.
5.2 Build Compiler and Execution Graph
The compiler extends the workflow of AAFLOW compilation pro-
cess by incorporating state dependencies into the execution graph.
Given a workflow 𝑊 , the compiler constructs a stateful graph
𝐺𝑠 =(𝑉 , 𝐸 𝑑, 𝐸𝑠 ), where 𝐸𝑑 represents data dependencies and 𝐸𝑠
represents KV-state dependencies. Each operator is instantiated as:
𝑣𝑖 =(𝑂𝑝 𝑠
𝑖 ,R 𝑖,L 𝑖 )(28)
where R𝑖 captures resource requirements and L𝑖 encodes lo-
cality constraints derived from KV-state placement. During com-
pilation, the system identifies shared context across agents and
inserts explicit state operators such as 𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 and 𝑂𝑝 𝑘𝑣_𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 .
This transformation enables the reuse of model execution state
across agents rather than recomputation from text. The compila-
tion process preserves the determinism guarantees of AAFLOW
while extending its execution model to include stateflow alongside
dataflow.
5.3 KV-State Manager
The KV-state manager is responsible for representing and maintain-
ing KV cache across distributed resources. Inspired by block-based
KV management in vLLM [ 19], the system partitions KV cache
into fixed-size blocks to enable efficient reuse and transfer. Each
KV state is represented as a collection of blocks with associated
metadata, as defined in Section 3. Internally, the system maintains
a distributed mapping:
M:(𝑠𝑡𝑎𝑡𝑒_𝑖𝑑, 𝑏𝑙𝑜𝑐𝑘_𝑖𝑑) → (𝑑𝑒𝑣𝑖𝑐𝑒, 𝑎𝑑𝑑𝑟𝑒𝑠𝑠)(29)
This mapping allows the runtime to locate KV blocks without
scanning global state. The manager also tracks lineage information,
ensuring that forked states maintain consistent ancestry relation-
ships. Metadata is encoded using Apache Arrow [3], which provides
a columnar, zero-copy representation that can be shared across com-
ponents without serialization overhead. This design aligns with
prior work demonstrating that zero-copy data exchange is critical
for high-performance distributed pipelines.
5.4 Transport Subsystem
The transport subsystem enables efficient movement of KV state
across nodes and devices. It leverages high-performance commu-
nication frameworks such as UCX [ 35] and MPI [ 6] to perform
zero-copy transfers of tensor buffers. Unlike traditional distributed
systems that serialize objects into intermediate formats, our system
transfers raw KV blocks directly between memory regions. Meta-
data is transmitted separately using Arrow descriptors, while large
tensor buffers are transferred using RDMA when available. The
6

## PDF Page 7

transfer cost is modeled as:
𝑇𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 = |𝐾𝑉|
𝐵𝑊 +𝛿(30)
To reduce communication overhead, the system operates at block
granularity and transfers only the subset of KV state required by
downstream operators. This approach is particularly effective for
prefix-based reuse, where only early segments of the sequence are
needed. Additionally, the transport subsystem supports overlapping
communication with computation. As KV blocks arrive, operators
can begin partial execution, improving overall pipeline throughput.
5.5 Execution Runtime
The execution runtime orchestrates the execution of the compiled
graph across distributed resources. It schedules operators based on
both data availability and KV-state availability, ensuring that tasks
are executed only when required inputs and state are ready.
Each operator invocation interacts with the underlying LLM
serving system through KV-aware APIs. Specifically, when execut-
ing a reasoning operator, the runtime injects precomputed KV state
into the model, bypassing the prefill stage and directly initiating
decoding. This mechanism builds upon the KV reuse capabilities of
systems such as vLLM and SGLang, extending them from single-
node execution to distributed workflows [19, 47].
5.6 Fault Tolerance and Consistency
Maintaining correctness in the presence of distributed state requires
careful validation. Each KV state carries metadata that ensures com-
patibility across operators. In particular, lineage tracking ensures
that state is only reused in contexts where it remains semantically
valid. When failures occur, the system can recover by recomputing
state from the nearest valid prefix. This fallback mechanism ensures
robustness without requiring full checkpointing of intermediate
states.
The proposed system generalizes agentic execution from a state-
less, text-based model to a stateful, distributed model. By explicitly
representing, transferring, and reusing KV cache, the system elimi-
nates redundant prefill computation and enables scalable multi-
agent workflows. The combination of state-aware compilation,
structured state representation, and cost-driven scheduling forms
the foundation for efficient stateful execution.
5.7 Branching Optimization
Branching workloads are particularly well-suited for stateful exe-
cution. Consider a workflow that generates 𝑘 reasoning branches
from a shared prefix. In text-based systems, each branch must inde-
pendently process the full context:
𝑇 𝑘
𝑡𝑒𝑥𝑡 =𝑘·𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿)(31)
In contrast, our system computes the prefix once and then forks
the resulting KV state:
𝑇 𝑘
𝑠𝑡𝑎𝑡𝑒 =𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +𝑘·𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 (32)
Since decoding is significantly cheaper than prefill, this leads to
substantial performance gains. Figure 5 illustrates this optimization.
Restricted merge is used to append non-overlapping segments,
rather than attempting to mathematically blend divergent parallel
attention matrices, which would corrupt RoPE positional encodings.
6 EV ALUATION
To isolate the performance of distributed KV-transfer from the
variance of application-level framework overhead, we evaluate
our abstraction using deterministic synthetic prompts and natural
questions [17] datasets and a trace-driven analytical model parame-
terized by rigorous empirical microbenchmarks (TTFT, multi-agent
computing cost, transfer/recompute tradeoffs, memory footprint,
throughput, and framework overhead).AAFLOW+ is also com-
patible with vLLM, and SGLang backends
6.1 Baselines
We compare against representative systems from three categories:
LLM serving, KV-cache optimization, and multi-agent orchestra-
tion.
(1) vLLM (PagedAttention)[ 19]: vLLM is a state-of-the-art
LLM serving system that optimizes KV cache using block-based
memory management and PagedAttention. It represents the strongest
baseline for single-node KV reuse and is widely used in production.
(2) SGLang (RadixAttention)[ 47]: SGLang improves KV reuse
by identifying shared prefixes across structured language programs
and exploiting radix-tree-style attention reuse. It provides a natural
comparison for prefix-sharing optimizations.
(3) DistServe[ 50]: DistServe is a distributed LLM serving system
that decouples prefill and decode stages across nodes. While it
improves resource utilization, it does not expose KV cache as a
reusable distributed object across agents.
(4) AAFLOW-text[ 34]: AAFLOW-text focuses on memory-
efficient inference through offloading from RAG and scheduling
techniques. It highlights that prefill from vectorstore through RAG
could improve, but does not optimize inter-agent KV reuse.
(5) Text-based Dense Prefil Orchestration (Sarathi-style)[1]:
This baseline represents current agent frameworks where agents
exchange text messages without KV reuse. Each agent performs
independent prefill.
(6) Communication-oriented KV-cache reuse (KVCOMM)[43]:
KVCOMM shares reusable cache context across related agent inter-
actions instead of fully replaying text prompts. Unlike AAFLOW+,
it models KV communication without exposing a full workflow-
level abstraction for state materialization, fork, transfer, restricted
composition, and eviction.
6.2 Metrics
We evaluate systems using metrics that capture both model-level
performance and system-level efficiency.
Time-to-First-Token (TTFT):.TTFT measures the latency between
request arrival and the generation of the first output token:
𝑇𝑇 𝐹𝑇=𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 +𝑇 𝑞𝑢𝑒𝑢𝑒 +Ω(33)
Since prefill dominates TTFT for long contexts, reducing redundant
prefill is critical.
7

## PDF Page 8

Aggregate Compute Cost:The aggregate compute cost is defined
as:
𝑇𝑡𝑜𝑡𝑎𝑙 =𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 +𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 +Ω(34)
Framework Overhead ( Ω):Following AAFLOW, we isolate sys-
tem overhead as:
Ω=𝑇 𝑡𝑜𝑡𝑎𝑙 − (𝑇𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 +𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 )(35)
This includes scheduling, communication, serialization, and syn-
chronization costs.
Throughput:Throughput is measured as tokens per second:
𝑇 ℎ𝑟𝑜𝑢𝑔ℎ𝑝𝑢𝑡= Total tokens generated
𝑇𝑡𝑜𝑡𝑎𝑙
(36)
Memory Footprint:We measure peak KV memory usage:
𝑀𝑒𝑚𝐾𝑉 =max
𝑡
∑︁
𝑖
|𝐾𝑉𝑖 (𝑡)|(37)
KV Reuse Ratio:To quantify reuse effectiveness, we define:
𝑅𝑒𝑢𝑠𝑒= Tokens served from KV cache
Total tokens processed (38)
Transfer Efficiency:We evaluate the ratio between transfer cost
and avoided recomputation:
𝐸 𝑓 𝑓 𝑖𝑐𝑖𝑒𝑛𝑐𝑦= 𝑇𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 −𝑇 𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟
𝑇𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙
(39)
6.3 Experimental Setup
All experiments are conducted on a distributed GPU cluster.
Hardware:We use a cluster of 4–16 nodes, each equipped with
NVIDIA A100 (80GB and 40GB), 32–64 CPU cores, and RDMA-
enabled InfiniBand interconnects.
Models and backend:The HF backend uses AutoTokenizer and
AutoModelForCausalLM with deterministic decoding. KV meta-
data is extracted from past_key_values; tensors are not serialized
by default. The measured real-model values used by the bench-
mark matrix include prefill time, decode time, TTFT approximation,
generated-token count, KV shape metadata, and KV byte size.
Table 1: HF, vLLM, SGLang backend use below model cover-
age in the completed run.
Name HF model id Max Output
HF model id context tokens
MistralMistral-7B-Instruct-v0.332,640 64
Llama3Meta-Llama-3-8B-Instruct8,128 64
Mistral was tested up to 32,640 context tokens so that con-
text_tokens + output_tokens stayed within the configured 32,768
token window. Llama3 was tested up to 8,128 context tokens with
64 output tokens, matching the configured 8,192-token limit (Table -
1). Our runtime integrates with the backend’s KV-cache APIs while
extending them to support distributed state transfer. Communi-
cation is implemented using UCX and NCCL. Mistral-7B, vLLM,
and SGLang are licensed under Apache 2.0. Llama-3-8B is licensed
under the Meta Llama 3 Community License.
Cost and network parameters:For stateful runtime experiments,
the configured state-transfer model uses measured KV bytes. Ex-
periment 1 used bandwidth_bytes_per_sec = 25,000,000,000 ,
equivalent to 25 GB/s or 200 Gbps, with network_latency_sec =
50us, resume_overhead_sec = 0.1ms , and very small framework
overheads (omega_state_sec = omega_text_sec = 50us ). Ex-
periment 3 sweeps network bandwidth from 10 Gbps to 400 Gbps
and uses both RDMA-like 10us and Ethernet-like 100us latency
settings.
6.4 Workloads and Topologies
The benchmarked scenario is a shared-prefix agentic workflow,
not independent stateless chat. The main topology is a parallel
broadcast / Tree-of-Thought style DAG:
root context→KV materialize→KV fork
→ {agent 1, . . . ,agent 𝑘 } →merge(40)
A single root context is processed once, and𝑘 downstream agents
evaluate different reasoning paths using the same prefix. The multi-
agent scaling experiment sweeps 𝑘∈ { 1, 2, 4, 8, 16}. The main real-
model runs use 𝑌= 64generated tokens per branch. This output
length is important: AAFLOW+ primarily reduces prefill and TTFT.
If 𝑌 were thousands of tokens, decode would dominate and the
relative TTFT advantage would be smaller. The prompts are deter-
ministic synthetic long-context prompts. They are used to control
context length and branch count precisely. These experiments there-
fore measure systems behavior—state reuse, transfer, memory, and
overhead—rather than dataset answer quality.
We evaluate three representative workloads:Multi-Agent Debate:
multiple agents iteratively refine responses using shared context.
Tree-of-Thought Reasoning:branching reasoning paths with shared
prefixes.Retrieval-Augmented Generation (RAG):agents share re-
trieved context and perform downstream reasoning. It is not ex-
pected to help independent short stateless prompts, because such
prompts have no shared state to fork or transfer. Each workload
varies in context length (1K–32K tokens), number of agents (2–16),
and branching factor (2–16).
6.5 Meaning of total latency
The total_latency_sec field in these tables is a modeled aggre-
gate workload cost, not the observed Slurm wall-clock runtime
of the experiment script. For text baselines, the benchmark mul-
tiplies measured per-prompt prefill and decode costs by the num-
ber of branch instances and prompts. For example, Experiment
1 uses 16 agents, branch factor 8, and 32 prompts, so dense text
passing is charged for16 × 8 × 32 = 4096full-context prefill/de-
code executions. AAFLOW+ is charged for one shared material-
ized state plus reused state transfers and continuations. Therefore
large total_latency_sec values should be interpreted as aggre-
gate work avoided by state reuse, not as the elapsed time of the
Slurm job.
6.6 Experiment 1: TTFT Reduction
The first experiment measures time to first token (TTFT) as a func-
tion of context length. Text-passing systems repeatedly rebuild the
8

## PDF Page 9

0
 5000
 10000
 15000
 20000
 25000
 30000
Context Length (tokens)
0.0
0.5
1.0
1.5
2.0
2.5
3.0
3.5
4.0TTFT (s)
TTFT vs Context Length by Baseline
AAFLOW+
aaﬂow_text
dense_preﬁll
distserve_style
kvcomm_preﬁx
sglang_preﬁx
vllm_local_preﬁx
Figure 7: Experiment-1: TTFT vs context length across mul-
tiple baselines. The curves confirm that text baselines scale
with context length, while AAFLOW+ grows slowly because
branch cost follows the transfer/resume path rather than
repeated prefill
Table 2: Experiment-1: Mean TTFT reduction and Through-
put with variation context grid and fixed 16 agents.
Model Baseline Mean TTFT (s) Relative to AAFLOW+
Mistral AAFLOW+ 0.041 1.00×
Mistral dense prefill 2.017 49.2×slower
Mistral AAFLOW-text 2.057 50.2×slower
Mistral vLLM local prefix 0.437 10.7×slower
Mistral SGLang prefix 0.280 6.8×slower
Mistral KVCOMM 0.704 17.2×slower
Mistral DistServe style 0.1233.0×slower
Llama3 AAFLOW+ 0.030 1.00×
Llama3 dense prefill 0.499 16.6×slower
Llama3 AAFLOW-text 0.509 17.0×slower
Llama3 vLLM local prefix 0.124 4.1×slower
Llama3 SGLang prefix 0.086 2.9×slower
Llama3 KVCOMM 0.187 6.2×slower
Llama3 DistServe style 0.0521.7×slower
same prefix and pay a TTFT cost that scales with context length:
𝑇𝑇 𝐹𝑇text ∝𝐿. AAFLOW+ pays the prefill cost once and then re-
sumes from the distributed state:
𝑇𝑇 𝐹𝑇state ≈𝑇 transfer +𝑇 resume.
Table 2(HF+Mistral, Llama3) and Figure 7(HF+Mistral) reports
the mean TTFT across all tested context lengths for each model.
AAFLOW+ has the lowest mean TTFT for both models. On Mistral,
dense text prefill, AAFLOW-text and vLLM-local, SGLang, share
almost same cold-start TTFT because each must first materialize
the prompt prefix locally, while AAFLOW+ has 0.041s, a49 .2×
reduction. Local-prefix baselines reduce total repeated work after
cache population, which is reflected in aggregate compute cost
rather than cold TTFT. The nearest competitor by mean TTFT is
DistServe-style at 0.123s, still2 .99× slower than AAFLOW+. The
largest contexts show the widening gap most clearly.
The TTFT curves validate the expected asymptotic behavior.
Dense and text baselines scale with context length because every
agent or branch repeats prefix prefill. AAFLOW+ grows much more
slowly because the marginal branch cost is the KV transfer/resume
path. Mistral shows the strongest visible spread because the run
reaches 32K context; DistServe-style is the nearest TTFT competitor
because it also separates prefill from decode, but it does not expose
the same explicit state abstraction and therefore remains slower in
these state-transfer workloads.
2
 4
 6
 8
 10
 12
 14
 16
Number of Agents
2
4
6
8
10
12Speedup (baseline / AAFLOW+)
Speedup vs Number of Agents
AAFLOW+
aaﬂow_text
dense_preﬁll
distserve_style
kvcomm_preﬁx
sglang_preﬁx
vllm_local_preﬁx
Figure 8: Experiment-2: Scaling impact of operator abstrac-
tion for multi-agent jobs with HF+Mistral. Total latency and
speedup versus the nearest competitor with HF backend. The
scaling result is the clearest evidence that the KV state ab-
straction matters for multi-agent workloads.
Table 3: Experiment-2: Aggregate Compute Cost and Effi-
ciency Gain (EG) vs nearest competitor in HF backend
Model Agents AAFLOW+ Dense SGLang (s) EG to
(s) (s) Competitor SGLang
Mistral 1 30.700 169.757 119.135 3.88×
Mistral 2 30.700 339.514 224.850 7.32×
Mistral 4 58.371 679.027 436.281 7.47×
Mistral 8 113.714 1358.055 859.142 7.56×
Mistral 16 224.399 2716.109 1704.865 7.60×
Llama3 1 29.067 143.959 112.396 3.87×
Llama3 2 29.067 287.918 216.891 7.46×
Llama3 4 56.351 575.836 425.880 7.56×
Llama3 8 110.918 1151.671 843.858 7.61×
Llama3 16 220.052 2303.342 1679.815 7.63×
6.7 Experiment 2: Multi-Agent Scaling
To evaluate multi-agent scaling, we extrapolate aggregate multi-
agent compute time using an analytical cost model parameterized
by empirical microbenchmarks gathered on our GPU cluster. In text-
passing systems, each agent pays for repeated context processing,
so cost increases approximately linearly with the agent count. In
9

## PDF Page 10

high-branch-factor workflows (e.g., 16 parallel branches), a single
node can’t run all decodes without OOM errors, so the workload
must be distributed across nodes, requiring KV network transfer.
AAFLOW+ materializes the shared context once and then fork the
state, which should improve the speedup as𝑘grows:
𝑇 𝑘
state ≈𝑇 prefill +𝑘·𝑇 decode,
Table 3 and Figure 8 show aggregate compute cost by agent
count. The scaling table shows two effects. First, AAFLOW+ uses
the available stateful parallel width for the first two agents, so 1-
agent and 2-agent costs are equal for both models. Second, after
the parallel width is filled, costs grow by waves rather than by
full repeated prefill. Mistral grows from 30.700s at 1–2 agents to
224.399s at 16 agents. Llama3 grows from 29.067s at 1–2 agents to
220.052s at 16 agents. The nearest non-AAFLOW+ competitor at
every agent count is SGLang prefix, but it remains3 .87×–7.63×
slower because local prefix reuse does not remove workflow-level
branch duplication.
The dense baseline is much worse: at 16 agents, the dense to-
tal aggregated compute cost is 2716.109 for Mistral. AAFLOW+
converts the agent dimension from repeated prefill into repeated
decode continuation from an already materialized state. Even a
strong local-prefix baseline cannot fully remove duplicated branch
work once many agents need the same prefix.
0
 5000
 10000
 15000
 20000
 25000
 30000
Context Length (tokens)
0.0
0.5
1.0
1.5
2.0
2.5
3.0
3.5Time (s)
Transfer/Recompute Crossover by Baseline Policy
AAFLOW+ transfer @ 100Gbps
AAFLOW+ transfer @ 10Gbps
AAFLOW+ transfer @ 200Gbps
AAFLOW+ transfer @ 25Gbps
AAFLOW+ transfer @ 400Gbps
Dense/text recompute
Local-preﬁx reuse (vLLM/SGLang/KVCOMM)
Figure 9: Experiment-3: RDMA-like transfer benefit sum-
mary with HF backend and Mistral model. This experiment
gives a concrete scheduling rule for stateful execution. The
maximum transfer-vs-recompute speedup grows with band-
width.
6.8 Experiment 3: Transfer vs. Recomputation
The third experiment compares KV transfer cost to recomputing
the prompt prefill where𝑇 recompute =𝑇 prefill :
𝑇transfer = KV bytes
bandwidth +latency,
The scheduler prefer state transfer when 𝑇transfer <𝑇 recompute.
Figure 9 summarizes the RDMA-like latency sweep. On slow 10
Gbps links, the KV object can be large enough that recomputa-
tion may be preferable for some contexts (5 out of 8). This is ex-
pected: low bandwidth makes the serialized KV payload expensive.
Table 4: Experiment-4: Mean peak KV memory and memory
ratio with HF backend
Model Baseline Peak KV Memory
(GiB) Ratio
Mistral AAFLOW+ 8.355 1.00×
Mistral dense prefill 49.987 5.98×larger
Mistral AAFLOW-text 53.986 6.46×larger
Mistral vLLM local prefix 14.3511.72×larger
Mistral SGLang prefix 14.591 1.74×larger
Mistral KVCOMM 15.702 1.88×larger
Mistral DistServe style 50.995 6.10×larger
Llama3 AAFLOW+ 4.210 1.00×
Llama3 dense prefill 25.188 5.98×larger
Llama3 AAFLOW-text 27.202 6.46×larger
Llama3 vLLM local prefix 7.2311.72×larger
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