## PDF Page 1

Practical Online KV Cache Compaction for LLM Agents:
An Empirical Study
Yujian Liu1* Jiabao Ji1∗ Li An1∗ Rohit Jain2
Gungor Polatkan2 Siyu Zhu2 Shiyu Chang1
1UC Santa Barbara 2LinkedIn
{yujianliu,jiabaoji,li_an,chang87}@ucsb.edu
Abstract
LLM agents accumulate long trajectories of
reasoning steps, tool calls, and environment
feedback, making the KV cache a major infer-
ence bottleneck. KV cache compaction can
reduce this cost, but most prior methods as-
sume a static context where future queries are
known or can be approximated offline. Agents
instead require online compaction: new infor-
mation must be compressed before future rel-
evance is known, using proxy queries cheap
enough for the inference path. We study online
compaction across token eviction (TE) and at-
tention matching (AM), adapting both to com-
pact agent turns and comparing cheap proxy
sources such as boundary, repeat-prefill, and de-
layed future-generation queries. Experiments
on BROWSECOMP-PLUSand WIDESEARCH
show that immediate compaction often hurts
performance, whereas delaying compaction to
use the agent’s future queries recovers much
of the gap. Moreover, TE is often more ro-
bust than AM under imperfect proxies. Across
models at different scales, TE preserves most
of the accuracy while reducing KV cache by
80%, and can improve throughput over the no
compaction baseline. These results position
proxy-query selection as a core design choice
for practical online KV compaction.
1 Introduction
LLM agents are increasingly used for long-horizon
tasks such as software engineering, deep research,
web browsing, and personal assistance (Anthropic,
2026; OpenAI, 2026; Google, 2026; OpenClaw,
2026). Their strength comes from maintaining an
informative context: the model reasons, calls tools,
observes results, and decides what to do next. This
interaction pattern has enabled substantially more
capable systems than single-shot prompting, but it
also creates a direct inference bottleneck. Every
*Equal contribution. Work done when Yujian, Jiabao, and
Li were interning at LinkedIn.
generated reasoning step and every tool response
is appended to the running context, and the model
must retain a key-value (KV) cache for that grow-
ing history. As agent trajectories stretch across
many turns, the cache can dominate memory use
and increase the cost of each decoding step.
KV cache compaction is a natural way to re-
duce this cost. Instead of storing the full cache, a
compaction method replaces a long sequence of
cached keys and values with a shorter represen-
tation that approximately preserves the attention
behavior of the original cache (Liu et al., 2023;
Zhang et al., 2023). Much of the work compress-
ing long prompts before answering studies astatic
setting: a complete context is available before gen-
eration, the cache is compacted offline, and the
resulting compact cache is then consumed by later
queries. In such settings, signals about how the
context will be used are often available or can be
sampled offline. For example, query-aware token
eviction methods can use an observation window
containing the question or continuation that will
read the context (Li et al., 2024; Cai et al., 2025).
Other approaches can further spend additional com-
putation to create training signals before inference,
either by generating proxy queries for fitting a com-
pact cache or by generating synthetic conversations
and distilling them into a trainable cache (Zweiger
et al., 2026; Eyuboglu et al., 2025).
Agent trajectories, however, differ from this
static setting. An agent does not begin with a fixed
document to compress; it gradually constructs its
context through interactions with an environment.
Search results, file diffs, and execution traces arrive
throughout the trajectory and are incorporated into
the live context. Compaction in this regime is there-
fore inherentlyonline: newly collected information
must be compacted before the full future trajectory
is known. Two properties distinguish it from static
compaction.First, future relevance is not yet
observable.When a turn is compacted, the infor-
1
arXiv:2608.00902v1  [cs.CL]  2 Aug 2026

## PDF Page 2

mation needed from it several turns later may differ
from what that turn or even the immediately follow-
ing turn would emphasize. A compaction signal
derived only from the current context may there-
fore poorly represent how the compacted cache
will be used later.Second, the compaction proce-
dure must fit within a reasonable time budget.
Because compaction is performed inside the agent
loop, both obtaining a signal about what informa-
tion to preserve and executing the compaction al-
gorithm contribute directly to the agent’s runtime.
Procedures that rely on additional rollouts, long
synthetic continuations, or expensive optimization
may be feasible offline but can add substantial la-
tency inside a live agent trajectory. Together, these
properties create an underexplored design space
for adapting existing compaction methods: which
available signals should guide compaction, and
how signal quality and runtime cost interact with
the compaction method.
To study this design space, we present a system-
atic empirical evaluation of how existing KV cache
compaction methods behave when adapted to agent
tasks. We focus on two widely used sequence-
level compaction families, both of which depend
on query vectors that represent how the compacted
cache will later be read. We refer to these asproxy
queries. Token eviction (TE) uses proxy queries to
score cached positions by their induced attention
mass, then keeps the original KVs at the highest-
scoring positions (Li et al., 2024). Attention match-
ing (AM) uses the same proxy-query-based key
selection, but additionally fits an additive atten-
tion bias and reconstructed values so that attention
outputs against the compacted cache better match
those against the full cache (Zweiger et al., 2026).
We adapt both families to the online agent setting
by compacting completed turns as the trajectory
unfolds, where proxy queries are derived from sig-
nals available at or near the completed turns. Our
main analysis studies the interaction between com-
paction family and proxy source, including current-
turn boundary queries, lightweight repeat-prefill
queries, and deferred future-turn queries obtained
from the agent’s own subsequent generation. The
resulting experiments map which proxy sources
are useful, when deferring compaction helps, and
when adding more proxy sources hurts.
We evaluate on BROWSECOMP-PLUS(Chen
et al., 2025) and WIDESEARCH(Wong et al.,
2025), using Qwen3.5 and Gemma-4 models at
multiple scales. Experiments show that immedi-
ate compaction often degrades task performance,
whereas delaying compaction to use queries from
the agent’s own subsequent generation consistently
recovers much of the gap. Despite its much simpler
selection-only design, TE is surprisingly robust to
imperfect proxies and remains competitive with
AM across proxy, delay, and compaction-budget
choices. On Qwen3.5-27B and Gemma-4-31B, de-
layed compaction at a ratio of 0.2 preserves most of
the no-compaction accuracy while reducing peak
KV footprint by up to 3.5× and 2.7×, and increas-
ing serving throughput by up to 4.2 × and 1.7×,
respectively. Together, these results identify proxy-
query selection as core design choices for practical
online KV compaction.
2 Related Work
Token-level KV eviction and query-aware spar-
sity.A large body of work reduces KV memory
by retaining only selected cached tokens. Attention-
based eviction methods exploit concentration, per-
sistence, or structural attention patterns to keep
heavy-hitter, sink, recent, or head-specific to-
kens (Liu et al., 2023; Zhang et al., 2023; Xiao
et al., 2024; Ge et al., 2024a). Query- or layer-
aware methods further score historical tokens from
an observation window or allocate budgets across
layers (Li et al., 2024; Tang et al., 2024; Yang et al.,
2024; Cai et al., 2025). Expected attention simi-
larly estimates importance from a future-query dis-
tribution when future attention is unavailable (De-
voto et al., 2025). These methods show that query-
conditioned signals are useful for KV reduction.
In agent trajectories, however, future queries are
endogenous to the model’s own later actions. A
compaction decision made after one tool interac-
tion must therefore preserve information for future
states of the trajectory that do not yet exist.
Learned and optimized compact representa-
tions.Other work replaces token selection with
learned or optimized compact states. Prompt- and
context-compression methods summarize contexts
into soft tokens, recurrent states, or compressed
activation slots (Mu et al., 2024; Chevalier et al.,
2023; Ge et al., 2024b; Zhang et al., 2024a; Chu
et al., 2026). Cartridges trains compact KV repre-
sentations through offline self-study, requiring syn-
thetic conversations and gradient-based optimiza-
tion (Eyuboglu et al., 2025). Attention matching
fits a compact cache to match full-cache attention
outputs on proxy queries (Zweiger et al., 2026).
2

