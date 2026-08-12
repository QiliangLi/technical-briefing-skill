# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

## PDF Page 1

[AAFLOW+] Stateful Operator Abstraction with Zero-Copy
Distributed KV Cache Orchestration for Multi-Agent Workflows
Arup Kumar Sarker
Alexander James Halpern
Mills Staylor
University of Virginia,
Biocomplexity Institute and Initiative
Charlottesville, VA, USA
djy8hg@virginia.edu
halperna22@gmail.com
qad5gv@virginia.edu
Gregor von Laszewski
Geoffrey Fox
Yue Cheng
Biocomplexity Institute and Initiative
University of Virginia
Charlottesville, VA, USA
laszewski@gmail.com
vxj6mb@virginia.edu
mrz7dp@virginia.edu
Aymen Alsaadi
Shantenu Jha
Rutgers University
Princeton Plasma Physics Laboratory
Princeton, NJ, USA
aymen.alsaadi@rutgers.edu
shantenu.jha@rutgers.edu
ABSTRACT
Multi-agent LLM systems increasingly integrate retrieval, plan-
ning, and reasoning, but remain fundamentally text-centric, re-
quiring agents to repeatedly recompute shared context through
expensive prefill. Although single-request inference is known to
be accelerated by KV-cache management, it is usually restricted
to local serving scopes. We introduce AAFLOW+, a stateful ex-
tension of agentic workflow operators that makes KV cache a
first-class distributed systems object. AAFLOW+ builds processes
into communication-aware graphs that concurrently optimize data,
prompts, and reusable model state. It also provides operators for KV
materialization, transfer, fork, composition, and eviction. Its run-
time enables zero-copy, transfer-aware execution, allowing agents
to reuse long context without recomputation. AAFLOW+ reduces
TTFT by up to 50.2×, achieves up to 7.63× reduced multi-agent com-
pute cost at 16-agent scale, reduces KV memory by 1.72–6.10×, and
increases throughput by more than 7.74×, based on an analytical
cost model parameterized by empirical hardware microbenchmarks.
The results demonstrate that KV transmission outperforms recom-
putation on networks with moderate to high bandwidth, making
sure KV-state sharing greatly increases efficiency in multi-agent
LLM systems by replacing text passing.
PVLDB Reference Format:
Arup Kumar Sarker, Alexander James Halpern, Mills Staylor, Gregor von
Laszewski, Geoffrey Fox, Yue Cheng, Aymen Alsaadi, and Shantenu Jha.
[AAFLOW+] Stateful Operator Abstraction with Zero-Copy Distributed
KV Cache Orchestration for Multi-Agent Workflows. PVLDB, 14(1):
XXX-XXX, 2020.
doi:XX.XX/XXX.XX
PVLDB Artifact Availability:
The source code, data, and/or other artifacts have been made available in
AAFLOW/stateful_agentic_algebra directory at https://github.com/aru
pcsedu/AAFLOW.
This work is licensed under the Creative Commons BY-NC-ND 4.0 International
License. Visit https://creativecommons.org/licenses/by-nc-nd/4.0/ to view a copy of
this license. For any use beyond those covered by this license, obtain permission by
emailing info@vldb.org. Copyright is held by the owner/author(s). Publication rights
licensed to the VLDB Endowment.
Proceedings of the VLDB Endowment, Vol. 14, No. 1 ISSN 2150-8097.
doi:XX.XX/XXX.XX
1 INTRODUCTION
Large language models are increasingly deployed asagentic sys-
temsthat interleave retrieval, reasoning, tool invocation, and mem-
ory across multiple stages.

## Evidence locator: PDF Page 2

## PDF Page 2

object. AAFLOW+ extends operator abstraction fromdataflowto
stateflow, enabling explicit modeling of KV-state lifecycle through
operators for materialization, transfer, fork, restricted composition,
and eviction (Figure 1).

## Evidence locator: PDF Page 18

## PDF Page 18

