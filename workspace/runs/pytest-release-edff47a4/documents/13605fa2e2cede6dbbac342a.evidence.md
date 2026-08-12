# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

## PDF Page 1

IEEE COMPUTER ARCHITECTURE LETTERS 1
SwiftQK: Fast and Communication-Efficient Tensor
Parallelism for Query-Key Normalization
Gyudong Kim , Wonjun Han , and Young Geun Kim
Abstract—Query-Key Normalization (QK-Norm) improves the
training stability and quality of modern Large Language Models
(LLMs). However, under Tensor Parallelism (TP), layerwise QK-
Norm introduces additional cross-GPU communication because
the normalization factor depends on the full hidden vector . We
present SwiftQK, a multi-GPU RMSNorm kernel that exchanges
only scalar normalization statistics and overlaps the remaining
Peer-to-Peer reduction with independent element-wise computa-
tion in a deadlock-safe persistent kernel. Evaluations on recent
LLMs show that SwiftQK reduces QK-Norm latency by 81.4–
93.9% relative to the standard TP QK-Norm using full-vector
All-Gather . In end-to-end serving, SwiftQK reduces TPOT on
average by 29.5% over the All-Gather-based baseline and by
14.3% over an optimized scalar-aggregation implementation.
Index Terms—Distributed architectures, tensor parallelism,
kernel fusion.
I. INTRODUCTION
T
HE rapid growth of Large Language Models (LLMs)
has made distributed serving essential for addressing
limited GPU memory capacity and latency constraints [1].
A widely adopted strategy for distributed serving is Tensor
Parallelism (TP), which shards intra-layer computation across
multiple GPUs. By parallelizing each layer, TP reduces per-
request latency. As a result, modern inference engines such as
vLLM [2] commonly adopt TP.
Recent LLMs increasingly adopt Query-Key Normalization
(QK-Norm) to stabilize attention. In its layerwise formulation,
each normalization factor depends on the full projected Query
(Q) or Key (K) vector. However, this vector is partitioned
across GPUs under TP, requiring cross-GPU synchronization
that introduces substantial communication overhead.
To mitigate the communication overhead of TP, existing
kernel-fusion techniques overlap communication with compu-
tation [3], [4]. These techniques are effective when commu-
nication can be hidden behind sufficient independent compu-
tation. However, QK-Norm has lightweight computation and
large cross-GPU synchronization cost, making overlap alone
insufficient. This motivates combining communication-volume
reduction with overlapping for layerwise QK-Norm under TP.
In this letter, we proposeSwiftQK, a communication-
efficient multi-GPU RMS-Norm kernel for QK-Normalization
This work was supported in part by the National Research Foundation of
Korea (NRF) grant funded by MSIT (RS-2025-24534857, RS-2026-25522655,
RS-2025-25434746, and RS-2026-25486583), in part by IITP-ITRC (Infor-
mation Technology Research Center) grant funded by MSIT under Grant
IITP-2026-RS-2023-00260091, and in part by IITP-ICT Creative Consilience
Program grant funded by MSIT under Grant IITP-2026-RS-2020-II201819.
(Gyudong Kim and Wonjun Han are co-first authors.) (Corresponding author:
Young Geun Kim.)
Department of Computer Science and Engineering, Korea University,
Seoul 02855, Republic of Korea (e-mail: gyudong kim@korea.ac.kr; sift-
heads@korea.ac.kr; younggeun kim@korea.ac.kr).
under TP.

## Evidence locator: PDF Page 2

## PDF Page 2

IEEE COMPUTER ARCHITECTURE LETTERS 2
Attention Block 
w/ QK-NormPre-LN Transformer
● ●
Input
Attention
Norm 1
Norm 2
MLP
Output
Scaled Dot-Product Attention 
Concat
Linear
K
Linear
VLinear
Norm
Linear
Q
Norm
Q/K Sync (All -gather) Layer Sync (All-Reduce)
 𝑌2   𝑍2𝐵2
Attention MLP
 𝐴1  𝑌1   𝑍1
𝐵1
Input Input
Output Output
Norm
𝐴2  𝑌2 𝑍2
𝐵2
NormNorm
 𝑄2
 𝑉2
𝐾2
Norm
 𝑌1 𝑍1
𝐵1
𝑉1
 𝐾1
 𝑄1