## PDF Page 3

We use attention matching as one compaction fam-
ily in our study. These methods are usually static:
the context, task distribution, or proxy queries can
be prepared before deployment. We instead study
compaction when proxy queries must be obtained
cheaply during an ongoing agent trajectory.
Multi-turn and agent KV management.Sev-
eral recent works study KV reuse or compression
in multi-turn settings. KVzip motivates query-
agnostic compression for caches that may be reused
by many future queries, and SCBENCHshows
that sublinear-memory methods can degrade under
multi-turn KV-cache lifecycles (Kim et al., 2025;
Li et al., 2025). Serving systems improve multi-
turn or agent efficiency by reusing, scheduling, or
retaining KV states across conversation and tool-
execution boundaries (Gao et al., 2024; Li et al.,
2026). These works are complementary to ours.
They treat the growing interaction history as a sys-
tems object to cache, reuse, or schedule, whereas
we ask which information inside each newly com-
pleted agent turn should be preserved when that
turn is compacted and then frozen. SCBENCH, for
example, studies shared-context settings in which
multiple requests query a long context that is al-
ready available. In our setting, the context is pro-
duced online: search results, file contents, and other
observations are appended only after the agent is-
sues the corresponding actions. This makes online
compaction a decision about an evolving trajectory,
not only reuse of a fixed context.
Orthogonal KV-compression dimensions.KV
memory can also be reduced along axes orthogo-
nal to sequence length: quantization lowers key/-
value precision (Zirui Liu et al., 2023; Hooper
et al., 2025; Kang et al., 2024); low-rank meth-
ods compress or offload KV states through lower-
dimensional representations (Zhang et al., 2024b;
Sun et al., 2025; Xu et al., 2025); and architec-
tural methods use grouped or latent KV represen-
tations (Ainslie et al., 2023; DeepSeek-AI et al.,
2024). These approaches address a different axis
of the memory problem and can be combined with
compaction on sequence length.
3 Design Space of Online KV Compaction
We first describe the online KV compaction prob-
lem. The goal is not to propose a new algorithm or
a single final recipe, but to isolate which choices
matter when a compactor is placed inside an agent
loop. We begin by formalizing the two compaction
families studied throughout the paper, then describe
how we adapt them from a static prompt setting to
online agent trajectories.
3.1 Static KV Compaction
Consider one attention layer and one KV head. We
omit the usual 1/
√
d attention scale for notational
simplicity. Let K,V∈R n×d denote the full key
and value cache for a context of length n, and let
Q∈R q×d denote a set of q proxy queries. The
full-cache attention output on these queries is
A(Q;K,V) = softmax

QK⊤

V.(1)
A compactor constructs a shorter cache of length
m≪n whose attention outputs approximate
A(Q;K,V) . We focus on TE and AM because
they are widely used and, crucially for the online
setting, their compaction steps can be executed ef-
ficiently once the proxy queries are available. The
left side of Figure 1 illustrates these two families.
Token eviction.Token eviction (TE) (Li et al.,
2024) keeps original KV entries at selected posi-
tions. The selection is driven by attention scores
induced by the proxy queries. Let
αij =
h
softmax

QK⊤
i
ij
(2)
be the attention weight from proxy query i to
cached position j. We score each cached position
by its root-mean-square attention mass,
sj(Q,K) =
 
1
q
qX
i=1
α2
ij
!1/2
.(3)
TE selects the highest-scoring positions and stores
the corresponding original keys and values:
S= Top-m{s j}n
j=1,K C =K S,V C =V S,
(4)
where KC,V C ∈R m×d. TE is thus a pure selec-
tion method: after selecting S, the stored keys and
values are unchanged.
Attention matching.Attention matching
(AM) (Zweiger et al., 2026) uses the same
proxy-query-based key selection as TE, setting
KC =K S. It then fits an additive bias β∈R m
and compact values VC ∈R m×d. It consists of
two stages. First, β is chosen so that the selected
keys account for the full cache’s unnormalized
3

## PDF Page 4

Figure 1: Overview of the online KV compaction design space.Left: TE and AM both score cached tokens using
proxy queries. TE stores the selected original keys and values, while AM keeps the selected keys and optimizes
the attention bias and compacted values.Right: current-turn proxies are available when the turn finishes, whereas
future-turn proxies delay compaction untilklater turns provide additional queries.
attention mass. Let 1m ∈R m and 1n ∈R n be
all-ones vectors:
min
β
exp(QK⊤
C +β)1 m −exp(QK ⊤)1n

2
2
,
(5)
where β is broadcast across queries. Then, holding
β fixed, AM fits values to match the full-cache
attention outputs. Define
bA(Q;K C,β,V C)≜softmax

QK⊤
C +β

VC,
(6)
AM solves
min
VC
bA(Q;K C,β,V C)−A(Q;K,V)

2
F
.
(7)
The bias β changes how much attention each se-
lected key receives, while VC is allowed to differ
from the original selected values. Thus TE com-
mits to the original KV , whereas AM keeps the
selected keys but fits the attention bias and values
to match full-cache outputs on the proxy queries.
This formulation is applied independently to
each layer and KV head. In our experiments,
both Qwen3.5 (Team, 2026) and Gemma-4 (Google
DeepMind, 2026) are hybrid-attention models, so
we compact only their full-attention layers and
leave non-full-attention states unchanged; imple-
mentation details are given in Appendix A.
3.2 Online Compaction for Agent Trajectories
In an agent trajectory, the context is not fixed before
generation. The model starts from a prefix contain-
ing the system prompt, tool definitions, and user
query. It then repeatedly generates assistant mes-
sages, emits tool calls, receives tool responses, and
continues from the expanded context. We segment
this history into turns:
P, T 1, T 2, . . . , Tt, . . .
where P is the uncompacted prefix and each Tt
contains the assistant-side generation for that step
and the resulting tool response. Online compaction
compresses completed turns as they arrive. Once
turn Tt is compacted, future generations attend to
the compacted representation and discard the orig-
inal KV; the compacted turn is then frozen and is
not re-optimized or re-compacted later.
This setup changes the role of proxy queries. In
the static setting, proxy queries can be drawn from
known questions or offline synthetic data. In the
online setting, the future queries that will read Tt
are not yet available whenTt finishes. We therefore
study two cheap proxy families that do not require
extra rollouts, as summarized in Figure 1 right.
Current-turn proxies.These proxies are avail-
able immediately when Tt completes, so they allow
immediate compaction. We consider two ways to
obtain such proxies. ❶ Boundary queriesuse
the model’s query vectors at structural closing or
transition tokens from the actual trajectory. For
example, for Qwen3.5, we extract query vectors
from the closing token <|im_end|>. These queries
are cheap and require no extra forward pass, but
they may not reflect what future turns will need
from Tt. ❷ Repeat-prefill queriesare inspired
4