F EV ALUATION DETAILS
We utilize a trace-driven model parameterized by hardware mi-
crobenchmarks to rigorously isolate the fundamental systems-level
KV-transfer limits from the inherently high variance of Python-
based agentic frameworks. We show full experimental results with
the Hugging Face (HF) backend and the Mistral model in Section 6
(Evaluation) of this paper. In the appendix section, we will cover
all experiments with HF, vLLM, and SGLang backends with the
Llama3 model and vLLM, and SGLang backends with the Mistral
model. All source code and experimental results are committed to
the following repository: https://github.com/arupcsedu/AAFLO
W, and all environmental setup and dependencies are written on
stateful_agentic_algebra/Readme.mdfile.
F.1 Experiment 1 extension: TTFT Reduction
The first experiment measures time to first token (TTFT) as context
length increases. Text-passing systems repeatedly rebuild the same
prefix and therefore pay a TTFT cost that scales with context length:
𝑇𝑇 𝐹𝑇text ∝𝐿.
AAFLOW+ pays the prefill cost once and then resumes from the
distributed state:
𝑇𝑇 𝐹𝑇state ≈𝑇 transfer +𝑇 resume.
Across all three backends shown in Table 8, AAFLOW+ achieves
the lowest workflow-level TTFT because it replaces repeated prompt
replay with explicit state resume. On the HF backend, the clearest
gap appears on Mistral: AAFLOW+ reaches 0.041 s mean TTFT,
compared with 2.057 s for AAFLOW-text, 2.017 s for dense pre-
fill, and 0.704 s for KVCOMM. Even the strongest non-AAFLOW+
workflow baseline, DistServe style, remains at 0.123 s, still 3.0 ×
slower. On Llama3, the same ordering holds: AAFLOW+ reaches
0.030 s, while DistServe style is 0.052 s and SGLang prefix is 0.086 s.
The largest-context results show the same effect more sharply. On
vLLM at maximum context, Mistral AAFLOW+ is 0.171 s, whereas
dense prefill is 38.880 s, AAFLOW-text is 39.655 s, KVCOMM is
13.315 s, and DistServe style is 0.316 s. On SGLang at maximum
context, Mistral AAFLOW+ is 0.876 s, while dense prefill is 13.317 s,
AAFLOW-text is 13.566 s, KVCOMM is 5.089 s, and DistServe style
is 1.021 s.
The reason is consistent across backends. Dense prefill and
AAFLOW-text always reconstruct the prompt prefix, so their TTFT
grows with context length. Local-prefix baselines such as vLLM-
prefix and SGLang-prefix improve over dense replay, but their reuse
is confined to one serving engine and does not expose explicit trans-
fer, placement, or branch lineage across workflow agents. KVCOMM
communicates KV-like state, but in these experiments it pays more
modeled communication overhead and achieves lower effective
reuse than AAFLOW+. DistServe style remains the closest competi-
tor because it also separates prefill from decode, but it still lacks
the explicit fork/transfer/restricted-merge workflow abstraction of
AAFLOW+, so it cannot fully eliminate branch-level prefix replay.
F.2 Experiment 2: Multi-Agent Scaling
The goal is to evaluate how total latency changes as the number
of agents increases. Text-centric systems repeat prefill and context
construction for each agent. AAFLOW+ should amortize the shared
prefix and scale mainly with branch continuation work. The imple-
mentation uses a finite parallel-wave model, so small agent counts
can fit into one stateful wave while larger agent counts require
additional waves.
The multi-agent scaling results show (Table 9) that AAFLOW+
changes how latency grows with agent count. On the HF back-
end, the strongest comparison appears at 16 agents: for Mistral,
AAFLOW+ reaches 224.39 s, while the nearest non-AAFLOW+ com-
petitor, SGLang prefix, is 1704.86 s, giving a 7.60× speedup; dense
prefill is even worse at 2716.11 s. For Llama3 at 16 agents, AAFLOW+
reaches 220.05 s, while SGLang prefix is 1679.81 s, again a 7.63× gap.
The same trend holds on the live serving backends. On vLLM at 16
agents, Mistral AAFLOW+ is 465.45 s versus 3532.56 s for SGLang
prefix; on SGLang, Mistral AAFLOW+ is 701.29 s versus 5363.03 s for
SGLang prefix. Llama3 follows the same pattern, reaching 253.53 s
versus 1926.11 s on vLLM and 329.07 s versus 2514.49 s on SGLang.
AAFLOW+ outperforms other methods by materializing the
shared prefix once and forking reusable state, causing memory
growth in execution waves as parallel capacity is reached, rather
than through repeated full-prefill operations. In contrast, non-
AAFLOW+ baselines like dense prefill and AAFLOW-text allocate
a complete prefill for each agent, while vLLM-prefix and SGLang-
prefix offer only local prefix reuse within the engine. Although local
reuse reduces some duplication, it does not eliminate workflow-
level branch duplication when multiple agents share a prefix, lead-
ing to a growing scaling gap as agent count increases.
F.3 Experiment 3: Transfer vs. Recomputation
The goal is to evaluate the scheduler decision:
𝑇transfer = KV bytes
bandwidth +latency, 𝑇 recompute =𝑇 prefill.
Experiment 3 (Table 10) shows that AAFLOW+ needs both ex-
plicit state operators and a cost model.

## Evidence locator: PDF Page 8

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

## Evidence locator: PDF Page 12

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
pendent requests or agents.

## Evidence locator: PDF Page 10

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