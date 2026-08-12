# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

## PDF Page 1

Sangam: Efficiently Serving Diffusion LLMs with the
AR Stack
Nitin Kedia
The University of Texas at Austin
Austin, United States
Saurabh Agarwal
The University of Texas at Austin
Austin, United States
Myungjin Lee
Cisco Research
Bellevue, United States
Aditya Akella
The University of Texas at Austin
Austin, United States
Abstract
Diffusion language models (dLLMs) generate text by itera-
tively denoising a masked response and can commit multiple
output positions per model invocation. Their bidirectional
attention prevents exact autoregressive-style KV caching,
since committing one position shifts the KV activations of all
others. Approximate caching techniques such as Fast-dLLM
and dKV-Cache refresh KV activations repeatedly and reuse
them across intervening decodes, inducing a repeated pre-
fill/decode structure. This makes AR serving mechanisms
relevant to dLLMs, but not directly applicable. dLLM de-
codes are block-sized rather than token-sized, prefills re-
cur, and bidirectional attention precludes the chunked pre-
fill mechanism used for stall-free colocated serving. We
present Sangam, a serving system for cached dLLM infer-
ence. Sangam introduces a deficit token-budget scheduler
that admits in-flight decodes first, admits whole indivisible
prefills only when the accumulated token budget allows, and
carries unused budget forward. This achieves amortized stall-
free scheduling. Disaggregated serving avoids prefill-decode
interference but suffers from prefill/decode resource parti-
tioning problem. Sangam adopts a hybrid serving strategy,
overflowing prefills onto decode workers to relieve prefill
under-provisioning, and uses the same deficit-budget sched-
uler to protect those workers’ decodes from the overflow. We
show that like AR serving, dLLM serving design space is gov-
erned by prefill-decode interference and prefill/decode parti-
tioning. Colocated serving is most effective on decode-heavy
workloads, cutting mean latency by 9-20% over hybrid execu-
tion on LLaDA-8B ShareGPT; while hybrid execution is most
effective on prefill-heavy workloads, cutting mean latency by
8-20% over colocated execution on Dream-7B arXiv. Sangam
is available athttps://github.com/UT-InfraAI/sangam.
1 Introduction
Diffusion language models (dLLMs) [31, 39, 53] are a recent
alternative to autoregressive (AR) language models. This
model class is gaining rapid traction: beyond open-weight
model series such as LLaDA [8, 29, 31] and Dream [52, 53],
commercial releases including Google’s DiffusionGemma [33],
Inception’s Mercury [19], and ByteDance’s Seed Diffusion [43]
advertise single-request generation speedups of 4-10×over
comparable AR models. We study efficient serving of dLLMs
under concurrent requests.
AR models generate text one token at a time from left
to right. A masked-diffusion language model [ 39] instead
appends a fixed-length response region, initialized as[MASK]
tokens, to the prompt and iteratively denoises that region.
Each denoising iteration runs a Transformer [47] forward
pass over the prompt and response, predicts tokens for the
masked positions, and commits a subset of those positions in
parallel.

## Evidence locator: PDF Page 6

## PDF Page 6

Kedia et al.
3.3 Static prefill-decode worker partitioning is
fragile
Disaggregation is appealing for dLLM serving because it
removes prefill-decode interference by design. This benefit
is not free: it presupposes a prefill:decode partition whose
optimum depends on the workload mix and SLO targets [28,
35, 36, 44].

## Evidence locator: PDF Page 13

