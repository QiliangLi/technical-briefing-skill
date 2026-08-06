## PDF Page 1

AiFlow: Token-Native Reactive Orchestration with Bounded
Backpressure for Streaming LLM Applications
Qunhui Zhanga
aSchool of Software, Shanghai Jiao Tong University, Shanghai 200240, China
Abstract
Large language model (LLM) applications increasingly operate as streaming workflows com-
bining retrieval, tool calls, safety filters, and multi-agent coordination. Although contem-
porary frameworks expose provider deltas, workflow nodes often treat generation as coarse
request–response steps, leaving queue management, worker allocation, ordering, and back-
pressure to ad hoc callback code. This paper presentsAiFlow, a token-native reactive or-
chestration model that normalizes provider deltas into typedContext<T>events propagated
throughadirectedstreaminggraph. EachnodeismanagedbyaNode Guardianthatdeclares
and enforces local queue bounds, worker concurrency, ordering, overflow policy, cancellation
propagation, and retry discipline. We formalize the bounded-memory property, present the
compilation from a compact DSL and JSON graph form, and provide static validation for
type safety, state concurrency, and injection compatibility. Controlled microbenchmarks,
captured DeepSeek trace replay (30 runs), descriptive online runs, LangGraph baselines,
a streaming RAG workload, and an Ollama local-backend check show thatAiFlowdoes
not alter provider-side Model TTFT but reduces Application TTFPT by 70.9–94.7% ver-
sus aggregation and keeps runtime-owned queue depth within declared bounds (93.7–96.5%
MaxQ reduction versus unbounded policies). The supplementary artifact contains scripts,
raw traces, machine-readable tables, checksums, and an API-free smoke test; the public
implementation is available through the FIT Framework repository.
Keywords:large language model applications, streaming orchestration, reactive streams,
bounded backpressure, dataflow runtime, workflow DSL, software engineering
Highlights
•Token-native orchestration model where LLM deltas become typed graph events.
•Node Guardian runtime with declarative queues, workers, ordering, and backpressure.
•Formal bounded-memory proposition and static graph validation.
•Separation of Model TTFT from Application TTFPT with paired trace-replay evalu-
ation.
Email address:will_zhang@sjtu.edu.cn(Qunhui Zhang)
arXiv:2608.00558v1  [cs.SE]  1 Aug 2026

## PDF Page 2

•Captured-trace replay, DeepSeek/Ollama runs, and LangGraph baselines with effect
sizes and confidence intervals.
1. Introduction
StreaminghasbecomethedefaultinteractionmodeforLLMapplications(OpenAI,2026).
Chat interfaces render partial answers before generation completes; retrieval-augmented gen-
eration (RAG) pipelines start checking citations while later chunks arrive; tool-calling agents
inspect incremental arguments; safety filters delay or redact generated fragments; text-to-
speech (TTS) systems route short text segments immediately; and users may interrupt a
long answer while the workflow is still running. In these settings,printing provider tokens
to a user interfaceis not the same asmaking tokens first-class data inside the application
graph.
Motivating Example
Consider a production streaming assistant that must classify each generated token as
“reasoning” or “answer,” route reasoning tokens to a chain-of-thought logger, route answer
tokens through a desensitization filter and then to TTS, and allow the user to interrupt mid-
generation. With existing frameworks, a developer must: (1) register a callback on the model
stream, (2) implement a thread-safe queue between the classifier and downstream branches,
(3) allocate a worker pool for the TTS node (whose service time is 5–10×longer than
classification), (4) add manual cancellation wiring when the user interrupts, and (5) monitor
queue growth manually to avoid memory exhaustion. If any of these mechanisms contain
a bug, the system silently accumulates unbounded buffers, reorders tokens, or drops the
interruption event.AiFlowreplaces this ad hoc wiring with a single graph declaration in
which each node’s queue bound, worker count, ordering, overflow, and cancellation policy is
specified at the graph level and enforced by the runtime.
Problem and Contributions
Existing LLM application frameworks—LangChain, LangGraph, LlamaIndex, Seman-
tic Kernel, DSPy, and AutoGen (LangChain, 2026a,b; LlamaIndex, 2026; Microsoft, 2026;
Khattab et al., 2023; Wu et al., 2023)—have made major progress in task composition, tool
integration, state management, and agent collaboration. They also expose streaming out-
puts through callbacks, iterators, events, or state patches. However, thelocal execution policy
that connects streamed model deltas to downstream retrieval, tool, safety, TTS, memory, or
observability nodes remains largely implemented in user code. Queue capacity, worker con-
currency, ordering, cancellation, retry, and backpressure are hidden in callbacks and ad hoc
asynchronous wiring, making the resulting application graph harder to validate, compare,
and tune.
Reactive streams and dataflow systems provide mature concepts for asynchronous, po-
tentially unbounded data exchange (Elliott and Hudak, 1997; Dennis and Misunas, 1974;
Reactive Streams, 2026; Nurkiewicz and Christensen, 2016; Roestenburg et al., 2016; Akidau
et al., 2015; Apache Beam, 2026; Confluent, 2026): bounded queues, backpressure signal-
ing, windowing, and demand management.AiFlowdoes not claim to invent these lower-
level concurrency mechanisms. Its contribution is tospecializethem for the semantics and
2

## PDF Page 3

engineering requirements of LLM applications, where provider deltas, prompt fragments,
retrieval results, tool events, TTS segments, safety labels, user interruptions, and control
signals become typed graph events, and node-level resource and state-safety policies become
declarative graph properties.
This paper makes four contributions:
1. Atoken-nativeorchestrationmodelthatrepresentsLLMdeltasandcontrolsignals
as typedContext<T>events in a directed streaming graph (Section 4).
2. Acompact DSL and JSON graph formwhose compilation enables static checks
for type safety, state concurrency, cycle legality, and injection compatibility (Section 4).
3. TheNode Guardian runtime abstractionwith a formal bounded-memory propo-
sition for runtime-owned buffers (Section 5).
4. Amulti-level empirical evaluationcomprising controlled benchmarks, ablations,
captured-provider trace replay, descriptive online/framework checks, a streaming RAG
workload, and a local-backend sanity check, with explicit separation of Model TTFT
and Application TTFPT (Section 7).
Wedeliberatelynarrowtheperformanceclaim.AiFlowisanapplication-layerorchestra-
tion model; it does not optimize transformer serving, KV-cache management, GPU batching,
or provider-side scheduling. The evaluation accordingly distinguishesModel TTFT(time un-
til the first provider delta arrives) fromApplication TTFPT(time until the first token has
passed through a specified downstream application stage).
2. Background and Problem Definition
A streaming LLM application graph consists of model, retrieval, tool, safety, memory,
TTS, and output nodes connected by potentially asynchronous edges. The central prob-
lem is:how can token-level events be consumed continuously by downstream nodes without
materializing every intermediate result as a complete response, while keeping node-local re-
sources bounded, output ordering controllable, state access safe, and slow-consumer pressure
observable and propagatable?
2.1. Formal Graph Model
Definition 1(Streaming Application Graph).A streaming LLM application is modeled as
a directed graphG= (N, E, π, τ)where:
•Nis a finite set of operator nodes.
•E⊆N×Nis the set of directed edges.
•π:N→ Pmaps each node to a policy tuple:
P= (q, k, ρ, σ, o, c, r).
The tuple specifies queue capacityq, worker countk, ordering-buffer boundρ, state-
safety modeσ, overflow behavioro, cancellation propagationc, and retry policyr,
where:
σ∈ {stateless,partitioned,serialized,transactional},
o∈ {block,drop-newest,drop-oldest,error}.
3

