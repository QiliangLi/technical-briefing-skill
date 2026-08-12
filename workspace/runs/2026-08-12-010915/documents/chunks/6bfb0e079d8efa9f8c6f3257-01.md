## PDF Page 1

KAP: BRIDGING THEKNOWLEDGE
SELECTION–RUNTIMECONSUMPTIONGAP IN
LLM SYSTEMS
Shuo Wang Fang Xi ∗ Wenyuan Huang Qing Wang Junming Su
QiYuanLab
Beijing, China
{wangshuo,xifang,huangwenyuan,sujunming}@qiyuanlab.com
d202510468@xs.ustb.edu.cn
ABSTRACT
Modern LLM systems increasingly rely on knowledge-selection processes that
produce high-value structured priors, such as ranked evidence, graph topology,
multimodal alignment, and confidence signals. Yet LLM serving remains funda-
mentally oblivious to this rich structure: once such signals are serialized into a
prompt, the backend observes only a flat token sequence, forcing dense and uni-
form consumption of the full key-value (KV) state during decoding. We term this
architectural mismatch the Knowledge Selection–Runtime Consumption (KSRC)
gap: richer contexts enlarge the full-prompt KV footprint and decode-time mem-
ory traffic, increasing latency and degrading throughput even when reasoning de-
pends on only a small fraction of the context. To bridge the gap, we propose
Knowledge Access Planning(KAP), a paradigm-shifting execution abstraction
that elevates structured knowledge priors from passive prompt-construction hints
into first-class physical execution artifacts. KAP establishes a universal interme-
diate representation (IR)—the runtime access plan—which compiles structured
knowledge signals to govern physical KV access without altering logical prompt
semantics, model weights, or training procedures. Through this IR, KAP shifts
LLM serving from token-aware context consumption to plan-driven, knowledge-
aware runtime consumption. We instantiate KAP with GRAPHSPEC, a compiler–
executor realization connecting structured knowledge selection to an LLM serving
backend. We derive a phase-boundary model for the positive-speedup regime of
plan-guided execution. Across 4K–128K long-context QA workloads, GRAPH-
SPECmaintains answer quality comparable to full-context decoding while decou-
pling physical KV consumption from prompt length, reducing proposal-time KV
access to 5.5% of source KV state at 128K, and fundamentally shifting the scaling
trajectory of long-context generation.
1 INTRODUCTION
The Knowledge Selection–Runtime Consumption Gap.Modern LLM systems increasingly de-
pend on upstream processes that select, structure, and prioritize external knowledge. Retrieval-
augmented generation is a prominent instance: modern pipelines combine dense retrieval, rerank-
ing, and structured reasoning frameworks such as GraphRAG (Edge et al., 2024) and HippoRAG
(Jimenez Gutierrez et al., 2024) to rank evidence, traverse graph structure, localize supporting spans,
and estimate confidence (Lewis et al., 2020; Karpukhin et al., 2020). Such knowledge-selection fron-
tends increasingly operate as semantic planning systems, yet the LLM serving backend receives only
their serialized residue. Prompt serialization collapses these high-dimensional knowledge-selection
decisions into a one-dimensional token stream, leaving the backend oblivious to the semantic struc-
ture already resolved upstream. Physical execution is consequently governed by token layout rather
than knowledge importance, wasting frontend semantic computation and backend memory band-
width on undifferentiated context. We term the resulting architectural mismatch the Knowledge
∗Corresponding author.
1
arXiv:2607.24260v1  [cs.LG]  27 Jul 2026

## PDF Page 2