## PDF Page 13

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
4 5 6 7
QPS
0
2
4
6
8Mean E2E latency (s)
Hybrid-5P3C-Low-Budget
Hybrid-5P3C-High-Budget
(a)5P3C, mean e2e latency.
4 5 6 7
QPS
0
10
20
30P99 E2E latency (s)
Hybrid-5P3C-Low-Budget
Hybrid-5P3C-High-Budget (b)5P3C, p99 e2e latency.
4 5 6 7
QPS
0
2
4
6
8Mean E2E latency (s)
Hybrid-3P5C-Low-Budget
Hybrid-3P5C-High-Budget
(c)3P5C, mean e2e latency.
4 5 6 7
QPS
0
10
20
30P99 E2E latency (s)
Hybrid-3P5C-Low-Budget
Hybrid-3P5C-High-Budget (d)3P5C, p99 e2e latency.
Figure 12.Sensitivity of hybrid scheduling to the deficit
token budget 𝜏 on LLaDA-8B with the ShareGPT trace, at
the 5P3C (top row) and 3P5C (bottom row) ratios; each row
reports mean (left) and p99 (right) end-to-end latency vs.
QPS, with a low (𝜏=1024) and a high (𝜏=4096) budget.
The reduction in p99 latencies by using low budgets is not
free. Processing overflow prefills slowly via a low budget
means the colocated workers spare less prefill capacity to
the system, so prefills queue longer in the dedicated prefill
pool and the mean end-to-end latency rises. This presents
itself in the 3P5C configuration (Figure 12c), where the prefill
pool is under-provisioned to begin with. Here the mean rises,
from about 2% higher at QPS 6 to 9% at QPS 7.5 (9.5 s against
8.7 s) as the three-worker prefill pool backs up. For the 5P3C
configuration (Figure 12a), the mean end-to-end latency is
however essentially unchanged (within a few percent) be-
cause the five-worker prefill pool is large enough to absorb
the prefill work the colocated workers no longer take on.
7 Related Work
dLLM architectures.The dLLM design space is large and
continuously expanding [22], with no single serving solution
covering it. One strain of models restores causal structure
to reduce inference footprint by exact KV caching. Block
Diffusion [5] attends causally across blocks and bidirec-
tionally within them, leading to models such as SDAR [9],
Fast-dLLM v2 [50], LLaDA2-100B [8], and IDLM [ 56]. Be-
cause these models behave exactly like an AR model at the
block level, LLM serving engines such as SGLang [58] has
added support for these dLLMs, as competitors to specula-
tive decoding [ 21, 23, 24]. Another strain of models keep
attention bidirectional, with LLaDA-8B [ 31] and Dream-
7B [52, 53] as widely used instances. An active line of work
continues to advance dLLMs through new model architec-
tures [12, 16, 38, 40], sampling strategies [ 7, 18, 57], and
scaling laws [15, 30, 48].
We pick two popular, representative scenarios, LLaDA-8B
and Dream-7B with Fast-dLLM blockwise caching, to make
a methodological point: approximate KV caching induces a
cyclic prefill/decode structure in dLLM inference and makes
it amenable to the AR serving stack. We then identify the
critical differences, block-sized decodes, recurring prefills,
and the absence of chunked prefill, and adapt the stack to
them. Because this cyclic structure is shared by any cached
dLLM, including block-causal models that simply re-prefill
less often, the same mechanisms and the same partitioning-
versus-interference analysis carry across the class.
dLLM serving engines.To our knowledge, dInfer [ 27]
and dLLM-Serve [ 11] are the only other serving engines
built for LLaDA-8B and Dream-7B. dInfer contributes paral-
lel decoding strategies, approximate K/V caching, and kernel
optimizations, evaluated at batch size 1. Its optimizations tar-
get the decoding algorithm and are orthogonal to Sangam’s
scheduling, so we do not compare directly. dLLM-Serve like-
wise centers on algorithmic techniques such as decomposing
transient logit peaks and sparsifying attention storage and
proposes a vLLM-style prefill-prioritizing policy for prefill-
decode (termed as "refresh-reuse") scheduling. We reproduce
this prefill-prioritizing policy as the 𝜏= 16384colocated
configuration in § 6.4, rather than comparing against the
dLLM-Serve codebase, which is tightly coupled with its other
algorithmic proposals, and show it incurs the prefill-decode
interference that motivates this work.
8 Conclusion
Approximate KV caching gives diffusion language models
a repeated prefill/decode structure, making the AR serving
stack a useful starting point for dLLM serving. However,
cached dLLMs violate several assumptions behind that stack:
decodes operate on response blocks rather than single tokens,
prefills recur at block boundaries or cache-refresh points,
and bidirectional attention prevents chunked prefill. Sangam
addresses these differences with a deficit token-budget sched-
uler that provides amortized stall-free colocated serving for
indivisible dLLM prefills, and with a serving architecture
that supports colocated, static disaggregated, and hybrid pre-
fill/decode execution under one implementation.

## Evidence locator: PDF Page 11

