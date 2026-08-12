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

Algorithm 1 GraphSpec KAP compiler.Graph-RAG-specific access-plan compilation.
1:procedureGRAPHSPECCOMPILE(π graph, X,P KV, B, ρverify)
Input:Graph-RAG priorsπ graph, logical promptX, paged-KV metadataP KV, budgetB,
verification policyρ verify
Output:runtime access planplan
2:spans←GROUNDEVIDENCE(π graph, X)
3:tokenSpans←ALIGNTOKENSPANS(spans, X)
4:U←SELECTEVIDENCEUNDERBUDGET(tokenSpans, π graph, B)
5:V←RESOLVESELECTEDKVOBJECTS(U,tokenSpans,P KV)
6:pos←PRESERVELOGICALPOSITIONS(U,tokenSpans, X)
7:slots←ASSIGNCOMPACTSLOTS(V)
8:blockTable←BUILDBLOCKTABLE(V,slots,P KV)
9:slotMap←BUILDSLOTMAPPING(U,tokenSpans,slots)
10:view←BUILDSELECTEDKVVIEW(V,blockTable,slotMap, pos)
11:M← {view,blockTable,slotMap}
12:ρ access ←BUILDSELECTEDKVPROPOSALPOLICY(view, B)
13:plan←EMITRUNTIMEACCESSPLAN(U, M, pos, ρ access, ρverify)
14:returnplan
15:end procedure
policies. Algorithm 1 formalizes the GraphSpec-specific compilation path. The staged translation
exposes the portability of the universal IR: semantic selection remains application-defined, while
physical realization is specialized by the backend compiler.
Selected-KV view materialization.The compiler materializes the proposal-side access specifi-
cation carried by the runtime access plan as a selected-KV view overVLLM’s paged-KV cache.
As shown by the selected-KV-view and runtime-object-mapping components in Figure 3, semantic
evidence selections are resolved into token-span and KV-page mappings, and the selected pages are
compacted in access order. Crucially, this materialization reorganizes only physical KV placement:
the original logical positions are preserved through the visibility mask, prompt-length metadata,
block tables, and slot mappings consumed by the attention backend. Block tables resolve plan-
visible logical blocks to compact physical pages, while slot mappings place newly scheduled tokens
into their corresponding physical KV slots.
During proposal, these metadata expose only the KV objects selected by the runtime access plan;
during verification, full-context metadata exposes the complete KV state. Both paths retain the same
logical positions, keeping proposal and verifier logits aligned under consistent positional semantics.
The verification policy remains associated with the request and invokes full-context fallback when
selected-KV execution is invalid. The resulting selected-KV view therefore exemplifies how the
universal plan IR can be specialized into engine-specific physical state while preserving model con-
ditioning, a realization pattern that extends beyondVLLM’s paged-KV organization.
3.2 GRAPHSPECKAPEXECUTOR
Selected-KV proposal.The GraphSpec KAP executor interprets the runtime access plan through
two coordinated execution paths. The plan references the materialized selected-KV view and its
block-table, slot-mapping, positional, and verification metadata; GraphSpec uses the same base
model for proposal generation and verification. Recent long-context speculative systems reduce pro-
posal cost through shortened retrieval contexts, quantized draft states, or learned memory-efficient
drafters (Chen et al., 2025; Tiwari et al., 2025; Yang et al., 2026). GraphSpec adopts the same gen-
eral draft-and-verify structure but derives its proposal path differently: the base model executes over
a selected-KV view compiled from frontend knowledge priors through the runtime access plan.
Each proposal step is implemented as a decode-like forward pass withq prop = 1. The executor
provides the current proposed token, its full-sequence logical position, the compact block table,
compact slot mapping, and compact attention metadata constructed by the compiler. The model
parameters are identical to the full-context verifier; only the prompt-side KV objects exposed to
attention are restricted by the selected KV view.
7

## PDF Page 8

As illustrated on the executor side of Figure 3, the proposal state is provisional. The access plan de-
termines which prompt-side KV pages are visible during candidate generation, but final acceptance
and committed-state advancement remain with the full-context verifier. Proposal efficiency therefore
comes from executing the same model over selected-KV access while retaining a full-context veri-
fication path. At the architectural level, this realization shows how a KAP executor can introduce a
specialized knowledge-consumption path alongside an existing full-context path without changing
the underlying model.
Full-context verification.After proposingkcandidate tokens, GraphSpec verifies them with a
full-context verifier path. The verification input is a short contiguous query window withq verify =
k+ 1: a verifier-approved carry token that anchors the window, followed by thekproposed tokens.
The verifier uses the full KV cache, full-context block table, full-context slot mapping, and original
logical positions.
Letcdenote the carry token and let ˆx1:k denote the proposed token window. The verifier forward is
the runtime transition that both validates proposals and advances the full-context state:
(m, c+,KV full,+) =V full
θ

KVfull, c, ˆx1:k;ρ

,(2)
whereρis the verification policy andm∈ {0, . . . , k}is the number of proposed tokens accepted
consecutively from the beginning of the candidate window. For QA-oriented serving, we instantiate
ρas target-guided tolerant verification: the Top-3 rule used in our implementation accepts a proposed
token when it lies within the target model’s top-3 candidates under the full context. The resulting
acceptance countmis the runtime quantity underlying the acceptance termhin Section 4.
The verifier transition produces the accepted prefix, the next verifier-approved carry tokenc +, and
the committed full-context stateKV full,+ for the committed sequence. Full-context verification
therefore advances the full-KV state within the same verifier transition, eliminating a separate resyn-
chronization pass. As shown by the verifier KV path in Figure 3, selected-KV proposal access is
reconciled with the full-context state before tokens are committed, providing the quality guard for
selective execution. Encoding this reconciliation as a plan policy separates physical-access optimiza-
tion from output-commitment semantics, allowing executor strategies to evolve without weakening
the correctness path.
Runtime stability and fallback.Reducing proposal-time KV access is necessary but not suffi-
cient for end-to-end speedup: dynamic metadata, changing tensor shapes, or repeated KV allocation
can erase the savings from selected-KV access. At the implementation level, the selected-KV pro-
posal path must remain close toVLLM’s optimized uniform decode path: the plan should restrict
KV visibility without turning decoding into a shape-changing metadata-reconstruction path. Graph-
Spec therefore keeps proposal and verification shapes stable whenever possible (Kwon et al., 2023).
The proposal path follows a stable decode-like execution shape inVLLM with compact attention
metadata, while the verifier uses a fixedq verify =k+ 1window for a chosen proposal lengthk.
In practice, GraphSpec stabilizes query lengths, compact KV capacity, block structure, block tables,
slot mappings, attention metadata shapes, and CUDA graph dispatch tags. A reusable compact KV
workspace reduces allocation overhead and makes the proposal path more graph-replay friendly.
Consequently, the block-table and slot-mapping objects in Figure 3 are performance-critical runtime
metadata: their regularity determines whether selected-KV access preservesVLLM’s optimized
decode execution. These constraints also explain why proposal-side KV reduction is not expected
to translate linearly into end-to-end throughput: selected-KV access reduces one component of the
critical path, while verification and runtime orchestration remain necessary.
Fallback combines runtime feasibility and plan quality. GraphSpec uses full-context access when
the plan exceeds the compact workspace, violates metadata-stability assumptions, has insufficient
graph-prior confidence, retains too much KV (shigh), or yields low observed acceptance (h
low). These conditions operationalize the quantities underlying the phase boundary in Section 4:
a plan must satisfy theh–strade-off while preserving the execution regularity required by high-
performance LLM serving. Making feasibility and fallback conditions visible to planning turns
backend constraints into compiler inputs, enabling knowledge selection, plan construction, and
physical execution to be optimized as a coordinated system.
8