## PDF Page 5

by query-agnostic KV compaction in KVzip (Kim
et al., 2025). We append a reconstruction prompt
after the previous turn’s content and teacher-force
the model to repeat the completed turn:
<previous context>
Let me repeat the previous thinking,
tool call, and tool response.
<repeated context>
We extract proxy queries only from the teacher-
forced repeated content. The repeated thinking
and tool-call text provides proxies for compacting
the assistant generation, while the repeated tool
response provides proxies for compacting the tool-
response segment.
Future-turn proxies.The second proxy fam-
ily delays compaction in order to use real future
queries. To compact Tt with a delay of k turns,
the system keeps Tt in raw form while generating
turns Tt+1, . . . , Tt+k. During these generations,
the model attends to the uncompressed prefix P ,
earlier frozen compacted turns, the raw cache for
Tt, and any newer turns that are still inside the
delay window. By default, we record the query
vectors produced during the assistant generations
in Tt+1, . . . , Tt+k and use them as proxies when
compacting Tt after Tt+k finishes. We also ablate
adding the query vectors from the corresponding
tool-response prefill tokens as an additional proxy
source. From turn Tt+k+1 onward, Tt is read only
through its frozen compacted representation. Thus
a larger delay provides proxy queries that are closer
to the way later computation actually reads Tt, but
it also postpones the memory and compute savings
because more raw turns must remain in the cache.
4 What Matters for Online KV
Compaction
4.1 Setup
We evaluate on two complementary agentic-search
benchmarks. BROWSECOMP-PLUS(Chen et al.,
2025) is a fixed-corpus benchmark for deep-search
agents: each example asks a difficult information-
seeking question with a verifiable final answer, and
solving it requires iteratively retrieving evidence
from the corpus rather than relying on parametric
knowledge. WIDESEARCH(Wong et al., 2025) in-
stead targets broad information seeking. It requires
the agent to collect many atomic facts and organize
them into a well-structured table, so completeness
matters as much as correctness.
In both settings the agent starts from the
system prompt and user question, then repeat-
edly generates tool calls, observes tool outputs,
and either continues searching or returns its
final answer. For BROWSECOMP-PLUS, the
agent queries a local FAISS search server with
Qwen3-Embedding-4B (Zhang et al., 2025b) re-
trieval. For WIDESEARCH, the agent searches the
open internet through Bing Web Search API. We
study two model families: Qwen3.5 and Gemma-4,
both of which use hybrid attention. In this section,
we report performance of the 4B models and defer
results of larger models to Section 5. We compact
assistant generation and tool response separately,
while preserving structural boundary tokens needed
by the chat template. We score both benchmarks
with a Qwen3.5-397B judge. For BROWSECOMP-
PLUSwe report answer accuracy under the official
grader template; for WIDESEARCHwe report the
item-level F1 for the final table, which credits par-
tially collected atomic facts.
4.2 Proxy-Query Ablation
We first fix the compaction ratio to 0.2, reducing
each compactable segment to 20% of its original
length, and compare how different proxy sources af-
fect performance. This section focuses on task per-
formance; we study runtime savings in Section 5.1.
Table 1 organizes the results into current-turn prox-
ies and one-turn-delayed future proxies. Corre-
sponding 95% bootstrap confidence intervals are
reported in Appendix Table 6.
Which current-turn proxy should we use?We
compare repeat-prefill and boundary queries for
TE, and repeat-prefill for AM. Boundary queries
are not evaluated for AM because AM fits bias
and value parameters against proxy targets; a
single boundary query provides a poorly con-
strained optimization target. For TE, the stronger
current-turn proxy depends on the benchmark.
On BROWSECOMP-PLUS, replacing repeat-prefill
with boundary queries improves Qwen3.5-4B from
32.75% to 45.25% and Gemma-4-E4B from 9.00%
to 21.50%. On WIDESEARCH, however, the two
proxies perform similarly. Boundary queries can
therefore act as useful aggregation points, but their
advantage is not universal. Their strong perfor-
mance on BROWSECOMP-PLUSis also consistent
with recent work that uses attention to an end-of-
thinking token to identify important reasoning to-
kens, as well as analyses showing that punctua-
5

## PDF Page 6

Proxy source Delay BROWSECOMP-PLUSWIDESEARCH
Qwen3.5-4B Gemma-4-E4B Qwen3.5-4B Gemma-4-E4B
Acc. Turns Acc. Turns F1 Turns F1 Turns
No compaction – 46.00 20 33.00 13 44.55 24 31.94 9
Current-turn proxies
AM Repeat-prefill 0 31.25 31 11.25 930.9528 13.63 8
TE Repeat-prefill 0 32.75 51 9.00 12 24.56 8217.1911
TE Boundary 045.254021.5012 24.29 50 15.73 11
One-turn-delayed future proxies
AM Assistant generation 1 39.75 3327.501039.5933 20.17 9
AM + repeat-prefill 143.2530 24.25 10 38.83 2921.499
AM + repeat-prefill + tool response 1 43.25 30 27.50 9 37.39 29 20.17 9
TE Assistant generation 144.003827.5010 37.34 39 25.90 11
TE + boundary 1 43.00 37 27.00 11 38.09 3526.5311
TE + boundary + tool response 1 42.25 39 26.75 1139.1435 25.39 10
Table 1: Proxy-source ablation at compaction ratio 0.2 on BROWSECOMP-PLUSand WIDESEARCH. For
BROWSECOMP-PLUS, “Acc.” is final answer accuracy; for WIDESEARCH, “F1” is the mean item-level ta-
ble F1. “Turns” is the median number of agent turns.
tion and other structural tokens can form semanti-
cally meaningful attention sinks (Choi et al., 2025;
Zhang et al., 2025a).
Does delaying compaction help?Future-turn
proxies use actual assistant-generation queries from
the next turn, so they are closer to the way the
compacted turn will be read later. Across all
four model and benchmark pairs, using one-turn-
delayed assistant-generation queries improves over
immediate repeat-prefill for both AM and TE. For
TE, delayed queries also outperform boundary
queries in three of the four pairs. The only ex-
ception is Qwen3.5-4B on BROWSECOMP-PLUS,
where immediate boundary queries reach 45.25%
accuracy, slightly above the 44.00% obtained with
delayed queries. The consistency of the results
shows that even a one-turn delay generally pro-
vides a more informative compaction signal than
proxies constructed from the current turn alone.
Should we combine proxy sources?We next
add the best available current-turn proxy to the
future-turn proxy: repeat-prefill for AM and bound-
ary queries for TE. We then add future tool-
response queries as a third source. The combi-
nation rule differs by compaction family. For TE,
each proxy source selects a fixed portion of the
token budget. For example, with two sources, half
the selected tokens come from future-turn queries
and half from boundary queries. For AM, we down-
sample each additional proxy source to the same
length as the future turn source, then concatenate
all sources as the optimization target. The results
show that more proxy sources do not automatically
help. For TE, all three configurations are within 2
points of one another for every model and bench-
mark pair, suggesting TE’s robustness to variations
in proxy source, so long as the future assistant gen-
eration is available. Overall, the configurations
perform comparably, and adding current-turn or
tool-response queries provides no reliable gain.
How does compaction change agent behav-
ior?Table 1 also shows that compaction changes
the agent’s behavior, not only its final perfor-
mance. Across both benchmarks, Qwen3.5-4B
tends to lengthen its trajectories under compaction.
Its no-compaction baselines use medians of 20
turns on BROWSECOMP-PLUSand 24 turns on
WIDESEARCH, whereas the delayed configurations
use 30-39 and 29-39 turns, respectively. In contrast,
Gemma-4-E4B remains close to its no-compaction
trajectory length on both benchmarks. The longer
Qwen3.5-4B trajectories suggest that the model
may compensate for weakened context by issu-
ing additional searches and recovering missing
evidence through the environment. We examine
this hypothesis directly in Section 5.2. This cross-
model difference reinforces that online compaction
should be evaluated as an agent-level intervention,
not only as an attention-approximation problem.
6