Request
Selection
Engine
Score
Rank
Traverse
Ranked 
Evidence
Structural 
Relations
Evidence 
Spans
Score
Backend Input KV Representation Runtime 
ConsumptionConventional Serving
KAP-Enabled Serving
Serialized Prompt
Full-Context KV State Uniform Full-Context 
Access
LLM
Runtime
LLM
Runtime
Universal IR
Verification
/ Fallback
Structured 
Knowledge
Priors
Selected KV View Plan-Guided Access
KAP Compiler KAP Executor
KSRC
Gap
Runtime Access Plan
Figure 1:The KSRC gap and KAP-enabled LLM serving.A knowledge-selection frontend
produces structured knowledge priors. Conventional serving exposes only a serialized prompt to
the LLM serving backend and uniformly consumes full-context KV state, creating the KSRC gap.
KAP instead carries these priors across the boundary through a runtime access plan—a universal IR
that determines a selected-KV view and enables plan-guided access with verification or fallback.
Selection–Runtime Consumption Gap: knowledge selection determines what matters, while the
runtime executes as if the full serialized context must be consumed uniformly. As knowledge-
selection processes become more capable, the gap becomes more pronounced. Richer knowledge
inputs, including graph expansions, larger evidence sets, multimodal context, longer supporting his-
tories, and other structured signals, may improve reasoning quality, but they also increase serialized
context length, KV-cache traffic, decoding latency, and serving cost (Pope et al., 2023; Kwon et al.,
2023), often forcing practitioners to discard useful information simply to satisfy runtime constraints.
Knowledge selection has become structure-aware, while LLM serving remains token-aware.
Knowledge Access Planning.To bridge the knowledge selection–runtime consumption gap, we
introduce KAP, a general paradigm for plan-driven knowledge execution. Rather than allowing
frontend decisions to terminate at prompt serialization, KAP organizes runtime knowledge con-
sumption around a universal intermediate representation (IR)—the runtime access plan—that de-
couples logical prompt semantics from physical KV-cache access. As illustrated in Figure 1, KAP
bridges the KSRC gap through a compiler–executor division of responsibility: the KAP compiler
translates high-dimensional knowledge priors into this IR, and the KAP executor interprets it to
govern physical access within the LLM serving backend. Together, the compiler and executor shift
LLM serving from token-aware context consumption to plan-driven runtime knowledge consump-
tion without modifying the knowledge-selection frontend, language model, or logical prompt.
The architectural scope of the IR extends beyond any single knowledge source. Because runtime
access plans separate frontend semantic units from backend runtime objects, KAP is independent
of any particular modality, model architecture, or LLM serving substrate. Structured signals such
as textual relevance, graph centrality, multimodal alignment, agent-memory salience, and source
confidence can be compiled into a common execution representation, while backend-specific execu-
tors translate that representation into concrete runtime actions. Rather than treating larger context
windows as a mandate for proportionally larger physical consumption, KAP makes knowledge con-
sumption an explicit execution-planning problem.
We argue that bridging the knowledge selection–runtime consumption gap initiates a fundamental
shift in how long-context LLM systems should consume knowledge. Expanding context windows
2

## PDF Page 3

toward million-token scales cannot by itself resolve the LLM serving bottleneck if physical con-
sumption continues to grow with serialization. The future of scalable reasoning therefore lies in
knowledge-selection–execution co-design, where frontend selectivity and backend consumption are
optimized against a shared systems objective. Section 4 formalizes the coupling through a phase
boundary, providing analytical and empirical grounding for a new scaling principle: as knowledge
selection becomes more selective while preserving execution fidelity, the physical cost of LLM serv-
ing can, and should, scale sublinearly with context length.
GraphSpec as a concrete instantiation.To demonstrate the practicality of the KAP paradigm,
we instantiate it as GRAPHSPEC, with Graph-RAG serving as the knowledge-selection frontend
andVLLM as the LLM serving backend. GRAPHSPECtreats graph-derived frontend outputs as
structured knowledge priors, compiles them into runtime access plans, and lets the backend consume
knowledge according to these plans while retaining full-context verification.
The instantiation serves as a reference implementation of KAP: graph-derived priors are no longer
used only to construct prompts, but are preserved as executable guidance for runtime knowledge
consumption. GRAPHSPECrepresents one concrete realization of the KAP executor; KAP itself
does not prescribe a particular cache organization, access mechanism, or verification strategy. Sec-
tion 3 describes how GRAPHSPECmaterializes the abstraction usingVLLM runtime objects, and
Section 5 evaluates its serving efficiency and answer quality.
Contributions.Our main contributions are:
•Problem formulation:We identify and formalize the knowledge selection–runtime consumption
gap as a previously underexplored architectural gap in LLM systems that consume externally
supplied knowledge. Modern knowledge-selection frontends expend substantial computation to
estimate, structure, and prioritize task-relevant knowledge, but prompt serialization prevents these
decisions from remaining actionable inside the LLM serving backend. The result is a fundamental
scaling misalignment: physical serving cost grows with serialized context length rather than with
the knowledge that actually drives reasoning.
•Knowledge Access Planning paradigm:We introduce KAP, a paradigm that shifts LLM serving
from passive prompt serialization to plan-driven runtime knowledge consumption. At its core,
KAP establishes the runtime access plan as a universal intermediate representation that translates
structured knowledge-selection decisions into backend physical-access policies while decoupling
logical prompt semantics from physical KV consumption.
•GraphSpec instantiation:We build GRAPHSPECas a concrete reference implementation of
KAP, with Graph-RAG serving as the knowledge-selection frontend andVLLM as the LLM
serving backend. By connecting frontend knowledge priors to the LLM serving runtime through
runtime access plans, GRAPHSPECdemonstrates that KAP is not only a conceptual paradigm but
a deployable serving abstraction that can be realized within an existing LLM serving stack.
•Phase-boundary analysis:We derive a phase-boundary model that quantifies how knowledge-
guided selectivity and runtime acceptance jointly determine the positive-speedup region. The
resulting conditional boundary provides an analytical criterion for knowledge-selection–execution
co-design across the frontend, the KAP compiler, and the LLM serving backend.
•Empirical evaluation:We conduct a controlled empirical evaluation on long-context QA work-
loads with up to 128K-token contexts. At 128K, GRAPHSPECexposes only 5.5% of the source
KV state to the proposal path while maintaining answer quality comparable to full-context decod-
ing, with a corresponding 1.19×decode-throughput speedup. The observed behavior is consistent
with the predicted phase-boundary trend, supporting both the KAP paradigm and its GRAPHSPEC
realization.
2 KNOWLEDGEACCESSPLANNING
KAP is organized around a universal intermediate representation: theruntime access plan. Rather
than defining KAP by a particular sparse-access mechanism, cache layout, or decoding procedure,
this runtime IR carries structured knowledge selection across the prompt boundary and into LLM
serving. It provides a common representation through which frontend semantic decisions can be
compiled into physical-access policies interpreted by the LLM serving backend. We first define the
3