Norm Norm Norm
Norm
0
0.2
0.4
0.6
0.8
1
O-pp O-tp O2-pp O2-tp O3-pp O3-tp O-pp O-tp O2-pp O2-tp O3-pp O3-tp
OthersQ/K Norm Computation
Normalized Latency*
Q/K Sync
2GPU 4GPU
PP TP*
Olmo Olmo2 Olmo3
1
0.8
0.6
0.4
0.2
0 PP TP* PP TP* PP TP*
Olmo Olmo2 Olmo3
PP TP* PP TP*
(a) (b) (c)
Fig. 1. (a) Transformer block w/QK-Norm (b) TP w/layerwise QK-Norm, requiring All-Gather Q/K sync (c) PP–TP normalized total prompt-processing
latency comparison w/ and w/o layerwise QK-Norm; for each model and GPU count, latency is normalized to the corresponding PP latency.
Tensor Parallelism (TP) [1]. PP partitions the model by layers,
whereas TP partitions each layer across GPUs.
1) Pipeline Parallelism:In PP, GPUs execute different
groups of layers as sequential pipeline stages. This reduces
the per-device model footprint and limits communication to
stage boundaries. However, PP can introduce pipeline bubbles
and inter-stage dependencies, which increase serving latency.
2) Tensor Parallelism:For latency-sensitive LLM serving,
modern inference engines [2] often rely on TP when fast inter-
GPU interconnects are available. In TP, GPUs jointly execute
each layer by sharding intra-layer operations such as linear
projections and attention. As shown in Fig. 1(b), the first
linear projections in Attention and MLP layers are partitioned
along the output dimension, while the following projections
are partitioned along the input dimension. This layout allows
each GPU to directly consume its local activation shard in
the next matrix multiplication, requiring synchronization only
when the final projection output is combined, typically via
All-Reduce. By avoiding pipeline bubbles and unnecessary
communication between consecutive matrix multiplications,
TP is effective for reducing per-request latency.
C. Characterization of Layerwise QK-Norm Overhead
Recent LLMs increasingly adopt QK-Norm to stabi-
lize attention. However, layerwise QK-Norm breaks the
communication-efficient execution pattern of TP by inserting a
normalization step between the Q/K projections and attention
computation. Since TP partitions the projected Q/K hidden
dimension across GPUs, each GPU only holds a shard of the
full projected Q or K vector. RMS-Norm requires a reduction
over the full hidden vector, so each GPU cannot compute the
correct normalization factor from its local shard alone. This
introduces synchronization of Q/K vectors before attention can
proceed, typically via All-Gather in TP (Fig. 1(b)).
Fig. 1(c) reports normalized total prompt-processing time
for ShareGPT request set [11] on OLMo [12], OLMo2 [6],
and OLMo3 [8]. The workload uses vLLM’s unified serving
mode with continuous batching and is evaluated on two and
four A100 GPUs under PP and TP. The earlier model OLMo
does not use QK-Norm, whereas OLMo2 and OLMo3 apply
it to the projected Q and K tensors. The breakdown separates
Q/K synchronization, Q/K normalization computation, and the
remaining execution time. Across all settings, TP achieves
lower latency than PP, and the benefit generally increases with
more GPUs. However, this benefit is much smaller for OLMo2
and OLMo3 than for OLMo: on four GPUs, TP reduces
latency by 36.2% for OLMo, but only by 7.5% and 12.0%
for OLMo2 and OLMo3, respectively. This gap shows that
QK-Norm significantly weakens the latency advantage of TP.
Under PP, QK-Norm overhead (Q/K synchronization + Q/K
normalization computation) contributes only a small fraction
of the total execution time, accounting for 1.4% and 1.3%
on average for OLMo2 and OLMo3, respectively. In contrast,
under TP, QK-Norm overhead becomes a major bottleneck,
and its cost grows with the TP degree. For OLMo2 and
OLMo3, its overhead increases from 20.0% and 19.0% on
two GPUs to 30.1% and 29.7% on four GPUs, respectively.
This increase is dominated by Q/K synchronization, which
accounts for 73.6% and 72.8% of QK-Norm overhead on two
GPUs and rises to 85.6% and 85.5% on four GPUs. This trend
occurs because increasing the TP degree reduces per-GPU nor-
malization computation, but increases exposed synchronization
cost. As a result, layerwise QK-Norm overhead becomes a
communication-dominated bottleneck that limits TP efficiency.
D. Kernel Fusion for Communication Overlap
To reduce exposed communication overhead of TP, existing
kernel fusion methods such as FLUX [3] and FlashOverlap [4]
overlap communication with computation. These methods
mainly target GEMM-related communication patterns, such as
GEMM followed by All-Reduce, where matrix multiplication
provides enough computation to hide communication latency.
However, overlap is effective only when there is suffi-
cient computation to cover the communication cost. This
assumption does not hold for QK-Normalization under TP (see
Fig. 2 for comparison).