## PDF Page 7

1 3 5 1 3 5
Qwen + BCP
42
43
44
45
46
47Acc / F1 (%)
43.0
43.0
46.8
43.2
43.8
46.2
1 3 5 1 3 5
Qwen + WS
36
38
40
42
44
46
37.3
40.0
39.9
39.6
40.1
40.9
1 3 5 1 3 5
Gemma + BCP
28
30
32
34
27.5
29.2
29.0
27.5
30.8
30.0
1 3 5 1 3 5
Gemma + WS
20.0
22.5
25.0
27.5
30.0
32.5
25.9
28.9
27.8
20.2
23.5
24.5
(a) Delay Window Sweep
0.1 0.2 0.4 0.1 0.2 0.4
Qwen + BCP
36
38
40
42
44
46Acc / F1 (%)
37.2
45.2
44.2
40.8
43.2
43.8
0.1 0.2 0.4 0.1 0.2 0.4
Qwen + WS
32.5
35.0
37.5
40.0
42.5
45.0
34.5
38.1
40.6
33.4
39.6
43.1
0.1 0.2 0.4 0.1 0.2 0.4
Gemma + BCP
22
24
26
28
30
32
34
24.2
27.5
29.8
23.5
27.5
26.0
0.1 0.2 0.4 0.1 0.2 0.4
Gemma + WS
15
20
25
30
35
24.0
26.5
30.2
14.3
21.5
27.4
(b) Compaction Ratio Sweep
TE AM No compaction
Figure 2: Sensitivity to compaction budget and delay window. The top row varies the delay window over {1,3,5}
turns at compaction ratio 0.2; the bottom row varies the compaction ratio over {0.1,0.2,0.4} using the stronger
short-delay setting for each model and method pair. Each panel fixes one model ( Qwen3.5-4B or Gemma-4-E4B)
and benchmark (BROWSECOMP-PLUSor WIDESEARCH). Dashed lines mark the no-compaction baselines.
4.3 Sensitivity to Compaction Budget and
Delay
The previous ablation fixes the compaction ratio
and uses at most a one-turn delay. We next char-
acterize how performance varies with the mem-
ory budget and delay window. For each model–
benchmark–method combination, we select the
best-performing proxy strategy from Table 1 and
sweep either the compaction ratio or delay. Fig-
ure 2 shows the results. For the delay, we fix the
compaction ratio to 0.2 and vary the delay over 1,
3, and 5 turns. For the compaction-ratio, we vary
the ratio over 0.1, 0.2, and 0.4, using the stronger
short-delay setting between immediate compaction
and a one-turn delay for each combination.
The delay sweep shows that additional future
context helps, although the gains are not always
monotonic. For all combinations, longer delays
(3 or 5 turns) outperform the one-turn delay. On
BROWSECOMP-PLUSwith Qwen, both methods
benefit most from a five-turn delay, slightly ex-
ceeding the no-compaction baseline. In the other
settings, gains tend to peak or flatten earlier. Thus,
observing more of the agent’s future queries is gen-
erally useful, but the best delay depends on the
model, benchmark, and compaction method.
The compaction-ratio sweep shows a clearer
overall relationship with memory budget. In-
creasing the ratio from 0.1 to 0.2 improves every
model–benchmark–method combination, confirm-
ing that a ratio of 0.1 is too aggressive in these
settings. Increasing the ratio further to 0.4 im-
proves six of the eight combinations. In partic-
ular, performance increases monotonically with
budget on WIDESEARCH. The exceptions occur
on BROWSECOMP-PLUS, where Qwen3.5-4B TE
and Gemma-4-E4B AM both peak at ratio 0.2. Thus,
a larger compact cache usually improves perfor-
mance, particularly for broad search.
Takeaways.Across these experiments, current-
turn proxy choice is benchmark-dependent, and
combining proxy sources provides no reliable
gain. In contrast, delayed future-turn queries
improve performance consistently, although the
best delay varies across settings. Increasing the
memory budget also usually helps, especially on
WIDESEARCH, but a larger compact cache is not
uniformly better. Finally, AM’s additional op-
timization is not automatically beneficial under
online constraints. Despite being much simpler,
TE remains surprisingly competitive across proxy,
7

## PDF Page 8

