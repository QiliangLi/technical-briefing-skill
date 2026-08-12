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
parallel. For serving, this means that one model invocation
can advance generation by multiple output tokens, whereas
an AR decode invocation commits one next token.
This execution model changes the role of key-value (KV)
caching. In an AR model, causal attention makes previously
computed KV activations stable: later tokens cannot change
the KV activations of earlier tokens. A serving system can
therefore compute prompt KV once duringprefilland reuse
it across subsequentdecodesteps. dLLMs use bidirectional
attention over the full prompt-and-response sequence. When
one masked position is committed, the attention inputs for
other positions change, and their KV activations may also
change. Exact KV reuse across denoising iterations is there-
fore invalid, so a naive dLLM serving system recomputes the
full prompt-plus-response context at every iteration.
Recent dLLM acceleration techniques [25, 26, 34, 51] make
this cost more manageable through approximate KV reuse.
Fast-dLLM [51] divides the fixed response region into con-
tiguousblocks, where a block is the subset of response posi-
tions denoised before generation advances to the next con-
tiguous subset, and refreshes KV at block boundaries. dKV-
Cache [26] admits KV activations of committed response
tokens into the cache and periodically refreshes the cache to
bound approximation error. These methods make a cached
dLLM request alternate between KV-refreshing prefill phases
and cache-reusing decode iterations.
This repeated prefill/decode structure makes AR serving
mechanisms relevant to cached dLLMs. Existing AR serv-
ing systems provide continuous batching [ 55], colocated
stall-free batching [2], disaggregated prefill/decode execu-
tion [ 17, 35, 59], and paged KV-cache management [ 20].
These mechanisms address the right classes of control prob-
lems: iteration-level admission, prefill/decode interference,
1
arXiv:2607.04206v1  [cs.DC]  5 Jul 2026

## PDF Page 2

Kedia et al.
KV memory management, and placement across GPU work-
ers. However, cached dLLMs violate several assumptions that
these mechanisms rely on in AR serving. Efficient dLLM serv-
ing requires aligning these building blocks with bidirectional,
cached dLLM execution.
The first mismatch is decode cost. An AR decode con-
tributes one query token per request to an iteration. A block-
wise dLLM decode contributes an entire response block while
attending over the prompt and response context. Decode it-
eration time therefore grows much faster with batch size for
dLLMs than for comparable AR models: a handful of con-
current decodes already saturate GPU compute and memory
bandwidth, so admitting more decodes into a batch yields
little additional throughput (§ 3.1). A dLLM serving system
thus cannot singularly rely on large decode batches to in-
crease throughput the way AR systems do.
The second is recurring, request-dependent prefill work.
In AR serving, prefill is associated with request arrival. In
cached dLLM serving, a request returns to prefill at block
boundaries [51] or cache refresh points [26]. With variable
length unmasking samplers such as confidence-threshold
sampling, different requests and different blocks within the
same request may require different numbers of denoising iter-
ations before the next refresh. The scheduler must therefore
admit work at iteration granularity [55], since one request
may need to re-enter prefill while other requests continue
decoding. Prefill-decode interference can arise even without
new arrivals. AR colocated serving hides this interference
with chunked prefill [2], splitting a prefill into pieces small
enough not to stall co-batched decodes. This does not apply
to dLLMs: bidirectional attention makes every token’s KV
activation depend on the full prompt-and-response context,
so a prefill must run as one forward pass over that context
and cannot be chunked.
The third mismatch is static prefill/decode partitioning.
Disaggregated serving [17, 35, 59] removes prefill-decode
interference by assigning separate GPU pools to the two
phases but introduces a partitioning problem [ 28]. Addi-
tionally in cached dLLMs, requests cross the prefill/decode
boundary repeatedly and the balance between prefill and de-
code work depends on the trace, load, and request progress.
A fixed partition therefore creates more stranded capacity:
one phase can build a queue while workers assigned to the
other phase have spare capacity. Solutions proposed for
the general prefill/decode partitioning problem are often
coarse, operationally complex, and require a large number
of GPUs [35, 36, 44]. Conditional disaggregation [32] han-
dles prefill under-provisioning and is simple to implement,
overflowing prefills onto decode workers when the prefill
queue backs up. This does not directly carry over to dLLMs:
because decode workers are acutely sensitive to interference
from injected overflow prefills, and naive conditional dis-
aggregation for dLLMs provides no mechanism to protect
those decodes from the overflowed prefill work.
We present Sangam, a serving system for cached dLLM
inference. Sangam uses a central scheduler for cluster-level
routing and worker-local schedulers for iteration-level batch-
ing. The central scheduler routes request-arrival prefills and
cache refresh re-prefills across GPU workers using cluster-
level load information, while each worker constructs micro-
batches locally between model invocations.
The core worker-level mechanism in Sangam is a deficit
token-budget scheduler for amortized stall-free colocated
serving. Each iteration has a fixed token budget. The worker
admits in-flight decodes first, then admits a waiting prefill
only when the budget left after decodes, plus the deficit
carried over from prior iterations, can fit the whole prefill.
Unused budget carries forward as deficit, preventing starva-
tion of large indivisible prefills. Since an indivisible prefill
must enter in one iteration, per-iteration stall-free batching
is unattainable; the deficit scheme instead recovers it in an
amortized sense, without relying on chunked prefill [2]. The
budget remains an important scalability knob: smaller bud-
gets protect decode iterations from prefill interference, while
larger budgets admit prefill work more aggressively and can
sustain higher loads when prefill queueing is the bottleneck.
Building on the deficit-budget scheduler, Sangam turns
static disaggregation into a stronger design point via con-
ditional disaggregation. We call it thehybridconfiguration
which keeps a dedicated prefill pool but replaces the dedi-
cated decode workers with deficit token budget based colo-
cated workers. When the prefill pool becomes the bottleneck,
the scheduler logically overflows prefills onto these colocated
workers. For cached dLLMs this applies to both request-
arrival prefills and cache refresh re-prefills, and overflowed
prefills run under the same deficit token-budget policy so the
operator can bound their interference with ongoing decodes.
Taken together, these mechanisms let Sangam characterize
the dLLM serving design space along two fundamental prob-
lems:prefill/decode partitioningandprefill-decode interference,
as in AR serving. Colocated and disaggregated serving sit
at opposite corners of this space, the former free of parti-
tioning but exposed to interference, the latter the reverse.
We find that colocated serving is in general more suited for
dLLM serving due to block-size decodes which have high
GPU utilization at low batch sizes and data-dependent re-
curring prefills which exacerbates partitioning problems in
disaggregated serving.
Contributions.This paper’s contributions are as follows:
• We characterize cached dLLM serving as a repeated
prefill/decode execution problem and identify the AR-
serving assumptions that fail under this structure:
block-sized decodes, recurring prefills, and prefill chunk-
ing (§ 3).
• We design a deficit token-budget scheduler which mit-
igates prefill-decode interference in colocated serving
2

