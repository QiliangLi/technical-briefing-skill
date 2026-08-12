hat combines vector retrieval, reranking,
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