## PDF Page 9

4 COSTMODEL ANDPHASE-BOUNDARYANALYSIS
A runtime access plan reduces serving cost by exposing only a selected portion of the available KV
state to a planned execution path. However, selective access also introduces a quality-efficiency
trade-off: removing too much context may reduce proposal quality, lower verifier acceptance, and
increase the cost paid per committed token. We develop a cost model for plan-guided execution and
derive a phase boundary that separates positive- and negative-speedup regimes, first for a general
proposal–verification setting, and then specialize the result to GRAPHSPEC, where the proposal and
verification paths use the same base model.
4.1 COST MODEL AND CONDITIONAL PHASE BOUNDARY
Consider a runtime access planAproduced by the KAP compiler according to the universal IR
in Equation 1. Standard full-context serving corresponds to consuming the full prompt access set
Afull ={1, . . . , L}at each decoding step; runtime access planning instead exposes a budgeted
subset or physical view derived fromAwhile preserving full-context verification.
Model assumptions.We adopt a memory-bound view of autoregressive decoding (Pope et al.,
2023; Kwon et al., 2023), treat context length as locally constant within one proposal–verification
cycle, and model weight and KV reads as effective memory-traffic costs. The analysis abstracts
away scheduler, metadata-construction, synchronization, and kernel-launch overheads; these factors
affect realized speedup but not the idealized break-even condition derived below. LetW main de-
note the effective weight-memory cost of one full-context main-model decode forward, and letKV
denote the cost of reading the full historical KV cache. Standard full-context decoding incurs:
Costfull ≈W main +KV.(3)
A runtime access plan affects the proposal path through two quantities. The retained-KV ratio is:
s(A) = KV accessed by the proposal path
KV accessed by full-context decoding ,(4)
and the proposal acceptance rate is:
h(A) = accepted proposed tokens
speculated proposed tokens .(5)
We write these assandhwhenAis clear.
Consider a planned cycle that proposesktokens and verifies them with the full-context main model.
LetW prop denote the per-step weight-memory cost of the proposal path. The cycle produces1 +kh
output tokens in expectation, so standard full-context decoding would spend:
Costbase = (1 +kh)(W main +KV).(6)
The planned cycle spends:
Costplan =k(W prop +sKV) + (W main +KV),(7)
where the first term is the proposal cost under plan-guided selected-KV access and the second term
is full-context verification. A runtime access plan yields positive speedup when it costs less than
standard full-context decoding for the same expected output:
Costplan <Cost base.(8)
Substituting Equations 6 and 7, we obtain:
k(Wprop +sKV) + (W main +KV)<(1 +kh)(W main +KV)
Wprop +sKV < h(W main +KV)
(h−s)KV > W prop −hW main.(9)
Equation 9 defines the idealized phase boundary for the proposal–verification class of plan-guided
execution. Conditional on thehandsinduced by a plan, it separates the positive- and negative-
speedup regimes under the cost-model assumptions. The left-hand side is the acceptance-adjusted
KV-access margin, while the right-hand side is the residual proposal-path cost after accounting for
accepted main-model work. A plan is beneficial only when it reduces retained KV access enough,
and preserves proposal acceptance enough, to offset proposal-path and full-context verification costs.
9

## PDF Page 10

4.2 GRAPHSPEC SPECIALIZATION AND PLANNING IMPLICATIONS
GraphSpec is a self-speculative instantiation of KAP: the proposal and verification paths use the
same base model. Therefore,
Wprop =W main.(10)
With equal proposal and verification model costs, Equation 9 becomes:
(h−s)KV >(1−h)W main.(11)
The specialized boundary exposes the basic margin condition behind GraphSpec-style selected-KV
self-speculation:
h > s.(12)
The condition is necessary for a positive KV-access margin, while realized speedup still depends on
the break-even KV scale below and practical runtime overheads. Ifh≤s, the selected-KV proposal
path does not create such a margin; increasing context length alone cannot move the plan into the
positive-speedup region. Whenh > s, the approximate idealized break-even KV scale is:
KV crit ≈ (1−h)W main
h−s .(13)
Thus, GraphSpec is naturally long-context oriented: as context length grows,KVincreases, and a
plan with high acceptance and low retained-KV ratio can cross the phase boundary.
For KAP, the boundary turns access planning into a constrained plan-selection problem: retain
enough critical evidence to keep the proposal path aligned with the full-context verifier, while re-
moving enough low-value KV access to reduce runtime cost. We define the ideal phase slack of a
runtime access plan as:
∆phase(A) =h(A)(W main +KV)−(W prop +s(A)KV).(14)
A plan lies in the positive-speedup region when∆ phase(A)>0. The corresponding phase-slack
objective is:
A∗
phase = arg max
A
∆phase(A),s.t.Q task(A)≈Q task(full),(15)
whereQ task denotes answer-level task quality. For GRAPHSPEC,∆ phase = (h−s)KV−(1−
h)Wmain. Importantly,handsare coupled through the quality of the compiled plan. Retaining more
runtime state increasessbut may improvehby preserving context that aligns the proposal path with
the full-context verifier; more selective access lowerssbut may reduceh. Knowledge-prior quality
shapes the trade-off: informative priors can sustain a given acceptance level at a smaller retained-
KV ratio, whereas weak or miscalibrated priors require broader retention or move execution toward
the negative-speedup region. The quantityh−scaptures the KV-side acceptance–retention margin,
whereas∆ phase represents the complete idealized break-even slack. The compiler should therefore
optimize phase slack rather than minimize retained KV access in isolation. The phase boundary
converts knowledge-selection quality into execution utility: knowledge priors are valuable not only
when they identify semantically relevant evidence, but also when they induce runtime access plans
with favorable break-even behavior. This establishes knowledge-selection–execution co-design as a
quantitative systems objective rather than a qualitative architectural principle.
The boundary provides a planning criterion rather than a guarantee of proposal quality. The compiler
can vary the access budget and thereby influences, whilehis induced by the resulting plan and
verification policy. Observed acceptance and profiled runtime costs can therefore inform budget
adjustment or fallback when the estimated phase slack becomes unfavorable.
Three practical implications follow. First, the proposal lengthkcancels out of the ideal break-even
condition, so it does not determine whether a plan can enter the positive-speedup region; instead, it
shapes finite-cycle performance by amortizing full-context verification and interacting with runtime
overheads. Second, proposal and verification logits must remain comparable, which is why Graph-
Spec preserves logical positions even when physical KV access is selective or compacted. Third,
h(A)depends on the verification policy. For the QA-oriented setting evaluated by GraphSpec, we
instantiatehas the Top-3 tolerant acceptance rate computed against the full-context verifier:
(htop3 −s)KV >(1−h top3)Wmain.(16)
Equation 16 instantiates the conditional cost model for target-guided tolerant verification; it is not
an exact sampling guarantee; answer quality is evaluated empirically against standard full-context
decoding.
10