## PDF Page 3

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
init seq Where did the cat sit? [M] [M] [M] [M] [M] [M]
iter 1 Where did the cat sit? On [M] [M] [M] [M] [M]
iter 2 Where did the cat sit? On the [M] mat [M] [M]
iter 3 Where did the cat sit? On the [M] mat EOS [M]
iter 4 Where did the cat sit? On the warm mat EOS [M]
Figure 1.Diffusion LLM inference for the prompt "Where
did the cat sit?" and response "On the warm mat". A dLLM
appends a fixed-length block ofmasktokens (shown as [M])
to the prompt and unmasks a subset of positions in parallel
and out of order each iteration. Generation stops onceeosis
committed (iter 3) and every position before it is unmasked
(iter 4); positions aftereosare ignored.
for dLLMs without relying on chunked prefill, which
bidirectional attention precludes (§ 4.1).
• We implement Sangam and evaluate colocated, static
disaggregated, and hybrid serving on two open-weight
dLLMs and two trace-driven workloads, showing the
regimes where each mode is effective and explain-
ing why by identifying prefill/decode partitioning and
prefill/decode interference as the two fundamental
factors (§ 6.3).
• We demonstrate that hybrid scheduling with deficit
token budgets can be used as a simple augmentation
to static disaggregated deployments, keeping their
performance in prefill heavy workloads and signifi-
cantly improving their performance in decode heavy
workloads (§§ 6.3 and 6.5).
2 Background
We first describe the dLLM architecture and inference.
2.1 dLLM Architecture and Inference
dLLMs are masked-diffusion sequence models [ 6, 39, 41]
that treat generation as iterative denoising rather than next-
token prediction. Architecturally, they reuse the Transformer
decoder blocks [47]. However, the causal mask is dropped
so tokens attend bidirectionally over the full prompt-and-
response.
A request supplies a prompt 𝑝 and a maximum genera-
tion length 𝐿. The response is initialized to 𝐿[MASK] tokens
which are progressively unmasked using several denoising
steps. Each step runs a forward pass with the full sequence of
[𝑝; 𝐿] tokens, predicts a token distribution at every masked
position in parallel, andunmasksa subset of those predic-
tions while keeping the rest masked. Unlike an AR model,
which commits one new token left to right per iteration,
a dLLM appends a fixed-length block of [MASK] tokens to
the prompt and unmasks positions in parallel and out of
order until the response is complete (Figure 1). Each such
denoising step is structurally an AR-styleprefill: it is typ-
ically compute-bound. KV caching, a standard strategy in
AR serving, does not directly apply: because attention in
dLLM is bidirectional, unmasking a single position in one
step shifts the keys and values of every other token in the
next step.
2.2 Caching in dLLM Inference
Recent dLLM serving optimizations, such as Fast-dLLM [51]
and dKV-Cache [26], observe that KV activations remain
sufficiently stable across adjacent denoising steps to permit
approximately lossless caching. Figure 2 summarizes the ex-
ecution state machines these regimes induce. This caching
avoids the naive dLLM approach of executing a full-sequence
prefill at every step (Figure 2b). Instead, these systems rein-
troduce a decode state by reusing KV caches over short
windows, occasionally forcing a return to the prefill state to
refresh the cache and bound activation drift (Figure 2c).
Fast-dLLM achieves this via blockwise unmasking, which
trades any-order expressivity for cacheability by constrain-
ing generation to advance autoregressively across token
blocks. The cache is fully recomputed at each block bound-
ary and reused for all internal denoising steps. In contrast,
dKV-Cache [26] preserves any-order diffusion by caching
at the per-token level. Using itsdKV-Cache-PDvariant, the
prompt KV is computed once and fixed, while the KV of de-
coded response tokens is intermittently refreshed to prevent
drift.
Consequently, both schedules transform the dLLM request
lifecycle into a cyclic prefill-decodes-prefill pattern, funda-
mentally diverging from the standard AR model of a single
prefill followed by many lightweight decodes (Figure 2a).
These dLLM "decodes" are vastly more computationally in-
tensive than their AR counterparts. Because a dLLM decode
involves a multi-token forward pass attending to nearly the
entire sequence length, its per-step cost more closely resem-
bles a small AR chunked prefill [2]. Caching makes dLLM
execution resemble AR serving closely enough to inherit
much of its optimization literature, but the resemblance is
not exact. The cyclic recurrence of heavy decodes and forced
prefills, together with bidirectional attention, breaks assump-
tions embedded in AR infrastructure, so importing these
techniques demands substantial system-level adaptation.
2.3 LLM Serving
Before introducing challenges for serving dLLMs using AR
serving stack, we briefly explain the key techniques.
Continuous Batching.Orca [ 55] introducedcontinuous
batching, which dynamically schedules requests per model
iteration to minimize queue delay and prevent lifetime batch
locking. However, co-scheduling newly arrived prefills with
in-flight decodes introducesprefill-decode interference. Pre-
fills are compute-bound operations over large prompt se-
quences, whereas decodes are memory-bound single-token
3

## PDF Page 4

Kedia et al.
Prefill Decode
(a)Autoregressive LLM.
Prefill
(b)Naive diffusion LLM.
Prefill Decode
(c)Cached diffusion LLM.
Figure 2.Execution state machines for three LLM serving regimes. The autoregressive baseline (a) prefills once and then
decodes one token at a time. A naive diffusion LLM (b) re-runs prefill at every denoising step. Adding a KV cache to the diffusion
model (c) reintroduces a decode state but still requires an occasional return to prefill when the cache must be refreshed.
operations. Mixing them forces the shared iteration time to
scale with the incoming prompt length, meaning a newly
admitted prefill causes multi-secondgeneration stalls[ 2] for
all concurrently decoding requests.
Disaggregated Serving.To solve this interference problem,
one solution is disaggregated serving [17, 35, 59] which takes
thephysicalroute of processing prefill and decode onto dis-
joint GPU pools so the two phases never share an iteration.
The KV state produced by a prefill worker is transferred to
a decode worker before generation continues. This elimi-
nates phase-mix scheduling entirely, trading interference for
partitioning, placement, and KV migration cost.
Chunked Prefill. Another solution to the interference prob-
lem is using chunked prefill combined with stall-free batch-
ing. Sarathi-Serve [ 2] introduces these two techniques. It
takes thecolocatedroute of mitigating the stall while keep-
ing prefill and decode on the same GPU. It introduces two
ideas:chunked prefillsthat split a long prompt into pieces so
no single iteration carries the full prefill cost, andstall-free
batchingthat admits ongoing decodes first and then tops up
the iteration with prefill chunks under a per iteration token
budget 𝜏. The token budget is the throughput-versus-latency
knob, and 𝜏 is sized so that the resulting mixed iteration bal-
ances both Time Between Tokens (TBT) SLOs and saturating
the GPU compute.
3 Motivation
We discuss properties of LLM serving that need to be modi-
fied for serving dLLMs.
3.1 Bigdecodes
Figure 3 plots decode iteration time against batch size for two
dLLMs (LLaDA-8B, Dream-7B) and their AR counterparts1
(Llama-3-8B [14], Qwen2.5-7B [37], measured on SGLang [58]).
For both dLLMs, iteration time grows several-fold across the
measured range, while for the AR models it grows only mod-
estly. Decode batching is therefore significantly less impact-
ful for high-throughput low-latency dLLM serving compared
to AR LLMs.
1The architecture of LLaDA-8B and Dream-7B have been derived from
LLaMA-3-8B and Qwen-2.5-7B respectively.
1 4 8 16 32 48
Batch size
0
10
20
30Decode Iter Time (ms)
LLaDA-8B
LLaMA-3-8B
(a)LLaDA-8B vs Llama-3-8B.
1 4 8 16 32 48
Batch size
0
5
10
15
20
25Decode Iter Time (ms)
Dream-7B
Qwen2.5-7B (b)Dream-7B vs Qwen2.5-7B.
Figure 3.Decode iteration time vs batch size for two dLLMs
(LLaDA-8B, Dream-7B) and their AR counterparts (Llama-
3-8B, Qwen2.5-7B) at sequence length 1024. dLLM iteration
time climbs steeply, so batching past a few requests stops
improving throughput. AR iteration time grows only gently
out to batch 64, so AR keeps benefiting from batching.
The parallel unmasking mechanics of dLLMs impose a
fundamentally heavier compute load during batch execution
compared to traditional autoregressive generation. The pri-
mary throughput gains of decode batching stem from amor-
tizing the memory-bandwidth bound loading of weights in
MLP operations. In AR decode, each request appends only
a single query token, so the marginal MLP cost per request
is negligible and many requests can be packed before the
MLP becomes compute-bound. Attention remains memory-
bandwidth-bound and scales per request in both regimes.
The difference is on the MLP path. Under block-based ap-
proximate caching such as Fast-dLLM, each active dLLM
request contributes its entire current unmasking block (32
tokens by default) to the microbatch at every step. The MLP
operations that batching is meant to amortize now receive
a full block per request rather than a single token, so the
per-request MLP cost is roughly block_size×larger.
Consequently, these individuallybigdecodes restrict the
throughput gains typically achieved via large decode batches.
Unlike standard AR engines that rely on massive batches to
maximize hardware utilization, the block-wise unmasking
of dLLMs saturates GPU compute and memory bandwidth
with only a few concurrent requests.
Takeaway 1: Each decode contributes a full block of compute,
so decode batches saturate GPUs at low batch sizes. Because of
4

