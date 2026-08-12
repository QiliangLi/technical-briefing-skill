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
under TP. SwiftQK addresses a new operator-level bottle-
neck in TP by reformulating QK-Norm as an operator-
aware communication-minimal primitive, rather than only as
a communication-overlap problem. It replaces full-vector Q/K
activation exchange with scalar partial-sum aggregation and
overlaps Peer-to-Peer (P2P) scalar reduction with independent
element-wise multiplication over the same local Q/K shard
inside a deadlock-safe persistent kernel.
Evaluations on recent open language models show that
SwiftQK reduces TPOT by 29.5% and increases saturated
request throughput by 25.4% on average over the All-Gather-
based QK-Norm used by the evaluated models. Notably,
even against an optimized scalar-aggregation implementation,
SwiftQK reduces TPOT by 14.3% and increases saturated
request throughput by 8.8% on average.
II. BACKGROUND ANDMOTIVATION
A. Layerwise QK-Normalization
Earlier LLMs followed a standard Pre-LN transformer ar-
chitecture. In this design, linear projections produce the Query
(Q), Key (K), and Value (V) tensors, which are then directly
passed to Scaled Dot-Product Attention.
As model sizes and input lengths increase, stabilizing atten-
tion logits becomes more important. To address this issue, ViT-
22B [5] adopts Query-Key Normalization (QK-Norm), which
normalizes the projected Q and K tensors before attention.
QK-Norm can be applied at different granularities. Layer-
wise QK-Norm computes one normalization factor over the
entire projected Q or K dimension, whereas headwise QK-
Norm computes an independent factor for each attention head.
Recent open language model series [6]–[8] adopt the layerwise
formulation by applying RMSNorm [9] before Scaled Dot-
Product Attention (Fig. 1(a)).
Letx∈R H denote a full projected Q or K vector, where
His its dimension. RMS-Norm is computed as:
RMSNorm(x) = xq
1
H
PH
j=1 x2
j +ϵ
⊙γ(1)
whereϵis a small constant for numerical stability andγis a
learnable scaling parameter. Because the normalization factor
depends on allHelements, partitioning this dimension under
TP requires cross-rank aggregation.
B. Model Parallelism
Serving large language models often requires distributing
computation and memory across multiple GPUs. Inference
systems therefore rely on model parallelism, which partitions a
model across devices to reduce per-device resource demands.
The two common forms are Pipeline Parallelism (PP) [10] and
arXiv:2608.09160v1  [cs.LG]  10 Aug 2026

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
Fig. 2 for comparison). RMS-Norm performs only lightweight
reduction and element-wise operations, while the required
cross-GPU communication cost is large. Therefore, simply
overlapping communication with computation is insufficient
to remove the QK-Norm bottleneck under TP.
III. DESIGN ANDIMPLEMENTATION OFSWIFTQK
To mitigate the layerwise QK-Norm bottleneck under TP,
we proposeSwiftQK, a communication-efficient fused multi-
GPU RMS-Norm kernel. SwiftQK performs the entire QK-
Norm procedure within a single fused kernel, reducing the
kernel launch overhead caused by separate communication
and normalization kernels. For each token, SwiftQK decom-
poses RMS-Norm into three phases: local squared-sum com-
putation, communication-computation overlap between peer-
to-peer reduction and element-wise multiplication, and final
normalization with the global RMS factor. SwiftQK executes

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
SwiftQK hides this remaining latency by overlapping the
P2P reduction with RMS-Norm weight multiplication, which
is independent of the reduction result. Specifically, Warp 0 is
dedicated to the communication path and performs the P2P
reduction over the IPC buffers to obtain the global squared
sum. Meanwhile, the remaining warps perform element-wise
multiplication with the RMS-Norm weights. Because this
multiplication does not depend on the global squared sum,
it can safely proceed while the P2P reduction is in progress.
C. Phase C: Final Normalization with the Global RMS Factor
After the P2P reduction and the element-wise multiplication
complete, SwiftQK has all inputs needed for the RMS scaling:
the global squared sum and the weight-multiplied local shard.
It then applies the global RMS scaling factor to each local
element and writes only the final normalized shard to HBM.
D. Deadlock-Safe Persistent Execution
All peer blocks participating in the same synchronization
step must be concurrently resident during in-kernel P2P syn-
chronization. If one block waits for a peer block that is not
yet resident, the kernel can enter cyclic waiting, i.e., deadlock.
To prevent deadlock, SwiftQK uses a persistent execution
model with a bounded launch grid. It launches only as many
blocks as can reside concurrently on the Streaming Multipro-
cessors (SMs), rather than launching one block per token. Let
Bres denote the maximum number of resident blocks per SM
under the SwiftQK kernel configuration, and letN SM denote
the number of SMs. SwiftQK launches at mostB res ×N SM
blocks, whereB res is determined by the per-block resource
usage, including registers, shared memory, and thread count.
Algorithm 1Fused Multi-GPU Persistent RMS-Norm Kernel
Input:Local InputX local, WeightsW local, Total HiddenH total
Input:Num GPUsN, Current Rankr, IPC BuffersB IP C
Output:Normalized local shardY local
foreach tokentin assigned tokens (stride loop)do
Phase A: Local Sum of Squares
Slocal ←BlockReduce Sum(Xlocal[t]2)
ifthread id = 0then
BIP C [r].sumsq[t]←S local
end if
__syncthreads()// Barrier for Phase A
Phase B: Comm-Comp Overlap
ifwarp id = 0then
// Communication Path: Push-wait sync
RemoteWrite(flag) to peer GPUs
SpinWait(local flag)
Sglobal ← PN−1
k=0 BIP C [k].sumsq[t]// P2P reduction
RM S−1 ←1/
p
Sglobal/Htotal +ϵ
else
// Computation Path: Element-wise Product
foreachjin assigned hidden dimensionsdo
Xlocal[t][j]←X local[t][j]×W local[j]
end for
end if
__syncthreads()// Barrier for fused ops
Phase C: Final Normalization
foreachjin assigned hidden dimensionsdo
Ylocal[t][j]←X local[t][j]×RM S −1
end for
end for
When the number of tokens exceeds the number of resi-
dent blocks, each block processes multiple tokens in a loop,
forming a block-level token pipeline. This preserves deadlock
safety while maintaining throughput without launching sepa-
rate communication and normalization kernels.
IV. EVALUATION
A. Experimental Setup
Models and Workloads:We evaluate SwiftQK on three recent
LLMs with layerwise QK-Norm from the open language
model series: OLMoE (7B, MoE) [7], OLMo 2 (13B, dense),
and OLMo 3 (32B, dense). This selection varies model scale
and architecture while keeping QK-Norm common across
models. We use ShareGPT dataset and conduct model-specific
RPS sweeps below saturation: 46.5–48 RPS for OLMoE, 23.5–
25 RPS for OLMo 2, and 12.5–14 RPS for OLMo 3. For
the saturated-throughput evaluation, we submit the complete
request set at once to operate the server under saturating load.
Execution Environment:We conduct micro-architectural pro-
filing on two NVLink-connected NVIDIA RTX 3090 GPUs
and end-to-end serving evaluation on 4- and 8-GPU NVLink-
connected NVIDIA A100 servers. All kernels are integrated
into the vLLM serving engine.
Baselines and Metrics:We compare SwiftQK with
All-Gather-based QK-Norm,Comm-Overlap, and Mini-
Max(eager), and MiniMax(fusion).Comm-Overlapoverlaps
All-Gather communication with RMSNorm computation with-
out reducing the communication payload. MiniMax(eager)
performs scalar-statistic aggregation without full-vector Q/K
All-Gather, while MiniMax(fusion) further fuses scalar-

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
[2] W. Kwonet al., “Efficient memory management for large language
model serving with pagedattention,” inProceedings of the 29th sym-
posium on operating systems principles, 2023, pp. 611–626.
[3] L.-W. Changet al., “Flux: Fast software-based communication overlap
on gpus through kernel fusion,”arXiv preprint arXiv:2406.06858, 2024.
[4] K. Honget al., “Flashoverlap: A lightweight design for efficiently
overlapping communication and computation,”arXiv preprint arXiv, vol.
2504, 2025.
[5] M. Dehghaniet al., “Scaling vision transformers to 22 billion parame-
ters,” inInternational conference on machine learning. PMLR, 2023,
pp. 7480–7512.
[6] T. OLMo, “2 olmo 2 furious,”arXiv preprint arXiv:2501.00656, 2024.

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