## PDF Page 11

5 EXPERIMENTS
We evaluate GRAPHSPECas an instantiation of KAP for long-context knowledge-augmented LLM
serving through four research questions that organize the evidence chain from the knowledge
selection–runtime consumption gap diagnosis to KAP’s systems behavior, execution mechanism,
and analytical boundary:
•RQ1:Does GRAPHSPECdecouple physical KV consumption from serialized context growth?
•RQ2:Does GRAPHSPECsustain efficiency gains while preserving answer quality across context
lengths?
•RQ3:Does the runtime access plan bridge knowledge selection and runtime consumption?
•RQ4:Is the observed speedup trend consistent with the phase-boundary analysis?
5.1 SETUP
Model and serving backend.We use Qwen3-VL-32B-Instruct as the target model and implement
GraphSpec by extendingVLLM v0.16.0. Experiments run on four NVIDIA A800 80GB GPUs
with tensor parallelism 4 and bfloat16 execution, with the serving engine configured for the 4K–
128K context sweep. Unless otherwise specified, the full-context baseline, GraphSpec, and prompt-
materialization baselines use the same model weights, tokenizer, decoding configuration, software
stack, and hardware environment. GraphSpec uses the same base model for proposal and verification
withk= 6speculative tokens. The full-context baseline and GraphSpec are evaluated on the same
complete input prompt; prompt-materialization baselines use the shortened prompt produced by
their corresponding selection strategy.
Dataset.We use SPIQA, a multimodal QA benchmark grounded in figures, tables, and text
from scientific papers. The Graph-RAG frontend processes this multimodal evidence and returns
grounded evidence passages and graph-derived priors as inputs to the measured LLM serving stage.
For long-context evaluation, we preserve the supporting evidence and expand each context with
query-specific hard negatives.
Context-length control.To isolate the effect of context length, we do not use different datasets to
represent different context sizes. Instead, for each query, we keep the answer and core supporting
evidence fixed, and append query-specific hard-negative passages to construct prompts of increasing
length:
4K,8K,16K,32K,64K,128K.
The distractor list for each query is fixed across all lengths; longer contexts take progressively longer
prefixes, yielding a nested length sweep in which low-priority context increases while the core evi-
dence remains unchanged.
Methods.We compare the following methods:
•Full-context baseline:standardVLLM decoding over the complete prompt, with the full histori-
cal KV state available at each decoding step.
•GraphSpec:our runtime access planning method, which compiles Graph-RAG priors into run-
time access plans with logical-position-preserving selected-KV views and executes them through
sparse self-speculative decoding with full-context verification.
•Physical concat:a prompt-level compression counterfactual that uses GraphSpec’s selected evi-
dence spans as a prompt compressor, materializing a short prompt instead of executing a runtime
access plan.
•Random concat:a prompt-level compression baseline that concatenates randomly selected pas-
sages under a matched prompt budget.
•Local window:a prompt-level compression baseline that keeps fixed windows from the serialized
context under a matched prompt budget, without using Graph-RAG priors.
11

## PDF Page 12