## PDF Page 5

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
0 200 400 600 800 1000
Output length (tokens)
0
200
400
600Iterations
LLaDA-8B, ShareGPT
(a)LLaDA-8B, ShareGPT.
100 200 300 400 500
Output length (tokens)
0
100
200
300
400Iterations
Dream-7B, arXiv summ. (b)Dream-7B, arXiv summ.
Figure 4.Iterations (forward passes) versus output length,
one point per request. Because the number of positions un-
masked per iteration is data-dependent, requests that emit
the same number of tokens still take widely different num-
bers of iterations to finish, visible as the vertical spread at
any fixed output length.
this, dLLM inference engines cannot singularly rely on creating
large batches to drive throughput improvements.
3.2 Recurring Prefills and Variable Iterations Across
Requests
Under blockwise denoising, every block ends with a re-prefill,
but the iteration on which that boundary arrives is data-
dependent. Recent sampling strategies [13, 49, 51] unmask
avariablenumber of tokens per iteration, so the step count
needed to unmask a block is not fixed. Confidence-threshold
based sampling unmasks every masked position whose top-1
probability exceeds a threshold and lets the per-step yield
vary with how confident the model happens to be. Prompt-
dependent complexity compounds the variability: under the
same sampling rule, easy prompts can resolve a block in a
handful of iterations while harder ones need many more.
We show this empirically. In Figure 4, each point is one re-
quest’s total iteration (forward-pass) count plotted against
its output length, for LLaDA-8B on ShareGPT and Dream-7B
on arXiv summarization traces ( Table 1). The block size is
fixed, so output length determines the number of blocks, and
all requests at a given output length denoise the same num-
ber of blocks. Yet at any fixed output length the points still
spread vertically over a wide range, so requests with identical
block counts take very different total iteration counts. The
spread can only come from per-block variation: individual
blocks unmask in different numbers of iterations, and two
requests even with the same number of blocks reach their
block boundaries on different iterations.
The first consequence is for batch scheduling. If every
co-batched request crossed its block boundaries on the same
iteration, the server could switch the whole batch between
prefill and decode in lockstep. The variability above rules
this out: requests batched together reach their block bound-
aries on different iterations, so there is no single iteration
at which the batch as a whole changes phase. Each request
must instead be advanced on its own boundary schedule: on
every iteration the server decides, per request, whether it
5P3D 4P4D 6P2D
0 20 40 60 80
E2E Latency (s)
0.0
0.5
1.0CDF
(a)e2e latency
0 20 40 60
Queueing Delay (s)
0.0
0.5
1.0CDF (b)scheduling delay
Figure 5.LLaDA-8B on a single 8-GPU H100 node under
three static disaggregated splits (4P4D, 5P3D, 6P2D) on the
ShareGPT trace at QPS 6.5. 4P4D and 6P2D both inflate e2e
latency, but for different reasons: under 4P4D the scheduling
delay accrues at the prefill workers, while under 6P2D it
accrues at the decode workers.
is decoding within a block, re-prefilling, or finished. There-
fore continuous batching that Orca [55] introduced for AR
serving is needed: the scheduler decides on each iteration
which requests run, and a request that finishes its current
block can immediately submit its re-prefill while the rest of
the batch keeps decoding.
The second consequence is for prefill-decode interference.
A freshly arrived prompt prefill, or any in-flight request re-
freshing its KV cache (re-prefill), stalls the decodes of every
other co-batched request. AR produces prefill work only at
request arrival, so a steady-state decode batch sees interfer-
ence only from new request arrivals. In dLLMs every in-flight
request is also a recurring prefill source, since each block
boundary re-injects a prefill. This increases prefill-decode
interference. AR serving uses two techniques to mitigate
this interference: Colocated serving with chunked prefills
(Sarathi-Serve [2]) and disaggregated serving [17, 35, 59], as
discussed in § 2.3. Sarathi-Serve only adds partial prefills
to ongoing decode batches to limit the interference caused
by prefills. dLLMs do not support prefill chunking. This is
because of bidirectional attention, where prompt tokens at-
tend to each other (and the placeholder response tokens),
affecting each other’s KV values. So the AR KV-Cache in-
variant that KV values of prior tokens are not affected by
subsequent tokens doesn’t hold, and thus prefills cannot be
processed in chunks. We discuss disaggregated serving in
the next subsection § 3.3.
Takeaway 2: Variable-token samplers make block boundaries
a per-request, data-dependent event, so continuous batching at
the iteration boundary is required for dLLM serving. Further-
more, prefill-decode interference occurs far more often than in
AR because every in-flight request becomes a recurring prefill
source. But dLLMs don’t support prefill chunking, a critical
mechanism to mitigate this interference.
5

## PDF Page 6

Kedia et al.
3.3 Static prefill-decode worker partitioning is
fragile
Disaggregation is appealing for dLLM serving because it
removes prefill-decode interference by design. This benefit
is not free: it presupposes a prefill:decode partition whose
optimum depends on the workload mix and SLO targets [28,
35, 36, 44]. Systems that adjust this partition online exist, but
they rebalance coarsely, leave GPUs underutilized between
adjustments, and add operational complexity (we return to
these in detail below). We characterize how brittle static
disaggregated serving is in Figure 5 by serving 8 LLaDA-
8B replicas on an 8-GPU node and sweeping prefill:decode
worker splits (4P4D, 5P3D, 6P2D) on the ShareGPT trace
at QPS 6.5. 5P3D has the lowest end-to-end time. However
both 4P4D and 6P2D expose two distinct failure modes that
inflate e2e latency (Figure 5a) through queueing delay (Fig-
ure 5b), but on opposite sides of the pipeline. At 4P4D prefill
capacity is insufficient: queueing delay accrues at the pre-
fill workers, reaching a median near 24 s and lifting the e2e
median to 28 s. Reallocating one GPU to prefill (6P2D) re-
lieves the prefill workers, but the now-smaller decode pool
exhausts its memory capacity and queueing delay instead
accrues at the decode workers (median ∼8s), still leaving an
e2e median of 23 s. Only the balanced 5P3D controls both,
with scheduling delay near zero and an e2e median under
5 s. Finer-grained partitions are possible with more GPUs,
but the optimal allocation still shifts with request load and
composition.
Adjusting the split online is itself a hard problem. Moon-
cake [36], a production system, rebalances its prefill and
decode pools with a controller that follows a daily machine
tide, adding capacity to the overloaded side and reclaiming
it from the other, but it does so only on a coarse, diurnal
timescale by scaling cluster-level capacity, so a pool can stay
over- or under-provisioned between adjustments and the
scheme leans on spare GPUs. This approach is available to
large clusters but not to smaller deployments which have
few workers, coarse ratios, and no idle headroom to spare.
A finer-grained alternative lets decode workers absorb pre-
fill work when the prefill side is overloaded: Splitwise [35]
morphs machines between roles through a mixed pool, and
the conditional disaggregation in Dynamo [ 32] processes
a request’s prefill on the decode worker when the remote
prefill queue is backed up. However, overflow prefills on
otherwise-decode workers are especially sensitive to inter-
ference. In disaggregated serving, only the decode pool, a
fraction of the workers, carries all decode work, concentrat-
ing it on few workers already near GPU saturation (§3.1).
Therefore an injected prefill stalls their in-flight decodes
rather than filling slack. A mechanism is therefore needed
that protects these decode workers while still sparing some
capacity to an underprovisioned prefill side.
𝜏
0
decodes𝐷1
prefill𝑝1
𝑆1
𝑆2
decodes𝐷2
large prefill𝑝3
admitted
decodes𝐷3
prefill𝑝4
iter𝑡=1 iter𝑡=2 iter𝑡=3
Carry𝑆1
raises budget
leftover𝑆2
carries on
waiting prefill queue
𝑝1
𝑝3(large)
𝑝4
in-flight decodes𝐷𝑡 admitted prefillunused budget𝑆𝑡 waiting prefill
Figure 6.Deficit token-budget scheduling over three itera-
tions. Each iteration first fills the per-iteration budget𝜏 with
in-flight decodes 𝐷𝑡, then admits waiting prefills greedily in
request arrival order while they fit in the remaining budget
𝑅𝑡 =𝜏−𝐷 𝑡 +𝑆 𝑡−1 . Any unspent budget 𝑆𝑡 is carried forward,
raising the effective ceiling in the next iteration so that a
large prefill (e.g. 𝑝3) can be admitted without exceeding the
amortized per-iteration budget𝜏.
There is also a prior question of which regime to use at
all. For AR serving, it is well known that disaggregation
suits prefill-heavy workloads and colocation decode-heavy
workloads [28]. In dLLMs, each decode is heavier (§ 3.1)
and the prefill work per request grows because every block
boundary triggers a re-prefill (§ 3.2). Therefore, it is not clear
which regime is more suited for dLLM serving which we
evaluate in § 6.3.
Takeaway 3: No static prefill:decode split is jointly optimal:
prefill-biased splits starve decode of KV Cache while decode-
biased splits queue prefills. Existing online remedies are either
coarse or operationally complex, and still leave interference-
sensitive decode workers exposed. We instead pursue hybrid
scheduling (§ 4.2): a fast-reacting, operationally simple mech-
anism that overflows a saturated prefill pool into protected
decode-role workers.
4 Sangam Design
Based on the characteristics of dLLM’s discussed in pre-
vious section, we introduce Sangam. First, we discuss the
core building blocks of Sangam (§4.1, §4.2) before finally
discussing the architecture (§4.3).
4.1 Colocated serving withdeficittoken budgets
To enable amortized stall-free batching without prefill chunk-
ing, we introduce adeficit token budgetinspired by Deficit
Round-Robin [42], illustrated in Figure 6. Each iteration car-
ries a token budget 𝜏. The scheduler first seats every in-
flight decode, which is never displaced, so the budget left for
fresh prefill work is budget=𝜏−Tokens(decodes) +deficit ,
where deficit is the unspent budget carried forward from the
previous iteration. Waiting prefills (both new prefills and
block-boundary re-prefills) are admitted greedily in request
6