## PDF Page 4

IR schema and its invariants, and then present the compiler–executor architecture that produces and
consumes it.
2.1 RUNTIMEACCESSPLAN AS AUNIVERSALIRFORLLM SERVING
A runtime access plan acts as the execution contract between knowledge selection and LLM serv-
ing. Knowledge-selection frontends reason over semantic objects such as passages, evidence spans,
graph nodes, and relevance signals, whereas LLM serving runtimes execute over physical objects
such as token spans, KV objects, cache blocks, attention regions, and scheduling metadata. The
plan bridges these abstraction levels by specifying how frontend-selected knowledge is represented,
grounded in the logical prompt, mapped to backend runtime objects, accessed during decoding, and
validated before outputs are committed. The contract separates the logical context that defines model
conditioning from the physical access pattern used for efficient execution.
We represent the universal IR as:
A= (U, M, pos, ρ access, ρverify),(1)
whereUcontains selected knowledge units,Mbinds those units to runtime objects and their phys-
ical organization,pospreserves their logical positions, andρ access andρ verify encode access and
verification behavior. These fields form the common semantic contract between compiler-specific
priors and executor-specific runtime objects.
To fulfill its role, a runtime access plan answers five complementary design questions.What knowl-
edge should participate in execution?Selected knowledge units identify the prioritized evidence
retained under a runtime budget.Where is the selected knowledge located at runtime?Runtime
object mappings bind logical evidence to objects exposed by the LLM serving runtime, including
token spans, KV objects, cache blocks, attention regions, and other runtime metadata.How can
runtime optimization preserve model semantics?Logical positions ensure that selective or reor-
ganized KV access does not alter the positional semantics perceived by the model (Su et al., 2024;
Liu et al., 2024).How should selected knowledge be consumed during decoding?The runtime
access policy specifies how the executor exposes selected objects during execution.How is execu-
tion correctness guarded?The verification policy defines how selective execution is verified or
reverted before outputs are committed.
Collectively, these five dimensions define the plan schema exposed by the KAP compiler to the
KAP executor. The schema makes selected knowledge actionable at runtime, but a valid execution
abstraction must also preserve the invariants that keep selective access faithful to selection intent,
model semantics, and output correctness. We therefore require runtime access plans to satisfy three
cross-field requirements.Prior preservationensures that frontend knowledge signals are not lost
at the prompt boundary, but remain available as runtime guidance throughout execution.Logical-
position preservationseparates physical KV organization from the logical ordering and positional
semantics perceived by the model, so runtime optimization does not rewrite the conditioning context.
Verification-aware executionmakes selective access a guarded execution path: outputs produced
under plan-guided access are committed only after reconciliation with full-context verification or
fallback. Together, these requirements distinguish runtime access plans from ordinary frontend
metadata: they preserve the semantic structure produced by knowledge selection while exposing the
execution structure needed for runtime optimization.
The resulting plan abstraction connects knowledge selection to runtime execution without prescrib-
ing a particular cache organization, access mechanism, verification strategy, or LLM serving back-
end. These requirements also clarify that an effective plan is not simply the one that exposes the
least runtime state, but the one that balances selective execution with the fidelity needed for verified
generation. Section 4 formalizes the quality-efficiency trade-off through a phase-boundary analysis,
while the next subsection maps the plan abstraction onto the KAP compiler–executor architecture.
2.2 KAPCOMPILER–EXECUTOR ARCHITECTURE
The KAP architecture operationalizes the runtime access plan through an explicit compiler–executor
separation. As illustrated in Figure 2, the knowledge-selection frontend retains its existing role: it
selects and prioritizes task-relevant knowledge, producing structured knowledge priors together with
4