## PDF Page 11

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
Disaggregated Serving.Disaggregated dedicates fixed
pools to each phase (five prefill, three decode here) to re-
move prefill-decode interference and hence keep decode
times low. The cost is a resource partitioning problem: be-
cause the split is static, instantaneous load fluctuations on the
prefill side, from new request arrivals and data-dependent re-
prefills, queue up behind the five prefill workers. On LLaDA-
8B ShareGPT (Figure 10a) this prefill queueing delay reaches
6.3 s p90 and 11.6 s p99, against 2.6 s and 6.4 s for colocated.
The same partitioning problem surfaces on Dream-7B arXiv
too, but only at the highest load, where disaggregated’s pre-
fill pool saturates at QPS 9.5 and its mean latency jumps to
7.2 s against colocated’s 5.8 s (Figure 9d). Static partitioning
doesn’t always face imbalance though. On Dream-7B arXiv,
disaggregated has lesser prefill queueing than colocated as
the model, workload, and partitioning align Figure 10c.
Colocated Serving.Colocated lets every worker run both
phases, so it intrinsically absorbs load fluctuations, avoid-
ing the prefill queue. But a small token budget nevertheless
would result in high prefill queueing delay. This is seen in
LLaDA-8B ShareGPT (Figure 10a), where colocated has the
lowest prefill queueing delay across the CDF. For Dream-7B
arXiv (Figure 10c) , 𝜏=1024the budget is not enough for this
trace so prefill queueing delay is highest. On the decode side,
colocated spreads decodes across all eight workers, shrinking
decode batch sizes and thus decode batch times. For autore-
gressive models this would under utilize the GPU compute,
but dLLM decodes are heavy enough that a handful of them
saturate GPU utilization (§ 3.1). Decodes also experience
interference in colocated which is controlled by the token
budget. The net decode cost is model and workload depen-
dent. On prefill-heavy Dream-7B arXiv (Figure 10d), with
long prompts and few decodes, interference dominates and
disaggregated keeps the lowest decode time (5.6 s p99 against
colocated’s 7.3 s). On the decode-heavy LLaDA-8B ShareGPT
trace (Figure 10b) spreading roughly offsets interference and
the two are close at the median (2.5 s versus 2.7 s).
Hybrid Serving.Hybrid-5P3C replaces the dedicated de-
code workers with tight-budget colocated workers, so when
its prefill pool saturates the overflow path spreads prefills
across all GPUs. It therefore drains prefill queueing in every
case: on LLaDA-8B ShareGPT it matches colocated (6.4 s p99,
well below disaggregated’s 11.6 s), and on Dream-7B arXiv it
is the lowest of the three (1.1 s p99). The cost is interference
between overflow prefills and the decodes on those colocated
workers, which lifts hybrid decode time above disaggregated
(18.3 s versus 16.6 s p99 on ShareGPT, 6.2 s versus 5.6 s on
arXiv). Overall, hybrid matches or improves the mean end-
to-end latency over pure disaggregated in all cases and tracks
its tail closely.
Finally, KV Cache transfer in disaggregated and hybrid is
a negligible overhead with p99 value at 384 ms on LLaDA-8B
ShareGPT and 192 ms on Dream-7B arXiv against multi-
second decodes due to fast intra-node links. One can argue
that inter-node bandwidths are lower, but this can offset by
layerwise KV streaming and transfer-decode overlap [35, 45,
46], which we do not employ. Prior work also indicates that
KV transfer is not the primary bottleneck in disaggregated
serving [28].
6.4 Colocated Scheduling
We demonstrate that deficit token budget based colocated
scheduling reduces request decode times by reducing prefill-
decode interference, and that the budget trades tail latency
against the lower percentiles: a lower budget reduces the
tail at the cost of raising the median, and vice versa. To
do this we evaluate a suite of iteration token budgets 𝜏∈
{512, 1024, 2048, 16384}. 𝜏=512is the smallest per-iteration
budget we test where most prefills are deferred for several
iterations until carryover budget accumulates. As 𝜏 grows
the scheduler admits prefills more eagerly, and at𝜏=16384
the budget is high enough that any prefill is processed in
the immediate next iteration of its arrival (when memory
capacity is also available), so the scheduler degenerates to
the prefill-prioritizing behavior of Orca [55] and vLLM [20].
This prefill-prioritizing budget is an in-system realization of
dLLM-Serve’s [11] refresh-reuse policy, reproduced under
identical model, trace, and hardware.
Figure 11 reports, for every (model, trace) pair, a p99 end-
to-end latency curve wrt. load (top row) and the end-to-end
latency breakdown of a mean and a tail (p99) request at one
specific QPS (bottom row), representative of the scheduler
behavior. The breakdown picks a single request id within
a small band around every budget’s own e2e latency (one
at p50, and another at p99), widening the band until one id
qualifies in all of them. Each iteration has a prefill budget
according the value of 𝜏, so as QPS rises the arrival rate of
fresh prefills and re-prefills outpaces what the scheduler can
admit.

## Evidence locator: PDF Page 12

## PDF Page 12

Kedia et al.
Colocated-512 Colocated-1024 Colocated-2048 Colocated-16384
4 5 6 7
QPS
0
10
20
30P99 E2E latency (s)
(a)LLaDA-8B, ShareGPT
4 5 6 7 8
QPS
0
5
10
15
20P99 E2E latency (s)
 (b)LLaDA-8B, arXiv
4 5 6 7 8
QPS
0
10
20
30P99 E2E latency (s)
 (c)Dream-7B, ShareGPT