Model Method Acc. Avg. turns Peak KV (k tokens) Serving batch Throughput (q/h)
Qwen3.5-27B
No compaction 52.50 18 612.9 8 217
AM 51.00 28 172.8 32918
TE 52.00 31 175.2 32 717
Gemma-4-31B
No compaction 48.75 13 272.1 8 217
AM 50.00 17 99.6 16364
TE 50.75 18 121.3 16 324
Table 2: Task performance and simulated serving efficiency on larger models. Accuracy, average turns, and
trajectory lengths come from batch-size-1 runs on BROWSECOMP-PLUS. Peak KV is the maximum per-turn KV
length. Serving batch is the batch used for the throughput simulation. All compaction settings use one-turn-delayed
assistant-generation queries and a compaction ratio of 0.2.
delay, and budget choices, suggesting that AM’s
richer optimization provides limited benefit when
the available proxy queries imperfectly represent
how the cache will later be used.
5 Additional Analyses
The study in Section 4 focuses on answer accu-
racy and identifies strategies that preserve most of
the no-compaction performance on smaller models.
We next study two complementary questions. First,
do these strategies preserve task performance and
improve serving efficiency on larger models? Sec-
ond, how does compaction change agent behavior
beyond final answer accuracy?
5.1 Task Performance and Serving Efficiency
on Larger Models
We extend our evaluation to Qwen3.5-27B and
Gemma-4-31B, substantially larger models from
both architectural families. We evaluate on
BROWSECOMP-PLUSat a compaction ratio of 0.2.
We compare no compaction with AM and TE us-
ing one-turn-delayed assistant-generation queries
in this section. The complete proxy-source ablation
results, including 95% confidence intervals, are re-
ported in Appendix Table 7, which demonstrate a
similar trend as the 4B models.
Table 2 reports both task performance and serv-
ing efficiency. We generate agent trajectories at
batch size 1 using our Hugging Face evaluation
code and use these runs to measure answer accu-
racy and trajectory length. To estimate how the
same workloads would execute on an optimized
inference engine, we extract the KV length and
number of generated tokens at every turn and re-
play these trajectory shapes using decode latencies
measured with SGLang (Zheng et al., 2024). This
connects the task outcomes produced by our evalua-
tion code to the memory and latency characteristics
of a production-oriented serving stack. We use
each method’s peak KV footprint to determine the
largest admissible batch and report the resulting
decode throughput. Appendix A.7 provides the
complete simulation setup.
Table 2 shows that both methods retain most
of the no-compaction task performance at larger
scale. On Qwen3.5-27B, no compaction obtains
52.50% accuracy, compared with 51.00% for AM
and 52.00% for TE. On Gemma-4-31B, both meth-
ods slightly exceed the baseline, which partly re-
flects the fact that some no-compaction trajectories
run out of memory even at batch size 1, whereas
compaction keeps their KV caches within the limit.
For Qwen3.5-27B, compaction reduces peak KV
from 612.9K tokens to about 175K tokens. This
raises the guaranteed serving batch from 8 to 32.
As a result, aggregate throughput increases from
217 queries/hour without compaction to 918 with
AM and 717 with TE, corresponding to 4.2 ×
and 3.3× improvements. On Gemma-4-31B, peak
KV falls from 272.1K tokens to 99.6K with AM
and 121.3K with TE. The serving batch increases
from 8 to 16, raising throughput by 1.7 × and
1.5×, respectively. The gains are smaller than for
Qwen3.5-27B, but the same pattern holds across
both models: compaction reduces the memory foot-
print enough to support more concurrent requests.
Thus, even though the compacted agents take more
turns on average, the increase in concurrency off-
sets the additional decode work, yielding higher
overall throughput in queries per hour.
5.2 Behavioral Effects of Compaction
Section 4 shows that compaction changes the
agent’s trajectory turns for Qwen3.5-4B. One hy-
pothesis is that the model compensates for weak-
ened context by issuing additional searches, repeat-
ing similar queries to recover information that was
8

## PDF Page 9

Method NN Sim. Duplicate
No compaction 0.72 11.7%
TE-boundary 0.78 21.3%
AM-delay+RP 0.75 16.7%
Table 3: Search-query repetition within agent trajecto-
ries. “NN Sim.” is the average nearest-neighbor sim-
ilarity to earlier search queries in the same trajectory.
“Duplicate” is the percentage of search queries whose
nearest earlier query has similarity above 0.9.
previously retrieved. We test this from the search
queries generated in each trajectory.
For each search query, we compute its maximum
cosine similarity to earlier search queries in the
same trajectory using the same embedding model
as the retrieval server. We report the mean nearest-
neighbor similarity and the fraction of queries
whose similarity to a previous query exceeds 0.9.
Table 3 shows that compaction increases both mea-
sures. These results show that the accuracy of
compacted agents can partly come from behavioral
adaptation. In particular, the compaction preserves
answer accuracy but also induces more repeated
search, suggesting that the agent uses the environ-
ment to recover information weakened by com-
paction. Thus, online KV compaction should be
evaluated not only by model-side memory savings
and final accuracy, but also by how it changes the
agent’s interaction pattern with the environment.
6 Conclusion
We study online KV-cache compaction for LLM
agents, where context is accumulated through in-
teraction and future relevance is unknown at com-
paction time. Across token eviction and attention
matching, proxy choice is central: boundary tokens
provide a strong immediate signal, while delayed
future-generation queries can further improve com-
paction. Our results also show that compaction
changes agent behavior, so practical memory sys-
tems should consider not only compression and
accuracy, but also downstream trajectories.
Limitations
Our study has several limitations. First, we fo-
cus on BROWSECOMP-PLUSand WIDESEARCH,
where agents gather evidence through search and
document-reading tools. This setting captures long-
horizon information gathering, but does not cover
other agent workloads such as code editing, GUI
control, or state-changing web tasks, where the
structure of future relevance may differ.
Second, we intentionally restrict the study to
cheap online proxy sources for TE and AM. More
expensive approaches, including additional roll-
outs, learned compressors, or gradient-based opti-
mization, may produce stronger compact caches
under larger latency budgets. These methods are
complementary to our low-overhead online setting.
Third, we evaluate fixed compaction ratios and
delay windows rather than adaptive policies. A
deployed agent system could choose when and how
aggressively to compact based on memory pressure,
turn length, tool type, or uncertainty. Future work
can explore such adaptive controllers, while our
results identify strong proxy-query primitives and
the tradeoffs they should account for.
Potential Risks and Use of Artifacts
Our work studies online KV-cache compaction for
LLM agents, with the goal of reducing inference
cost while preserving agent accuracy. The main
risk is that compaction can remove or weaken infor-
mation that the agent later needs. In deployment,
this may lead to incorrect final answers, redundant
tool use, or overconfident responses based on in-
complete context. Our experiments therefore evalu-
ate both task accuracy and agent behavior, and the
proposed methods should be used with appropriate
validation in high-stakes applications.
We use existing public research artifacts con-
sistently with their intended purposes. The eval-
uation data comes from BROWSECOMP-PLUS
and WIDESEARCH, which are released on Hug-
ging Face. The evaluated models, Qwen3.5 and
Gemma-4, are released under Apache-2.0 licenses,
as is the Qwen3-Embedding-4B retrieval model.
Our implementation builds on open-source soft-
ware including Hugging Face Transformers, re-
leased under Apache-2.0, and FAISS, released un-
der the MIT license.
AI Usage Disclosure
We used AI assistants to help debug code and adapt
open-source implementations for our experiments.
We also used AI assistants to polish the paper writ-
ing. All technical decisions, experimental designs,
and analysis were made by the authors.
9

## PDF Page 10