Table 1:Independent human audit of the LLM-as-judge pass criterion and evidence-coverage
diagnostics.The 0.5 threshold was fixed before the audit. Three annotators independently judged
100 randomly sampled SPIQA answers without access to LLM scores; judge–human agreement
compares the thresholded LLM decisions with the majority-vote human labels. Evidence recalls
measure token-level/ROUGE-1 coverage of gold answer, rationale, or caption evidence in retrieved
passages.
Dataset Samples Judge–human agreement Answer recall Rationale recall Caption recall
SPIQA 100 95% 68.8% 66.8% 76.8%
Metrics.We report both serving efficiency and answer-level quality. Efficiency is reported pri-
marily through decode throughput (TPS) and time-to-first-token (TTFT), with the main quantitative
results shown in tables. For GraphSpec, we additionally report the retained-KV ratios, the Top-3
tolerant acceptance rateh, andh−s. For answer quality, we report LLM similarity and the corre-
sponding pass rate defined below. For phase-boundary analysis, we compare the observed retained
ratio, acceptance rate, and throughput speedup against the directional implication of the cost model
in Section 4. All serving-path measurements are collected with diagnostic profiling disabled. For the
controlled evaluation, Graph-RAG evidence and priors are frozen before benchmarking, so frontend
retrieval is excluded from TTFT for every method. TTFT is measured from frozen-request submis-
sion to the first generated token; for GRAPHSPEC, it includes runtime-access-plan compilation and
selected-KV materialization. Reported throughput covers the complete executor path rather than
isolated model-forward performance.
LLM-as-judge quality metric.Our primary open-ended QA quality metric is an LLM similarity
score in[0,1]. Exact string match is too brittle for our setting because correct answers may use dif-
ferent wording, omit irrelevant details, or combine evidence from multiple retrieved passages. The
judge compares each generated answer with the reference answer and produces a structured score
using four dimensions: fact consistency (40%), information completeness (30%), logical structure
(20%), and expression quality (10%). We reportpass rate, the fraction of examples whose weighted
similarity score is at least 0.5. This decision threshold was fixed before the human audit and was not
tuned using human annotations. To independently validate the criterion, we randomly sampled 100
SPIQA answers from the evaluated outputs. Three annotators assessed answer correctness indepen-
dently without access to the corresponding LLM scores, and their majority vote defined the human
reference label. After thresholding the LLM similarity score at 0.5, its binary decisions agreed with
the majority-vote human labels on 95 of the 100 samples. Table 1 summarizes this blinded audit.
Separately, we report evidence-recall diagnostics that measure whether the retrieved context covers
gold answer, rationale, or caption evidence, providing an orthogonal view of source coverage.
5.2 RQ1: DOESGRAPHSPEC DECOUPLE PHYSICALKVCONSUMPTION FROM SERIALIZED
CONTEXT GROWTH?
RQ1 targets the physical-consumption side of the knowledge selection–runtime consumption gap.
Under standard full-context execution, a longer serialized prompt enlarges the KV state consumed
at every decoding step. KAP predicts a different scaling behavior: Graph-RAG priors should let
proposal-time consumption become increasingly selective as context grows, and the avoided access
should translate into throughput gains. To test both consequences, we construct nested evidence-
preserving prompts from 4K to 128K tokens and run the full-context baseline and GRAPHSPECon
the same complete prompt at every length.
Result discussion.Table 2 confirms both effects. As context length increases from 4K to 128K,
the proposal-visible KV ratio falls from 40.1% to 5.5%, while proposal acceptance remains near
0.95–0.96; over the same sweep, decode-throughput speedup rises from 1.08×to 1.19×. TTFT re-
mains close to the full-context baseline because GRAPHSPECpreserves the complete logical prompt
and targets decode-time KV consumption rather than prefill elimination. The result directly supports
KAP’s answer to the knowledge selection–runtime consumption gap: frontend knowledge relevance
can decouple proposal-time physical consumption from serialized context growth, and the resulting
access reduction translates into end-to-end decode gains.
12

## PDF Page 13

Table 2: RQ1 proposal-visible KV ratio and decode throughput over six context buckets. All entries
are averages over the evaluation set. Active KV/source andhare reported for GraphSpec;his the
Top-3 tolerant proposal acceptance rate.
Length Full-context TPS GraphSpec TPS Speedup Full-context TTFT GraphSpec TTFT Active KV/sourceh
4K 51.92 56.11 1.08×1.51s 1.56s 40.1% 0.958
8K 51.58 55.57 1.08×0.65s 0.87s 34.4% 0.957
16K 50.59 54.82 1.08×2.06s 2.17s 24.2% 0.957
32K 48.72 53.19 1.09×4.87s 4.92s 16.1% 0.956
64K 45.68 51.70 1.13×12.56s 12.71s 10.8% 0.962
128K 41.10 48.80 1.19×38.31s 37.90s 5.5% 0.953
Table 3: RQ2 final-answer quality across context lengths. GraphSpec and the full-context baseline
are evaluated with the same answer-level metric;his reported only as an execution diagnostic.
Length Full-context pass GraphSpec pass Full-context avg. sim. GraphSpec avg. sim. GraphSpech
4K 80.0% 80.2% 0.691 0.696 0.958
8K 82.6% 82.9% 0.715 0.716 0.957
16K 87.4% 87.4% 0.743 0.745 0.957
32K 86.9% 87.0% 0.744 0.749 0.956
64K 86.0% 87.9% 0.741 0.748 0.962
128K 84.6% 84.3% 0.728 0.732 0.953
5.3 RQ2: DOESGRAPHSPEC SUSTAIN EFFICIENCY GAINS WHILE PRESERVING ANSWER
QUALITY ACROSS CONTEXT LENGTHS?
RQ2 tests whether the benefits of KAP, as instantiated by GRAPHSPEC, persist across operating
scales rather than appearing only at a favorable context length. We combine the access and through-
put results from RQ1 with answer-level evaluation over the same 4K–128K sweep. GRAPHSPEC
changes proposal-time physical KV consumption, while the complete logical prompt remains avail-
able to full-context verification; a successful instantiation should therefore improve efficiency with-
out degrading final answers at any evaluated length. The Top-3 tolerant acceptance rate is reported
only as an execution diagnostic, not as the quality criterion.
Result discussion.Table 3 shows that GRAPHSPECpreserves answer quality across the full
context-length range. Its pass rate differs from the full-context baseline by at most 0.3 percent-
age points at five of the six lengths; at 64K it is 1.9 points higher, while average similarity remains
closely matched throughout. Thus, the efficiency gains in RQ1 are not obtained by trading away
answer quality. Combined with RQ1, where throughput improves by 1.08×–1.19×and proposal-
visible KV consumption falls as context grows, these results establish a consistent efficiency–quality
advantage across all evaluated lengths. The combined evidence validates the KAP approach in
GRAPHSPEC: physical knowledge consumption can be reduced to deliver systems gains without
sacrificing the answer quality anchored by the complete logical context.
5.4 RQ3: DOES THE RUNTIME ACCESS PLAN BRIDGE KNOWLEDGE SELECTION AND
RUNTIME CONSUMPTION?
RQ3 isolates the mechanism central to KAP: whether the same frontend knowledge is materialized
as a shortened prompt or compiled into a runtime access plan. Physical concat materializes the
same evidence selected by GRAPHSPECas a shortened prompt, holding evidence quality fixed while
removing the runtime access plan. Random concat removes Graph-RAG-guided selection, and Local
window replaces it with a position-based heuristic; both operate under comparable prompt budgets.
If evidence selection or prompt shortening alone were sufficient to close the knowledge selection–
runtime consumption gap, these alternatives would recover GRAPHSPEC’s quality–efficiency trade-
off.
Result discussion.Table 4 rejects that alternative. Physical concat is the decisive ablation: despite
materializing the same selected evidence in a 0.95K-token prompt, its pass rate falls to 73.9%,
compared with 87.9% for GRAPHSPEC. Random concat and Local window retain larger 7.8K-token
13

## PDF Page 14