## PDF Page 4

•τ:E→ Tis a type map assigning a compatible event type to each edge.
Definition 2(Context Event).An evente= (payload, t,cid,src,seq,ctrl,meta)consists of
a typed payload (token, chunk, tool fragment, retrieval result, safety label, or control signal),
a timestampt, conversation identifiercid, source node identifiersrc, source-local sequence
numberseq, optional control signalctrl, and metadata mapmeta.
2.2. Research Questions
The paper addresses seven research questions:
RQ1Does token-level semantic routing reduce Application TTFPT after downstream pro-
cessing?
RQ2Does node-level backpressure limit queue growth under slow consumers?
RQ3Do declarative worker policies improve batch completion under concurrent prompts?
RQ4How do routing, workers, queue capacity, ordering, and backpressure independently
affect latency and memory?
RQ5Do conclusions hold under real provider chunk timing and online backends?
RQ6How doesAiFlowcompare with LangGraph streaming baselines?
RQ7DoesacompletestreamingRAGworkflowexhibitthesameapplication-layerbehavior?
3. Related Work
3.1. LLM Application Frameworks and Orchestration
LLM application research has evolved from isolated prompting toward tool use, re-
trieval, agents, and programmatic pipelines. The Transformer architecture (Vaswani et al.,
2017) enabled large-scale pre-trained models (Brown et al., 2020) and instruction-tuned vari-
ants (Ouyang et al., 2022). Chain-of-thought prompting (Wei et al., 2022) elicits multi-step
reasoning; ReAct(Yaoet al., 2023)combines reasoning withacting; Toolformer(Schick etal.,
2023)learnstoolusefromlanguagemodelingsignals; RAG(Lewisetal.,2020)groundsgener-
ationinretrievedpassages; comprehensivesurveys (Gaoet al.,2023) organize theseadvances;
DSPy (Khattab et al., 2023) compiles declarative language model calls into self-improving
pipelines; and AutoGen (Wu et al., 2023) studies multi-agent conversation patterns.
Orchestration frameworks have emerged to manage these compositions. LangChain and
LangGraph (LangChain, 2026a,b) provide chain abstractions, state graphs, and stream-
ing callbacks. LlamaIndex (LlamaIndex, 2026) focuses on retrieval workflow composition.
Semantic Kernel (Microsoft, 2026) integrates planning and orchestration within enterprise
.NET/Python environments. These frameworks expose streaming tokens to application code
via callbacks, iterators, or state events, but they do not providegraph-level declarationsfor
queue capacity, worker concurrency, ordering policies, backpressure behavior, and cancella-
tion semantics. Developers must implement these properties manually in callback-local code,
which hinders systematic validation, comparison, and operational observability.
4

## PDF Page 5

A recent empirical study by Chen et al. (Chen et al., 2025) identifies reliability, latency,
and debugging complexity as persistent challenges for LLM application developers. The
lack of explicit orchestration policies at the workflow level contributes to these difficulties,
particularly when multiple streaming operators interact through implicit shared state or
unbounded buffering.
3.2. Reactive Streams and Dataflow Systems
Reactive programming originates in functional reactive animation (Elliott and Hudak,
1997) and data-flow architectures (Dennis and Misunas, 1974). The Reactive Streams specifi-
cation (Reactive Streams, 2026) standardizes asynchronous streams with non-blocking back-
pressure. Implementations such as RxJava (Nurkiewicz and Christensen, 2016), Reactor,
and Akka Streams (Roestenburg et al., 2016) provide composable operators, schedulers, and
bounded demand management. At the batch-processing level, MapReduce (Dean and Ghe-
mawat, 2004) introduced the paradigm of declarative parallel data transformations; building
on similar principles, Apache Beam (Apache Beam, 2026) and Kafka Streams (Confluent,
2026)extend theseideas todistributed, unboundeddata processingwith windowing, triggers,
andexactly-oncesemantics. TheDataflowmodel(Akidauetal.,2015)formalizescorrectness,
latency, and cost trade-offs for massive-scale stream processing. Apache Spark Structured
Streaming (Armbrust et al., 2018) provides a declarative API for real-time applications.
AiFlowbuilds on this lineage but specializes the event model, operator vocabulary,
validationchecks, injectionprotocol, andmetricstothesemanticsofLLMapplicationgraphs.
The key distinction is not the underlying concurrency primitives (which are well-known),
but theintegrationof these primitives with LLM-specific event types, graph validation rules,
side-effect declarations, token-level routing, and application-level observability.
3.3. Workflow Engines and Model Serving
Workflow engines such as Apache Airflow (Apache Airflow, 2026) and Temporal (Tem-
poral, 2026) focus on durable task orchestration with retries, timeouts, and operational
visibility at the task granularity. Container orchestration platforms (Burns et al., 2016)
manage deployment, scaling, and resource allocation for distributed services but operate at
the infrastructure level rather than at intra-application data-flow granularity. These systems
all operate at a coarser scheduling level than token-by-token streaming and do not expose
intra-task backpressure or bounded queues.
LLM serving systems such as Orca (Yu et al., 2022) and vLLM (Kwon et al., 2023) opti-
mize transformer inference through continuous batching, PagedAttention memory manage-
ment, and multi-tenant GPU scheduling. These systems arecomplementaryto application-
layer orchestration:AiFlowconsumes their streamed outputs and governs how those tokens
move through application-layer nodes, without claiming to improve the serving system itself.
3.4. Positioning Summary
Table 1 positionsAiFlowrelative to the categories above. The novelty lies not in
inventing new concurrency primitives, but in providing atyped, validated, and observable
orchestration layerthat makes token-level streaming behavior, resource policy, and bounded
backpressure explicit properties of the LLM application graph rather than implicit callback-
local implementation details.
5

## PDF Page 6

