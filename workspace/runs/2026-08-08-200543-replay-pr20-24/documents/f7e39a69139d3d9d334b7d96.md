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
ory across multiple stages. Frameworks such as ReAct, Reflex-
ion, AutoGen, and DSPy expand this design space, while RAG
improves factual grounding by conditioning generation on exter-
nal data [16, 20, 38, 41, 42]. However, as these workflows become
deeper and more collaborative, a fundamental systems bottleneck
emerges: agents continue to communicate primarily throughtext.
Even when shared context has already been computed, downstream
agents must replay it through costly prefill computation, repeatedly
reconstructing identical model state.
This inefficiency is closely tied to the treatment of the key-value
(KV) cache, a central object in LLM inference and a key component
of AI memory [ 22]. Recent serving systems such as vLLM [ 19],
SGLang [47], DistServe, MemServe, Mooncake, ChunkAttention,
KVCOMM, and RelayCaching [12, 15, 29, 43, 44, 49] demonstrate
that KV cache management is critical for reducing latency and
improving throughput. These systems optimize KV reuse through
techniques such as block-level allocation, prefix sharing, and de-
coupled prefill and decode stages. However, their scope is largely
confined to single-request or single-cluster execution. They do not
provide a workflow-level abstraction for explicitly transferring,
branching, and reusing KV state across multiple agents, which im-
pacts pipeline execution. In planner–retriever–solver workflows,
multiple agents often operate over the same long context prefix.
In tree-of-thought or debate settings, agents branch from shared
prefixes and explore alternative reasoning paths. In collaborative
RAG, agents independently retrieve overlapping evidence and re-
process similar context. In all cases, current systems serialize shared
state back into text, transforming a stateful execution problem into
repeated prompt replay. The result is increased time-to-first-token
(TTFT), duplicated computation, higher framework overhead, and
limited control over state placement and reuse.
Recent frameworks like AAFLOW [ 34], model agentic work-
flows as compositions of distributed operators and reduce orches-
tration overhead via communication-aware DAG execution and
zero-copy data transfer. However, AAFLOW remains data-centric
and does not expose internal model state, such as KV cache, as
part of its abstraction. We introduceAAFLOW+, a stateful ex-
tension that elevates KV cache to a first-class distributed systems
arXiv:2607.10987v1  [cs.DC]  13 Jul 2026

## PDF Page 2

object. AAFLOW+ extends operator abstraction fromdataflowto
stateflow, enabling explicit modeling of KV-state lifecycle through
operators for materialization, transfer, fork, restricted composition,
and eviction (Figure 1). This lets the compiler choose between text
passing, KV reuse, state transfer, and eviction, shifting optimiza-
tion from prompt construction to explicit state management. Our
runtime makes the KV cache transportable by using explicit meta-
data, zero-copy communication, and transfer-aware scheduling. By
separating metadata from tensor buffers and using Arrow-based
formats, the system minimizes serialization costs and enables effi-
cient state transfer between distributed components [2]. AAFLOW+
ensures correctness by enforcing compatibility on model identity,
positional encoding, and execution history, allowing safe prefix
reuse and controlled state composition.
Figure 1: Layered architecture of stateful operator abstrac-
tion. The design extends AAFLOW-style operator execution
with explicit KV-state materialization, fork, transfer, merge,
and eviction.
We evaluate AAFLOW+ on GPU clusters using Mistral-7B and
Llama-3-8B. Results show that stateful execution significantly im-
proves performance over text-based orchestration. AAFLOW+ re-
duces TTFT by up to50.2 × at long context, achieves up to7.63 ×
lower multi-agent latency at 16-agent scale, reduces peak KV mem-
ory by1.72 ×–6.10×, and improves throughput by over7.74 ×.
Transfer–recompute analysis shows that KV transfer dominates
recomputation on moderate-to-high bandwidth networks, while
consistency experiments preserve deterministic output agreement.
These results show that workflow-level KV-state sharing reduces
latency, memory pressure, and framework overhead while comple-
menting existing LLM serving systems.
2 BACKGROUND AND MOTIV ATION
2.1 From Agentic Dataflow to Stateful Execution
Agentic large language model (LLM) applications are increasingly
organized as multi-stage workflows in which retrieval, reasoning,
tool use, memory access, and response generation interact dynami-
cally. While frameworks like DSPy treat language-model applica-
tions as compositional programs that can be optimized through
compilation [16, 41], systems like AutoGen and LangGraph offer
flexible multi-agent programming abstractions. Nonetheless, the
majority of agent frameworks continue to be largely text-centric,
with agents exchanging serialized strings representing tool outputs,
recovered excerpts, intermediate summaries, and natural language
messages. Although this approach is practical at the application
layer, it conceals a more serious inefficiency in the system. A down-
stream agent typically needs to re-tokenize and re-prefill the same
context before it can produce fresh output when it receives text
that has previously been handled by an upstream model invocation.
Instead of viewing agentic workflows as loosely connected frame-
work callbacks, AAFLOW [ 34] treated them as compilable dis-
tributed programs. In AAFLOW, a workflow is represented as a set
of operators,
𝑊={𝑂𝑝 𝑒𝑚𝑏𝑒𝑑 , 𝑂𝑝𝑟𝑒𝑡𝑟𝑖𝑒𝑣𝑒 , 𝑂𝑝𝑟𝑒𝑎𝑠𝑜𝑛 , 𝑂𝑝𝑚𝑒𝑚𝑜𝑟 𝑦, 𝑂𝑝𝑢𝑝𝑠𝑒𝑟𝑡 },(1)
where each operator is defined as
𝑂𝑝 𝑖 =(𝐼 𝑖, 𝑂𝑖, 𝑓𝑖, 𝑃𝑖 ).(2)
Here, 𝐼𝑖 and 𝑂𝑖 denote the input and output objects, 𝑓𝑖 is the trans-
formation function, and 𝑃𝑖 is the communication pattern associated
with the operator. This abstraction allows the runtime to lower an
agentic workflow into an execution graph,
𝐺=𝐶𝑜𝑚𝑝𝑖𝑙𝑒(𝑊),(3)
where communication patterns such as broadcast, shuffle, reduce,
and embarrassingly parallel execution become explicit parts of
the execution plan. The key insight of this paper is that the same
principle should apply not only to external workflow data, such
as documents, embeddings, and vector indices, but also tointer-
nal model execution state. The state created during LLM prefill is
typically locked inside a local serving runtime in current agentic
systems. Because of this, multi-agent workflows maximize the flow
of data throughout the model, but they are unable to optimize the
transportation and reuse of the key-value (KV) cache, the model’s
most costly intermediate artifact.
Figure 2: Textflow forces downstream agents to replay con-
text, whereas stateflow transfers reusable KV execution state.
2.2 Cost of Text-Based Agent Communication
Consider a two-agent workflow where an upstream agent gets
documents and creates a lengthy context, and a downstream agent
uses that context to perform reasoning in order to comprehend the
limitations of text-based communication. In existing systems, text
is usually emitted by the upstream agent and consumed as a new
prompt by the downstream agent. Before generating its first output
2

## PDF Page 3