## Evidence locator: PDF Page 3

## PDF Page 3

IEEE COMPUTER ARCHITECTURE LETTERS 3
these phases in a persistent fused kernel, where resident
CUDA blocks repeatedly process tokens in a block-level token
pipeline. The algorithm detail is explained in Algorithm 1.
A. Phase A: Local Aggregation for Communication Reduction
The first phase of SwiftQK reduces QK-Norm communi-
cation to the minimum statistic needed for RMS-Norm. In
standard TP execution, each GPU exchanges full Q and K
activation shards through All-Gather before computing the
normalization statistics. However, the RMS factor (denomi-
nator of Equation 1) does not require the full hidden vector. It
only requires the squared sum of the hidden vector, PH
j=1 x2
j.
SwiftQK computes a local squared sum on each GPU over
its hidden-dimension shard and aggregates these partial sums
across GPUs using FP32 accumulation. This recovers the
global squared sum required for the RMS factor, replacing
theO(H)activation exchange withO(1)scalar partial-sum
aggregation while preserving the same global normalization
semantics.
B. Phase B: Comm–Comp Overlap for Latency Hiding
Although Phase A reduces the communication volume, the
P2P reduction still requires synchronization across GPUs.
Each GPU can compute the global squared sum only after the
scalar partial sums from all peer GPUs become visible through
the IPC buffers. This waiting time remains as synchronization
latency even after the communication volume is reduced.

## Evidence locator: PDF Page 4

## PDF Page 4

IEEE COMPUTER ARCHITECTURE LETTERS 4
01234
15.000
45.000
75.000
Olmo2
(5120,5120)
0
0.5
1
Relative 
Latency
1
0.75
0.5
0.25
0
Relative NVLink
TX Throughput
Relative SM
Issue Rate
(a)
Olmoe
(2048,2048)
Olmo3
(5120,1024)
1
0.75
0.5
0.25
0
 0