Table 4: RQ3 ablation of evidence selection and execution strategy on 64K contexts. “Full logical
prompt” indicates whether the original serialized context and logical positions are preserved. For
prompt-materialization baselines, accessed KV/source is the served-prompt ratio; for GraphSpec, it
is the proposal-visible KV ratio. Pass rate applies the pre-specified 0.5 threshold to LLM similarity,
as independently audited in Table 1.
Method Backend Full logical prompt Served prompt Accessed KV/source TPS TTFT Avg. sim. Pass rate
Full-context standardVLLM Yes 65.2K 100.0% 45.68 12.56s 0.741 86.0%GraphSpec GraphSpec Yes 64.9K 10.8% 51.70 12.71s 0.748 87.9%Physical concat standardVLLM No 0.95K 1.46% 52.82 1.95s 0.653 73.9%Random concat standardVLLM No 7.79K 12.0% 52.23 5.17s 0.491 49.7%Local window standardVLLM No 7.78K 12.0% 52.26 5.20s 0.469 47.1%
Table 5: RQ4 empirical consistency with the phase-boundary model. The retained ratiosdecreases
as context length grows, whilehremains high; consequentlyh−sincreases together with measured
throughput speedup.
Lengths h h−sActual speedup
4K 0.401 0.958 0.557 1.08×
8K 0.344 0.957 0.614 1.08×
16K 0.242 0.957 0.715 1.08×
32K 0.161 0.956 0.796 1.09×
64K 0.108 0.962 0.853 1.13×
128K 0.055 0.953 0.897 1.19×
prompts yet fall further to 49.7% and 47.1%, confirming that arbitrary or positional selection is not
an adequate substitute for graph-derived priors. Only GRAPHSPECimproves throughput over the
full-context baseline while retaining the complete logical context and comparable answer quality. In
this controlled comparison, the runtime access plan is therefore the operative bridge in KAP: it turns
frontend selection into backend-executable consumption, whereas evidence selection that terminates
in prompt materialization leaves the knowledge selection–runtime consumption gap unresolved.
5.5 RQ4: IS THE OBSERVED SPEEDUP TREND CONSISTENT WITH THE PHASE-BOUNDARY
ANALYSIS?
RQ4 evaluates the empirical consistency of the observed performance trend with the phase-boundary
analysis in Section 4. Without refitting the cost model to the measurements, we test its directional
implication that the positive-speedup regime becomes more favorable as proposal acceptance re-
mains high relative to the retained-KV ratio. We therefore tracks,h, the marginh−s, and measured
speedup across context lengths.
Result discussion.Table 5 is consistent with the phase-boundary prediction. As contexts grow,s
decreases from 0.401 to 0.055 whilehremains high, so the marginh−sincreases from 0.557 to
0.897. Measured speedup follows the same direction, rising from 1.08×to 1.19×. The agreement
supports the directional implication of the phase-boundary model: a larger KV-side acceptance–
retention margin corresponds to a more favorable regime for plan-guided execution. It thereby
closes the KAP analysis–system–experiment loop by connecting the compiler’s planning criterion,
the executor’s observed behavior, and end-to-end speedup.
6 RELATEDWORK
Retrieval-augmented generation and graph-guided retrieval.Retrieval-augmented generation
grounds LLM outputs in external knowledge by retrieving relevant passages or documents before
generation (Lewis et al., 2020; Guu et al., 2020). Generative retrieve-and-read systems such as
Fusion-in-Decoder and retrieval-enhanced language models such as RETRO integrate retrieved pas-
sages into generation (Izacard & Grave, 2021; Borgeaud et al., 2022). Dense retrieval methods
such as DPR improve open-domain retrieval by learning neural passage representations (Karpukhin
14

## PDF Page 15

et al., 2020), and multi-hop retrieval extends dense selection to complex questions requiring evi-
dence chains (Xiong et al., 2021). Graph-based retrieval and reasoning methods build structured
representations over entities, documents, or events for multi-hop QA (Tu et al., 2019; Edge et al.,
2024; Jimenez Gutierrez et al., 2024). These works improve thefrontend knowledge selectionstage.
KAP is complementary: it asks how the selected knowledge should be consumed by the LLM serv-
ing backend once it has been retrieved.
RAG serving and KV-cache reuse.General LLM serving systems improve batching, scheduling,
offloading, and cache reuse for autoregressive generation (Yu et al., 2022; Aminabadi et al., 2022;
Sheng et al., 2023; Kwon et al., 2023; Zheng et al., 2024). Recent RAG-specific systems optimize
serving by caching or reusing intermediate states of retrieved knowledge. RAGCache caches re-
trieved knowledge states in a hierarchy to reduce TTFT and improve throughput (Jin et al., 2024).
CacheBlend fuses cached knowledge chunks even when they are not strict prefixes of the input
(Yao et al., 2024), and TurboRAG precomputes KV caches for document chunks to accelerate RAG
prefill (Lu et al., 2025). RAGO studies systematic performance optimization for different RAG
pipelines through a structured RAGSchema abstraction (Jiang et al., 2025). These systems reduce
retrieval-generation latency, especially around prefill, scheduling, and cache reuse. In contrast, KAP
addresses the runtime-consumption side of knowledge-augmented inference: frontend knowledge
priors are compiled into executable access plans so that the backend can selectively consume knowl-
edge rather than uniformly processing the serialized prompt. Unlike pipeline schemas that organize
retrieval and generation components, the runtime access plan is a backend-consumed IR that governs
physical knowledge access during execution.
Prompt compression and long-context usage.Prompt compression methods reduce inference
cost at the input layer by shortening the serialized context before inference. LLMLingua and
LongLLMLingua compress prompts to reduce cost and latency while attempting to preserve task-
relevant information (Jiang et al., 2023; 2024b); Selective Context similarly prunes redundant con-
text for efficiency (Li et al., 2023). These methods are complementary to KAP: they transform the
prompt presented to the model, whereas KAP preserves the logical input and moves selection into
an executable runtime access plan. The distinction matters in long-context and graph-based QA
settings, where models can be sensitive to the position of relevant information (Liu et al., 2024)
and where evidence boundaries, provenance, or graph organization may carry reasoning value (Tu
et al., 2019; Xiong et al., 2021). GraphSpec therefore treats frontend priors not merely as prompt-
construction hints, but as runtime guidance for physical KV consumption.
KV-cache compression and sparse attention.A large body of work reduces the cost of long-
context inference by optimizing attention or compressing KV access. IO-aware kernels such as
FlashAttention reduce attention memory traffic (Dao et al., 2022). H 2O keeps heavy-hitter tokens
in the KV cache (Zhang et al., 2023); StreamingLLM identifies attention sinks for stable streaming
inference (Xiao et al., 2024); SnapKV and PyramidKV compress KV states by selecting impor-
tant tokens or allocating cache across layers (Li et al., 2024a; Cai et al., 2025). Quest performs
query-aware KV-page selection at inference time (Tang et al., 2024), while MInference accelerates
long-context prefill through dynamic sparse attention patterns (Jiang et al., 2024a). These methods
infer token or page importance from model-internal attention or query statistics. KAP instead uses
frontend knowledge priorsas the source of runtime access decisions, and GraphSpec applies sparse
access only to the proposal pass while using full-context verification to guard answer-level quality.
Accordingly, our evaluation isolates this orthogonal systems mechanism rather than providing an
exhaustive ranking of general-purpose KV-cache compression methods.
Speculative and self-speculative decoding.Speculative decoding accelerates generation by draft-
ing candidate tokens with a cheaper path and verifying them with a target model (Leviathan et al.,
2023; Chen et al., 2023). System-oriented extensions such as SpecInfer organize candidates into
token trees for speculative verification (Miao et al., 2024). Subsequent approaches improve draft-
ing through multiple decoding heads, feature-level prediction, early exits, or parallel decoding (Cai
et al., 2024; Li et al., 2024b; Elhoushi et al., 2024; Fu et al., 2024). Long-context variants pursue
several complementary routes: TriForce performs hierarchical speculation with dynamic sparse-KV
retrieval (Sun et al., 2024); RAPID drafts from shortened retrieval contexts (Chen et al., 2025);
QuantSpec uses hierarchically quantized weights and KV states for self-speculation (Tiwari et al.,
15

## PDF Page 16

2025); and LongSpec employs a learned memory-efficient drafter with a constant-sized KV cache
(Yang et al., 2026). GraphSpec adopts selected-KV proposal with full-context verification as one
concrete KAP executor policy. Its distinction lies in how the proposal view is produced: Graph-
RAG priors are compiled into a runtime access plan and a logical-position-preserving selected-KV
view, rather than being materialized as a shortened prompt or inferred solely within the drafting
mechanism.
7 LIMITATIONS
Our evaluation validates KAP through GRAPHSPEC, one concrete instantiation built with a Graph-
RAG knowledge-selection frontend and aVLLM serving backend. Therefore, our empirical evi-
dence does not exhaust the broader design space of runtime knowledge consumption. The reported
results are strongest for long-context QA workloads where graph-derived priors can be grounded in
evidence spans and realized as backend runtime objects. Other KAP instantiations may use differ-
ent frontends, plan compilers, access policies, verification mechanisms, or LLM serving backends,
and their effectiveness will depend on the quality of the knowledge priors, the compiler’s ability
to translate them into useful runtime access plans, and the backend’s ability to execute those plans
without excessive metadata, scheduling, or synchronization overhead. Future KAP instantiations
could realize runtime access plans through alternative sparse-access, tiered-KV, or disaggregated
execution mechanisms. Thus, our results establish KAP as a feasible serving paradigm and identify
a broader design space for future runtime knowledge-consumption systems.
8 CONCLUSION
We identified the knowledge selection–runtime consumption gap as an architectural mismatch in
knowledge-augmented LLM serving: knowledge-selection frontends produce high-value priors
about relevant knowledge, yet conventional LLM serving backends consume only the serialized
prompt and its full KV state. To bridge the gap, we introduced KAP, a paradigm for plan-driven
knowledge execution organized around a universal serving-time IR that compiles structured knowl-
edge priors into physical-access policies while preserving logical prompt semantics. GRAPHSPEC
provides a reference implementation with a Graph-RAG knowledge-selection frontend and aVLLM
serving backend. Our phase-boundary analysis and controlled long-context QA evaluation connect
knowledge selectivity, runtime consumption, and systems efficiency. Beyond GRAPHSPEC, KAP
provides a universal execution substrate for knowledge-selection–execution co-design across mul-
timodal, agentic, and deliberative long-context systems, where semantic knowledge selection and
physical context consumption must be optimized jointly.
REFERENCES
Reza Yazdani Aminabadi, Samyam Rajbhandari, Ammar Ahmad Awan, Cheng Li, Du Li, Elton
Zheng, Olatunji Ruwase, Shaden Smith, Minjia Zhang, Jeff Rasley, and Yuxiong He. Deepspeed-
inference: Enabling efficient inference of transformer models at unprecedented scale. InProceed-
ings of the International Conference for High Performance Computing, Networking, Storage and
Analysis, 2022. URLhttps://doi.org/10.1109/SC41404.2022.00051.
Sebastian Borgeaud, Arthur Mensch, Jordan Hoffmann, Trevor Cai, Eliza Rutherford, Katie Mil-
lican, George Bm Van Den Driessche, Jean-Baptiste Lespiau, Bogdan Damoc, Aidan Clark,
Diego De Las Casas, Aurelia Guy, Jacob Menick, Roman Ring, Tom Hennigan, Saffron Huang,
Loren Maggiore, Chris Jones, Albin Cassirer, Andy Brock, Michela Paganini, Geoffrey Irving,
Oriol Vinyals, Simon Osindero, Karen Simonyan, Jack Rae, Erich Elsen, and Laurent Sifre. Im-
proving language models by retrieving from trillions of tokens. InProceedings of the 39th In-
ternational Conference on Machine Learning, 2022. URLhttps://proceedings.mlr.
press/v162/borgeaud22a.html.
Tianle Cai, Yuhong Li, Zhengyang Geng, Hongwu Peng, Jason D. Lee, Deming Chen, and Tri
Dao. Medusa: Simple llm inference acceleration framework with multiple decoding heads. In
International Conference on Machine Learning, 2024. URLhttps://arxiv.org/abs/
2401.10774.
16