token, the downstream model must make a prefill pass over the
whole context if the prompt length is𝐿. We denote this cost as
𝑇𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿).(4)
The total execution time for a single agent invocation can therefore
be approximated as
𝑇𝑎𝑔𝑒𝑛𝑡 =𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌) +Ω,(5)
where 𝑇𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌) is the cost of autoregressively generating an out-
put sequence of length 𝑌 , and Ω captures framework overhead
from scheduling, serialization, synchronization, and data move-
ment. The inefficiency becomes more severe in multi-agent settings.
If 𝑘 agents consume the same context independently, the system
may pay the prefill cost𝑘times:
𝑇 𝑘
𝑡𝑒𝑥𝑡 ≈𝑘·𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +
𝑘∑︁
𝑗=1
𝑇𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌𝑗 ) +Ω 𝑡𝑒𝑥𝑡 .(6)
Figure 3: Text-based multi-agent execution duplicates prefill
computation across branches that share the same context.
Tree-of-Thought reasoning, multi-agent argument, self-consistency
sampling, speculative planning, and parallel retrieval synthesis all
exhibit this execution pattern. Although the process in each sce-
nario has a shared prefix or shared context, text-based communi-
cation compels each branch to separately recreate the model state.
This redundancy is shown in Figure 3. The execution system han-
dles each branch as a separate model invocation even though the
agents conceptually share a shared context. Poor branch factor
scalability is the outcome, particularly for long-context workloads
where time-to-first-token (TTFT) is dominated by prefill.
2.3 KV Cache as Reusable Execution State
Serving systems have already demonstrated that performance de-
pends on appropriate KV-cache management. To manage KV cache
using block-level paging and minimize memory fragmentation [19],
vLLM provides PagedAttention. To enhance KV-cache reuse across
structured language-model programs, SGLang introduces Radix-
Attention [47]. These systems show that effective LLM execution
depends on the KV cache. Their optimizations, however, mostly
function within a serving runtime. A universal distributed abstrac-
tion for exposing KV cache as a schedulable state object across
multi-agent workflows is not offered by them.
Our work is motivated by this distinction. We don’t try to replace
the current serving systems. Rather, we investigate the possibil-
ity of lifting KV cache from a local serving optimization into a
distributed workflow abstraction. According to this perspective, a
multi-agent workflow should be able to manage partitions, buffers,
and interim outputs in the same manner as distributed data systems
may materialize, transmit, fork, reuse, and ultimately evict KV state.
2.4 Motivating Stateflow Example
Figure 2 illustrates the difference between textflow and stateflow.
Agent B needs to prefill the textual context that Agent A emits
in the textflow scenario. Agent A produces a reusable KV state
object in addition to a logical output in the stateflow scenario.
Then, instead of paying for complete prompt replay, Agent B can
resume execution from the transferred state, simply paying for
state movement and continuation. By contrasting the cost of state
transfer with the cost of text replay, the anticipated benefit may
be stated. Text-based execution is beneficially replaced by stateful
execution when
𝑇𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 (𝐾𝑉) +𝑇 𝑟𝑒𝑠𝑢𝑚𝑒 +Ω 𝑠𝑡𝑎𝑡𝑒 <𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +Ω 𝑡𝑒𝑥𝑡 .(7)
Equation 7 defines the central systems condition studied in this
paper. Multi-agent workflows can lower TTFT and overall latency
by working over state rather than text if transferring and resuming
from KV state is less expensive than replaying the prompt.
3 STATEFUL OPERATOR ABSTRACTION
3.1 Extending the Operator Model
Each operator is described by AAFLOW [34] as a tuple with inputs,
outputs, a transformation function, and a communication pattern.
For data-centric workflow steps including embedding, retrieval,
reasoning, memory lookup, and index updating, this approach is
adequate. It does not, however, specifically differentiate between
model execution state and ordinary data. Because KV cache is
connected to model settings, token placements, attention layout,
device placement, and branch lineage, it is distinct from regular
data. Reusing it inappropriately can modify model meaning, while
discarding it unnecessarily produces wasteful processing. We there-
fore extend the original operator definition into a stateful operator:
𝑂𝑝 𝑠
𝑖 =(𝐼 𝑖, 𝑂𝑖, 𝑆𝑖𝑛
𝑖 , 𝑆𝑜𝑢𝑡
𝑖 , 𝑓𝑖, 𝑃𝑖, 𝜎𝑖 ).(8)
Here, 𝐼𝑖 and 𝑂𝑖 remain the ordinary data inputs and outputs, while
𝑆𝑖𝑛
𝑖 and 𝑆𝑜𝑢𝑡
𝑖 represent input and output state objects. The function
𝑓𝑖 describes the logical transformation performed by the operator,
and 𝑃𝑖 describes the communication pattern used to execute it. The
new term 𝜎𝑖 denotes the state policy associated with the operator.
This policy determines whether state is transferred, aliased, forked,
merged, pinned, evicted, or recomputed. Making state movement
transparent to the compiler is the goal of Equation 8. The runtime
only observes strings and tensors moving between operators in a
text-based workflow. The runtime also detects state dependencies
in a stateful workflow, which may affect placement and scheduling.
Thus, the execution graph becomes
𝐺𝑠 =(𝑉 , 𝐸 𝑑, 𝐸𝑠 ),(9)
where 𝑉 is the set of operators, 𝐸𝑑 is the set of data edges, and 𝐸𝑠
is the set of state edges. Data edges describe conventional work-
flow dependencies, while state edges describe KV-cache reuse and
movement.
3.2 KV State Object
A KV cache object must carry enough information to determine
whether it can be safely reused. We define a state object as
𝑆𝐾𝑉 =(𝑀,Θ, 𝐵,Π,Λ,Γ),(10)
3

## PDF Page 4