## PDF Page 5

Knowledge Access Planning (KAP)
Knowledge Selection Frontend KAP Compiler KAP Executor
Emit 
Plan
Execute 
Plan
KAP Inputs
Structured Knowledge 
Priors
Relevance / Salience
Structural Relations
Semantic Boundaries
Scores / Provenance
Complete Logical 
Prompt
serialized input retained
Access Plan 
Compilation
compiles inputs into 
access plans
Runtime Access Plan
Selected Knowledge Units
Runtime Object Mapping
Logical Positions
Runtime Access Policy
Verification Policy
Plan-Guided Access
Full-Context 
Verification
1
2
Priors 
+ 
Prompt
Selected KV Access
interprets the Runtime Access Plan
selected KV objects are accessed
Full-Context KV State
. . .
Universal IR for LLM Serving
Figure 2:KAP compiler–executor architecture.The KAP compiler takes structured knowledge
priors together with the complete logical prompt and emits a runtime access plan, the universal IR
for LLM serving. The plan encodes selected knowledge units, runtime object mappings, logical
positions, runtime access policy, and verification policy. The KAP executor interprets the plan
to perform plan-guided selected-KV access over full-context KV state and applies the specified
verification policy, illustrated here through full-context verification.
the complete logical prompt. The KAP compiler interprets these artifacts under a runtime budget
and emits a runtime access plan that identifies selected knowledge, binds it to runtime objects,
records logical positions, and specifies access and verification policies. The KAP executor interprets
the emitted plan as runtime actions, exposing selected KV objects during decoding and invoking
full-context verification or fallback before outputs are committed.
The division of responsibility realizes the requirements established in the preceding subsection.
Compilation preserves knowledge priors and carries logical positions into backend-visible map-
pings; execution applies the access policy while enforcing the verification policy. The complete
logical prompt therefore remains the model’s conditioning context even when physical KV ac-
cess is selective. By separating knowledge selection, plan compilation, and plan-guided execu-
tion, KAP makes selected knowledge actionable within LLM serving without requiring changes to
the knowledge-selection frontend or the base language model. More fundamentally, the compiler–
executor separation defines KAP as a model-, modality-, and framework-independent systems ab-
straction: heterogeneous priors from multimodal contexts, agent histories, graph-structured knowl-
edge, and other sources can be compiled into a common runtime access-plan IR, while backend-
specific executors realize the same IR across diverse cache organizations, attention mechanisms,
and inference substrates. KAP thereby provides an extensible foundation for knowledge-selection–
execution co-design, allowing application-specific frontends and backend execution mechanisms to
evolve independently through a common executable representation. Section 3 shows how GRAPH-
SPECinstantiates the architecture for a Graph-RAG frontend and theVLLM serving backend.
3 GRAPHSPEC: INSTANTIATINGKAPWITH AGRAPH-RAG FRONTEND AND
VLLM BACKEND
We present GRAPHSPECas a reference implementation of the universal runtime access plan IR
and compiler–executor architecture introduced by KAP in Section 2. Rather than defining a new
knowledge-selection frontend or serving engine, GRAPHSPECspecializes KAP to an integrated
Graph-RAG frontend andVLLM serving backend. The Graph-RAG frontend supplies graph-
derived knowledge priors and the complete logical prompt, whileVLLM provides the execution
5

## PDF Page 6

GraphSpec KAP Compiler GraphSpec KAP Executor
Graph-RAG Priors Evidence Spans Token Spans KV Page Mapping Runtime Access Plan
Knowledge Graph
Retrieved Passages
P1: ... A
causes B in
cell signaling ...
P2: ... C
interacts with
D under ...
P3: ... E
inhibits F via ...
P4: ... D
regulates A via
a ...
···
Structured Signals
1. Node Score
2. Edge Score
3. Freshness
4. Source reliability
★ ★ 
★
☆ 
☆
Logical Positions
Original positions 
are retained;
selected KV pages 
are compacted
P1: ... A 
causes B in cell 
signaling ...
P2: ... C interacts 
with D under 
condition ...
P3: ... E inhibits 
F via pathway
P4: ... D 
regulates A via 
a ...
Complete Logical Prompt
(logical positions)
Full KV Cache
(physical pages)
0 32 64 ··· N-1 0 1 2 ··· M-1
···
···
···
···
Plan Meta
 Plan ID: req_1
 Created: t
