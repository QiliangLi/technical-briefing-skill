# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

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
ture already resolved upstream.

## Evidence locator: PDF Page 14

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

## Evidence locator: PDF Page 15

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
retrieval-generation latency, especially around prefill, scheduling, and cache reuse.

## Evidence locator: PDF Page 12

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

## Evidence locator: PDF Page 13

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

## Evidence locator: PDF Page 16

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
knowledge selectivity, runtime consumption, and systems efficiency.