where 𝑀 is the model identifier, Θ is the model and tokenizer
configuration, 𝐵 is the set of KV blocks, Π is positional metadata,
Λ is lineage metadata, and Γ describes placement and ownership.
The block set𝐵is represented as
𝐵={𝑏 1, 𝑏2, . . . , 𝑏𝑚 },(11)
where each block has the form
𝑏 𝑗 =(𝐾 𝑗, 𝑉𝑗, ℓ𝑗, 𝑟𝑗, 𝑑𝑗 ).(12)
The key and value tensors in this representation are 𝐾𝑗 and 𝑉𝑗 , the
layer index is ℓ𝑗 , the token-position range covered by the block is𝑟 𝑗 ,
and the device or memory domain where the block is now located is
𝑑 𝑗 . The idea behind this block-level representation is similar to that
of paged KV-cache management in vLLM, which manages cache
storage in blocks as opposed to a single monolithic sequence [19].
The lineage term Λ is particularly important for multi-agent
workflows. It records whether a state was produced by direct prefill,
by transfer, by fork, or by restricted composition. This prevents the
runtime from treating all KV states as interchangeable. Two states
are compatible only if they satisfy the predicate
𝐶𝑜𝑚𝑝𝑎𝑡(𝑆 𝑎, 𝑆𝑏 )=⊮[𝑀 𝑎 =𝑀 𝑏 ] ·⊮[Θ 𝑎 =Θ 𝑏 ] ·⊮[Π 𝑎 ∼Π 𝑏 ],(13)
where Π𝑎 ∼Π 𝑏 denotes positional compatibility. This predicate is
conservative by design: when compatibility cannot be established,
the runtime falls back to text replay or recomputation.
3.3 Stateful Operator Semantics
The abstraction introduces a family of KV-state operators that ex-
tend the original AAFLOW workflow. The first operator is materi-
alization:
𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 (𝑥, 𝑀) →𝑆 𝐾𝑉 .(14)
This operator creates a reusable KV state object after consuming a
tokenized context 𝑥 and a model 𝑀. Materialization distinguishes
between the cost of decoding future tokens and the cost of process-
ing the input context, as contrast to regular generation. The second
operator is transfer:
𝑂𝑝 𝑘𝑣_𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 (𝑆𝐾𝑉 , 𝑛𝑎, 𝑛𝑏 ) →𝑆 ′
𝐾𝑉 .(15)
A state object is moved or aliased from node 𝑛𝑎 to node 𝑛𝑏 by this
operation. Depending on where the source and destination are
located, its communication pattern could be point-to-point transfer,
RDMA, or a collective operation. The transfer operator modifies the
state’s location and ownership metadata but not its logical content.
The third operator is fork:
𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 (𝑆𝐾𝑉 , 𝑘) → {𝑆 (1)
𝐾𝑉 , 𝑆 (2)
𝐾𝑉 , . . . , 𝑆(𝑘)
𝐾𝑉 }.(16)
The abstraction procedure that makes branching effective is
called a fork. It generates several logical offspring of a common
prefix state. When branches diverge, copy-on-write behavior is ap-
plied, even if these descendants may initially share the same physi-
cal blocks. Self-consistency sampling, Tree-of-Thought reasoning,
multi-agent argument, and parallel plan exploration all directly
benefit from this operation. The fourth operator is restricted merge:
𝑂𝑝 𝑘𝑣_𝑚𝑒𝑟𝑔𝑒 (𝑆1, 𝑆2, 𝜇) →𝑆 ∗.(17)
The merge discipline is specified by the policy 𝜇. Since arbitrary
KV-cache merging is not typically semantically correct, we pur-
posefully limit this operation. Merge is only permitted under spe-
cific structural limitations, such as prefix-compatible concatena-
tion, segment-aware assembly, or reduction through a summariz-
ing model invocation, because KV state is position-dependent and
model-layout-dependent. KV cache is not treated as a general tensor
object by this cautious approach.
3.4 Cost Model for Stateful Execution
The operator abstraction is useful only if it exposes an optimization
target. For text-based execution, the cost of a branch with context
length𝐿can be written as
𝑇𝑡𝑒𝑥𝑡 =𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌) +Ω 𝑡𝑒𝑥𝑡 .(18)
For stateful execution, the corresponding cost is
𝑇𝑠𝑡𝑎𝑡𝑒 =𝑇 𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 (𝑆𝐾𝑉 ) +𝑇 𝑟𝑒𝑠𝑢𝑚𝑒 +𝑇 𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌) +Ω 𝑠𝑡𝑎𝑡𝑒 .(19)
The system should choose stateful execution when
𝑇𝑠𝑡𝑎𝑡𝑒 <𝑇 𝑡𝑒𝑥𝑡 .(20)
Expanding this condition gives
𝑇𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟 (𝑆𝐾𝑉 ) +𝑇 𝑟𝑒𝑠𝑢𝑚𝑒 +Ω 𝑠𝑡𝑎𝑡𝑒 <𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +Ω 𝑡𝑒𝑥𝑡 .(21)
For a branching workflow with 𝑘 branches sharing a prefix, the
text-based cost is approximately
𝑇 𝑘
𝑡𝑒𝑥𝑡 =𝑘·𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +
𝑘∑︁
𝑗=1
𝑇𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌𝑗 ) +Ω 𝑘
𝑡𝑒𝑥𝑡 .(22)
With KV-state fork, the prefix is materialized once:
𝑇 𝑘
𝑠𝑡𝑎𝑡𝑒 =𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) +𝑇 𝑓 𝑜𝑟𝑘 (𝑆𝐾𝑉 , 𝑘) +
𝑘∑︁
𝑗=1
𝑇𝑑𝑒𝑐𝑜𝑑𝑒 (𝑌𝑗 ) +Ω 𝑘
𝑠𝑡𝑎𝑡𝑒 .(23)
The expected savings therefore come from replacing repeated prefill
with a single materialization and a cheaper fork operation:
Δ𝑇=(𝑘−1)𝑇 𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙 (𝐿) −𝑇 𝑓 𝑜𝑟𝑘 (𝑆𝐾𝑉 , 𝑘) − (Ω 𝑘
𝑠𝑡𝑎𝑡𝑒 −Ω 𝑘
𝑡𝑒𝑥𝑡 ).(24)
This equation makes the performance intuition precise. Stateful
execution is most beneficial when the shared context is long, the
branch factor is high, and state management overhead remains
lower than the avoided prefill cost.
3.5 Correctness and Validity Constraints
The inability to treat KV cache like arbitrary data is a major problem
in stateful abstraction. Only model-specific and sequence-specific
requirements make it valid. As a result, three invariants must be
maintained in every state transition.
Model compatibility must first be maintained. One incompati-
ble model, tokenizer, or attention layout cannot reuse a KV state
created by another. Secondly, positional compatibility needs to be
maintained. Fork and merge operations must maintain position se-
mantics since attention state is linked to word order and positional
encoding. Third, lineage consistency needs to be maintained. In
order for the scheduler to assess if future reuse is safe, a branch
formed from a prefix state must document its pedigree. Equation 10
contains metadata terms that encode these requirements. The ab-
straction does not try unsafe reuse if any invariant fails. Rather,
4

## PDF Page 5

the runtime resorts to text-based recomputation. The abstraction
is useful for real systems because of this cautious design, which is
crucial for accuracy.
AAFLOW is extended from dataflow to stateflow by the stateful
abstraction. The abstraction treats the KV cache as a structured state
object with explicit operators, compatibility criteria, placement
metadata, and cost models rather than as an opaque local artifact
inside the serving engine. This makes it possible for the runtime
and compiler to decide when to materialize, transfer, fork, merge,
or evict model state. The outcome is a workflow architecture that
allows for the effective reuse of costly LLM prefill computation
while maintaining the analyzability of operator-driven execution.
4 DESIGN
We design a distributed runtime that extends AAFLOW’s operator-
driven execution to astateful execution systemcapable of managing
KV cache across multi-agent workflows. The key principle is to treat
model execution state as a first-class distributed object, rather than
a temporary artifact limited to one node. The runtime integrates
a stateful compiler, a distributed KV-state layer, and a state-aware
scheduler to coordinate data and state dependencies, as well as
transfer/recompute decisions.
4.1 Stateful Workflow Compilation
The first step in our system is to extend the compilation process
from a purely data-driven model to a hybrid data-state model. Given
a workflow𝑊 , AAFLOW compiles it into an execution graph𝐺. We
extend this to construct astateful execution graph: 𝐺𝑠 =(𝑉 , 𝐸 𝑑, 𝐸𝑠 ),
where 𝑉 represents operator nodes, 𝐸𝑑 captures data dependencies,
and 𝐸𝑠 captures state dependencies corresponding to KV cache
flow. Unlike traditional DAGs that only encode data movement,𝐺𝑠
exposes KV-state propagation. State edges allow the scheduler to
reason about locality, reuse, and transfer before recomputing shared
context. This enables optimizations such as avoiding recomputation
when compatible state already exists elsewhere in the system.
4.2 KV State Representation
To support distributed state management, we define a structured
representation of KV cache. Conceptually, KV cache consists of a
sequence of blocks:
𝐾𝑉={𝐵 1, 𝐵2, . . . , 𝐵𝑛 }(25)
where each block corresponds to a segment of the input sequence
and contains key-value tensors 𝐵𝑖 =(𝐾 𝑖, 𝑉𝑖, 𝑙𝑖, 𝑝𝑖 ). Here, 𝐾𝑖 and 𝑉𝑖
denote the key and value tensors,𝑙 𝑖 identifies the layer index, and
𝑝𝑖 encodes the positional range associated with the block. We use
Apache Arrow [3] to represent metadata and block layouts in a
columnar, zero-copy format. This allows different components of
the system to share state descriptors without serialization over-
head. The underlying tensor buffers are transferred using high-
performance communication frameworks such as UCX [ 35, 39]
and MPI [6], ensuring efficient movement across nodes. The trans-
port subsystem overlaps communication and computation, allow-
ing operators to begin execution as KV blocks arrive, improving
throughput.
4.3 KV State Lifecycle
Figure 4: Lifecycle of KV state from creation to reuse and
eviction.
The lifecycle of KV state in our system follows a structured se-
quence, as shown in Figure 4. State is first materialized during the
prefill phase of LLM execution, then can be forked to enable parallel
reasoning (e.g., in Tree-of-Thought workflows).Forkedstates may
be transferred between nodes for distributed processing. When com-
putation resumes, agents use thetransferredstate directly, avoiding
redundant prefill. If necessary, state may beevicteddue to memory
constraints or policy. This lifecycle promotes state reuse, reduces
redundant computation, and maintains execution flexibility.
4.4 Memory Management and Eviction
Managing KV state for multiple agents strains GPU memory. To
mitigate this, a cost-aware eviction strategy balances reuse with
memory use. Each state receives a score based on reuse and size.
States with lower scores are evicted first under memory pressure,
similar to distributed cache strategies but tailored for KV state
reuse.
To mitigate GPU memory exhaustion, the runtime implements a
heuristic eviction strategy prioritizing KV states based on a com-
bination of memory footprint size and historical reuse frequency.
Formalizing and profiling optimal distributed KV eviction policies
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