4 5 6 7 8 9
QPS
0
5
10
15
20P99 E2E latency (s)
 (d)Dream-7B, arXiv
Prefill Queueing Delay Prefill Time Decode Time Others
C-512C-1024C-16384 C-512C-1024C-16384
0
5
10
15
20
25E2E Time (s) @ 6.5 QPS
7.3
4.7 4.5
22.2
17.3 18.9
Mean P99
(e)LLaDA-8B, ShareGPT
C-1024C-2048C-16384 C-1024C-2048C-16384
0.0
2.5
5.0
7.5
10.0
12.5E2E Time (s) @ 7.5 QPS
4.5 4.1 3.9
11.2 10.4 9.9
Mean P99 (f)LLaDA-8B, arXiv
C-512C-1024C-16384 C-512C-1024C-16384
0
5
10
15
20E2E Time (s) @ 7 QPS
6.1
4.1 3.7
17.6
13.2 14.4
Mean P99 (g)Dream-7B, ShareGPT
C-1024C-2048C-16384 C-1024C-2048C-16384
0.0
2.5
5.0
7.5
10.0E2E Time (s) @ 8.5 QPS
4.0 3.6 3.4
10.0
8.9 8.7
Mean P99 (h)Dream-7B, arXiv
Figure 11.Deficit token-budget sweep 𝜏∈ { 512, 1024, 2048, 16384} for colocated serving. The top row reports a p99 end-to-end
latency load curve (vs. QPS) for each (model, trace) pair across all four budgets. The bottom row decomposes a single mean
and tail (p99) request, taken at one fixed QPS in that pair’s stable regime, into prefill queueing delay, prefill time, decode time,
and other. Columns are (model, trace) pairs.
the opposite way: at 𝜏=16384queueing is already negligible,
so the lower budget buys it nothing and only adds interfer-
ence, leaving the high budget with the lower mean (4.5 s
against 4.7 s on LLaDA-8B, 3.7 s against 4.

## Evidence locator: PDF Page 8

## PDF Page 8

Kedia et al.
Central Scheduler
Requests
Colocated
Worker · · ·
Colocated Worker
Prefill Queue
Decode Set
Deficit Scheduler
dLLM
Re-prefills
(a)Colocated
Hybrid Scheduler
RequestsKV Transfer
Prefill Pool
𝑁𝑃 workers
Colocated Pool
𝑁𝐶 workers
Prefill Worker
Prefill Worker
...
Decode + Overflow
Decode + Overflow
...
Nominal
Overflow
Re-prefills
(b)Hybrid
Figure 7.Sangamarchitectures. (a) Colocated: identical
workers each run prefill and decode locally under the deficit-
budget scheduler (Algorithm 1). (b) Hybrid: dedicated prefill
workers transfer KV to (primarily) decode-role colocated
workers, with prefill overflow to colocated workers when all
prefill workers exceed a load threshold𝜃.
The overflow trigger is token-based. The hybrid scheduler
tracks for each worker,𝑜𝑤 , the outstanding prefill tokens the
worker has been assigned but not yet processed. The prefill
pool is considered overloaded only wheneverynon-draining
prefill worker has 𝑜𝑤 ≥𝜃 for an operator-set threshold 𝜃
(in tokens). If prefill overflow is detected, the scheduler dis-
patches the request to the least-loaded colocated worker
that is still under 𝜃 and has free KV for it. Colocated KV
is reserved first for the requests that already finished pre-
fill and are waiting only on colocated memory to decode
(the “pending decodes” of Algorithm 2). If neither path can
take the request, the scheduler holds it on a central FIFO
pending queue and retries assignment as load or memory
frees. Colocated workers run the deficit-budget scheduler
with a tight per-iteration budget𝜏 than prefill workers, since
their primary role is decoding and overflow prefills should
be admitted only opportunistically.
Hybrid scheduler interpolates between disaggregated and
colocated serving. with 𝜃=∞, overflow never fires, so the
scheduler behaves as if purely disaggregated. With low 𝜃
and low 𝑁𝑃 /𝑁𝐶 ratio, hybrid exhibits colocated behavior as
the colocated workers run both prefills and decodes. How-
ever, it cannot achieve fully colocated behavior because the
prefill workers do not run any decodes. We deliberately omit
migrating in-flight decodes onto dedicated workers because
such decodes would suffer from uncontrolled interference
from prefills in the prefill workers.
4.3 Sangam Architecture
Based on the above design decisions, Sangam uses a two-
level architecture. A central scheduler accepts incoming re-
quests, tracks per-worker load, and routes each request (and
each block-boundary re-prefill) to a worker.