## PDF Page 7

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
Algorithm 1Deficit token-budget scheduling
Input:Token Budget𝜏;deficitfrom the previous iteration
State:In-flightdecodes; queue of waitingprefills
1:ifprefillsis emptythen
2:deficit←0
3:returndecodes⊲decode-only iteration
4:end if
5:budget←𝜏−Tokens(decodes) +deficit
6:microbatch←decodes⊲decodes are never displaced
7:whileprefillsis not emptydo
8:𝑝←first request inprefills
9:idle←(microbatchis empty)
10:ifTokens(𝑝) ≤budgetoridlethen
11:move𝑝fromprefillsintomicrobatch
12:budget←budget−Tokens(𝑝)
13:else
14:break⊲𝑝waits; prefills cannot be split
15:end if
16:end while
17:deficit←max(budget,0)⊲carry leftover
18:returnmicrobatch
arrival-time order, not strict FIFO, so a re-prefill from an
older request is ordered ahead of a fresh prefill from a newer
one. The scheduler processes the queue and admits each pre-
fill while it fits the remaining budget; the first that does not
fit stops the scan. When no prefill is waiting, the iteration
is decode-only: the carried deficit is cleared to zero and the
decode batch runs as is. Otherwise, whatever budget is left
over is preserved as the next iteration’sdeficit and rolls into
the next round.
Because dLLMs cannot chunk prefills, a single oversized
prompt may exceed 𝜏 and might never be admitted into
an idle system. We resolve this with an idle rule inside the
admission loop: while the microbatch is still empty (no in-
flight decode and no prefill admitted yet this iteration), the
scheduler admits the head prefill even if it exceeds the budget.
This is required forlivenessin the system.
Per-iteration stall-free batching is unattainable for dLLMs:
an indivisible prefill must enter in a single iteration and
stalls co-batched decodes by its full size. Due to this, prior
dLLM serving has had to default to prefill-prioritizing sched-
ulers [11] and pay the interference cost or be decode-prioritizing
and suffer loss in throughput. The deficit scheduler guaran-
tees an amortized bound: over any busy period of 𝑊 itera-
tions with prefills continuously waiting, admitted prefill to-
kens total at most𝑊 𝜏− Í𝑊
𝑡=1 𝐷𝑡, so the average per-iteration
prefill load is capped at𝜏. In other words, the deficit construc-
tion substitutes temporal deferral for spatial chunking: rather
than splitting one prefill across iterations, it defers whole
prefills until enough budget accumulates, bounding the amor-
tized prefill contribution to 𝜏. Temporal deferral is the only
axis available once bidirectional attention rules out spatial
Algorithm 2Hybrid Scheduler
Input: request 𝑟; prefill pool𝑃, colocated pool𝐶; per-worker
outstanding-prefill load 𝑜𝑤 ; overload threshold 𝜃; colo-
cated deficit budget𝜏
1:𝑤←LeastLoaded(𝑃, 𝑟)⊲min𝑜 𝑤 under𝜃, free KV
2:if𝑤≠None then
3:dispatch𝑟to𝑤as prefill-only;return
4:end if
5:⊲prefill pool saturated or out of KV: overflow
6:𝑤←LeastLoaded(𝐶, 𝑟)
7: if 𝑤≠None andcolocated KV fits 𝑟 after pending
decodesthen
8:dispatch𝑟to𝑤as colocated under𝜏;return
9:end if
10:enqueue𝑟on the FIFO pending queue⊲retry
head-of-line later
chunking. Thus the scheduler achieves stall-free batching
(in an amortized sense)without prefill chunking, increasing
the scope of stall-free continuous batching to a model class
for which chunked prefill is structurally unavailable. The
iteration token budget 𝜏 with deficit tracking provides a
tunable knob over the queueing-delay versus prefill-decode
interference trade-off for dLLMs, similar to AR serving. At
a given request load, the budget should be high enough to
clear prefills before they queue and low enough to shield
decodes from interference.
4.2 Hybrid Scheduling
A natural alternative to colocated serving is the prefill/decode
disaggregated serving pioneered for AR LLMs [17, 35, 59]:
dedicate one pool of workers to prefill, another to decode, and
transfer KV from the first to the second. Disaggregated serv-
ing eliminates prefill-decode interference by design. How-
ever, right sizing the prefill and decode pools is critical to
improve goodput as shown by the design study [ 28]. To
solve prefill under-provisioning which causes high queue-
ing delays at prefill workers, Sangam pairs dedicated prefill
workers withdeficit token budgetbased colocated workers
in the decode role, rather than purely prefill-prioritizing or
decode-prioritizing colocated workers. This reduces prefill-
decode interference within the colocated workers while also
absorbing queueing at the prefill workers. A deployment
provisions 𝑁𝑃 dedicated prefill workers and 𝑁𝐶 colocated
workers. Under nominal load the central scheduler routes
each request (and each block-boundary re-prefill) to the pre-
fill pool, and the colocated pool serves the disaggregated
decode role. When the prefill pool saturates, the scheduler
overflowsthe request to a colocated worker, which prefills
and decodes the request locally with no cross-worker KV
transfer. This seamlessly converts spare decode capacity into
prefill capacity with prefill-decode interference controlled
by deficit token budget.
7

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
each block-boundary re-prefill) to a worker. Workers run
the model forward pass and apply the per-iteration batching
policy locally. This split is needed because routing decisions
need a global view of worker load and memory capacity us-
age across the cluster, while microbatch composition has to
run on the worker’s hot path between iterations and cannot
afford a round-trip to a central process. Sangam instantiates
this two-level architecture in two worker layouts.
Colocated architecture (Figure 7a).Every worker is
identical and runs prefill and decode locally. Each worker
maintains a pending-prefill queue, an in-flight decode set,
and admits work each iteration under the deficit-budget
scheduler of § 4.1.
Hybrid architecture (Figure 7b).This is the instantia-
tion of the hybrid scheduler described in § 4.2.
A block-boundary re-prefill is not pinned to the worker
that ran the previous block: dLLMs discard the per-request
KV Cache at every block boundary and only the token IDs
persist, so the central scheduler is free to redispatch a re-
prefill to whichever worker is least loaded without paying
any cross-worker KV transfer cost. This enables better load
balancing across workers as the central scheduler can reas-
sign requests at several points in their life-cycle.
5 Implementation
Sangam is implemented in roughly 16K lines of Python
built on PyTorch and HuggingFace transformers. A central
CPU-based scheduler coordinates a pool of GPU workers.
Each worker can run as colocated, prefill-only, or decode-
only, so the same system supports both architectures of Sec-
tion 4. Control-plane RPCs use gRPC. KV Cache transfers
are streamed over torch.distributed/NCCL. The system
uses PagedAttention [20] for easy programmatic access to
manage and transfer the KV cache. We also use FlashIn-
fer’s [54] paged-KV attention kernels and CUDA Graphs as
it significantly reduces iteration times.
6 Evaluation
We seek to answer the following questions in our evaluation:
•Q1:How does Sangam compare against Fast-dLLM?
• Q2:How do colocated, disaggregated, and hybrid serv-
ing compare across different combinations of dLLM
models and traces?
• Q3:Does deficit scheduling deliver amortized stall-
free batching without prefill chunking, and how does
the deficit token budget𝜏 trade off throughput against
inter token latency for colocated dLLM serving?
• Q4:How does the use of deficit token budget based hy-
brid scheduling impact its performance as the budget
𝜏varies?
8