References
Joshua Ainslie, James Lee-Thorp, Michiel de Jong,
Yury Zemlyanskiy, Federico Lebrón, and Sumit Sang-
hai. 2023. Gqa: Training generalized multi-query
transformer models from multi-head checkpoints.
Preprint, arXiv:2305.13245.
Anthropic. 2026. Introducing claude opus 4.7. Ac-
cessed: 2026-05-24.
Zefan Cai, Yichi Zhang, Bofei Gao, Yuliang Liu,
Yucheng Li, Tianyu Liu, Keming Lu, Wayne Xiong,
Yue Dong, Junjie Hu, and Wen Xiao. 2025. Pyra-
midkv: Dynamic kv cache compression based
on pyramidal information funneling.Preprint,
arXiv:2406.02069.
Zijian Chen, Xueguang Ma, Shengyao Zhuang, Ping
Nie, Kai Zou, Andrew Liu, Joshua Green, Kshama
Patel, Ruoxi Meng, Mingyi Su, Sahel Shari-
fymoghaddam, Yanxi Li, Haoran Hong, Xinyu
Shi, Xuye Liu, Nandan Thakur, Crystina Zhang,
Luyu Gao, Wenhu Chen, and Jimmy Lin. 2025.
Browsecomp-plus: A more fair and transparent eval-
uation benchmark of deep-research agent.Preprint,
arXiv:2508.06600.
Alexis Chevalier, Alexander Wettig, Anirudh Ajith, and
Danqi Chen. 2023. Adapting language models to
compress contexts.Preprint, arXiv:2305.14788.
Daewon Choi, Jimin Lee, Jihoon Tack, Woomin Song,
Saket Dingliwal, Sai Muralidhar Jayanthi, Bhavana
Ganesh, Jinwoo Shin, Aram Galstyan, and Sra-
van Babu Bodapati. 2025. Think clearly: Improv-
ing reasoning via redundant token pruning.Preprint,
arXiv:2507.08806.
Chenglong Chu, Guorui Zhou, Guowang Zhang, Han Li,
Hao Peng, Hongtao Cheng, Jian Liang, Jiangxia Cao,
Kun Gai, Lingzhi Zhou, Lu Ren, Qi Zhang, Ruiming
Tang, Ruitao Wang, Xinchen Luo, Yi Su, Zhiyuan
Liang, Ziqi Wang, Boyang Ding, and 19 others. 2026.
Kwai summary attention technical report.Preprint,
arXiv:2604.24432.
DeepSeek-AI, Aixin Liu, Bei Feng, Bin Wang, Bingx-
uan Wang, Bo Liu, Chenggang Zhao, Chengqi Dengr,
Chong Ruan, Damai Dai, Daya Guo, Dejian Yang,
Deli Chen, Dongjie Ji, Erhang Li, Fangyun Lin, Fuli
Luo, Guangbo Hao, Guanting Chen, and 138 others.
2024. Deepseek-v2: A strong, economical, and effi-
cient mixture-of-experts language model.Preprint,
arXiv:2405.04434.
Alessio Devoto, Maximilian Jeblick, and Simon Jégou.
2025. Expected attention: Kv cache compression by
estimating attention from future queries distribution.
Preprint, arXiv:2510.00636.
Sabri Eyuboglu, Ryan Ehrlich, Simran Arora, Neel
Guha, Dylan Zinsley, Emily Liu, Will Tennien, Atri
Rudra, James Zou, Azalia Mirhoseini, and Christo-
pher Re. 2025. Cartridges: Lightweight and general-
purpose long context representations via self-study.
Preprint, arXiv:2506.06266.
Bin Gao, Zhuomin He, Puru Sharma, Qingxuan Kang,
Djordje Jevdjic, Junbo Deng, Xingkun Yang, Zhou
Yu, and Pengfei Zuo. 2024. Cost-efficient large lan-
guage model serving for multi-turn conversations
with cachedattention.Preprint, arXiv:2403.19708.
Suyu Ge, Yunan Zhang, Liyuan Liu, Minjia Zhang,
Jiawei Han, and Jianfeng Gao. 2024a. Model tells
you what to discard: Adaptive kv cache compression
for llms.Preprint, arXiv:2310.01801.
Tao Ge, Jing Hu, Lei Wang, Xun Wang, Si-Qing Chen,
and Furu Wei. 2024b. In-context autoencoder for con-
text compression in a large language model.Preprint,
arXiv:2307.06945.
Google. 2026. Gemini 3.5: Frontier intelligence with
action. Accessed: 2026-05-24.
Google DeepMind. 2026. Gemma 4 model
card. https://ai.google.dev/gemma/docs/
core/model_card_4. Accessed: 2026-05-24.
Coleman Hooper, Sehoon Kim, Hiva Mohammadzadeh,
Michael W. Mahoney, Yakun Sophia Shao, Kurt
Keutzer, and Amir Gholami. 2025. Kvquant: To-
wards 10 million context length llm inference with
kv cache quantization.Preprint, arXiv:2401.18079.
Hao Kang, Qingru Zhang, Souvik Kundu, Geonhwa
Jeong, Zaoxing Liu, Tushar Krishna, and Tuo Zhao.
2024. Gear: An efficient kv cache compression
recipe for near-lossless generative inference of llm.
Preprint, arXiv:2403.05527.
Jang-Hyun Kim, Jinuk Kim, Sangwoo Kwon, Jae W.
Lee, Sangdoo Yun, and Hyun Oh Song. 2025. Kvzip:
Query-agnostic kv cache compression with context
reconstruction.Preprint, arXiv:2505.23416.
Hanchen Li, Runyuan He, Qiuyang Mang, Qizheng
Zhang, Huanzhi Mao, Xiaokun Chen, Hangrui Zhou,
Alvin Cheung, Joseph Gonzalez, and Ion Stoica.
2026. Continuum: Efficient and robust multi-turn
llm agent scheduling with kv cache time-to-live.
Preprint, arXiv:2511.02230.
Yucheng Li, Huiqiang Jiang, Qianhui Wu, Xufang Luo,
Surin Ahn, Chengruidong Zhang, Amir H. Abdi,
Dongsheng Li, Jianfeng Gao, Yuqing Yang, and Lili
Qiu. 2025. Scbench: A kv cache-centric analysis of
long-context methods.Preprint, arXiv:2412.10319.
Yuhong Li, Yingbing Huang, Bowen Yang, Bharat
Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle Cai,
Patrick Lewis, and Deming Chen. 2024. Snapkv:
Llm knows what you are looking for before genera-
tion.Preprint, arXiv:2404.14469.
Zichang Liu, Aditya Desai, Fangshuo Liao, Weitao
Wang, Victor Xie, Zhaozhuo Xu, Anastasios Kyril-
lidis, and Anshumali Shrivastava. 2023. Scis-
sorhands: Exploiting the persistence of importance
hypothesis for llm kv cache compression at test time.
Preprint, arXiv:2305.17118.
10

## PDF Page 11