0.025
0.05
(b)
4
3
2
1
0
Max Absolute
Error
Mean Absolute
Error
1
0.5
0
0.05
0.025
0
RMSE
0.05
0.025
0
BF16
Minimax(fusion)All-Gather-based SwiftQK
64 4096 64 4096 64 4096Tokens FP8
(e4m3)
15
45
75
(c)
0.000
30.000
60.000
2
0.000
30.000
60.000
2
0.000
30.000
60.000
2
Olmo2(13B) Olmo3(32B)Olmoe(7B)
8GPU
0.000
30.000
60.000
0.000
30.000
60.000
2
0.000
30.000
60.000
2
TPOT(ms)
50
RPS
Olmo2(13B) Olmo3(32B)Olmoe(7B)
4GPU
②Overlap①AG-based ③Minimax(eager) ④Minimax(fusion)
46.5 47 47.5 48 46.5 47 47.5 4823.5 24 24.5 25 12.5 13 13.5 14 23.5 24 24.5 25 12.5 13 13.5 14
⑤SwiftQK
25
①②③④⑤ ①② ③④⑤ ①② ③④⑤ ①②③④⑤ ①② ③④⑤ ①②③ ④⑤Method
0
Throughput
(req/s)
Fig. 2. (a) Micro-architectural profiling; values in ( , ) indicate Q/K sizes. (b) Numerical precision comparison. (c) Serving performance comparison.
statistic aggregation and RMSNorm computation into an op-
timized kernel [13]. In both MiniMax baselines, cross-rank
scalar synchronization and RMSNorm computation are exe-
cuted sequentially, without hiding the synchronization latency
behind computation. We report TPOT and saturated request
throughput, defined as the average interval between output
tokens and completed requests per second, respectively.
B. Micro-architectural Profiling
Fig. 2(a) compares All-Gather-based QK-Norm, Mini-
Max(fusion), and SwiftQK at 64 and 4096 input tokens. The
reported latency includes both communication and normaliza-
tion computation, and all metrics are normalized to All-Gather-
based QK-Norm. Across all evaluated models and token
counts, SwiftQK reduces QK-Norm latency by 81.4–93.9%
compared with All-Gather-based QK-Norm and by 29.4–
77.0% compared with MiniMax(fusion). These results show
that SwiftQK provides additional latency reduction beyond
scalar-statistic aggregation.
Both MiniMax(fusion) and SwiftQK show lower mea-
sured NVLink TX throughput than All-Gather-based QK-
Norm, reflecting their compact scalar communication pay-
loads. At 4096 tokens, SwiftQK achieves a 2.8–4.6×higher
SM issue rate than MiniMax(fusion). This result is consistent
with SwiftQK’s in-kernel communication-computation over-
lap, where Warp 0 performs scalar P2P reduction while the
remaining warps execute independent weight multiplication.
C. Numerical Precision Comparison
Fig. 2(b) compares the numerical precision of the All-
Gather-based QK-Norm, MiniMax(fusion), and SwiftQK
against a high-precision gold output computed by full All-
Gather followed by FP64 RMSNorm. SwiftQK accumulates
local squared sums and cross-GPU scalar reductions in FP32,
even for BF16 and FP8-E4M3 activations. SwiftQK closely
matches the reference path in maximum absolute, mean ab-
solute, and RMS errors:5.0e−2,2.1e−3, and3.4e−3
for BF16, and5.0e−1,2.5e−2, and3.9e−2for FP8-
E4M3, respectively. These results indicate that SwiftQK does
not introduce additional numerical error beyond the target low-
precision format.
D. End-to-End Serving Performance
Fig. 2(c) compares TPOT across model-specific RPS sweeps
and saturated request throughput. Compared with the standard
All-Gather-based baseline, SwiftQK reduces TPOT by 29.5%
and increases saturated request throughput by 25.4% on av-
erage. Compared with Comm-Overlap and MiniMax(eager),
SwiftQK reduces TPOT by 17.9% and 28.5%, respectively,
with corresponding throughput gains of 14.6% and 20.1%.
Notably, even against an optimized scalar-aggregation imple-
mentation, SwiftQK reduces TPOT by 14.3% and increases
saturated request throughput by 8.8% on average. These results
show that SwiftQK’s end-to-end benefit is not only from
scalar-statistic aggregation, but also from combining reduced
communication volume with fused persistent execution and
in-kernel communication-computation overlap.
V. CONCLUSION AND FUTURE WORK
SwiftQK is a communication-efficient multi-GPU RMS-
Norm kernel for layerwise QK-Normalization under TP. It
replaces full-vector activation exchange with scalar partial-
sum aggregation and overlaps Peer-to-Peer reduction with
independent element-wise computation, reducing QK-Norm
communication without changing normalization semantics. On
recent OLMo models, SwiftQK reduces QK-Norm latency
by 81.4–93.9% relative to the All-Gather-based QK-Norm. In
end-to-end serving, SwiftQK reduces TPOT on average by
29.5% over All-Gather-based QK-Norm and by 14.3% over
an optimized scalar-aggregation implementation.
There are various ways to place and define normalization
within Transformer blocks, and recent work continues to
explore this design space [14]. When normalization spans TP-
partitioned activations and requires cross-GPU synchroniza-
tion, SwiftQK’s design principles may also apply. Future work
will explore how to adapt SwiftQK to these normalization
variants.
REFERENCES
[1] M. Shoeybiet al., “Megatron-lm: Training multi-billion param-
eter language models using model parallelism,”arXiv preprint
arXiv:1909.08053, 2019.
[2] W. Kwonet al.

## Evidence locator: PDF Page 5

## PDF Page 5

IEEE COMPUTER ARCHITECTURE LETTERS 5
[7] N. Muennighoffet al., “Olmoe: Open mixture-of-experts language
models,” inInternational Conference on Learning Representations, vol.
2025, 2025, pp. 62 061–62 121.
[8] T. Olmo, “Olmo 3,”arXiv preprint arXiv:2512.13961, 2025.
[9] B. Zhang and R. Sennrich, “Root mean square layer normalization,”
Advances in neural information processing systems, vol. 32, 2019.
[10] Y . Huanget al., “Gpipe: Efficient training of giant neural networks
using pipeline parallelism,”Advances in neural information processing
systems, vol. 32, 2019.
[11] anon8231489123, “ShareGPT Dataset,” https://huggingface.co/datasets/
anon8231489123/ShareGPT Vicuna unfiltered, 2023.
[12] D. Groeneveldet al., “Olmo: Accelerating the science of language
models,” inProceedings of the 62nd Annual Meeting of the Association
for Computational Linguistics, 2024, pp. 15 789–15 809.
[13] vLLM Project, “MiniMax TP RMSNorm,” https://github.com/
vllm-project/vllm, 2026, rms norm tp.py, commit 99a8561.
[14] M. Chenet al., “Simplegpt: Improving gpt via a simple normalization
strategy,”arXiv preprint arXiv:2602.01212, 2026.