[36] Kaiying Shan, Niranda Perera, Damitha Lenadora, Tianle Zhong, Arup Ku-
mar Sarker, Supun Kamburugamuve, Thejaka Amila Kanewela, Chathura Widan-
age, and Geoffrey Fox. 2022. Hybrid Cloud and HPC Approach to High-
Performance Dataframes. In2022 IEEE International Conference on Big Data
(Big Data). 2728–2736. https://doi.org/10.1109/BigData55660.2022.10020958
[37] Ying Sheng, Lianmin Zheng, Binhang Yuan, Zhuohan Li, Max Ryabinin, Beidi
Chen, Percy Liang, Christopher Re, Ion Stoica, and Ce Zhang. 2023. FlexGen:
High-Throughput Generative Inference of Large Language Models with a Single
GPU. InProceedings of the 40th International Conference on Machine Learning
(Proceedings of Machine Learning Research), Andreas Krause, Emma Brunskill,
Kyunghyun Cho, Barbara Engelhardt, Sivan Sabato, and Jonathan Scarlett (Eds.),
Vol. 202. PMLR, 31094–31116. https://proceedings.mlr.press/v202/sheng23a.html
[38] Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and
Shunyu Yao. 2023. Reflexion: language agents with verbal reinforcement learning.
InProceedings of the 37th International Conference on Neural Information Process-
ing Systems(New Orleans, LA, USA)(NIPS ’23). Curran Associates Inc., Red Hook,
NY, USA, Article 377, 19 pages. https://dl.acm.org/doi/10.5555/3666122.3666499
[39] Mills Staylor, Arup Kumar Sarker, Gregor von Laszewski, Geoffrey Fox, Yue
Cheng, and Judy Fox. 2026. Combining Serverless and High-Performance Com-
puting Paradigms to support ML Data-Intensive Applications.Frontiers in High
Performance Computing(2026).
[40] Chathura Widanage, Niranda Perera, Vibhatha Abeykoon, Supun Kamburuga-
muve, Thejaka Amila Kanewala, Hasara Maithree, Pulasthi Wickramasinghe,
Ahmet Uyar, Gurhan Gunduz, and Geoffrey Fox. 2020. High performance data
engineering everywhere. In2020 IEEE International Conference on Smart Data
Services (SMDS). IEEE, 122–132. https://doi.org/10.1109/SMDS49396.2020.00022
[41] Qingyun Wu, Gagan Bansal, Jieyu Zhang, Yiran Wu, Beibin Li, Erkang (Eric)
Zhu, Li Jiang, Xiaoyun Zhang, Shaokun Zhang, Ahmed Awadallah, Ryen W.
White, Doug Burger, and Chi Wang. 2024. AutoGen: Enabling Next-Gen LLM
Applications via Multi-Agent Conversation. InCOLM 2024. https://www.mi
crosoft.com/en-us/research/publication/autogen-enabling-next-gen-llm-
applications-via-multi-agent-conversation-framework/
[42] Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan,
and Yuan Cao. 2023. ReAct: Synergizing Reasoning and Acting in Language
Models. InInternational Conference on Learning Representations (ICLR). https:
//openreview.net/pdf?id=WE_vluYUL-X
[43] Hancheng Ye, Zhengqi Gao, Mingyuan Ma, Qinsi Wang, Yuzhe Fu, Ming-Yu
Chung, Yueqian Lin, Zhijian Liu, Jianyi Zhang, Danyang Zhuo, and Yiran Chen.
2025. KVCOMM: Online Cross-context KV-cache Communication for Efficient
LLM-based Multi-agent Systems.
[44] Lu Ye, Ze Tao, Yong Huang, and Yang Li. 2024. ChunkAttention: Efficient Self-
Attention with Prefix-Aware KV Cache and Two-Phase Partition. InProceedings
of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL).
11608–11620. https://doi.org/10.18653/v1/2024.acl-long.623
[45] Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, and Byung-
Gon Chun. 2022. Orca: A distributed serving system for {Transformer-Based}
generative models. In16th USENIX symposium on operating systems design and
implementation (OSDI 22). 521–538.
[46] Matei Zaharia, Reynold S. Xin, Patrick Wendell, Tathagata Das, Michael Armbrust,
Ankur Dave, Xiangrui Meng, Josh Rosen, Shivaram Venkataraman, Michael J.
Franklin, Ali Ghodsi, Joseph Gonzalez, Scott Shenker, and Ion Stoica. 2016.
Apache Spark: a unified engine for big data processing.Commun. ACM59,
11 (Oct. 2016), 56–65. https://doi.org/10.1145/2934664
[47] Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff Huang,
Cody Hao Yu, Shiyi Cao, Christos Kozyrakis, Ion Stoica, Joseph E. Gonzalez,
Clark Barrett, and Ying Sheng. 2024. SGLang: efficient execution of struc-
tured language model programs. InProceedings of the 38th International Con-
ference on Neural Information Processing Systems(Vancouver, BC, Canada)
(NIPS ’24). Curran Associates Inc., Red Hook, NY, USA, Article 2000, 27 pages.
https://dl.acm.org/doi/10.5555/3737916.3739916
[48] Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff Huang,
Cody Hao Yu, Shiyi Cao, Christos Kozyrakis, Ion Stoica, Joseph E. Gonzalez,
Clark Barrett, and Ying Sheng. 2024. SGLang: efficient execution of struc-
tured language model programs. InProceedings of the 38th International Con-
ference on Neural Information Processing Systems(Vancouver, BC, Canada)
(NIPS ’24). Curran Associates Inc., Red Hook, NY, USA, Article 2000, 27 pages.
https://dl.acm.org/doi/10.5555/3737916.3739916
[49] Yinmin Zhong, Shengyu Liu, Junda Chen, Jianbo Hu, Yibo Zhu, Xuanzhe Liu,
Xin Jin, and Hao Zhang. 2024. DistServe: Disaggregating Prefill and Decoding for
Goodput-Optimized Large Language Model Serving. In18th USENIX Symposium
on Operating Systems Design and Implementation (OSDI). https://www.usenix.o
rg/conference/osdi24/presentation/zhong-yinmin
[50] Yinmin Zhong, Shengyu Liu, Junda Chen, Jianbo Hu, Yibo Zhu, Xuanzhe Liu,
Xin Jin, and Hao Zhang. 2024. {DistServe}: Disaggregating prefill and decoding
for goodput-optimized large language model serving. In18th USENIX Symposium
on Operating Systems Design and Implementation (OSDI 24). 193–210.
APPENDIX
A EXTENDED SYSTEM DESIGN
This appendix expands the design and implementation details of
AAFLOW+. The main paper presents the operator abstraction, state
object, scheduler, and evaluation results. Here, we describe how the
compiler, KV-state manager, transport layer, runtime, and backend
adapters interact during execution.
A.1 Design Components
AAFLOW+ is organized around five cooperating components: the
stateful compiler, the KV-state manager, the transport subsystem,
the state-aware scheduler, and the execution runtime. The stateful
compiler converts an agentic workflow into a graph containing both
data edges and state edges. The KV-state manager tracks block-level
KV metadata, ownership, lineage, and placement. The transport
subsystem moves KV blocks across devices and nodes using Ar-
row metadata and UCX/RDMA-style communication. The sched-
uler decides whether to transfer, reuse, fork, evict, or recompute
state. Finally, the execution runtime coordinates backend invoca-
tion through Hugging Face, vLLM, or SGLang-compatible execution
paths.
Given a workflow𝑊 , the compiler constructs a stateful execution
graph
𝐺𝑠 =(𝑉 , 𝐸 𝑑, 𝐸𝑠 ),
where 𝑉 is the set of operator instances, 𝐸𝑑 represents ordinary
data dependencies, and 𝐸𝑠 represents KV-state dependencies. Each
vertex is annotated as
𝑣𝑖 =(𝑂𝑝 𝑠
𝑖 , 𝑅𝑖, 𝐿𝑖, 𝐶𝑖 ),
where 𝑂𝑝 𝑠
𝑖 is the stateful operator, 𝑅𝑖 describes resource require-
ments, 𝐿𝑖 captures locality constraints derived from KV-state place-
ment, and𝐶𝑖 stores compatibility constraints such as model identity,
tokenizer configuration, attention layout, and positional encoding.
The compiler inserts KV-state operators when it detects shared
prompt prefixes or branchable contexts. For example, a text-centric
workflow
𝐶𝑜𝑛𝑡𝑒𝑥𝑡→ {𝐴𝑔𝑒𝑛𝑡 1, . . . , 𝐴𝑔𝑒𝑛𝑡𝑘 }
is rewritten as
𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 (𝐶𝑜𝑛𝑡𝑒𝑥𝑡) →𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 (𝑆𝐾𝑉 , 𝑘)
→ {𝐴𝑔𝑒𝑛𝑡 1 (𝑆 (1)
𝐾𝑉 ), . . . , 𝐴𝑔𝑒𝑛𝑡𝑘 (𝑆 (𝑘)
𝐾𝑉 )}.(41)
This transformation makes prefix reuse explicit and allows the
runtime to schedule reasoning branches without forcing each branch
to replay the same context.
A.2 KV-State Metadata Catalog
AAFLOW+ maintains a metadata catalog for every materialized
KV state. The catalog separates logical state identity from physical
tensor placement. This allows the scheduler to reason about state
reuse without scanning device memory or reconstructing prompt
text. Each KV state is represented as
𝑆𝐾𝑉 =(𝑀,Θ, 𝐵,Π,Λ,Γ),
14