Jesse Mu, Xiang Lisa Li, and Noah Goodman. 2024.
Learning to compress prompts with gist tokens.
Preprint, arXiv:2304.08467.
OpenAI. 2026. Introducing gpt-5.5. Accessed: 2026-
05-24.
OpenClaw. 2026. Openclaw — personal ai assis-
tant. https://github.com/openclaw/openclaw.
GitHub repository, accessed 2026-05-24.
Hanshi Sun, Li-Wen Chang, Wenlei Bao, Size Zheng,
Ningxin Zheng, Xin Liu, Harry Dong, Yuejie Chi,
and Beidi Chen. 2025. Shadowkv: Kv cache in shad-
ows for high-throughput long-context llm inference.
Preprint, arXiv:2410.21465.
Jiaming Tang, Yilong Zhao, Kan Zhu, Guangxuan Xiao,
Baris Kasikci, and Song Han. 2024. Quest: Query-
aware sparsity for efficient long-context llm inference.
Preprint, arXiv:2406.10774.
Qwen Team. 2026. Qwen3.5-omni technical report.
Preprint, arXiv:2604.15804.
Ryan Wong, Jiawei Wang, Junjie Zhao, Li Chen, Yan
Gao, Long Zhang, Xuan Zhou, Zuo Wang, Kai Xi-
ang, Ge Zhang, Wenhao Huang, Yang Wang, and
Ke Wang. 2025. Widesearch: Benchmarking agentic
broad info-seeking.Preprint, arXiv:2508.07999.
Guangxuan Xiao, Yuandong Tian, Beidi Chen, Song
Han, and Mike Lewis. 2024. Efficient streaming
language models with attention sinks.Preprint,
arXiv:2309.17453.
Yuhui Xu, Zhanming Jie, Hanze Dong, Lei Wang,
Xudong Lu, Aojun Zhou, Amrita Saha, Caiming
Xiong, and Doyen Sahoo. 2025. Think: Thin-
ner key cache by query-driven pruning.Preprint,
arXiv:2407.21018.
Dongjie Yang, XiaoDong Han, Yan Gao, Yao Hu, Shilin
Zhang, and Hai Zhao. 2024. Pyramidinfer: Pyra-
mid kv cache compression for high-throughput llm
inference.Preprint, arXiv:2405.12532.
Peitian Zhang, Zheng Liu, Shitao Xiao, Ninglu Shao,
Qiwei Ye, and Zhicheng Dou. 2024a. Long con-
text compression with activation beacon.Preprint,
arXiv:2401.03462.
Rongzhi Zhang, Kuang Wang, Liyuan Liu, Shuohang
Wang, Hao Cheng, Chao Zhang, and Yelong Shen.
2024b. Lorc: Low-rank compression for llms
kv cache with a progressive compression strategy.
Preprint, arXiv:2410.03111.
Stephen Zhang, Mustafa Khan, and Vardan Papyan.
2025a. Attention sinks: A ’catch, tag, release’ mech-
anism for embeddings.Preprint, arXiv:2502.00919.
Yanzhao Zhang, Mingxin Li, Dingkun Long, Xin Zhang,
Huan Lin, Baosong Yang, Pengjun Xie, An Yang,
Dayiheng Liu, Junyang Lin, Fei Huang, and Jingren
Zhou. 2025b. Qwen3 embedding: Advancing text
embedding and reranking through foundation models.
Preprint, arXiv:2506.05176.
Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong
Chen, Lianmin Zheng, Ruisi Cai, Zhao Song, Yuan-
dong Tian, Christopher Ré, Clark Barrett, Zhangyang
Wang, and Beidi Chen. 2023. H2o: Heavy-hitter ora-
cle for efficient generative inference of large language
models.Preprint, arXiv:2306.14048.
Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue
Sun, Jeff Huang, Cody Hao Yu, Shiyi Cao, Christos
Kozyrakis, Ion Stoica, Joseph E. Gonzalez, Clark
Barrett, and Ying Sheng. 2024. Sglang: Efficient
execution of structured language model programs.
Preprint, arXiv:2312.07104.
Zirui Liu, Jiayi Yuan, Hongye Jin, Shaochen Zhong,
Zhaozhuo Xu, Vladimir Braverman, Beidi Chen, and
Xia Hu. 2023. Kivi : Plug-and-play 2bit kv cache
quantization with streaming asymmetric quantiza-
tion.
Adam Zweiger, Xinghong Fu, Han Guo, and Yoon Kim.
2026. Fast kv compaction via attention matching.
Preprint, arXiv:2602.16284.
11

## PDF Page 12

HyperparameterQwen3.5 Gemma-4
Temperature 1.0 1.0
Top-p0.95 0.95
Top-k20 64
Presence penalty 1.5 –
Max tokens/turn 4096 4096
Max turns 100 100
Thinking mode enabled enabled
Table 4: Agent generation hyperparameters.
A Implementation Details
A.1 Package and Hardware
We implement online KV compaction in PyTorch
and Hugging Face Transformers. Experiments are
run on NVIDIA H200 GPUs. We load models
in bfloat16 and use the Transformers sdpa atten-
tion interface, which calls torch.nn.functional.
scaled_dot_product_attention. For both base-
line and online compaction methods, PyTorch dis-
patches to the cuDNN fused attention backend.
A.2 Generation Hyperparameters
Table 4 reports the decoding hyperparameters used
by the agent. We use model-specific system
prompts. For Qwen3.5, we use the original prompt.
In preliminary runs, we found that Gemma-4 often
produces short trajectories and stops searching be-
fore collecting enough evidence. We therefore use
a more explicit prompt that encourages it to search
more thoroughly.
Qwen3.5System Prompt
You are a helpful research assistant with
access to a knowledge base. Use the
provided tools to search for information
and retrieve documents to answer the user's
question thoroughly. You should search
multiple times to gather enough information
before answering.
Gemma-4-E4BSystem Prompt
You are an EXHAUSTIVE research assistant
with access to a local knowledge base via
the`local_knowledge_base_retrieval`and`
get_document`tools. Your job is to
investigate the user's question from MANY
angles, build deep evidence, and verify
every candidate answer before committing.
Giving up is NOT an option.
HARD RULES -- you MUST follow ALL of them:
1. NEVER ask the user for clarification or
more information. You already have all the
clues you need; your job is to use the
tools to find the answer.
2. SEARCH FLOOR -- You MUST issue AT LEAST
20 distinct`local_knowledge_base_retrieval
`calls before you are permitted to output
a final answer. This is a HARD floor -- the
investigation is INCOMPLETE until you
reach 20.
3. DOCUMENT−READ FLOOR. You MUST call`
get_document`AT LEAST 5 times across the
investigation to read full document content
(snippets are truncated at ~512 tokens and
the answer often sits past them).
4. NEVER GIVE UP. NEVER write phrases like
"I cannot determine", "I am unable to find
", "I do not have enough information", "
please provide more details", "based on the
available information I cannot answer", "
the knowledge base does not contain", or
anything similar. If you don't have enough
information, KEEP SEARCHING.
5. MULTI−ANGLE COVERAGE -- Each of your 20+
searches must approach the question from a
DIFFERENT angle. Never repeat a search
that already failed.
6. CROSS−VERIFY BEFORE COMMITTING. Once you
have a top candidate, you MUST issue
additional verification searches from new
angles to confirm the candidate satisfies
EVERY criterion.
7. DECOMPOSE AND DRILL. Start by
decomposing the question into all its
individual criteria. Issue focused searches
for each criterion. Then combine criteria
progressively to narrow down the candidate
set.
Remember: more searches always produce more
confident answers. The 20−search floor
exists because shallow investigation
routinely misses the correct answer in this
corpus. Stay in the search loop.
A.3 Compaction Algorithm Details
All compaction operations are applied indepen-
dently for each compacted layer and KV head.
For hybrid-attention models, we compact only
layers that own a full-attention KV cache. For
Qwen3.5, this excludes GatedDeltaNet layers. For
Gemma-4, this excludes sliding-window layers and
KV-sharing layers that do not maintain their own
KV states. Non-compacted layers keep their origi-
nal cache states.
We preserve structural special tokens and role-
boundary tokens with their original KV states. Ta-
ble 5 lists the token categories preserved for each
model family. These tokens are force-included in
the compacted cache and are not evicted by TE or
AM.
We compact completed agent turns without in-
cluding the static prompt prefix. The prefix con-
tains the system prompt, tool definitions, and user
12

## PDF Page 13

