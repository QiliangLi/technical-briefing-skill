stion into all its
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