## PDF Page 15

where 𝑀 is the model identifier, Θ is the model and tokenizer con-
figuration, 𝐵 is the set of KV blocks,Π stores positional metadata, Λ
records lineage, and Γ records placement and ownership. Internally,
the KV-state manager maintains the mapping
M:(𝑠𝑡𝑎𝑡𝑒_𝑖𝑑, 𝑏𝑙𝑜𝑐𝑘_𝑖𝑑) → (𝑑𝑒𝑣𝑖𝑐𝑒, 𝑛𝑜𝑑𝑒, 𝑎𝑑𝑑𝑟𝑒𝑠𝑠, 𝑟𝑎𝑛𝑔𝑒, 𝑜𝑤𝑛𝑒𝑟).
Table 6: Metadata maintained by the AAFLOW+ KV-state
manager.
Field Purpose
state_id Unique logical identifier for a KV state.
model_id Model family and checkpoint used to create
the state.
tokenizer_id Tokenizer and vocabulary compatibility.
position_range Token positions by each KV block.
layer_id Transformer layer with the KV block.
block_id Block identifier for partial transfer and reuse.
lineage Materialize, fork, transfer, merge, or evict
history.
device GPU, CPU, or remote memory location.
owner Runtime worker currently responsible for
the block.
refcount Number of logical states sharing the block.
last_access Timestamp or logical clock for eviction.
This design allows multiple forked states to share the same phys-
ical prefix blocks. When a branch diverges, the runtime applies
copy-on-write behavior: shared prefix blocks remain aliased, while
branch-specific continuation blocks are allocated separately.
B USE CASE: COLLABORATIVE RAG WITH
SHARED EVIDENCE
A representative use case is collaborative retrieval-augmented gen-
eration over a long document collection. Suppose a user asks a
complex scientific question requiring retrieval, risk analysis, veri-
fication, and final synthesis. A conventional multi-agent pipeline
may use four agents: a retriever, a reasoning agent, a verifier, and a
summarizer. All agents require the same retrieved evidence prefix,
but they perform different downstream tasks.
In a text-centric implementation, the retriever emits passages as
text. Each downstream agent then receives the same passages and
performs a separate prefill over the identical context:
𝑇 𝑘
text ≈𝑘·𝑇 prefill(𝐿) +
𝑘∑︁
𝑗=1
𝑇decode (𝑌𝑗 ) +Ω text.
This duplicates both compute and KV memory.
With AAFLOW+, the retrieved evidence is materialized once as
KV state:
𝑆𝐾𝑉 =𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 (𝐶𝑜𝑛𝑡𝑒𝑥𝑡, 𝑀).
The runtime then forks this state:
{𝑆 (1)
𝐾𝑉 , . . . , 𝑆(𝑘)
𝐾𝑉 }=𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 (𝑆𝐾𝑉 , 𝑘),
and assigns the forked states to the reasoning, verification, and
synthesis agents. Each agent resumes from the shared context state
and only pays the cost of branch-specific continuation:
𝑇 𝑘
state ≈𝑇 prefill(𝐿) +𝑇 fork (𝑆𝐾𝑉 , 𝑘) +
𝑘∑︁
𝑗=1
𝑇decode (𝑌𝑗 ) +Ω state.
The benefit is largest when the retrieved context is long, the number
of agents is large, and the branch outputs are short relative to the
shared prefix.
C END-TO-END EXECUTION
This section describes the full AAFLOW+ call flow for a shared-
prefix multi-agent workflow.
Workflow Submission:The user submits a workflow contain-
ing a shared context and multiple downstream agents:
𝑊=(𝐶𝑜𝑛𝑡𝑒𝑥𝑡,{𝐴𝑔𝑒𝑛𝑡 1, . . . , 𝐴𝑔𝑒𝑛𝑡𝑘 }, 𝑃𝑜𝑙𝑖𝑐𝑦).
The policy specifies whether state reuse is allowed, whether branches
can share physical blocks, and whether transfer or recomputation
should be preferred under memory pressure.
Compilation:The compiler parses the workflow and constructs
the stateful graph:
𝐺𝑠 =(𝑉 , 𝐸 𝑑, 𝐸𝑠 ).
It identifies common prefixes, inserts 𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 before the
first shared reasoning stage, inserts 𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 before branch ex-
pansion, and annotates each branch with state compatibility con-
straints.
State Materialization:The runtime sends the shared context
to the backend model and executes the prefill stage once. The back-
end produces KV tensors, which are registered with the KV-state
manager:
𝐶𝑜𝑛𝑡𝑒𝑥𝑡
𝑝𝑟𝑒 𝑓 𝑖𝑙𝑙
− − − − − →𝑆𝐾𝑉 .
The KV-state manager records block identifiers, token ranges, layer
identifiers, placement, and lineage.
Scheduling and Placement:The scheduler chooses placement
for each branch. For a branch assigned to the same node as the
materialized KV state, the scheduler prefers aliasing or local reuse.
For a branch assigned to a remote node, it compares transfer cost
against recomputation:
𝜋(𝑆)=
(
𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟, 𝑇 transfer (𝑆)<𝑇 prefill(𝐿),
𝑟𝑒𝑐𝑜𝑚𝑝𝑢𝑡𝑒, 𝑜𝑡ℎ𝑒𝑟𝑤𝑖𝑠𝑒.
Execution:Agents resume from the assigned KV state and gen-
erate branch-specific continuations. The runtime updates the state
graph as new continuation blocks are created:
𝑆 (𝑗)
𝐾𝑉 →𝐷𝑒𝑐𝑜𝑑𝑒 𝑗 (𝑌𝑗 ) →𝑂𝑢𝑡𝑝𝑢𝑡 𝑗 .
Merge and Finalization:The outputs are merged using a safe
reduction policy. AAFLOW+ does not arbitrarily blend divergent
attention states. Instead, it supports restricted merge patterns such
as non-overlapping sequential concatenation, prefix-compatible
extension, or text-level reduction through a summarizing model
invocation.
15

## PDF Page 16

D ALGORITHMS FOR KV OPERATORS
Each KV state follows a finite-state lifecycle:
𝐶𝑟𝑒𝑎𝑡𝑒𝑑→𝑅𝑒𝑔𝑖𝑠𝑡𝑒𝑟𝑒𝑑→𝐴𝑐𝑡𝑖𝑣𝑒→𝐹𝑜𝑟𝑘𝑒𝑑
→𝑇 𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟𝑟𝑒𝑑→𝑅𝑒𝑠𝑢𝑚𝑒𝑑→𝐸𝑣𝑖𝑐𝑡𝑒𝑑.(42)
The lifecycle is maintained by the KV-state manager and up-
dated after every operator invocation, shown in Table-7. Because
lineage is explicit, the scheduler can distinguish original material-
ized prefixes, forked aliases, transferred blocks, and branch-specific
continuation state.
D.1 KV Materialization
KV materialization converts a text context into reusable execution
state. This operation is invoked once for a shared prefix.
Algorithm 1KV-Materialize
Require:Context tokens𝑥, model𝑀, tokenizer/configurationΘ
Ensure:KV state𝑆 𝐾𝑉
1:Validate model and tokenizer configuration.
2:Execute backend prefill on𝑥using𝑀.
3:Collect layer-wise KV tensors{(𝐾 ℓ, 𝑉ℓ )}.
4:Partition tensors into KV blocks𝐵={𝑏 1, . . . , 𝑏𝑚 }.
5:Create metadata(𝑀,Θ,Π,Λ,Γ).
6: Register (𝑠𝑡𝑎𝑡𝑒_𝑖𝑑, 𝑏𝑙𝑜𝑐𝑘_𝑖𝑑) → (𝑑𝑒𝑣𝑖𝑐𝑒, 𝑛𝑜𝑑𝑒, 𝑎𝑑𝑑𝑟𝑒𝑠𝑠) in the
KV-state manager.
7:Return𝑆 𝐾𝑉 =(𝑀,Θ, 𝐵,Π,Λ,Γ).
Materialization is the only operation that pays the full prefill
cost for the shared prefix. All downstream reuse is expressed as
fork, transfer, alias, or resume.
D.2 KV Fork
KV fork creates multiple logical descendants from a shared prefix
state.
Algorithm 2KV-Fork
Require:Parent state𝑆 𝐾𝑉 , number of branches𝑘
Ensure:Forked states{𝑆 (1)
𝐾𝑉 , . . . , 𝑆(𝑘)
𝐾𝑉 }
1:Check that𝑆 𝐾𝑉 is valid and not evicted.
2:for𝑗=1to𝑘do
3:Create child metadata with lineageΛ (𝑗) =Λ∪ {𝑓 𝑜𝑟𝑘(𝑗)}.
4: Alias parent prefix blocks by increasing block reference
counts.
5:Assign branch-specific ownership and placement policy.
6:end for
7:Return𝑘logical child states.
Fork does not copy the entire KV tensor by default. It creates
logical children that share prefix blocks until branch-specific con-
tinuation requires new allocation.
Algorithm 3KV-Transfer
Require:State𝑆 𝐾𝑉 , source node𝑛 𝑎, destination node𝑛 𝑏
Ensure:Destination state𝑆 ′
𝐾𝑉
1:Estimate transfer cost𝑇 transfer =|𝐾𝑉|/𝐵𝑊+𝛿.
2:Estimate recomputation cost𝑇 prefill(𝐿).
3:if𝑇 transfer ≥𝑇 prefill(𝐿)then
4:ReturnRecomputeDecision.
5:end if
6: Select required KV blocks based on downstream position range.
7:Send Arrow metadata descriptor to𝑛 𝑏.
8:Transfer KV tensor buffers using UCX/RDMA/MPI transport.
9:Register received blocks in the destination KV-state manager.
10:Update placement metadataΓand lineageΛ.
11:Return transferred state𝑆 ′
𝐾𝑉 .
D.3 KV Transfer
KV transfer moves or aliases KV blocks between workers. The
scheduler invokes transfer only when it is cheaper than recompu-
tation.
The operation works at block granularity, allowing the runtime
to transfer only the prefix segments needed by the downstream
branch.
D.4 KV Resume
KV resume injects precomputed state into a backend invocation
and skips repeated prefill.
Algorithm 4KV-Resume
Require:State𝑆 𝐾𝑉 , branch prompt suffix𝑞, model backend𝐵
Ensure:Generated output𝑦
1: Validate compatibility of 𝑆𝐾𝑉 with backend model and tok-
enizer.
2: Load or map KV blocks into the backend-visible memory do-
main.
3:Initialize decoding position fromΠ.
4:Append branch-specific suffix tokens𝑞if required.
5:Decode output tokens using reused KV state.
6:Register any newly generated continuation KV blocks.
7:Return generated output𝑦.
Resume is the operation that converts state reuse into TTFT
reduction. Instead of rebuilding the shared prefix, the backend
continues from the imported or mapped KV state.
D.5 Restricted KV Merge
Restricted merge reconciles branch outputs without unsafe tensor-
level blending of divergent KV states.
This conservative merge rule is necessary because KV state is
position-dependent and model-layout-dependent. AAFLOW+ there-
fore treats merge as a controlled operator rather than as arbitrary
tensor composition.
16

## PDF Page 17

Table 7: AAFLOW+ KV-state lifecycle transitions.
Transition Trigger Runtime Action
Created→Registered Backend prefill completes Insert metadata into catalog.
Registered→Active Scheduler assigns owner Pin or map blocks to worker.
Active→Forked Branch expansion Create child state descriptors.
Forked→Transferred Remote branch placement Transfer required blocks.
Transferred→Resumed Agent execution begins Inject state into backend.
Resumed→Active Decode creates continuation Register new branch blocks.
Active→Evicted Memory pressure Free low-priority blocks.
Algorithm 5Restricted-KV-Merge
Require:States or outputs{𝑆 1, . . . , 𝑆𝑘 }, merge policy𝜇
Ensure:Merged state or merged text output
1:Check model compatibility and positional compatibility.
2:if𝜇permits prefix-compatible concatenationthen
3:Concatenate non-overlapping compatible state segments.
4:else if𝜇requires semantic reductionthen
5: Convert branch outputs to text and call a summarizing/re-
duction operator.
6:else
7: Reject tensor-level merge and fall back to text-level reduc-
tion.
8:end if
9:Record merge lineage inΛ.
10:Return merged result.
D.6 KV Eviction
KV eviction releases state when memory pressure exceeds the
configured threshold.
Algorithm 6KV-Evict
Require:KV-state catalogC, memory budget𝐵 max
Ensure:Updated catalog and freed memory
1:Compute priority score for each state:
𝑠𝑐𝑜𝑟𝑒(𝑆)=𝛼·𝑟𝑒𝑢𝑠𝑒(𝑆) −𝛽·𝑠𝑖𝑧𝑒(𝑆) −𝛾·𝑎𝑔𝑒(𝑆).
2:whileallocated memory>𝐵 max do
3:Select state𝑆 ∗ with lowest score.
4:if𝑟𝑒 𝑓 𝑐𝑜𝑢𝑛𝑡(𝑆 ∗)=0then
5:Free local tensor blocks and update catalog.
6:else
7: Decrement aliases or evict only unshared continuation
blocks.
8:end if
9:end while
10:Return updated catalog.
Eviction is aware of forked state. Shared prefix blocks are re-
tained when multiple branches still reference them, while low-value
continuation blocks can be released earlier.
E EXAMPLE: PLANNER–RETRIEVER–SOLVER
CALL FLOW
This section illustrates a complete AAFLOW+ execution path for a
planner–retriever–solver workflow.
Step 1 - Planning:The planner decomposes a user request into
subquestions and determines that the downstream agents require a
shared evidence context.
𝑈 𝑠𝑒𝑟𝑄𝑢𝑒𝑟𝑦→𝑂𝑝 𝑝𝑙𝑎𝑛 → {𝑆𝑢𝑏𝑡𝑎𝑠𝑘 1, . . . , 𝑆𝑢𝑏𝑡𝑎𝑠𝑘𝑘 }.
Step 2 - Retrieval and Context Assembly:The retriever fetches
documents and constructs a shared context:
𝑆𝑢𝑏𝑡𝑎𝑠𝑘𝑠→𝑂𝑝 𝑟𝑒𝑡𝑟𝑖𝑒𝑣𝑒 →𝐶𝑜𝑛𝑡𝑒𝑥𝑡 .
Step 3 - KV Materialization :The context is prefilling once:
𝐶𝑜𝑛𝑡𝑒𝑥𝑡→𝑂𝑝 𝑘𝑣_𝑚𝑎𝑡𝑒𝑟𝑖𝑎𝑙𝑖𝑧𝑒 →𝑆 𝐾𝑉 .
Step 4 - Fork Across Solvers:The state is forked across multiple
solver agents:
𝑆𝐾𝑉 →𝑂𝑝 𝑘𝑣_𝑓 𝑜𝑟𝑘 (𝑘) → {𝑆 (1)
𝐾𝑉 , . . . , 𝑆(𝑘)
𝐾𝑉 }.
Step 5 - Transfer or Local Reuse:For each solver branch, the
scheduler chooses local reuse, transfer, or recomputation:
𝜋(𝑆)=
 

𝑟𝑒𝑢𝑠𝑒, 𝑆is local and compatible,
𝑡𝑟𝑎𝑛𝑠 𝑓 𝑒𝑟, 𝑇 transfer <𝑇 prefill,
𝑟𝑒𝑐𝑜𝑚𝑝𝑢𝑡𝑒, 𝑜𝑡ℎ𝑒𝑟𝑤𝑖𝑠𝑒.
Step 6 - Solver Execution:Each solver resumes from the shared
KV state and generates a branch-specific answer:
𝐴𝑔𝑒𝑛𝑡 𝑗 (𝑆 (𝑗)
𝐾𝑉 ) →𝐴𝑛𝑠𝑤𝑒𝑟 𝑗 .
Step 7 — Safe Merge:The final synthesis stage merges branch out-
puts through a text-level reduction or prefix-compatible restricted
composition:
{𝐴𝑛𝑠𝑤𝑒𝑟 1, . . . , 𝐴𝑛𝑠𝑤𝑒𝑟𝑘 } →𝑂𝑝 𝑚𝑒𝑟𝑔𝑒 →𝐹𝑖𝑛𝑎𝑙𝐴𝑛𝑠𝑤𝑒𝑟 .
This call flow shows why AAFLOW+ is most effective for shared-
prefix multi-agent workloads. The expensive evidence context is
materialized once, while each branch pays only transfer/resume
and continuation costs.
17

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
plicit state operators and a cost model. The strongest concrete result
comes from the HF sweep: at 10 Gbps, transfer is beneficial for only
5 of 8 tested Mistral contexts, but at 25 Gbps and above it is benefi-
cial for all tested contexts. The maximum transfer-over-recompute
speedup rises from 2.86× at 10 Gbps to 7.14× at 25 Gbps and up to
113.88× at 400 Gbps. This gives a clear scheduling rule: transfer is
not always profitable on slow links, but it becomes decisively better
on RDMA-class GPU-cluster networks.
The baseline systems are structurally limited: dense and text-
passing approaches cannot choose between transfer and recompute
since KV state is not a transferable object. Local-prefix systems
only reuse cache within a server, lacking general policies for cross-
agent or cross-node transfer. As shown in Table 10, both vLLM
and SGLang manage KV internally but do not support stable public
KV export/import in this evaluation. In contrast, AAFLOW+ en-
ables state transfer as a core workflow operation, selecting transfer
only when it is more bandwidth-efficient than prompt replay, thus
achieving superior performance.
F.4 Experiment 4: Memory Efficiency
The goal is to compare peak KV memory as branch factor grows. A
stateful workflow should avoid duplicating the full shared prefix
for every branch.
18

## PDF Page 19

Table 8: Experiment 1: Mean TTFT by baseline with HF, vLLM, and SGLang backends and 1024 - 32768 context size.
HF Backend vLLM Backend SGLang Backend
Model Baseline Mean Speedup Mean Speedup Mean Speedup
TTFT(s) (slower) TTFT(s) (slower) TTFT(s) (slower)
Mistral AAFLOW+ 0.041 1.00×0.116 1.00×0.629 1.00×
Mistral dense prefill 2.017 49.2×20.026 172.6×7.396 11.8×
Mistral AAFLOW-text 2.057 50.2×20.425 176.1×7.531 12.0×
Mistral vLLM local prefix 0.437 10.7×4.211 36.3×2.013 3.2×
Mistral SGLang prefix 0.280 6.8×2.629 22.7×1.475 2.3×
Mistral KVCOMM 0.704 17.2×6.876 59.3×2.920 4.6×
Mistral DistServe style 0.123 3.0×0.197 1.7×0.710 1.1×
Mistral live vLLM serve n/a n/a 19.925 171.8×n/a n/a
Mistral live SGLang serve n/a n/a n/a n/a 6.781 10.8×
Llama3 AAFLOW+ 0.030 1.00×0.061 1.00×0.139 1.00×
Llama3 dense prefill 0.499 16.6×3.958 64.9×1.810 13.0×
Llama3 AAFLOW-text 0.509 17.0×4.036 66.2×1.843 13.3×
Llama3 vLLM local prefix 0.124 4.1×0.862 14.1×0.481 3.5×
Llama3 SGLang prefix 0.086 2.9×0.552 9.0×0.348 2.5×
Llama3 KVCOMM 0.187 6.2×1.383 22.7×0.704 5.1×
Llama3 DistServe style 0.052 1.7×0.082 1.3×0.161 1.2×
Llama3 live vLLM serve n/a n/a 3.901 64.0×n/a n/a
Llama3 live SGLang serve n/a n/a n/a n/a 1.674 12.0×
Table 9: Experiment 2: Scaling benchmark of AAFLOW+ versus nearest non-AAFLOW+ competitor, SGLang prefix with 32768
context size
AAF HF Backend AAF vLLM Backend AAF SGLang Backend
Model Age LOW+ SGLang Speed LOW+ SGLang Speed LOW+ SGLang Speed
nts total(s) total(s) up total(s) total(s) up total(s) total(s) up
Mistral 1 30.70 119.13 3.88×67.10 263.40 3.93×91.62 353.92 3.86×
Mistral 2 30.70 224.85 7.32×67.71 484.22 7.15×90.49 679.06 7.50×
Mistral 4 58.37 436.28 7.47×121.86 899.15 7.38×176.53 1338.65 7.58×
Mistral 8 113.71 859.14 7.56×238.75 1796.07 7.52×348.13 2654.54 7.63×
Mistral 16 224.39 1704.86 7.60×465.45 3532.56 7.59×701.29 5363.03 7.65×
Llama3 1 29.06 112.39 3.87×36.02 141.03 3.91×43.40 167.96 3.87×
Llama3 2 29.06 216.89 7.46×36.01 259.80 7.21×44.80 335.59 7.49×
Llama3 4 56.35 425.88 7.56×66.26 492.36 7.43×84.45 638.82 7.56×
Llama3 8 110.91 843.85 7.61×128.62 968.75 7.53×159.17 1211.65 7.61×
Llama3 16 220.05 1679.81 7.63×253.53 1926.11 7.60×329.07 2514.49 7.64×
The memory results(Table 11) show that AAFLOW+ achieves the
lowest peak KV footprint across all three backends because it rep-
resents forked state through explicit shared ownership and lineage.
For Mistral, the strongest gap appears against the fully duplicating
baselines: AAFLOW+ uses 8.355 GiB on HF, while AAFLOW-text
uses 53.986 GiB and DistServe style uses 50.995 GiB. Even the best
local-prefix baselines remain significantly higher, with vLLM-prefix
and SGLang-prefix both at 14.351 GiB, 14.591 GiB and KVCOMM
at 15.702 GiB. On Llama3, AAFLOW+ uses 4.210 GiB on HF, while
AAFLOW-text rises to 27.202 GiB and dense prefill to 25.188 GiB;
the nearest local-prefix baselines remain around 7.2 GiB.
The same ranking is preserved on vLLM and SGLang. On vLLM,
Mistral AAFLOW+ uses 8.290 GiB, while AAFLOW-text is 53.568 GiB
and KVCOMM is 15.580 GiB. On SGLang, Mistral AAFLOW+ again
uses 8.290 GiB, while AAFLOW-text is 53.268 GiB and KVCOMM
is 15.153 GiB. The advantage of AAFLOW+ lies in storing a single
shared prefix state and allocating only branch-specific continuation
states, while dense prefill and AAFLOW-text duplicate the entire
prefix. DistServe methods add extra branch and staging state, re-
sulting in memory usage similar to dense prefill. KVCOMM and
19

## PDF Page 20

Table 10: Experiment 3: Comparison of KV transfer cost to recomputing the prompt prefil.
Model Bandwidth Beneficial HF Backend vLLM Backend SGLang Backend
contexts Speedup vs Speedup vs Speedup vs
Recompute Recompute Recompute
Mistral 10 Gbps 5/8 2.46×2.54×2.86×
Mistral 25 Gbps 8/8 6.14×6.35×7.14×
Mistral 100 Gbps 8/8 24.54×25.39×28.55×
Mistral 200 Gbps 8/8 49.04×50.73×57.04×
Mistral 400 Gbps 8/8 97.90×101.29×113.88×
Llama3 10 Gbps 1/6 2.58×2.57×2.37×
Llama3 25 Gbps 6/6 6.44×6.43×5.92×
Llama3 100 Gbps 6/6 25.76×25.72×23.67×
Llama3 200 Gbps 6/6 51.48×51.39×47.30×
Llama3 400 Gbps 6/6 102.77×102.61×94.44×
Table 11: Experiment 4: Mean peak KV memory.
HF Backend vLLM Backend SGLang Backend
Model Baseline Mean peak Mean peak Mean peak
KV (GiB) KV (GiB) KV (GiB)
Mistral AAFLOW+ 8.355 8.290 8.290
Mistral dense prefill 49.987 49.600 49.510
Mistral AAFLOW-text 53.986 53.568 53.268
Mistral vLLM local prefix 14.351 14.240 14.113
Mistral SGLang prefix 14.591 14.338 14.142
Mistral KVCOMM 15.702 15.580 15.153
Mistral DistServe style 50.995 50.600 50.312
Llama3 AAFLOW+ 4.210 4.145 4.327
Llama3 dense prefill 25.188 24.800 24.212
Llama3 AAFLOW-text 27.202 26.784 26.319
Llama3 vLLM local prefix 7.231 7.120 6.851
Llama3 SGLang prefix 7.311 7.239 6.912
Llama3 KVCOMM 7.912 7.790 7.687
Llama3 DistServe style 25.695 25.300 25.128
local-prefix methods reduce duplication but lack explicit shared-
state ownership, preventing them from achieving AAFLOW+’s peak
memory efficiency.
F.5 Experiment 5: Throughput and Framework
Overhead
The goal is to measure effective generated-token throughput and
modeled framework overhead Ω. AAFLOW+ should improve work-
flow throughput by removing repeated prefill and reducing text
orchestration.
The throughput and overhead results (Table 12) show the clearest
split between workflow execution and raw serving. Among the
workflow rows, AAFLOW+ is best on every backend. For Mistral,
AAFLOW+ reaches 302.61 tok/s on HF, compared with 39.62 tok/s
for SGLang prefix, 38.81 tok/s for vLLM local prefix, 37.62 tok/s for
DistServe style, 35.59 tok/s for KVCOMM, and about 32 tok/s for
dense and AAFLOW-text. On vLLM, Mistral AAFLOW+ reaches
280.30 tok/s, while the strongest workflow competitor is 36.89 tok/s.
On SGLang, Mistral AAFLOW+ reaches 207.09 tok/s, while the
strongest workflow competitor is 27.10 tok/s. Llama3 shows the
same pattern: AAFLOW+ reaches 300.57/314.26/256.84 tok/s across
HF/vLLM/SGLang, whereas the strongest workflow competitor
stays near 39.27/41.35/33.61 tok/s.
The overhead values explain why AAFLOW+ keeps mean mod-
eled framework overhead fixed at 0.0075 s across both models and
all three backends. By contrast, AAFLOW-text and KVCOMM pay
much larger overheads: for Mistral, AAFLOW-text incurs 11.1659 s
on HF, 89.5948 s on vLLM, and 40.5748 s on SGLang, while KV-
COMM incurs 21.6770 s, 174.3231 s, and 78.9242 s. Dense prefill in-
curs minimal framework overhead but suffers from low throughput
due to repeated full-prefix computation. Local-prefix and DistServe-
style baselines also have modest overhead but fall short of AAFLOW+
because they retain workflow-level duplication of shared context.
20

## PDF Page 21

Table 12: Experiment 5: Mean throughput and overhead. n/a = not applicable, as that specific baseline is tightly coupled with
that specific backend.
HF Backend vLLM Backend SGLang Backend
Model Baseline Throughput Mean Throughput Mean Throughput Mean
(tok/s)Ω(s) (tok/s)Ω(s) (tok/s)Ω(s)
Mistral AAFLOW+ 302.61 0.0075 280.30 0.0075 207.09 0.0075
Mistral dense prefill 31.94 0.0019 22.78 0.0019 20.99 0.0019
Mistral AAFLOW-text 31.84 11.1659 22.62 89.5948 20.91 40.5748
Mistral vLLM local prefix 38.81 0.0627 36.11 0.0627 26.54 0.0627
Mistral SGLang prefix 39.62 0.0657 36.89 0.0657 27.10 0.0657
Mistral KVCOMM 35.59 21.6770 29.67 174.3231 24.03 78.9242
Mistral DistServe style 37.62 0.0597 35.23 0.0597 25.93 0.0597
Mistral live SGLang serve n/a n/a n/a n/a 591.14 0.0
Mistral live vLLM serve n/a n/a 704.08 0.0 n/a n/a
Llama3 AAFLOW+ 300.57 0.0075 314.26 0.0075 256.84 0.0075
Llama3 dense prefill 33.61 0.0019 25.83 0.0019 25.65 0.0019
Llama3 AAFLOW-text 33.54 6.7272 25.65 47.4580 25.54 23.4720
Llama3 vLLM local prefix 38.46 0.0627 40.48 0.0627 32.92 0.0627
Llama3 SGLang prefix 39.27 0.0657 41.35 0.0657 33.61 0.0657
Llama3 KVCOMM 36.16 13.0375 33.45 92.3380 29.63 45.6145
Llama3 DistServe style 37.46 0.0597 39.49 0.0597 32.15 0.0597
Llama3 live vLLM serve n/a n/a 801.55 0.0 n/a n/a
Llama3 live SGLang serve n/a n/a n/a n/a 673.26 0.0
Although live vLLM and SGLang show higher raw throughput,
these reflect optimized server performance, not explicit distributed
state transfer. Thus, AAFLOW+ leads among workflow systems in
this evaluation, with its remaining gap to live serving attributable
to explicit accounting of distributed state-transfer costs, rather than
concealing them within local engines.
21