## PDF Page 9

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
Prompt Tokens Output Tokens
Trace Median P99 Std. Median P99 Std.
ShareGPT Chat 795 2007 596 266 874 206
arXiv Summarization 2827 3923 890 162 360 73
Table 1.Prompt-length and output-length distributions for
the filtered ShareGPT and arXiv summarization traces.
6.1 Experiment Setup
Experiments are run on a AWS p5.48xlarge node with 8
NVIDIA H100 GPUs each with 80 GB HBM, and connected
via pairwise NVLink. We evaluate two open-source dLLMs,
LLaDA-8B-Instruct [31] and Dream-7B-Instruct [53], both
served in bfloat16. We use KV page size of 16 tokens (vLLM
default), and block size of 32 (Fast-dLLM default). We use
two traces: the ShareGPT [4] trace containing conversations
with LLMs, and the arXiv summarization [10] trace contain-
ing research paper summarization tasks. We filter out re-
quests having more than 4096 tokens and Table 1 reports the
prompt-length and decode-length distributions for the result-
ing traces. We append 1024 MASK tokens to the ShareGPT
prompts, and 512 to the arXiv Summarization prompts to
accommodate the longest outputs in these traces. Note that
a request denoises one 32-position block at a time and ad-
vances only after a block resolves, so blocks beyond the
committed EOS are never denoised or re-prefilled. A 266-
token output processes ceil(266/32)=9 blocks, not the full
L/32. The appended MASK tokens do however increase the
sequence length processed in every prefill and re-prefill it-
erations. We use a range of Poisson arrival rates, and re-
port metrics from 4000-request runs per (configuration, QPS)
point. Confidence-threshold based sampling with a threshold
of 0.9 (Fast-dLLM default) is used to unmask these tokens
representing a variable unmasking schedule.
We report end-to-end (E2E) latency, mean and P99, over a
wide range of arrival rates. We deliberately avoid Time to
First Token (TTFT) and Time Between Tokens (TBT) metrics
from AR serving because these don’t directly map to a dLLM
request lifecycle. Due to presence of re-prefills, there is no
single TTFT. Further, because bidirectional attention makes
prefills indivisible, high P99 TBT is intrinsic to any colocated
dLLM system and can only be bound in an amortized sense
(§ 4.1). To aid in understanding, we also report decode exe-
cution times, prefill execution times, and queueing delays at
representative request load as needed.
6.2 Comparison against Fast-dLLM
Fast-dLLM [51] ships as a inference script without an online
server and without batching support for variable-length on-
line traces, so it is run at batch size 1. For a fair comparison
we evaluate against an in-system version of Fast-dLLM: we
take its model definition and use the same block KV caching
0.5 1.0
QPS
10
20Mean E2E Latency (s)
Fast-dLLM
Colocated-1024
(a)Mean, ShareGPT.
0.5 1.0 1.5
QPS
20
40Mean E2E Latency (s)
Fast-dLLM
Colocated-1024 (b)Mean, arXiv summarization.
0.5 1.0
QPS
20
40P99 E2E latency (s)
Fast-dLLM
Colocated-1024
(c)p99, ShareGPT.
0.5 1.0 1.5
QPS
25
50
75P99 E2E latency (s)
Fast-dLLM
Colocated-1024 (d)p99, arXiv summarization.
Figure 8.Mean and p99 end-to-end latency under varying
QPS for in-system Fast-dLLM and Sangam (Colocated with
𝜏=1024) running LLaDA-8B on a single H100 80GB GPU.
and confidence-threshold sampling, but run it inside Sangam
so it benefits from the optimizations such as CUDA Graph
which reduce batch execution time by up to2×.
On LLaDA-8B with the ShareGPT trace, Fast-dLLM’s mean
latency stays flat up to QPS 0.3 and then increases sharply
(∼20.7 s at QPS 0.5). Sangam (Colocated,𝜏=1024) instead sus-
tains QPS 1.0 at comparable mean and tail latency (Figures 8a
and 8c), a∼3× throughput gap. On the arXiv trace Fast-dLLM
knees by QPS 0.3–0.4 while Sangam sustains QPS 1.0 at com-
parable latency (Figures 8b and 8d), a ∼2.5–3× gap. This
massive difference in throughput under the same latency is
because of insufficient GPU utilization by Fast-dLLM run-
ning without batching. Decode iterations at batch size 1 are
highly inefficient as seen in § 3.1.
We treat this comparison as a floor rather than a headline
result. Because the in-system Fast-dLLM still serves one re-
quest at a time, the gap isolates the value of online batched
serving, which § 3.2 motivates, not the value of deficit to-
ken budget based scheduler. The scheduler’s contribution is
evaluated against strong in-system baselines in § 6.3- § 6.5,
where every configuration is online and batched.
6.3 Colocated, Disaggregated, and Hybrid Serving
We next ask whether dLLM serving should use separate
pools of GPUs to prefill and decode, or let every GPU serve
both phases. We compare three ways(colocated, disaggre-
gated and hybrid)to configure an 8-GPU node, picking a
strong configuration of each. Thecolocatedmode runs all
eight GPUs as colocated workers with a 1024-token itera-
tion budget which strikes a balance between reducing prefill-
decode interference and throughput as will be shown in § 6.4.
Thedisaggregatedconfiguration has fixed prefill and decode
pools; we use a 5P3D split (five prefill workers, three decode
workers), the best static split for these workloads, since 4P4D
9

## PDF Page 10

Kedia et al.
Colocated-1024 Disaggregated-5P3D Hybrid-5P3C
4 5 6 7
QPS
0.0
2.5
5.0
7.5
10.0Mean E2E latency (s)
(a)LLaDA-8B, ShareGPT, mean.
4 5 6 7 8
QPS
0
2
4
6
8Mean E2E latency (s)
 (b)LLaDA-8B, arXiv, mean.
4 5 6 7 8
QPS
0
2
4
6
8Mean E2E latency (s)
 (c)Dream-7B, ShareGPT, mean.
4 5 6 7 8 9
QPS
0
2
4
6Mean E2E latency (s)
 (d)Dream-7B, arXiv, mean.
4 5 6 7
QPS
0
10
20
30P99 E2E latency (s)
(e)LLaDA-8B, ShareGPT, p99.
4 5 6 7 8
QPS
0
5
10
15
20P99 E2E latency (s)
 (f)LLaDA-8B, arXiv, p99.
4 5 6 7 8
QPS
0
5
10
15
20P99 E2E latency (s)
 (g)Dream-7B, ShareGPT, p99.
4 5 6 7 8 9
QPS
0
5
10
15P99 E2E latency (s)
 (h)Dream-7B, arXiv, p99.