## PDF Page 17

Zefan Cai, Yichi Zhang, Bofei Gao, Yuliang Liu, Yucheng Li, Tianyu Liu, Keming Lu, Wayne
Xiong, Yue Dong, Junjie Hu, and Wen Xiao. Pyramidkv: Dynamic kv cache compression based
on pyramidal information funneling. InConference on Language Modeling, 2025. URLhttps:
//openreview.net/forum?id=ayi7qezU87.
Charlie Chen, Sebastian Borgeaud, Geoffrey Irving, Jean-Baptiste Lespiau, Laurent Sifre, and John
Jumper. Accelerating large language model decoding with speculative sampling.arXiv preprint
arXiv:2302.01318, 2023. URLhttps://arxiv.org/abs/2302.01318.
Guanzheng Chen, Qilong Feng, Jinjie Ni, Xin Li, and Michael Qizhe Shieh. RAPID: Long-context
inference with retrieval-augmented speculative decoding. InProceedings of the 42nd Interna-
tional Conference on Machine Learning, volume 267 ofProceedings of Machine Learning Re-
search, pp. 8093–8107. PMLR, 2025. URLhttps://proceedings.mlr.press/v267/
chen25s.html.
Tri Dao, Dan Fu, Stefano Ermon, Atri Rudra, and Christopher R´e. FlashAttention: Fast and memory-
efficient exact attention with IO-awareness. InAdvances in Neural Information Processing
Systems, 2022. URLhttps://proceedings.neurips.cc/paper_files/paper/
2022/hash/67d57c32e20fd0a7a302cb81d36e40d5-Abstract-Conference.
html.
Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt,
Dasha Metropolitansky, Robert Osazuwa Ness, and Jonathan Larson. From local to global: A
graph rag approach to query-focused summarization.arXiv preprint arXiv:2404.16130, 2024.
URLhttps://arxiv.org/abs/2404.16130.
Mostafa Elhoushi, Akshat Shrivastava, Diana Liskovich, Basil Hosmer, Bram Wasti, Liangzhen
Lai, Anas Mahmoud, Bilge Acun, Saurabh Agarwal, Ahmed Roman, Ahmed Aly, Beidi Chen,
and Carole-Jean Wu. Layerskip: Enabling early exit inference and self-speculative decoding. In
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics, 2024.
URLhttps://aclanthology.org/2024.acl-long.681/.
Yichao Fu, Peter Bailis, Ion Stoica, and Hao Zhang. Break the sequential dependency of llm infer-
ence using lookahead decoding. InProceedings of the 41st International Conference on Machine
Learning, 2024. URLhttps://arxiv.org/abs/2402.02057.
Kelvin Guu, Kenton Lee, Zora Tung, Panupong Pasupat, and Ming-Wei Chang. REALM: Retrieval-
augmented language model pre-training. InProceedings of the 37th International Conference on
Machine Learning, 2020. URLhttps://proceedings.mlr.press/v119/guu20a.
html.
Gautier Izacard and Edouard Grave. Leveraging passage retrieval with generative models for open
domain question answering. InProceedings of the 16th Conference of the European Chap-
ter of the Association for Computational Linguistics: Main V olume, 2021. URLhttps:
//aclanthology.org/2021.eacl-main.74/.
Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, and Lili Qiu. Llmlingua: Com-
pressing prompts for accelerated inference of large language models. InProceedings of the
2023 Conference on Empirical Methods in Natural Language Processing, 2023. URLhttps:
//aclanthology.org/2023.emnlp-main.825/.
Huiqiang Jiang, Yucheng Li, Chengruidong Zhang, Qianhui Wu, Xufang Luo, Surin Ahn, Zhenhua
Han, Amir H. Abdi, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, and Lili Qiu. Minference 1.0:
Accelerating pre-filling for long-context llms via dynamic sparse attention. InAdvances in Neural
Information Processing Systems, 2024a. URLhttps://arxiv.org/abs/2407.02490.
Huiqiang Jiang, Qianhui Wu, Xufang Luo, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, and Lili
Qiu. Longllmlingua: Accelerating and enhancing llms in long context scenarios via prompt com-
pression. InProceedings of the 62nd Annual Meeting of the Association for Computational Lin-
guistics, 2024b. URLhttps://aclanthology.org/2024.acl-long.91/.
17