···
Selected Knowledge 
Units
S1 [40, 87]
S2 [104, 135]
···
Runtime Object 
Mapping
 Block Table 
Token Spans → KV 
Pages
 Slot Mapping 
Compact Slots → 
Original Logical 
Positions
Selected-KV View Materialization
···
compact physical layout for proposal access
Block Table Slot Mapping
Span ID S1 S2 ···
Start Pos 40 104
End Pos 87 135
Page ID 0 0, 1
KV Page ID 0 0 1 ···
Slot Range 0-47 48-63 64-79
Logical Pos 40-87 104-
119 120-135
Span ID S1 S2 S2
Selected-KV Proposal
Runtime 
Access Plan
Selected KV Access
···
Block Table Slot Mapping
Base
Model
Decode
Blocks
Proposed
Tokens
t1 t2 ··· tn
•  Plan-guided access
•  Fewer KV reads
•  Low latency
Full-Context Verification
Proposed Tokens
t1 t2 ··· tn
Verifier KV Path
Full KV Cache
0 1 2 3 4 M-1
···
Same
Base
Model
Decode
Blocks
Target Logits
Validate
accept / reject
per token
Verified Tokens (accepted)
t1 t2 ··· tk •  Full-context validation
•  Full KV access
•  Target-model checkk ≤ n
Runtime Access 
Policy
Selected-KV 
Proposal
Verification Policy
Full-Context 
Verification
Figure 3:GRAPHSPECrealization of the KAP compiler–executor architecture.Compiler: the
GraphSpec KAP compiler grounds Graph-RAG priors in evidence and token spans, maps selected
spans to paged-KV runtime objects, materializes a logical-position-preserving selected-KV view,
and encodes the corresponding mappings and policies in a runtime access plan. Executor: the
GraphSpec KAP executor interprets the plan through selected-KV proposal, reconciles proposed
tokens through full-context verification with the same base model, and commits the accepted prefix.
substrate for plan-guided KV access. The runtime access plan carries graph-level selection deci-
sions into backend runtime behavior. GRAPHSPECselects one point in the open executor design
space: selected-KV self-speculation with full-context verification. This execution policy provides
a concrete realization of KAP rather than defining the KAP abstraction itself. Figure 3 concretizes
the universal IR by mapping each plan dimension in Section 2.1 toVLLM runtime state. GRAPH-
SPECrepresents selected knowledge units as budgeted evidence spans; realizes runtime object map-
pings and logical positions through token-span-to-page mappings, block tables, slot mappings, and
preserved position indices; and instantiates the access and verification policies as selected-KV pro-
posal and full-context verification. The runtime access plan therefore remains the knowledge-level
IR, whereas the selected-KV view is itsVLLM-specific proposal-side materialization; the executor
coordinates this physical view with full-context verification before committing tokens.
3.1 GRAPHSPECKAPCOMPILER
Graph-RAG priors.GraphSpec treats the Graph-RAG frontend as a source of graph-derived
knowledge priors rather than as part of the serving runtime. In our implementation, the priors are
produced by a hybrid Graph-RAG retrieval procedure that combines vector retrieval, reranking,
graph node scoring, and PPR-based graph expansion to produce candidate evidence. Each retrieved
graph unit may carry frontend metadata such as node type, passage provenance, graph neighbor-
hood, anchor location, or other annotations useful for runtime access. Graph-RAG thus realizes
one point in a broader KAP frontend space: application-specific knowledge structures enter LLM
serving as compilable priors rather than backend-specific execution logic.
Evidence-to-runtime compilation.The compiler converts these priors into a backend-executable
plan in four stages. It first grounds graph-derived evidence in source passages and aligns the evi-
dence to token spans in the complete logical prompt. It then performs budget-aware semantic selec-
tion over evidence objects rather than KV pages. Next, it resolves the selected spans to KV pages
and materializes a compact physical view while preserving logical positions and constructing the
block tables and slot mappings required by the executor. Finally, it emits a runtime access plan that
references these runtime objects and specifies selected-KV proposal and full-context verification
6

## PDF Page 7