Figure 9.End-to-end latency vs. QPS for colocated, static-split disaggregated (5P3D), and hybrid (5P3C). Top row mean,
bottom row p99; columns are (model, trace) pairs. Colocated and hybrid degrade gracefully while the static disaggregated
typically saturates first.
Colocated-1024 Disaggregated-5P3D Hybrid-5P3C
0 5 10 15
Prefill Queueing Delay (s)
0.00
0.25
0.50
0.75
1.00CDF
QPS=6.5
(a)LLaDA-8B ShareGPT.
0 10 20
Decode Time (s)
0.00
0.25
0.50
0.75
1.00CDF
QPS=6.5 (b)LLaDA-8B ShareGPT.
0 1 2 3
Prefill Queueing Delay (s)
0.00
0.25
0.50
0.75
1.00CDF
QPS=8.5
(c)Dream-7B arXiv.
0.0 2.5 5.0 7.5 10.0
Decode Time (s)
0.00
0.25
0.50
0.75
1.00CDF
QPS=8.5 (d)Dream-7B arXiv.
Figure 10.Per-request CDFs of prefill queueing delay (left)
and request decode time (right), at moderate request load
(LLaDA-8B ShareGPT 6.5 QPS, Dream-7B arXiv 8.5 QPS). p99
values are highlighted.
is even more prefill-bound and 6P2D runs the decode pool
into its KV Cache capacity limit.Hybrid 5P3C(§ 4.2) reuses
the same split as disaggregated, but its three decode-role
workers are colocated workers. We run hybrid with over-
flow threshold 𝜃=8kand a tight deficit token budget 𝜏=1024.
This specific hybrid configuration is used to show the gains
which can be achieved by simply replacing decode workers
with tight budget colocated workers in static disaggregated
deployments.
Overall trends.Figure 9 reports mean and p99 end-to-end
latency across a range of QPS for four (model, trace) pairs.
At low load the three configurations are effectively tied; as
load rises they diverge. Disaggregated-5P3D saturates first in
every pair: on LLaDA-8B ShareGPT its mean latency reaches
11.8 s at QPS 7.5 against 7.1 s for colocated and 9.0 s for hybrid.
Colocated has the lowest mean and p99 in three of the four
pairs, the exception being the prefill-heavy Dream-7B arXiv,
where disaggregated and hybrid stay ahead of colocated
across almost the whole sweep (at QPS 7 disaggregated is
about 12% lower than colocated at both mean and p99, hybrid
17% and 16%) until the static disaggregated finally saturates
at the highest QPS. Hybrid stays close to the better of the
two: it follows colocated through the loaded region while
capturing the disaggregated advantage on Dream-7B arXiv.
These trends come from two metrics that distinguish the
schedulers: prefill queueing delay and request decode time,
which are the largest contributors to end-to-end latency.
Figure 10 shows the per-request CDFs of both at a repre-
sentative QPS for two illustrative pairs: the decode-heavy
LLaDA-8B ShareGPT and the prefill-heavy Dream-7B arXiv,
which bracket the behavior of the remaining two pairs. This
is because the arXiv trace has longer prompts than ShareGPT
(Table 1) and Grouped Query Attention (GQA) [3] in Dream-
7B which shrinks the KV Cache footprint and hence the
cost of memory-bandwidth bound decodes [1] compared to
LLaDA-8B which uses MHA.
10

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
admit. Requests then queue until enough deficit accumu-
lates, and queueing delay grows super-linearly. With 𝜏=512
each iteration carries minimal residual capacity, so its load
curve develops this knee well before others. For example,
on LLaDA-8B ShareGPT its p99 climbs from 27.8 s at QPS 7
to 45.6 s at QPS 7.5, reaching close to2× the best budget by
QPS 7.5 (45.6 s versus 22.1 s for𝜏=1024).
In the ShareGPT trace,𝜏=1024holds the lowest p99 across
a broad range on both models (between QPS 6-7.5 in LLaDA-
8B and QPS 7-8.5 in Dream-7B), keeping a margin of up
to roughly 10% over the next best 𝜏=2048. The breakdown
figures (Figures 11e and 11g) show why, and reveal that
the budget trades the tail against the lower percentiles. On
LLaDA-8B ShareGPT, raising 𝜏 from 1024 to 16384 nearly
halves the tail request’s queueing delay (2.5 s to 1.4 s) but
raises its decode time (13.1 s to 15.1 s) as more prefills inter-
fere with concurrent decodes, so the tail end-to-end climbs
from 17.3 s to 18.9 s. Dream-7B ShareGPT shows the same
pattern: the tail decode time climbs from 9.5 s to 12.3 s and
end-to-end from 13.2 s to 14.4 s. The mean request moves
11

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
against 4.7 s on LLaDA-8B, 3.7 s against 4.1 s on Dream-7B).
The mechanism behind this split is that a high budget ea-
gerly admits prefills as soon as they arrive, sharply stalling
the decodes being processed close to prefill arrivals. A lower
budget instead defers prefills and spreads processing across
many iterations, thinning the same interference over many
more decodes: this reduces the worst-case stall (a lower tail)
but increases the end-to-end latency at other percentiles i.e.
a higher mean. Pushing the budget too low overshoots, as
deferred prefills then queue for a long time: at 𝜏=512the
LLaDA-8B tail request waits 12.8 s in the queue, pushing
its end-to-end to 22.2 s, above both larger budgets, so the
tail optimum is intermediate. Note that as the request load
continues to increase, 𝜏=1024will reach its knee point be-
fore higher budgets as requests will queue faster than the
prefill processing capacity 𝜏=1024allows. Post that point,
queueing delay in 𝜏=1024will grow exponentially, giving
way to𝜏=2048as having the lowest latency, and so on.
In the arXiv trace, we find that the highest budget𝜏=16384
performs the best, although by a vanishing margin compared
to the next lower budgets𝜏=2048and𝜏=1024. The smallest
budget 𝜏=512saturates first: on LLaDA-8B arXiv Figure 11b
𝜏=512saturates at QPS 7 (10.9 s, climbing to 49.7 s at QPS 8),
while the larger budgets remain near 12-13 s at QPS 8. Thus
for this trace, there isn’t gains to be had in E2E times by
adjusting the budget because of the prefill heavy nature of
the arxiv trace (§ 6.1). On a prefill-heavy trace the dominant
requirement is to clear prefills before they queue, which a
high budget allows. Only in a decode-heavy trace there is
enough decode volume to protect from interference, so there
exists a specific budget such as 𝜏=1024for ShareGPT, which
defers prefills and provides gains. The E2E time breakdown
plots Figure 11f and Figure 11h corroborate this.
6.5 Hybrid Scheduling
We seek to understand how the deficit token budget𝜏 impacts
hybrid scheduling. Figure 12 shows load plots on LLaDA-
8B with the ShareGPT trace at the 5P3C and 3P5C pre-
fill:colocated worker ratios, comparing a low (𝜏=1024) against
a high (𝜏=4096) colocated budget. We use an overflow thresh-
old of𝜃=8192as it performs well in a sweep of hyperparamter
combinations in hybrid serving. At the 5P3C configuration
(Figures 12a and 12b), the lower budget ( 𝜏=1024) reduces
the p99 end-to-end latency at high load, about 8% at QPS 7
(26.8 s against 29.1 s) and 14% at QPS 7.5 (31.5 s against 36.7 s).
This is because a lower budget is more effective in keeping
overflow prefills from stalling decodes already in flight on
the colocated workers. Similarly in the 3P5C configuration
(Figure 12d), the low budget again reduces the p99 latency
roughly 5% at QPS 6 rising to 16–19% at high load (27.5 s
against 34.1 s at QPS 7.5). In both the cases, the impact is
visible at high load because the prefill overflow condition
triggers significantly more frequently at high load.
12

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
fill/decode execution under one implementation. Our eval-
uation on LLaDA-8B and Dream-7B shows that the effec-
tiveness of colocated, disaggregated, and hybrid serving is
governed by two fundamental factors, static prefill/decode
partitioning and prefill-decode interference, and that hy-
brid scheduling is a simple augmentation that preserves the
strengths of static disaggregated deployments while improv-
ing them on decode-heavy workloads. Sangam shows that a
disciplined reuse of the AR stack is the right foundation for
serving the growing class of cached dLLMs.
13

## PDF Page 14