## PDF Page 18

Wenqi Jiang, Suvinay Subramanian, Cat Graves, Gustavo Alonso, Amir Yazdanbakhsh, and Vidushi
Dadu. Rago: Systematic performance optimization for retrieval-augmented generation serving.
InProceedings of the 52nd Annual International Symposium on Computer Architecture, 2025.
URLhttps://arxiv.org/abs/2503.14649.
Bernal Jimenez Gutierrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, and Yu Su. Hipporag: Neu-
robiologically inspired long-term memory for large language models. InAdvances in Neural
Information Processing Systems, 2024. URLhttps://arxiv.org/abs/2405.14831.
Chao Jin, Zili Zhang, Xuanlin Jiang, Fangyue Liu, Xin Liu, Xuanzhe Liu, and Xin Jin.
Ragcache: Efficient knowledge caching for retrieval-augmented generation.arXiv preprint
arXiv:2404.12457, 2024. URLhttps://arxiv.org/abs/2404.12457.
Vladimir Karpukhin, Barlas O ˘guz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi
Chen, and Wen-tau Yih. Dense passage retrieval for open-domain question answering. InPro-
ceedings of the 2020 Conference on Empirical Methods in Natural Language Processing, 2020.
URLhttps://aclanthology.org/2020.emnlp-main.550/.
Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph
Gonzalez, Hao Zhang, and Ion Stoica. Efficient memory management for large language model
serving with pagedattention. InProceedings of the 29th Symposium on Operating Systems Prin-
ciples, 2023. URLhttps://doi.org/10.1145/3600006.3613165.
Yaniv Leviathan, Matan Kalman, and Yossi Matias. Fast inference from transformers via spec-
ulative decoding. InInternational Conference on Machine Learning, 2023. URLhttps:
//proceedings.mlr.press/v202/leviathan23a.html.
Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal,
Heinrich K ¨uttler, Mike Lewis, Wen-tau Yih, Tim Rockt ¨aschel, Sebastian Riedel, and Douwe
Kiela. Retrieval-augmented generation for knowledge-intensive nlp tasks. InAdvances in Neural
Information Processing Systems, 2020. URLhttps://arxiv.org/abs/2005.11401.
Yucheng Li, Bo Dong, Frank Guerin, and Chenghua Lin. Compressing context to enhance inference
efficiency of large language models. InProceedings of the 2023 Conference on Empirical Meth-
ods in Natural Language Processing, 2023. URLhttps://aclanthology.org/2023.
emnlp-main.391/.
Yuhong Li, Yingbing Huang, Bowen Yang, Bharat Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle
Cai, Patrick Lewis, and Deming Chen. Snapkv: Llm knows what you are looking for before
generation. InAdvances in Neural Information Processing Systems, 2024a. URLhttps://
arxiv.org/abs/2404.14469.
Yuhui Li, Fangyun Wei, Chao Zhang, and Hongyang Zhang. Eagle: Speculative sampling requires
rethinking feature uncertainty. InInternational Conference on Machine Learning, 2024b. URL
https://arxiv.org/abs/2401.15077.
Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, and
Percy Liang. Lost in the middle: How language models use long contexts.Transactions of
the Association for Computational Linguistics, 2024. URLhttps://aclanthology.org/
2024.tacl-1.9/.
Songshuo Lu, Hua Wang, Yutian Rong, Zhi Chen, and Yaohua Tang. Turborag: Accelerating
retrieval-augmented generation with precomputed kv caches for chunked text. InProceedings
of the 2025 Conference on Empirical Methods in Natural Language Processing, 2025. URL
https://aclanthology.org/2025.emnlp-main.334/.
Xupeng Miao, Gabriele Oliaro, Zhihao Zhang, Xinhao Cheng, Zeyu Wang, Zhengxin Zhang, Rae
Ying Yee Wong, Alan Zhu, Lijie Yang, Xiaoxiang Shi, Chunan Shi, Zhuoming Chen, Daiyaan Ar-
feen, Reyna Abhyankar, and Zhihao Jia. Specinfer: Accelerating generative large language model
serving with tree-based speculative inference and verification. InProceedings of the 29th ACM
International Conference on Architectural Support for Programming Languages and Operating
Systems, 2024. URLhttps://dl.acm.org/doi/10.1145/3620666.3651335.
18