Model Category Preserved tokens
Qwen3.5Turn boundary<|im_start|>,<|im_end|>
Qwen3.5Reasoning and tools<think> , </think>, <tool_call>, </tool_call>,
<tool_response>,</tool_response>
Gemma-4Turn boundary<|turn>,<turn|>
Gemma-4Reasoning and tools<|channel> , <channel|>, <|tool_call>,
<tool_call|>, <|tool_response>,
<tool_response|>
Table 5: Structural tokens preserved verbatim during compaction.
query, and is kept uncompressed in all experiments.
Each subsequent turn is split into the assistant-side
generation and the resulting tool-response segment.
The compaction is applied separately to the two
segments.
Unlike the original AM setting, we use a uniform
compaction budget across all compacted layers and
KV heads. AM first selects compact keys using the
same proxy-query-based selection procedure as TE.
It then fits an additive attention bias and optimized
compact values independently for each compacted
layer and KV head. We add a small regularizer to
both optimization stages: a ridge penalty that biases
the attention-bias term toward zero, and a value
regularizer that biases the optimized values toward
the selected original values. Both regularization
weights are set to 10−3 with spectral scaling by
default.
A.4 Evaluation Details
For the proxy-source ablation and sweep,
we evaluate on the first 400 examples of
BROWSECOMP-PLUSand all 200 examples of
WIDESEARCH. For BROWSECOMP-PLUS, the
local retrieval server uses FAISS nearest-neighbor
search over the BROWSECOMP-PLUScorpus
with Qwen3-Embedding-4B embeddings, returning
the top 5 documents with snippets truncated to
512 tokens. For WIDESEARCH, we use Bing
Web Search API for the open internet search.
Final answers are judged with the official grading
template usingQwen3.5-397B-A17B.
A.5 Bootstrap Confidence Intervals
We estimate uncertainty using 10,000 example-
level bootstrap iterations. Each iteration resam-
ples 400 and 200 questions with replacement on
BROWSECOMP-PLUSand WIDESEARCH, respec-
tively. Table 6 reports the point estimates and 95%
bootstrap confidence intervals.
A.6 Full Results on Larger Models
Table 7 reports the complete proxy-source ablation
forQwen3.5-27BandGemma-4-31B.
A.7 Larger-Model Serving Simulation
We simulate serving for the same 400
Qwen3.5-27B and Gemma-4-31B trajectories
used to measure task performance in Section 5.1.
For every assistant turn, we record the KV length
attended during decoding and the number of tokens
generated. Replaying these realized trajectory
shapes ensures that the quality and efficiency
results describe the same generations.
For Qwen3.5-27B, we measure latency with
SGLang 0.5.15.post1, using tensor parallelism of
two, FP8 model weights, and an FP8 KV cache.
With a static memory fraction of 0.95, the en-
gine exposes a KV pool of 6,903,905 tokens. For
Gemma-4-31B, we use vLLM 0.19.1.1 with FP8
weights and KV cache. The engine exposes a hy-
brid KV pool of 489,712 tokens. We use vLLM for
Gemma because it provides stable, preemption-free
serving for the model’s interleaved full-attention
and sliding-window layers. We measure per-
step decode latency using synthetic random-token
prompts at the batch sizes considered in Table 2.
Latencies between measured context lengths are
linearly interpolated.
For Qwen, let P be the largest per-turn KV
length. A batch of size B is guaranteed to fit when
BP does not exceed the KV pool. The largest ad-
missible integer batches are 11, 39, and 38 for no
compaction, AM, and TE, respectively; we use the
corresponding power-of-two batches 8, 32, and 32.
For Gemma, the largest admissible batches are 13
without compaction, 34 with AM, and 28 with TE.
We use batch 8 for no compaction and batch 16
13

## PDF Page 14

Proxy source Delay BROWSECOMP-PLUSWIDESEARCH
Qwen3.5-4B Gemma-4-E4B Qwen3.5-4B Gemma-4-E4B
Acc. 95% CI Acc. 95% CI F1 95% CI F1 95% CI
No compaction – 46.00 [41.50, 51.25] 33.00 [28.25, 37.50] 44.55 [39.65, 49.30] 31.94 [28.11, 35.76]
Current-turn proxies
AM Repeat-prefill 0 31.25 [26.75, 35.75] 11.25 [8.25, 14.50]30.95[27.00, 34.93] 13.63 [11.17, 16.27]
TE Repeat-prefill 0 32.75 [28.00, 37.50] 9.00 [6.25, 12.00] 24.56 [20.36, 28.80]17.19[14.64, 19.91]
TE Boundary 045.25[40.50, 50.00]21.50[17.50, 25.50] 24.29 [20.76, 27.91] 15.73 [13.14, 18.46]
One-turn-delayed future proxies
AM Assistant generation 1 39.75 [34.75, 44.25]27.50[23.25, 32.00]39.59[35.32, 43.81] 20.17 [17.15, 23.34]
AM + repeat-prefill 143.25[38.50, 48.00] 24.25 [20.00, 28.50] 38.83 [34.61, 42.96]21.49[18.25, 24.89]
AM + repeat-prefill + tool response 1 43.25 [38.50, 48.00] 27.50 [23.25, 32.00] 37.39 [33.18, 41.59] 20.17 [17.00, 23.53]
TE Assistant generation 144.00[39.25, 48.75]27.50[23.25, 32.00] 37.34 [32.86, 41.75] 25.90 [22.66, 29.19]
TE + boundary 1 43.00 [37.75, 47.25] 27.00 [22.75, 31.50] 38.09 [33.74, 42.40]26.53[23.32, 29.92]
TE + boundary + tool response 1 42.25 [37.25, 46.75] 26.75 [22.50, 31.00]39.14[34.84, 43.50] 25.39 [22.23, 28.71]
Table 6: Task performance with 95% bootstrap confidence intervals. The table follows the same setting as Table 1.
Proxy source Delay Qwen3.5-27B Gemma-4-31B
Acc. (95% CI) Avg. turns Acc. (95% CI) Avg. turns
No compaction – 52.50 [47.50, 57.25] 18 48.75 [43.75, 53.50] 13
Current-turn proxies
AM Repeat-prefill 0 42.25 [37.50, 47.00] 44 44.75 [40.00, 49.50] 15
TE Repeat-prefill 0 41.75 [37.00, 46.50] 7248.25 [43.50, 53.00]19
TE Boundary 048.25 [43.50, 53.00]33 43.00 [38.25, 48.00] 20
One-turn-delayed future proxies
AM Assistant generation 151.00 [46.00, 55.75]2850.00 [45.25, 55.00]17
AM + repeat-prefill 1 46.25 [41.50, 51.00] 21 47.75 [43.00, 52.50] 12
AM + repeat-prefill + tool response 1 47.75 [43.00, 52.75] 23 45.00 [40.00, 49.75] 12
TE Assistant generation 152.00 [47.25, 56.75]31 50.75 [46.00, 55.75] 18
TE + boundary 1 49.00 [44.00, 53.75] 3852.75 [48.00, 57.50]16
TE + boundary + tool response 1 46.75 [42.00, 51.75] 37 50.75 [46.00, 55.75] 17
Table 7: Full proxy-source results at compaction ratio 0.2 on BROWSECOMP-PLUSfor the larger models.
for both compacted methods. Although batch 32 is
admissible for AM, it has a lower throughput than
batch 16 because the used Gemma decode kernels
become less efficient at the larger batch.
14