Kedia et al.
References
[1] Amey Agrawal, Nitin Kedia, Jayashree Mohan, Ashish Panwar, Nipun
Kwatra, Bhargav S Gulavani, Ramachandran Ramjee, and Alexey Tu-
manov. 2024. Vidur: A large-scale simulation framework for llm
inference.Proceedings of Machine Learning and Systems6 (2024), 351–
366.
[2] Amey Agrawal, Nitin Kedia, Ashish Panwar, Jayashree Mohan, Nipun
Kwatra, Bhargav Gulavani, Alexey Tumanov, and Ramachandran Ram-
jee. 2024. Taming {Throughput-Latency} tradeoff in {LLM} inference
with {Sarathi-Serve}. In18th USENIX symposium on operating systems
design and implementation (OSDI 24). 117–134.
[3] Joshua Ainslie, James Lee-Thorp, Michiel De Jong, Yury Zemlyanskiy,
Federico Lebrón, and Sumit Sanghai. 2023. Gqa: Training general-
ized multi-query transformer models from multi-head checkpoints.
InProceedings of the 2023 Conference on Empirical Methods in Natural
Language Processing. 4895–4901.
[4] anon8231489123. 2023. ShareGPT Vicuna Unfiltered.
https://huggingface.co/datasets/anon8231489123/ShareGPT_
Vicuna_unfiltered. Apache-2.0 license. Approximately 53k cleaned
English ShareGPT conversations derived from 100k, split into
2048-token chunks for fine-tuning Vicuna-style models.
[5] Marianne Arriola, Aaron Gokaslan, Justin Chiu, Zhihan Yang, Zhix-
uan Qi, Jiaqi Han, Subham Sahoo, and Volodymyr Kuleshov. 2025.
Block diffusion: Interpolating between autoregressive and diffusion
language models. InInternational Conference on Learning Representa-
tions, Vol. 2025. 50726–50753.
[6] Jacob Austin, Daniel D Johnson, Jonathan Ho, Daniel Tarlow, and
Rianne Van Den Berg. 2021. Structured denoising diffusion models
in discrete state-spaces.Advances in neural information processing
systems34 (2021), 17981–17993.
[7] Parikshit Bansal and Sujay Sanghavi. 2025. Enabling approximate
joint sampling in diffusion lms.arXiv preprint arXiv:2509.22738(2025).
[8] Tiwei Bie, Maosong Cao, Kun Chen, Lun Du, Mingliang Gong,
Zhuochen Gong, Yanmei Gu, Jiaqi Hu, Zenan Huang, Zhenzhong
Lan, et al. 2025. Llada2. 0: Scaling up diffusion language models to
100b.arXiv preprint arXiv:2512.15745(2025).
[9] Shuang Cheng, Yihan Bian, Dawei Liu, Yuhua Jiang, Yihao Liu, Lin-
feng Zhang, Qian Yao, Zhongbo Tian, Wenhai Wang, Qipeng Guo,
et al. 2026. Sdar: A synergistic diffusion-autoregression paradigm
for scalable sequence generation. InFindings of the Association for
Computational Linguistics: ACL 2026. 22058–22075.
[10] Arman Cohan, Franck Dernoncourt, Doo Soon Kim, Trung Bui,
Seokhwan Kim, Walter Chang, and Nazli Goharian. 2018. A discourse-
aware attention model for abstractive summarization of long docu-
ments. InProceedings of the 2018 Conference of the North American
Chapter of the Association for Computational Linguistics: Human Lan-
guage Technologies, Volume 2 (Short Papers). 615–621.
[11] Jiakun Fan, Yanglin Zhang, Xiangchen Li, and Dimitrios S Nikolopou-
los. 2025. Taming the Memory Footprint Crisis: System Design for
Production Diffusion LLM Serving.arXiv preprint arXiv:2512.17077
(2025).
[12] Yonggan Fu, Lexington Whalen, Abhinav Garg, Chengyue Wu, Mak-
sim Khadkevich, Nicolai Oswald, Enze Xie, Daniel Egert, Sharath Tu-
ruvekere Sreenivas, Shizhe Diao, Chenhan Yu, Ye Yu, Weijia Chen,
Sajad Norouzi, Jingyu Liu, Shiyi Lan, Ligeng Zhu, Jin Wang,
Jindong Jiang, Morteza Mardani, Mehran Maghoumi, Song Han,
Ante Jukić, Nima Tajbakhsh, Jan Kautz, and Pavlo Molchanov.
2026.Nemotron-Labs-Diffusion: A Tri-Mode Language Model Unify-
ing Autoregressive, Diffusion, and Self-Speculation Decoding. Tech-
nical Report. NVIDIA Corporation. NVIDIA Open Model Li-
cense.https://research.nvidia.com/publication/2026-05_nemotron-
labs-diffusion-tri-mode-language-model-unifying-autoregressive
[13] Marjan Ghazvininejad, Omer Levy, Yinhan Liu, and Luke Zettlemoyer.
2019. Mask-predict: Parallel decoding of conditional masked language
models. InProceedings of the 2019 conference on empirical methods in
natural language processing and the 9th international joint conference
on natural language processing (EMNLP-IJCNLP). 6112–6121.
[14] Aaron Grattafiori, Abhimanyu Dubey, Abhinav Jauhri, Abhinav
Pandey, Abhishek Kadian, Ahmad Al-Dahle, Aiesha Letman, Akhil
Mathur, Alan Schelten, Alex Vaughan, et al. 2024. The llama 3 herd of
models.arXiv preprint arXiv:2407.21783(2024).
[15] Ishaan Gulrajani and Tatsunori B Hashimoto. 2023. Likelihood-based
diffusion language models.Advances in Neural Information Processing
Systems36 (2023), 16693–16715.
[16] Michael Hersche, Samuel Moor-Smith, Thomas Hofmann, and Abbas
Rahimi. 2026. Soft-Masked Diffusion Language Models. InThe Four-
teenth International Conference on Learning Representations.https:
//openreview.net/forum?id=Gba02UMvrG
[17] Cunchen Hu, Heyang Huang, Liangliang Xu, Xusheng Chen, Jiang Xu,
Shuang Chen, Hao Feng, Chenxi Wang, Sa Wang, Yungang Bao, et al.
2024. Inference without interference: Disaggregate llm inference for
mixed downstream workloads.arXiv preprint arXiv:2401.11181(2024).
[18] Daniel Israel, Guy Van den Broeck, and Aditya Grover. 2025.
Accelerating Diffusion LLMs via Adaptive Parallel Decoding.
InAdvances in Neural Information Processing Systems, D. Bel-
grave, C. Zhang, H. Lin, R. Pascanu, P. Koniusz, M. Ghassemi,
and N. Chen (Eds.), Vol. 38. Curran Associates, Inc., 52870–
52888.https://proceedings.neurips.cc/paper_files/paper/2025/file/
4c7d31b2da05a17f15101db5b37a1e24-Paper-Conference.pdf
[19] Samar Khanna, Siddhant Kharbanda, Shufan Li, Harshit Varma, Eric
Wang, Sawyer Birnbaum, Ziyang Luo, Yanis Miraoui, Akash Palrecha,
Stefano Ermon, et al. 2025. Mercury: Ultra-fast language models based
on diffusion.arXiv e-prints(2025), arXiv–2506.
[20] Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin
Zheng, Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica.
2023. Efficient memory management for large language model serving
with pagedattention. InProceedings of the 29th symposium on operating
systems principles. 611–626.
[21] Yaniv Leviathan, Matan Kalman, and Yossi Matias. 2023. Fast in-
ference from transformers via speculative decoding. InInternational
Conference on Machine Learning. PMLR, 19274–19286.
[22] Tianyi Li, Mingda Chen, Bowei Guo, and Zhiqiang Shen. 2025. A
survey on diffusion language models.arXiv preprint arXiv:2508.10875
(2025).
[23] Yuhui Li, Fangyun Wei, Chao Zhang, and Hongyang Zhang. 2024.
Eagle: Speculative sampling requires rethinking feature uncertainty.
arXiv preprint arXiv:2401.15077(2024).
[24] Aixin Liu, Bei Feng, Bing Xue, Bingxuan Wang, Bochao Wu,
Chengda Lu, Chenggang Zhao, Chengqi Deng, Chenyu Zhang, Chong
Ruan, et al . 2024. Deepseek-v3 technical report.arXiv preprint
arXiv:2412.19437(2024).
[25] Zhiyuan Liu, Yicun Yang, Yaojie Zhang, Junjie Chen, Chang Zou,
Qingyan Wei, Shaobo Wang, Yichen Zhu, and Linfeng Zhang. 2026.
dLLM-Cache: Accelerating Diffusion Large Language Models with
Adaptive Caching. arXiv:2506.06295 [cs.LG]https://arxiv.org/abs/
2506.06295
[26] Xinyin Ma, Runpeng Yu, Gongfan Fang, and Xinchao Wang. 2025.
dkv-cache: The cache for diffusion language models.Advances in
Neural Information Processing Systems38 (2025), 149009–149033.
[27] Yuxin Ma, Lun Du, Lanning Wei, Kun Chen, Qian Xu, Kangyu Wang,
Guofeng Feng, Guoshan Lu, Lin Liu, Xiaojing Qi, et al. 2025. dinfer:
An efficient inference framework for diffusion language models.arXiv
preprint arXiv:2510.08666(2025).
[28] Tiyasa Mitra, Ritika Borkar, Nidhi Bhatia, Ramon Matas, Shivam Raj,
Dheevatsa Mudigere, Ritchie Zhao, Maximilian Golub, Arpan Dutta,
Sailaja Madduri, et al. 2025. Beyond the buzz: A pragmatic take on
inference disaggregation.arXiv preprint arXiv:2506.05508(2025).
14

## PDF Page 15

