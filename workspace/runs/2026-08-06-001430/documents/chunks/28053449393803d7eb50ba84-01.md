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