## PDF Page 19

Reiner Pope, Sholto Douglas, Aakanksha Chowdhery, Jacob Devlin, James Bradbury, Anselm
Levskaya, Jonathan Heek, Kefan Xiao, Shivani Agrawal, and Jeff Dean. Efficiently scal-
ing transformer inference. InProceedings of Machine Learning and Systems, 2023. URL
https://arxiv.org/abs/2211.05102.
Ying Sheng, Lianmin Zheng, Binhang Yuan, Zhuohan Li, Max Ryabinin, Beidi Chen, Percy Liang,
Christopher Re, Ion Stoica, and Ce Zhang. Flexgen: High-throughput generative inference
of large language models with a single gpu. InProceedings of the 40th International Con-
ference on Machine Learning, 2023. URLhttps://proceedings.mlr.press/v202/
sheng23a.html.
Jianlin Su, Murtadha Ahmed, Yu Lu, Shengfeng Pan, Wen Bo, and Yunfeng Liu. Roformer: En-
hanced transformer with rotary position embedding.Neurocomputing, 2024. URLhttps:
//doi.org/10.1016/j.neucom.2023.127063.
Hanshi Sun, Zhuoming Chen, Xinyu Yang, Yuandong Tian, and Beidi Chen. Triforce: Lossless
acceleration of long sequence generation with hierarchical speculative decoding.arXiv preprint
arXiv:2404.11912, 2024. URLhttps://arxiv.org/abs/2404.11912.
Jiaming Tang, Yilong Zhao, Kan Zhu, Guangxuan Xiao, Baris Kasikci, and Song Han. Quest:
Query-aware sparsity for efficient long-context llm inference. InInternational Conference on
Machine Learning, 2024. URLhttps://arxiv.org/abs/2406.10774.
Rishabh Tiwari, Haocheng Xi, Aditya Tomar, Coleman Richard Charles Hooper, Sehoon Kim,
Maxwell Horton, Mahyar Najibi, Michael W. Mahoney, Kurt Keutzer, and Amir Gholami.
QuantSpec: Self-speculative decoding with hierarchical quantized KV cache. InProceedings
of the 42nd International Conference on Machine Learning, volume 267 ofProceedings of Ma-
chine Learning Research, pp. 59668–59686. PMLR, 2025. URLhttps://proceedings.
mlr.press/v267/tiwari25b.html.
Ming Tu, Guangtao Wang, Jing Huang, Yun Tang, Xiaodong He, and Bowen Zhou. Multi-hop
reading comprehension across multiple documents by reasoning over heterogeneous graphs. In
Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics, 2019.
URLhttps://aclanthology.org/P19-1260/.
Guangxuan Xiao, Yuandong Tian, Beidi Chen, Song Han, and Mike Lewis. Efficient streaming
language models with attention sinks. InInternational Conference on Learning Representations,
2024. URLhttps://arxiv.org/abs/2309.17453.
Wenhan Xiong, Xiang Li, Srini Iyer, Jingfei Du, Patrick Lewis, William Yang Wang, Yashar
Mehdad, Scott Yih, Sebastian Riedel, Douwe Kiela, and Barlas Oguz. Answering complex open-
domain questions with multi-hop dense retrieval. InInternational Conference on Learning Rep-
resentations, 2021. URLhttps://openreview.net/forum?id=EMHoBG0avc1.
Penghui Yang, Cunxiao Du, Fengzhuo Zhang, Haonan Wang, Tianyu Pang, Chao Du, and Bo An.
LongSpec: Long-context lossless speculative decoding with efficient drafting and verification.
InProceedings of the 64th Annual Meeting of the Association for Computational Linguistics
(V olume 1: Long Papers), pp. 1826–1844. Association for Computational Linguistics, 2026. doi:
10.18653/v1/2026.acl-long.83. URLhttps://aclanthology.org/2026.acl-long.
83/.
Jiayi Yao, Hanchen Li, Yuhan Liu, Siddhant Ray, Yihua Cheng, Qizheng Zhang, Kuntai Du, Shan
Lu, and Junchen Jiang. Cacheblend: Fast large language model serving for rag with cached
knowledge fusion.arXiv preprint arXiv:2405.16444, 2024. URLhttps://arxiv.org/
abs/2405.16444.
Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, and Byung-Gon Chun. Orca: A
distributed serving system for transformer-based generative models. In16th USENIX Symposium
on Operating Systems Design and Implementation, 2022. URLhttps://www.usenix.org/
conference/osdi22/presentation/yu.
19

## PDF Page 20

Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong Chen, Lianmin Zheng, Ruisi Cai, Zhao Song,
Yuandong Tian, Christopher R´e, Clark Barrett, Zhangyang Wang, and Beidi Chen. H 2o: Heavy-
hitter oracle for efficient generative inference of large language models. InAdvances in Neural
Information Processing Systems, 2023. URLhttps://arxiv.org/abs/2306.14048.
Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff Huang, Cody Hao Yu, Shiyi Cao,
Christos Kozyrakis, Ion Stoica, Joseph E. Gonzalez, Clark Barrett, and Ying Sheng. SGLang:
Efficient execution of structured language model programs. InAdvances in Neural Information
Processing Systems, 2024. URLhttps://arxiv.org/abs/2312.07104.
20