Sangam : Efficiently Serving Diffusion LLMs with the AR Stack
[29] Shen Nie, Qiyang Min, Shaoxuan Xu, Zihao Huang, Yuxuan Song,
Yong Shan, Yankai Lin, Wayne Xin Zhao, Chongxuan Li, and Ji-Rong
Wen. 2026. Improved Large Language Diffusion Models.arXiv preprint
arXiv:2606.25331(2026).
[30] Shen Nie, Fengqi Zhu, Chao Du, Tianyu Pang, Qian Liu, Guangtao
Zeng, Min Lin, and Chongxuan Li. 2025. Scaling up masked diffusion
models on text. InInternational Conference on Learning Representations,
Vol. 2025. 82974–82997.
[31] Shen Nie, Fengqi Zhu, Zebin You, Xiaolu Zhang, Jingyang Ou, Jun Hu,
Jun Zhou, Yankai Lin, Ji-Rong Wen, and Chongxuan Li. 2026. Large
language diffusion models.Advances in Neural Information Processing
Systems38 (2026), 50608–50646.
[32] NVIDIA. 2026.Dynamo: A Datacenter Scale Distributed Inference Serv-
ing Framework. Version 1.1.1.https://github.com/ai-dynamo/dynamo
[33] Brendan O’Donoghue and Sebastian Flennerhag. 2026. Dif-
fusionGemma: 4x Faster Text Generation. Google Blog.
https://blog.google/innovation-and-ai/technology/developers-
tools/diffusion-gemma-faster-text-generation/.
[34] Jingyang Ou, Shen Nie, Kaiwen Xue, Fengqi Zhu, Jiacheng Sun, Zhen-
guo Li, and Chongxuan Li. 2025. Your absorbing discrete diffusion
secretly models the conditional distributions of clean data. InInterna-
tional Conference on Learning Representations, Vol. 2025. 64972–65009.
[35] Pratyush Patel, Esha Choukse, Chaojie Zhang, Aashaka Shah, Íñigo
Goiri, Saeed Maleki, and Ricardo Bianchini. 2024. Splitwise: Efficient
generative llm inference using phase splitting. In2024 ACM/IEEE
51st Annual International Symposium on Computer Architecture (ISCA).
IEEE, 118–132.
[36] Ruoyu Qin, Zheming Li, Weiran He, Jialei Cui, Feng Ren, Mingxing
Zhang, Yongwei Wu, Weimin Zheng, and Xinran Xu. 2025. Mooncake:
Trading more storage for less computation—a {KVCache-centric}
architecture for serving {LLM} chatbot. In23rd USENIX conference on
file and storage technologies (FAST 25). 155–170.
[37] Qwen, :, An Yang, Baosong Yang, Beichen Zhang, Binyuan Hui, Bo
Zheng, Bowen Yu, Chengyuan Li, Dayiheng Liu, Fei Huang, Haoran
Wei, Huan Lin, Jian Yang, Jianhong Tu, Jianwei Zhang, Jianxin Yang,
Jiaxi Yang, Jingren Zhou, Junyang Lin, Kai Dang, Keming Lu, Keqin
Bao, Kexin Yang, Le Yu, Mei Li, Mingfeng Xue, Pei Zhang, Qin Zhu, Rui
Men, Runji Lin, Tianhao Li, Tianyi Tang, Tingyu Xia, Xingzhang Ren,
Xuancheng Ren, Yang Fan, Yang Su, Yichang Zhang, Yu Wan, Yuqiong
Liu, Zeyu Cui, Zhenru Zhang, and Zihan Qiu. 2025. Qwen2.5 Technical
Report. arXiv:2412.15115 [cs.CL]https://arxiv.org/abs/2412.15115
[38] Litu Rout, Constantine Caramanis, and Sanjay Shakkottai. 2026. An-
chored diffusion language model.Advances in Neural Information
Processing Systems38 (2026), 89607–89661.
[39] Subham S Sahoo, Marianne Arriola, Yair Schiff, Aaron Gokaslan, Edgar
Marroquin, Justin T Chiu, Alexander Rush, and Volodymyr Kuleshov.
2024. Simple and effective masked diffusion language models.Ad-
vances in Neural Information Processing Systems37 (2024), 130136–
130184.
[40] Subham Sekhar Sahoo, Zhihan Yang, Yash Akhauri, Johnna Liu, Deep-
ansha Singh, Zhoujun Cheng, Zhengzhong Liu, Eric P. Xing, John
Thickstun, and Arash Vahdat. 2026. Esoteric Language Models.
https://openreview.net/forum?id=XepOJx5ng4
[41] Jiaxin Shi, Kehang Han, Zhe Wang, Arnaud Doucet, and Michalis
Titsias. 2024. Simplified and generalized masked diffusion for discrete
data.Advances in neural information processing systems37 (2024),
103131–103167.
[42] Madhavapeddi Shreedhar and George Varghese. 1995. Efficient fair
queueing using deficit round robin. InProceedings of the conference
on Applications, technologies, architectures, and protocols for computer
communication. 231–242.
[43] Yuxuan Song, Zheng Zhang, Cheng Luo, Pengyang Gao, Fan Xia,
Hao Luo, Zheng Li, Yuehang Yang, Hongli Yu, Xingwei Qu, et al .
2025. Seed diffusion: A large-scale diffusion language model with
high-speed inference.arXiv preprint arXiv:2508.02193(2025).
[44] Jovan Stojkovic, Chaojie Zhang, Íñigo Goiri, Josep Torrellas, and Esha
Choukse. 2025. Dynamollm: Designing llm inference clusters for per-
formance and energy efficiency. In2025 IEEE International Symposium
on High Performance Computer Architecture (HPCA). IEEE, 1348–1362.
[45] Foteini Strati, Sara Mcallister, Amar Phanishayee, Jakub Tarnawski,
and Ana Klimovic. 2024. D \’ej\avu: Kv-cache streaming for fast,
fault-tolerant generative llm serving.arXiv preprint arXiv:2403.01876
(2024).
[46] Biao Sun, Ziming Huang, Hanyu Zhao, Wencong Xiao, Xinyi Zhang,
Yong Li, and Wei Lin. 2024. Llumnix: Dynamic scheduling for large
language model serving. In18th USENIX symposium on operating
systems design and implementation (OSDI 24). 173–191.
[47] Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion
Jones, Aidan N Gomez, Łukasz Kaiser, and Illia Polosukhin. 2017.
Attention is all you need.Advances in neural information processing
systems30 (2017).
[48] Dimitri von Rütte, Janis Fluri, Omead Pooladzandi, Bernhard
Schölkopf, Thomas Hofmann, and Antonio Orvieto. 2025. Scal-
ing behavior of discrete diffusion language models.arXiv preprint
arXiv:2512.10858(2025).
[49] Qingyan Wei, Yaojie Zhang, Zhiyuan Liu, Puyu Zeng, Yuxuan Wang,
Biqing Qi, Dongrui Liu, and Linfeng Zhang. 2026. Accelerating Dif-
fusion Large Language Models with SlowFast Sampling: The Three
Golden Principles. arXiv:2506.10848 [cs.CL]https://arxiv.org/abs/
2506.10848
[50] Chengyue Wu, Hao Zhang, Shuchen Xue, Shizhe Diao, Yonggan Fu,
Zhijian Liu, Pavlo Molchanov, Ping Luo, Song Han, and Enze Xie.
2025. Fast-dllm v2: Efficient block-diffusion llm.arXiv preprint
arXiv:2509.26328(2025).
[51] Chengyue Wu, Hao Zhang, Shuchen Xue, Zhijian Liu, Shizhe Diao,
Ligeng Zhu, Ping Luo, Song Han, and Enze Xie. 2025. Fast-dllm:
Training-free acceleration of diffusion llm by enabling kv cache and
parallel decoding.arXiv preprint arXiv:2505.22618(2025).
[52] Zhihui Xie, Jiacheng Ye, Lin Zheng, Jiahui Gao, Jingwei Dong, Zirui
Wu, Xueliang Zhao, Shansan Gong, Xin Jiang, Zhenguo Li, et al. 2025.
Dream-coder 7b: An open diffusion language model for code.arXiv
preprint arXiv:2509.01142(2025).
[53] Jiacheng Ye, Zhihui Xie, Lin Zheng, Jiahui Gao, Zirui Wu, Xin Jiang,
Zhenguo Li, and Lingpeng Kong. 2025. Dream 7b: Diffusion large
language models.arXiv preprint arXiv:2508.15487(2025).
[54] Zihao Ye, Lequn Chen, Ruihang Lai, Wuwei Lin, Yineng Zhang,
Stephanie Wang, Tianqi Chen, Baris Kasikci, Vinod Grover, Arvind
Krishnamurthy, et al. 2025. Flashinfer: Efficient and customizable
attention engine for llm inference serving.Proceedings of Machine
Learning and Systems7 (2025).
[55] Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, and
Byung-Gon Chun. 2022. Orca: A distributed serving system for
{Transformer-Based} generative models. In16th USENIX symposium
on operating systems design and implementation (OSDI 22). 521–538.
[56] Yifan Yu, Yuqing Jian, Junxiong Wang, Zhongzhu Zhou, Donglin
Zhuang, Xinyu Fang, Sri Yanamandra, Xiaoxia Wu, Qingyang Wu,
Shuaiwen Leon Song, et al . 2026. Introspective diffusion language
models.arXiv preprint arXiv:2604.11035(2026).
[57] Siyan Zhao, Devaansh Gupta, Qinqing Zheng, and Aditya Grover.
2026. d1: Scaling reasoning in diffusion large language models via
reinforcement learning.Advances in Neural Information Processing
Systems38 (2026), 56729–56762.
[58] Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff
Huang, Cody H Yu, Shiyi Cao, Christos Kozyrakis, Ion Stoica, Joseph E
Gonzalez, et al. 2024. Sglang: Efficient execution of structured lan-
guage model programs.Advances in neural information processing
systems37 (2024), 62557–62583.
15

## PDF Page 16

Kedia et al.
[59] Yinmin Zhong, Shengyu Liu, Junda Chen, Jianbo Hu, Yibo Zhu, Xu-
anzhe Liu, Xin Jin, and Hao Zhang. 2024. {DistServe}: Disaggregating
prefill and decoding for goodput-optimized large language model
serving. In18th USENIX Symposium on Operating Systems Design and
Implementation (OSDI 24). 193–210.
16