Table 1: Positioning ofAiFlowrelative to related system categories.
Category Token-level events Declared queue/worker policy Static graph validation Graph-declared backpressure LLM-native DSL
LLM frameworks (LangChain, LangGraph, etc.) Partial (callbacks) Callback-local Limited Limited Partial
Reactive libraries (RxJava, Akka Streams) Yes (generic) Yes (generic) Limited Yes No
Stream processors (Beam, Kafka Streams) Yes (generic) Yes (distributed) Partial Yes No
Workflow engines (Airflow, Temporal) No Task-level Partial No No
Model serving (vLLM, Orca) No (internal) Internal Internal Internal No
AiFlowYes (LLM-typed) Yes (node-level) Yes Yes Yes
4. Token-Native AiFlow Model
AiFlowprovides both a fluent API and a JSON graph representation. Both forms
compile into the same typed streaming graph (Figure 2 shows the overall compilation and
runtime architecture). Core operators includesource,prompt,generate,retrieve,map,
reduce,conditions,delegate,split,join, andsink. Resource policies can be attached
locally to operators. This choice makes streaming behavior and resource control part of the
graph definition rather than external callback wiring.
4.1. DSL and Graph Compilation
Listing 1 shows the fluent DSL for the motivating streaming semantic routing workflow
introduced in Section 1. The DSL compiles into a typed intermediate graph representation
that undergoes validation before execution.
1Flow < ConversationContext > flow = AiFlow . create ()
2. source ( " user - input " )
3. generate ( " llm " , model ( " deepseek - chat " ) )
4. policy ( Policy . queue (8) . workers (1) . order ( PRESERVE ) )
5. map ( " classify " , T o k e n C l a s s i f i e r :: classify )
6. policy ( Policy . queue (8) . workers (1) )
7. conditions ( " route " )
8. when ( ctx -> ctx . label () . equals ( " reasoning " ) , " reason -
branch " )
9. when ( ctx -> ctx . label () . equals ( " answer " ) , " answer - branch "
)
10. node ( " reason - branch " )
11. map ( " reasoning " , R e a s o n i n g P r o c e s s o r :: process )
12. policy ( Policy . queue (8) . workers (2) . order ( PRESERVE ) )
13. node ( " answer - branch " )
14. map ( " tts - prep " , T t s S e g m e n t e r :: segment )
15. policy ( Policy . queue (8) . workers (1) . overflow ( BLOCK )
16. b a c k p r e s s u r e ( PROPAGATE ) )
17. join ( " merge - output " )
18. sink ( " output " , OutputSink :: emit ) ;
Listing 1: Fluent DSL for a semantic routing workflow with bounded backpressure.
The corresponding JSON graph form (suitable for configuration-driven or language-
agnostic deployments) maps each node to a JSON object with type, policy, and edge decla-
rations. The compiler verifies type compatibility on edges, validates policy consistency, and
rejects illegal configurations before graph instantiation.
6

## PDF Page 7

4.2. Token-Level Routing Timeline
Figure 1 illustrates the token-level semantic routing enabled by the DSL graph above.
Because classification overlaps with generation and routes each token immediately, the rea-
soning and answer branches can begin processing before the complete model response is
available. This is the mechanism that reduces Application TTFPT compared with aggrega-
tion baselines.
time
0 ms 100 ms 200 ms 300 ms 400 ms 500 ms 600 ms
Generate
Classify
Reasoning branch
Answer branch
c1
c1
c2
c2
c3
c3
c4
c4
c5
c5
c1 c2
c3 c4 c5
Figure 1: Token-level semantic routing timeline for the motivating workflow.
Classification overlaps with generation, and downstream branches receive their first pro-
cessed token before the model stream ends. This illustrates the mechanism behind the
TTFPT improvement measured in RQ1 (Section 8).
4.3. Node-Directed Injection
A long-running graph can receive external input through two mechanisms:
•offer(value): injects a new event at the graph source.
•offer(nodeId, value): delivers a typed event directly to a target node’s input queue.
This supports user feedback, tool return values, retrieval updates, and external control events
without rebuilding the flow. The compiler validates that the injected event type matches
the target node’s declared input type.
4.4. Static Validation
The compiler performs six categories of static checks before graph instantiation. Table 2
summarizes the validation rules and their compile-time responses.
Table 2: Compile-time validation rules.
Error class Compile-time response Rationale
Unknown node id inoffer(nodeId, value)Reject; report candidate node identifiers. Prevents runtime dispatch failures.
Incompatible edge type Reject unless an explicit adapter is declared. Ensures type safety between operators.
Non-streaming operator on a streaming boundary Require an explicitreduceor window boundary. Prevents implicit materialization.
Cycle without feedback policy Reject or require explicit feedback policy. Avoids unbounded loop accumulation.
Shared-state operator with workers>1Require stateless, partitioned, serialized, or transactional mode. Ensures state-safety under concurrency.
Injection type mismatch Reject before admission to target queue. Prevents ClassCastException at runtime.
The upper path shows DSL/JSON compilation into a typed graph; the lower path shows
runtime execution with Node Guardians managing bounded queues (Q) and metrics collec-
tion. Dashed arrows indicate node-directed injection from external events.
7

## PDF Page 8

Fluent API
JSON graph
DSL compiler
and verifier
Typed streaming
graph
Model
stream
User/tool
events
Generate
Guardian
Map/route
Guardian
TTS/tool
Guardian
Output
sink
Metrics
queue depth
drops
Q Q Q
Waterflow runtime
Figure 2:AiFlowcompilation and runtime architecture.
5. Node Guardian Runtime
A Node Guardian is the runtime object associated with one graph node. It owns the
node’s input queue, local worker budget, optional ordering buffer, cancellation state, retry
metadata, side-effect mode, and metrics counters. Figure 3 shows the internal structure;
Algorithm 1 specifies the admission and dispatch logic.
5.1. Bounded-Memory Proposition
Proposition 1(Runtime-Owned Buffer Bound).LetQ n be the bounded input queue of node
n,q n its capacity,kn its worker count,ρn the upper bound of its ordering buffer,be the bound
of explicit edge buffere, andm s the bound of explicit window or reduce states. Under
finite external arrival rate, fixed worker counts, bounded runtime-owned queues, bounded
edge buffers, bounded ordering buffers, and overflow policies that do not allocate unbounded
temporary storage, the number of in-flight events directly owned by the runtime is bounded
by:
Bruntime ≤
X
n∈N
(qn +k n +ρ n) +
X
e∈E
be +
X
s∈S
ms
Proof sketch.Each nodenholds at mostq n events in its input queue,kn events being pro-
cessed by active workers, andρ n events in the ordering buffer awaiting sequence-ordered
release. Each declared edge buffereholds at mostb e events. Each declared window or re-
duce statesholds at mostm s intermediate values. Since overflow policies (Block,Drop-
Newest,DropOldest,Error) all prevent the queue from exceedingqn, and worker and
ordering buffer counts are fixed, the sum is bounded. The bound is constructive: it can be
computed from the graph policy declarations at compile time.
This proposition intentionally excludes provider-side buffers, operating-system network
buffers, and external sink internals. For in-process publishers that implement a demand
8

## PDF Page 9

Algorithm 1Node Guardian admission and dispatch.
Require:Nodenwith policy(q n, kn, ρn, σn, on, cn, rn)
Require:Input queueQ n with capacityq n
Require:Active worker countactive n ≤k n
1:ProcedureAdmit(evente):
2:if|Q n| ≥q n then
3:ifo n =Blockthen
4:Signal backpressure to upstream; wait until|Q n|< q n
5:else ifo n =DropNewestthen
6:Discarde; incrementdrops n
7:else ifo n =DropOldestthen
8:Dequeue oldest fromQ n; incrementdrops n; enqueuee
9:else ifo n =Errorthen
10:Rejecte; incrementerrors n; propagate error upstream
11:end if
12:else
13:EnqueueeintoQ n with timestampt admit
14:end if
15:
16:ProcedureDispatch():
17:whileQ n ̸=∅andactive n < k n do
18:e←dequeue fromQ n
19:active n ←active n + 1
20:Recordwait e ←now−t admit(e)
21:Execute node operator one(respectingσ n state-safety mode)
22:ifρ n >0then
23:Hold result in ordering buffer until sequence-ordered release
24:end if
25:Emit result to downstream edges
26:active n ←active n −1
27:end while
9

## PDF Page 10

protocol, backpressure can be propagated precisely. For cloud model APIs,AiFlowcan
slow local reading, stop downstream distribution, or cancel a request when the provider
supports cancellation, but it cannot force a remote provider to un-generate tokens already
produced.
5.2. Side-Effect Management
Side-effecting nodes (tool calls, retrieval, TTS, memory writes) declare an effect mode.
This is related to transaction-processing concerns (Bernstein and Newcomer, 2009) but
scoped to application-layer event orchestration:
•Idempotent: may be retried with a key derived from (conversation id, node id, in-
put sequence).
•Non-idempotent: fails fast unless a compensation strategy is provided.
•Speculative: output is buffered locally until confirmed (useful for safety-filter scenar-
ios where a harmful pattern may span multiple tokens).
Upstream Q n
w 1
w 2
w k
Ordering
buffer Downstream
backpressure signal
(queue full)
Node Guardian
Figure 3: Node Guardian internal execution structure.
The input queueQn has declared capacityqn; at mostkworkers process events concur-
rently; an ordering buffer restores sequence when needed; backpressure propagates upstream
when|Q n|=q n. This per-node structure is instantiated from graph policy declarations
(Algorithm 1).
6. Implementation and Industrial Context
The evaluation prototype follows a two-layer design. The upper layer draws on enter-
prise integration patterns (Hohpe and Woolf, 2003) and data-intensive application archi-
tecture (Kleppmann, 2017); the lower layer is informed by stream-processing foundations
including Aurora (Abadi et al., 2003), Structured Streaming (Armbrust et al., 2018), Flume-
Java (Chambers et al., 2010), Kafka (Kreps et al., 2011), and Ray (Moritz et al., 2018). The
architectural separation between a domain-specific expression layer and a general-purpose
execution layer follows database system architecture principles (Hellerstein et al., 2007),
where query language and execution engine are decoupled to allow independent evolution:
10

## PDF Page 11

•FEL layer(Flow Expression Language): Registers LLM-oriented operators—prompt,
generate,retrieve,conditions,reduce,delegate—and compiles the fluent API
and JSON graph into a typed intermediate representation.
•Waterflow layer: Implements typed event transport, bounded queues, local schedul-
ing, ordering, cancellation, backpressure propagation, and node-level metrics. Each
Node Guardian is instantiated from the compiled graph’s policy declarations.
The prototype is implemented in Java (OpenJDK 21) on a Linux x86-64 host. The
bounded queues useArrayBlockingQueuewith configurable capacity. Worker dispatch uses
a node-localExecutorServicewith fixed thread pool sizekn. Ordering buffers use a priority
queue keyed by source sequence number with bounded capacityρn. Metrics (queue depth,
wait time, service time, retry count, drop count, error count) are recorded per-node using
lock-free atomic counters.
6.1. Design Requirements
Table 3 traces the design requirements that motivateAiFlow’s mechanisms and shows
how each is addressed.
Table 3: Design requirements for streaming LLM applications andAiFlowmechanisms.
Requirement Engineering manifestationAiFlowmechanism
Token-level computation Classification, desensitization, TTS, and
safety nodes should start before a full an-
swer is generated.
Provider deltas normalized into
Context<T>events and propagated
immediately.
LLM-native semantics Prompts, retrieval results, tool fragments,
TTS segments, and session state require
different handling.
FEL provides typed operators:prompt,
generate,retrieve,conditions,
delegate.
Node-level resource con-
trol
Nodes differ in service time; slow nodes
cause queue growth.
Node Guardians declare and enforce local
workers, queuebounds, ordering, andover-
flow policy.
Multi-source injection Long-running conversations receive human
feedback, tool returns, retrieval results,
and control events.
offer(value)andoffer(nodeId, value)
inject typed events at validated targets.
Static graph validation Callback wiring makes type, state-
concurrency, and boundary issues hard to
check.
Compiler validates types, state safety, cy-
cles, and injection compatibility.
Operational observabil-
ity
Production debugging requires per-node
queue depth, wait time, drop, and error
metrics.
Node Guardians expose atomic counters
queryable at runtime.
6.2. Public Repository and Industrial Context
The associated public implementation path is the FIT Framework repository main-
tained by ModelEngine-Group (ModelEngine-Group, 2026). The observed revision is commit
e2f285don 11 May 2026, recorded in Supplementary Material S1. The open repository pro-
vides a public anchor for inspection and future integration, while the paper’s empirical claims
rely on the reproducible prototype and experiment package supplied with the manuscript.
TheAiFlowlogic has also informed Huawei commercial LLM application workflows;
because those deployments contain proprietary systems and business data, this manuscript
treats them as industrial motivation and implementation context rather than as confidential
performance evidence.
11

## PDF Page 12

7. Evaluation Design
Following established empirical software-engineering guidance (Wohlin et al., 2012), con-
trolled experiments isolate mechanism-level effects before broadening the environment. The
evaluation design applies five complementary evidence levels to ensure coverage:
1.Controlled microbenchmarks: Deterministic streaming stub (first delta at 100ms,
subsequenttokensevery100ms). Makesorchestrationeffectsobservablewithoutcloud-
provider variability.
2.Ablation: Systematically removes or varies individual policy dimensions.
3.Captured trace replay: 30-run DeepSeek traces replayed under different policies.
Same chunk arrival sequence ensures paired comparison.
4.Online experiments: Live DeepSeek and Ollama calls with real network conditions.
5.Framework baselines: LangGraph ordinary node callbacks as a representative real-
framework comparison.
The evidence levels are intentionally separated. Controlled and replayed experiments
support paired causal comparisons because every policy consumes the same event trace.
Online and LangGraph measurements are reported as descriptive external checks because
provider load, network conditions, and framework-specific execution paths cannot be paired
exactly across systems.
7.1. Artifact Packaging
The supplementary artifact is organized to support both quick inspection and indepen-
dent reruns. It contains the manuscript-reported CSV tables, raw DeepSeek and Ollama
traces, replay scripts, LangGraph baseline scripts, streaming RAG inputs, machine meta-
data, provenance records, checksums, and an API-free smoke test. The smoke test verifies
the replay and summarization path without requiring a cloud API key, local model service,
or network access. Live reruns require the corresponding API key or local Ollama service
and may produce different absolute latencies because provider and network conditions are
outside the application runtime.
7.2. Baselines
Baselines are chosen to avoid comparing only with intentionally weak aggregation:
•Aggregate: Materializes the complete model response before downstream work.
•Stream callback: Processes each token inline as it arrives (single-threaded).
•RxJava parallel: Explicit scheduling with bounded queues (carefully configured).
•Hand-written async optimized: A developer-crafted asynchronous pipeline.
•LangGraph node callback: Real graph framework with token-level callback pro-
cessing.
The LangGraph comparison is intentionally conservative: it evaluates a real graph work-
flow whose token handling remains callback-local, rather than claiming that an expert de-
veloper could not manually add queues and workers outside the graph abstraction.
12

## PDF Page 13

7.3. Protocol and Statistical Analysis
Controlled experiments report mean and standard deviation over 30 measured runs after
5 warm-up runs. For the 30-run DeepSeek trace replay, we report:
•Mean±standard deviation for primary metrics.
•95% confidence intervals computed as¯x±t0.025,n−1 ·s/ √n.
•Paired Wilcoxon signed-rank tests betweenAiFlowand baselines on the same 30
traces, with significance levelα= 0.05and Bonferroni correction for multiple compar-
isons.
•Cohen’sdeffect sizes for the primary metric comparisons.
The trace replay design is inherently paired: each policy consumes thesamecaptured
provider-arrival sequence. This eliminates provider-side variability and makes differences in
Application TTFPT, queue growth, and end-to-end time attributable to application-layer
orchestration.
Online DeepSeek and Ollama runs are reported descriptively because cloud-provider load
and network conditions cannot be fully controlled. Trace replay is therefore the primary
comparison mechanism.
7.4. Configuration
Table 4 states the controlled benchmark configuration, and Table 5 defines the scenario
coverage and evidence boundaries for each experimental scenario.
Table 4: Controlled benchmark configuration.
Item Configuration
Runtime JVM prototype; OpenJDK 21; Linux x86-64 CPU-only host.
Model stream Deterministic stub; first delta at 100ms; subsequent deltas every 100ms unless stated otherwise.
Protocol 5 warm-up runs + 30 measured runs; report mean, SD, 95% CI.
Trace control All policies receive the same token trace, timing, and downstream service-time distribution.
Default queues Generate/map/route:q= 8; TTS:q= 8; desensitization:q= 64.
Default workers Generate:k= 1; classify:k= 1; route:k= 1; TTS:k= 1; desensitize:k= 3.
Metrics Model TTFT, Application TTFPT, E2E latency, throughput, p95 queue wait, MaxQ, drops/errors, relative memory.
Statistical tests Paired Wilcoxon signed-rank test (α= 0.05, Bonferroni-corrected); Cohen’sdeffect size.
8. Results
8.1. RQ1: Token-Level Semantic Routing (Controlled)
Under a shared deterministic token trace, Model TTFT remains unchanged across all sys-
temsatapproximately101ms(Table6). Thedifferenceappearsafterdownstreamprocessing.
AiFlowreduces Application TTFPT to 210ms, compared with 10,940ms for aggregation
and 280–300ms for callback or naive streaming variants. Parallel reactive and hand-written
async baselines approachAiFlow’s raw latency when carefully configured, supporting our
positioning: the main contribution isgraph-level declaration and validationof orchestration
policy, not a new primitive that makes equivalent hand-written programs impossible.
13

## PDF Page 14

Table 5: Scenario coverage and evidence boundaries.
Scenario Main validation point Key metrics Unsupported extrapolation
Semantic routing Token-level classification and
branch routing.
Model TTFT, App TTFPT,
E2E.
Does not prove lower model-side
TTFT.
Slow TTS down-
stream
Queue bound under a slow con-
sumer.
MaxQ, drops/errors, E2E. Does not prove precise cloud-
provider demand control.
Concurrent desensiti-
zation
Worker/queue policy under
many prompts.
Batch completion, p95 wait,
MaxQ.
Does not validate every safety-
filter semantic.
Ablation and stress Independent effects of each pol-
icy dimension.
p50/p95, throughput, mem-
ory, queue growth.
Does not claim production ca-
pacity.
Real trace replay Orchestration under real
provider timing.
App TTFPT, MaxQ, E2E. Does not measure server-side
batching or GPU contention.
Online/Framework
checks
Live model + framework base-
line.
Model TTFT, App TTFPT,
MaxQ.
Descriptive only; does not claim
LangGraph cannot be manually
optimized.
Streaming RAG End-to-end retrieval + stream-
ing generation.
Retrieval latency, App
TTFPT, MaxQ.
Does not represent production-
scale RAG quality.
Table 6: Representative controlled results (30 measured runs after warm-up).
Benchmark MetricAiFlowAggregate Stream callback RxJava parallel Async optimized
Semantic routing Model TTFT (ms) 101±2 101±2 101±2 101±2 101±2
Semantic routing App TTFPT (ms) 210±10 10940±60 280±5 220±8 218±7
Semantic routing E2E (s) 10.9±0.1 21.8±0.1 11.3±0.1 11.1±0.1 11.0±0.1
Slow TTS App TTFPT (ms) 230±10 — 285±10 245±8 240±8
Slow TTS E2E (s) 12.5±0.1 — 12.8±0.1 12.6±0.1 12.6±0.1
Slow TTS MaxQ 8 — unbounded 8 8
Desensitization App TTFPT (ms) 310±10 — 380±10 330±10 325±10
Desensitization Batch (s) 11.2±0.1 — 31.6±0.1 12.1±0.1 11.9±0.1
8.2. RQ2–RQ3: Backpressure and Worker Policies
With a slow TTS-like downstream node (service time 500ms per token),AiFlowkeeps
the maximum queue depth at the declared bound of 8 with no drops or errors (Figure 4 illus-
trates this queue-depth behavior). With 50 concurrent prompts and a slower desensitization
node using three workers,AiFlowcompletes the batch in 11.2s, close to optimized Rx-
Java (12.1s) and hand-written async (11.9s) baselines, while exposing worker count, queue
capacity, and ordering policy at the graph level.
AiFlow’sdeclaredbound(q= 8)preventsunboundedaccumulation; theno-backpressure
policy allows queue growth proportional to unprocessed token count, reaching MaxQ= 131
(consistent with the ablation results in Table 7). In the online replay setting, unbounded
queues grow further to MaxQ= 231(Table 8) due to longer provider-side generation streams.
8.3. RQ4: Ablation
Table 7 shows that removing token-level routing raises Application TTFPT from 210ms
to 10,940ms (52×). Removing backpressure preserves first-token latency but increasesMaxQ
from 8 to 131 and relative memory from 1.0×to 3.4×. Queue size 1 reduces memory but
increases end-to-end time. Unordered output is slightly faster but unsuitable when source
order is semantically required. Figure 5 shows the Application TTFPT tail-latency trend
under increasing concurrency from the controlled stress test.
Underhighconcurrency, p95degradesduetoschedulingcontentionacrossNodeGuardians
sharing the host CPU, but p50 remains below 550ms even at 512 concurrent sessions.
14

## PDF Page 15

0 2 4 6 8 10 1208
30
60
90
131
declared bound
time (s)
queue depth
AiFlowbounded (q= 8)
No backpressure
Stream callback (inline)
Figure 4: Queue-depth evolution under a slow downstream consumer (controlled deterministic stream).
Table 7: Ablation results (controlled, deterministic stream).
Variant App TTFPT (ms) E2E (s) p95 (s) MaxQ Memory Interpretation
FullAiFlow210 10.9 11.1 8 1.0×Token overlap with bounded queues.
No token-level routing 10940 21.8 22.0 — 1.1×Downstream waits for aggregate output.
Global executor only 240 12.3 13.8 18 1.2×Slow nodes interfere with fast nodes.
No backpressure 205 10.8 11.0 131 3.4×Low latency but unsafe queue growth.
Queue size = 1 250 14.9 16.1 1 0.8×Small memory but frequent stalls.
Unordered output 205 10.7 10.9 8 1.0×Faster but unsuitable when order matters.
1 8 32 128 512
200
400
600
800
1,000
1,200
concurrent sessions
Application TTFPT (ms)
p50
p95
Figure 5: Application TTFPT tail-latency trend as concurrency increases (controlled stress test,q= 8).
15

## PDF Page 16

8.4. RQ5: Captured Trace Replay
The 30-run DeepSeek captured-trace replay (Table 8) confirms the controlled pattern un-
der real provider timing. In semantic routing, Model TTFT is shared at 1071.9ms (±352.4).
AiFlowreduces Application TTFPT from 5495.0ms (aggregation) to 1151.9ms while lim-
iting MaxQ to 8.0 rather than 231.2. Table 9 provides the corresponding tail-latency sup-
plement with p95 and p99 percentiles.
Statistical significance: Paired Wilcoxon signed-rank tests on the 30 replayed traces
confirm that the TTFPT reduction from aggregation is significant (p <0.001, Bonferroni-
corrected). Cohen’sd= 3.91indicates a very large effect size. The largedvalues (Table 12)
reflect the fundamental nature of the comparison: aggregation delaysalldownstream pro-
cessing until generation completes (seconds), while streaming begins processing at the first
token (milliseconds). The effect size is expected to be very large because the two processing
modes differ qualitatively, not merely quantitatively.
Note on identical streaming values: In Table 8, Stream callback,AiFlowbounded,
and No backpressure show the same Application TTFPT and E2E. This is expected and
correct: all three streaming policies deliver the first token to downstream processing at the
same time (first chunk arrival + one downstream service time), explaining the identical
TTFPT. E2E is also identical because the trace replay feeds each policy thesamecaptured
provider-arrival sequence; since provider-side generation time dominates end-to-end latency
and local queue management overhead is negligible relative to multi-second generation, the
E2E values coincide. The policies differ not inwhen the first or last token is processed,
but inhow much memory accumulateswhen subsequent tokens arrive faster than the con-
sumer processes them. The key differentiator is MaxQ (1.0 vs. 8.0 vs. 231.2), which reflects
whether queue growth is bounded by policy. The aggregate baseline delays all processing
until generation completes, explaining its much higher TTFPT and E2E.
Table 8: DeepSeek 30-run captured-trace replay: semantic routing and streaming RAG.
Workload PolicynModel TTFT (ms) App TTFPT (ms) App E2E (s) MaxQ drops/errors
Semantic routing Aggregate 30 1071.9±352.4 5495.0±1564.3 23.91±5.82 231.2 0/0
Semantic routing Stream callback 30 1071.9±352.4 1151.9±352.4 19.59±4.58 1.0 0/0
Semantic routingAiFlowbounded 30 1071.9±352.4 1151.9±352.4 19.59±4.58 8.0 0/0
Semantic routing No backpressure 30 1071.9±352.4 1151.9±352.4 19.59±4.58 231.2 0/0
Streaming RAG Aggregate 30 911.5±160.3 3401.5±1166.8 13.49±5.86 127.1 0/0
Streaming RAG Stream callback 30 911.5±160.3 991.5±160.3 11.13±4.69 1.0 0/0
Streaming RAGAiFlowbounded 30 911.5±160.3 991.5±160.3 11.13±4.69 8.0 0/0
Streaming RAG No backpressure 30 911.5±160.3 991.5±160.3 11.13±4.69 127.1 0/0
Table 9: DeepSeek semantic-routing replay: tail-latency supplement.
PolicynModel TTFT (ms) App TTFPT (ms) App TTFPT p95 (ms) App TTFPT p99 (ms) MaxQ p99 queue wait (ms)
Aggregate 30 1071.9 5495.0 6750.6 7486.5 231.2 0.0
Stream callback 30 1071.9 1151.9 1691.5 2321.1 1.0 13951.9
AiFlowbounded 30 1071.9 1151.9 1691.5 2321.1 8.0 13951.9
No backpressure 30 1071.9 1151.9 1691.5 2321.1 231.2 13951.9
8.5. RQ6: LangGraph Baselines
Table 10 shows a descriptive LangGraph ordinary-node-callback baseline: Model TTFT
is 1442.7ms (higher due to a different trace set and network conditions) and Applica-
16

## PDF Page 17

tion TTFPT is 6336.4ms for semantic routing. Because this baseline is not paired with
the replay traces, it is not used for the primary statistical claim. Its role is structural:
LangGraph exposes streamed tokens through callback-local processing, whereasAiFlow
exposes queue capacity, worker concurrency, ordering, and backpressure as graph-level dec-
larations. An expert LangGraph developer could manually add external queues and workers;
the comparison evaluates what is declared and validated by the graph abstraction itself.
Table 10: LangGraph callback baseline (30 live DeepSeek traces).
Scenario ImplementationnModel TTFT (ms) App TTFPT (ms) App TTFPT p95 (ms) E2E (s) MaxQ
Semantic routing LangGraph node callback 30 1442.7 6336.4 9220.0 25.63 1.0
RAG LangGraph node callback 30 1061.7 3511.0 5011.6 12.87 1.0
8.6. RQ7: Streaming RAG
In the 30-run DeepSeek RAG trace replay,AiFlowreduces Application TTFPT from
3401.5ms (aggregation) to 991.5ms, while limiting MaxQ to 8.0 instead of 127.1. An Ol-
lama qwen2.5:3b local-backend sanity check (Table 11) shows the same qualitative result:
Application TTFPT drops from 4129.2ms to 217.9ms, and MaxQ is bounded at 8.0.
Table 11: Ollama qwen2.5:3b local-backend sanity check (30 runs).
Policy Model TTFT (ms) App TTFPT (ms) App E2E (s) MaxQ p99 wait (ms) Event overhead (ms) CPU (s) RSS (MB) drop/err
Aggregate 137.9 4129.2 21.99 224.2 0.0 0.0003 0.014 39.2 0/0
Stream callback 137.9 217.9 18.08 1.0 13812.1 0.0003 0.014 39.2 0/0
AiFlowbounded 137.9 217.9 18.08 8.0 560.0 0.0003 0.014 39.2 0/0
No backpressure 137.9 217.9 18.08 175.1 13812.1 0.0003 0.014 39.2 0/0
8.7. Summary of Effect Sizes
Across the captured DeepSeek replay and local Ollama check, the relative effects are
consistent (Table 12). Compared with aggregation,AiFlowlowers Application TTFPT
by 79.0% (DeepSeek semantic), 70.9% (DeepSeek RAG), and 94.7% (Ollama). Compared
with no-backpressure replay,AiFlowpreserves the same first-processed-token latency while
reducing MaxQ by 96.5%, 93.7%, and 95.4% in the three workloads. These are paired replay
or local controlled comparisons on identical event traces.
Table 12: Summary of effect sizes across workloads (paired trace replay or local controlled replay).
Workload TTFPT reduction vs. aggregate MaxQ reduction vs. no-backpressure Cohen’sd(TTFPT) Wilcoxonp95% CI of reduction
DeepSeek semantic routing 79.0% 96.5% 3.91<0.001[75.2%, 82.8%]
DeepSeek streaming RAG 70.9% 93.7% 2.85<0.001[65.4%, 76.4%]
Ollama qwen2.5:3b sanity 94.7% 95.4% 8.12<0.001[93.1%, 96.3%]
9. Discussion
9.1. Mechanism Behind the Latency Improvement
The mechanism isnota faster model. When all systems consume the same model stream,
Model TTFT is identical.AiFlowimproves Application TTFPT when the first observable
17

## PDF Page 18

application result is defined as a token that has passed through downstream work (classifica-
tion, routing, desensitization, or TTS admission). In the aggregate baseline, no downstream
processing starts until the entire model response is collected. In streaming policies, the
first token begins downstream processing at the time it arrives, yielding the same TTFPT
regardless of backpressure configuration.
The practical value of bounded backpressure emerges when the system mustsustain
streaming under slow consumers or high concurrency. Without backpressure, queue growth is
proportional to the number of unprocessed tokens; with declared bounds, the runtime either
blocksproducers(preventingmemoryexhaustion)orappliesoverflowpolicy(e.g., drop-oldest
for latency-sensitive TTS). Proposition 1 guarantees that the total runtime-owned buffer is
bounded and computable from graph declarations. This distinction is invisible at the first-
token level but critical foroperational safetyin production deployments where long-running
conversations may generate hundreds of tokens against slow downstream consumers.
9.2. Relationship to Classical Dataflow
Queues, workers, ordering buffers, and backpressure are known systems ideas.AiFlow’s
engineering contribution lies in:
1.LLM-specific event typing: Provider deltas, prompt fragments, tool events, safety
labels, and control signals each carry type information that enables validated routing.
2.Graph-level policy declarations: Queue, worker, ordering, and overflow behavior
are part of the graph definition, enabling compile-time validation and runtime observ-
ability.
3.Node-directed injection: External events can be delivered to specific graph nodes
with compile-time type checking.
4.Side-effect discipline: Idempotency, compensation, and speculative modes are de-
clared per-node rather than managed in ad hoc callback code.
Equivalent behavior can be written manually; the claim is thatAiFlowmakes the
behaviorreusable, checkable, and observableas part of the workflow model.
9.3. Developer Experience Implications
The graph-level declaration approach has software-engineering implications beyond run-
time performance. Callback-based streaming requires developers to manage queue alloca-
tion, thread coordination, error handling, and cancellation logic explicitly across operator
boundaries. In contrast,AiFlow’s policy declarations reduce the implementation to:
•Operator logic: Each node implements only its functional behavior.
•Policy annotation: Queue, worker, ordering, and overflow are specified declaratively.
•No explicit wiring: Queue creation, worker pool management, backpressure signal-
ing, ordering restoration, and metrics collection are handled by the runtime.
While this paper does not include a formal user study (which would require a differ-
ent methodology and participant recruitment), the reduction from imperative concurrency
18

## PDF Page 19

management to declarative policy specification is a well-established software-engineering pat-
tern (Hohpe and Woolf, 2003; Kleppmann, 2017) whose benefits in correctness, maintain-
ability, and debugging have been demonstrated in other domains (SQL vs. imperative data
access, declarative UI frameworks, configuration management).
9.4. Limitations of the Current Evaluation
Production deployment requires additional evidence beyond the supplied experiments,
especially because reliability and performance issues in LLM pipelines can arise outside the
orchestration layer (Chen et al., 2025). The current study does not measure:
•Distributed node placement across machines.
•Provider multi-tenancy and GPU contention effects.
•Long-running fault recovery and durability guarantees.
•Large-scale knowledge-base quality in RAG.
•Adaptive scheduling based on runtime conditions.
10. Threats to Validity
Constructvalidity: Theevaluationmeasuresapplication-layerorchestration, notmodel
inference speed. We separate Model TTFT from Application TTFPT to avoid attributing
provider-side effects toAiFlow. The deterministic stream makes scheduling effects observ-
able, and real traces add provider timing, but online runs cover a limited number of models
and parameter settings.
Internal validity: Baseline implementation quality matters. Carefully configured reac-
tive or async baselines approachAiFlow’s raw latency. We frame the strongest conclusion
around graph-level declaration, validation, and bounded orchestration rather than absolute
performance dominance. The paired trace-replay design controls for provider variability, but
the 30-run sample size limits the power of tail-latency comparisons at extreme percentiles.
External validity: Cloud providers do not necessarily implement precise demand con-
trol.AiFlowcan slow local reading, stop downstream dispatch, or cancel requests, but
it cannot control remote buffers. Safety filtering needs windowing or speculative buffering
when harmful patterns span multiple tokens. The streaming RAG corpus is intentionally
small and should be read as an orchestration check, not evidence of retrieval quality at scale.
Online and LangGraph measurements use limited trace sets and are therefore treated as
descriptive evidence rather than definitive cross-framework performance rankings.
Conclusion validity: We apply paired Wilcoxon tests with Bonferroni correction and
report confidence intervals and effect sizes to support the reported reductions. The very
large Cohen’sdvalues (>2.0) reflect the qualitative difference between aggregation (all
downstream work delayed by full generation time) and streaming (downstream work begins
at first token); such large effects are characteristic of comparisons between fundamentally
different processing paradigms rather than incremental optimizations.
19

## PDF Page 20

11. Reproducibility and Data Availability
Supplementary Material S1 contains the evidence package for this submission:
•DeepSeek collection and replay scripts with 30-run raw traces and result CSVs.
•LangGraph baseline scripts and outputs.
•Streaming RAG scripts with local document set.
•Ollama local-backend scripts with 30-run raw traces.
•Input prompts and RAG documents (public, no PII).
•Machine metadata, checksums, table mapping, and provenance records.
•An API-free offline replay smoke test for installation-independent verification.
The package distinguishes three evidence levels: (1) reported summary tables in CSV
form, (2) executable scripts requiring API keys or local model service, and (3) an API-free
synthetic trace checking the replay pipeline without network access. The public software
implementation path is the ModelEngine-Group FIT Framework repository; the observed
revision is commite2f285don 11 May 2026. The data package is suitable for deposition in
a citable archive following software and data citation principles (Smith et al., 2016). API
keys, local environment files, interpreter caches, operating-system temporary files, personally
identifiable information, and proprietary Huawei deployment data are not included.
12. Conclusion
AiFlowtreats streamed LLM deltas as first-class typed events in an application graph
and attaches queue, worker, ordering, overflow, state-safety, cancellation, retry, and met-
rics policies to nodes. The Node Guardian runtime specializes reactive-stream and dataflow
ideas forLLMapplication orchestration. Across controlled, captured-trace replay, descriptive
online/framework checks, RAG, and local-backend experiments,AiFlowdoes not change
provider Model TTFT but reduces Application TTFPT by 70.9–94.7% versus aggregation
through downstream overlap, while keeping runtime-owned queues within declared bounds
(93.7–96.5% MaxQ reduction versus unbounded policies). The formal bounded-memory
proposition, static validation, and paired trace-replay methodology provide a rigorous foun-
dation for the primary claims.
Future work includes adaptive scheduling based on runtime queue-depth feedback, dis-
tributed node placement with network-aware policy, long-running fault recovery with durable
checkpoints, larger RAG corpora evaluation, and formal developer-experience studies com-
paring declarative policy specification with imperative concurrency management.
20

## PDF Page 21

Declaration of Competing Interest
The authors report thatAiFlowhas informed Huawei commercial LLM application
workflows and is related to the public ModelEngine-Group FIT Framework repository. Pro-
prietary Huawei deployments are not used as empirical evidence in this manuscript. The
authors declare no other known competing financial interests or personal relationships that
could have appeared to influence the work reported in this paper.
CRediT Author Statement
Qun-hui Zhang: Conceptualization, Methodology, Software, Writing – original draft.
Jian-guo Yao: Supervision, Methodology, Validation, Writing – review & editing.Yi-fan
Zhang: Software, Investigation, Data curation, Visualization.
Declaration of Generative AI and AI-assisted Technologies
During preparation of this work, the authors used large language model tools to assist
with language polishing, LaTeX formatting, and supplementary-material organization. Af-
ter using these tools, the authors reviewed and edited the content as needed, verified the
references and empirical claims, and take full responsibility for the content of the submitted
article.
Funding
This research did not receive any specific grant from funding agencies in the public,
commercial, or not-for-profit sectors.
Supplementary Material
Supplementary Material S1:AiFlow_JSS_Full_Experiment_Package.zip. This archive
contains reported summary tables, replay scripts, online-experiment scripts, public input
prompts and RAG documents, raw DeepSeek/Ollama traces and result CSVs, an API-free
smoke-test trace, generated smoke-test outputs, checksums, provenance metadata, and re-
viewer quick-start instructions.
Data Availability
Data and code supporting this study are available in the supplementary material accom-
panying this article. The public software implementation path is the ModelEngine-Group
FIT Framework repository (https://github.com/ModelEngine-Group/fit-framework).
21

## PDF Page 22

References
Abadi, D.G., Carney, D., Cetintemel, U., Cherniack, M., Convey, C., Lee, S., Stonebraker,
M., Tatbul, N., Zdonik, S., 2003. Aurora: A new model and architecture for data stream
management. VLDB Journal 12, 120–139.
Akidau, T., Bradshaw, R., Chambers, C., Chernyak, S., Fernandez-Moctezuma, R.J., Lax,
R., McVeety, S., Mills, D., Perry, F., Schmidt, E., Whittle, S., 2015. The Dataflow model:
A practical approach to balancing correctness, latency, and cost in massive-scale, un-
bounded, out-of-order data processing. Proceedings of the VLDB Endowment 8(12), 1792–
1803.
Apache Airflow, 2026. Apache Airflow documentation: Core concepts.https://airflow.
apache.org/docs/apache-airflow/stable/core-concepts/index.html(accessed 11
May 2026).
Apache Beam, 2026. Beam programming guide.https://beam.apache.org/
documentation/programming-guide/(accessed 11 May 2026).
Armbrust, M., Das, T., Torres, J., Yavuz, B., Zhu, S., Xin, R., Ghodsi, A., Stoica, I.,
Zaharia, M., 2018. Structured Streaming: A declarative API for real-time applications in
Apache Spark. Proceedings of the 2018 International Conference on Management of Data,
601–613.
Bernstein, P.A., Newcomer, E., 2009. Principles of Transaction Processing, second ed. Mor-
gan Kaufmann.
Brown, T.B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., et al., 2020. Lan-
guage models are few-shot learners. Advances in Neural Information Processing Systems
33, 1877–1901.
Burns, B., Grant, B., Oppenheimer, D., Brewer, E., Wilkes, J., 2016. Borg, Omega, and
Kubernetes. Communications of the ACM 59(5), 50–57.
Chambers, C., Raniwala, A., Perry, F., Adams, S., Henry, R.R., Bradshaw, R., Weizenbaum,
N., 2010. FlumeJava: Easy, efficient data-parallel pipelines. Proceedings of PLDI 2010,
363–375.
Confluent, 2026. Kafka Streams architecture.https://docs.confluent.io/platform/
current/streams/architecture.html(accessed 11 May 2026).
Dean, J., Ghemawat, S., 2004. MapReduce: Simplified data processing on large clusters.
Proceedings of OSDI 2004, 137–150.
Dennis, J.B., Misunas, D.P., 1974. A preliminary architecture for a basic data-flow processor.
Proceedings of ISCA 1974, 126–132.
Elliott, C., Hudak, P., 1997. Functional reactive animation. Proceedings of ICFP 1997, 263–
273.
22

## PDF Page 23

Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., Dai, Y., Sun, J., Wang, H.,
Wang, H., 2023. Retrieval-augmented generation for large language models: A survey.
arXiv:2312.10997.
Chen, X., Gao, C., Chen, C., Zhang, G., Liu, Y., 2025. An empirical study on challenges for
LLM application developers. ACM Transactions on Software Engineering and Methodol-
ogy 34(7), Article 205.https://doi.org/10.1145/3715007.
Hellerstein, J.M., Stonebraker, M., Hamilton, J., 2007. Architecture of a database system.
Foundations and Trends in Databases 1(2), 141–259.
Hohpe, G., Woolf, B., 2003. Enterprise Integration Patterns. Addison-Wesley.
Khattab, O., Singhvi, A., Maheshwari, P., Zhang, Z., Santhanam, K., Haq, S., Sharma,
A., Joshi, T.T., Moazam, H., Miller, H., Zaharia, M., Potts, C., 2023. DSPy: Compiling
declarative language model calls into self-improving pipelines. arXiv:2310.03714.
Kleppmann, M., 2017. Designing Data-Intensive Applications. O’Reilly Media.
Kreps, J., Narkhede, N., Rao, J., 2011. Kafka: A distributed messaging system for log
processing. Proceedings of the NetDB Workshop.
Kwon, W., Li, Z., Zhuang, S., Sheng, Y., Zheng, L., Yu, C.H., Gonzalez, J.E., Zhang,
H., Stoica, I., 2023. Efficient memory management for large language model serving with
PagedAttention. Proceedings of SOSP 2023, 611–626.
LangChain, 2026. LangChain streaming documentation.https://docs.langchain.com/
oss/python/langchain/streaming(accessed 11 May 2026).
LangChain, 2026. LangGraph streaming documentation.https://docs.langchain.com/
oss/python/langgraph/streaming(accessed 11 May 2026).
Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Kuttler, H., Lewis,
M., Yih, W., Rocktaschel, T., Riedel, S., Kiela, D., 2020. Retrieval-augmented generation
for knowledge-intensive NLP tasks. Advances in Neural Information Processing Systems
33, 9459–9474.
LlamaIndex, 2026. LlamaIndex documentation.https://docs.llamaindex.ai/(accessed
11 May 2026).
Microsoft, 2026. Semantic Kernel agent orchestration.https://learn.microsoft.com/
en-us/semantic-kernel/frameworks/agent/agent-orchestration/(accessed 11 May
2026).
ModelEngine-Group, 2026. FIT Framework. GitHub repository.https://github.com/
ModelEngine-Group/fit-framework(accessed 11 May 2026).
Moritz, P., Nishihara, R., Wang, S., Tumanov, A., Liaw, R., Liang, E., Elibol, M., Yang, Z.,
Paul, W., Jordan, M.I., Stoica, I., 2018. Ray: A distributed framework for emerging AI
applications. Proceedings of OSDI 2018, 561–577.
23

## PDF Page 24

Nurkiewicz, T., Christensen, B., 2016. Reactive Programming with RxJava. O’Reilly Media.
OpenAI, 2026. Streaming API responses.https://platform.openai.com/docs/guides/
streaming-responses(accessed 11 May 2026).
Ouyang, L., Wu, J., Jiang, X., Almeida, D., Wainwright, C., Mishkin, P., Zhang, C., Agar-
wal, S., Slama, K., Ray, A., Schulman, J., Hilton, J., Kelton, F., Miller, L., Simens, M.,
Askell, A., Welinder, P., Christiano, P., Leike, J., Lowe, R., 2022. Training language mod-
els to follow instructions with human feedback. Advances in Neural Information Processing
Systems 35, 27730–27744.
Reactive Streams, 2026. Reactive Streams specification 1.0.4.https://www.
reactive-streams.org/(accessed 11 May 2026).
Roestenburg, R., Williams, R., Bakker, R., 2016. Akka in Action. Manning.
Schick, T., Dwivedi-Yu, J., Dessi, R., Raileanu, R., Lomeli, M., Hambro, E., Zettlemoyer,
L., Cancedda, N., Scialom, T., 2023. Toolformer: Language models can teach themselves
to use tools. Advances in Neural Information Processing Systems 36.
Smith, A.M., Katz, D.S., Niemeyer, K.E., FORCE11 Software Citation Working Group,
2016. Software citation principles. PeerJ Computer Science 2, e86.
Temporal, 2026.Temporalplatformdocumentation.https://docs.temporal.io/(accessed
11 May 2026).
Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., Kaiser, L.,
Polosukhin, I., 2017. Attention is all you need. Advances in Neural Information Processing
Systems 30.
Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E., Le, Q., Zhou, D.,
2022. Chain-of-thought prompting elicits reasoning in large language models. Advances in
Neural Information Processing Systems 35, 24824–24837.
Wohlin, C., Runeson, P., Host, M., Ohlsson, M.C., Regnell, B., Wesslen, A., 2012. Experi-
mentation in Software Engineering. Springer.
Wu, Q., Bansal, G., Zhang, J., Wu, Y., Li, B., Zhu, E., Jiang, L., Zhang, X., Zhang, S.,
Liu, J., Awadallah, A.H., White, R.W., Burger, D., Wang, C., 2023. AutoGen: Enabling
next-gen LLM applications via multi-agent conversation. arXiv:2308.08155.
Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., Cao, Y., 2023. ReAct: Syn-
ergizing reasoning and acting in language models. International Conference on Learning
Representations.
Yu, G.I., Jeong, J.S., Kim, G.W., Kim, S., Chun, B.G., 2022. Orca: A distributed serving
system for transformer-based generative models. Proceedings of OSDI 2022, 521–538.
24