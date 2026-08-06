## PDF Page 1

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 1
LightRot: A Light-weighted Rotation Scheme and
Architecture for Accurate Low-bit Large Language
Model Inference
Sangjin Kim,Member, IEEE,Yuseon Choi,Graduate Student Member, IEEE,Jungjun Oh,Graduate Student
Member, IEEE,Byeongcheol Kim,Graduate Student Member, IEEE,and Hoi-Jun Yoo,Fellow, IEEE,
Abstract—As large language models (LLMs) continue to
demonstrate exceptional capabilities across various domains, the
challenge of achieving energy-efficient and accurate inference
becomes increasingly critical. This work presents LightRot, a
lightweight rotation scheme and dedicated hardware accelerator
designed for low-bit LLM inference. The proposed architecture
integrates Grouped Local Rotation (GLR) and Outlier Direction
Aligning (ODA) algorithms with a hierarchical Fast Hadamard
Transform (FHT)-based rotation unit to address key challenges in
low-bit quantization, including the energy overhead of rotation
operations. The proposed accelerator, implemented in a 28nm
CMOS process, achieves a peak energy efficiency of 27.4 TOPS/W
for 4-bit inference, surpassing prior state-of-the-art designs.
Unlike conventional approaches that rely on higher-precision
inference or evaluate on basic language modeling tasks like GPT-
2, LightRot is optimized for advanced models such as LLaMA2-
13B and LLaMA3-8B. Its performance is further validated on
MT-Bench, demonstrating robust applicability to real-world con-
versational scenarios and redefining benchmarks for chat-based
AI systems. By synergizing algorithmic innovations and hardware
efficiency, this work sets a new paradigm for scalable, low-bit
LLM inference, paving the way for sustainable AI advancements.
Index Terms—Large Language Model, Quantization, Low-
bit Inference, Transformer, Outlier Handling, Rotation-based
Quantization, and Hardware for Artificial Intelligence.
I. INTRODUCTION
N
OW ADAYS, large language models (LLMs) have
demonstrated remarkable capabilities across a wide
range of tasks, including language translation, code gen-
eration, and conversational AI. Their profound impact on
industries and daily interactions has solidified their role as a
Manuscript received 2 December 2024; revised 3 March 2025; accepted 28
March 2025.
This work was supported in part by Samsung Electronics Company Ltd.
under Grant IO201207-07799-01 and in part by the Institute of Information
and Communications Technology Planning and Evaluation (IITP) grant funded
by the Korea Government (MSIT) (2022-0-01170, PIM Semiconductor Design
Research Center) (Corresponding author: Hoi-Jun Yoo)
The Authors are with the PIM Semiconductor Design Research Center
(AI-PIM), Daejeon 34141, South Korea (e-mail: sangjinkim@kaist.ac.kr;
hjyoo@kaist.ac.kr)
© 2025 IEEE. Personal use of this material is permitted. Permission from
IEEE must be obtained for all other uses, in any current or future media,
including reprinting/republishing this material for advertising or promotional
purposes, creating new collective works, for resale or redistribution to servers
or lists, or reuse of any copyrighted component of this work in other works.
S. Kim, Y . Choi, J. Oh, B. Kim and H. Yoo, “LightRot: A Light-
Weighted Rotation Scheme and Architecture for Accurate Low-Bit Large
Language Model Inference,” in IEEE Journal on Emerging and Selected
Topics in Circuits and Systems, vol. 15, no. 2, pp. 231-243, June 2025, doi:
10.1109/JETCAS.2025.3558300.
cornerstone of modern artificial intelligence [1]–[4]. However,
the immense size of LLMs presents significant challenges,
particularly in terms of memory and computational demands.
This necessitates the development of lightweight techniques
such as quantization to optimize their performance. These opti-
mizations are critical not only for server-side inference, where
large-scale computational resources are available, but also for
on-device applications, where resources are constrained and
smaller LLMs must perform efficiently.
Quantization has emerged as a key technique to address
the computational and memory challenges posed by LLMs,
focusing on reducing the precision of data representations
while maintaining acceptable accuracy. As illustrated in Fig.
1 (a), the quantization process for LLMs involves three main
data types: weights (W), input activations (IA), and key-
value caches (KV). Among these, weights are typically quan-
tized after training through post-training quantization, allowing
them to be stored in a compressed form without impacting
runtime performance. In contrast, input activations and key-
value caches are generated dynamically during inference,
requiring efficient online quantization methods to minimize
runtime overhead.
A significant challenge lies in the distribution of input
activations, which often vary significantly across channels
and exhibit large outliers. These heavy-tailed distributions
lead to suboptimal quantization performance, as conventional
quantization methods struggle to capture the variations without
introducing substantial errors. Moreover, during the gener-
ation stage, frequent access to weight parameters stored in
external memory creates a critical bottleneck, both in terms
of energy consumption and inference speed. While weight-
only quantization [5]–[7] addresses these issues to some extent
by focusing on the weight data, it does not fully resolve
the challenges associated with input activations and key-value
caches, which remain major contributors to computational and
memory costs.
As shown in Fig. 1 (b), rotation-based quantization has
emerged as a promising solution to address the limitations
of conventional quantization methods. By applying a rotation
matrix to tensors, such as W, IA, and KV , this approach
reduces the impact of outliers and improves quantizability.
Specifically, the rotation operation reorients the data distribu-
tion, minimizing the variance in certain directions and enabling
a more even representation suitable for quantization.
One of the key principles behind this method is the com-
arXiv:2607.27704v1  [cs.AR]  30 Jul 2026

## PDF Page 2

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 2
(a)
(b)
Fig. 1: (a) Challenge of LLM Quantization by Outlier and (b)
Concept of Rotation
putational invariance property of rotation, which ensures that
tensor rotations do not affect the overall network outputs
when paired with proper inverse rotations after computation.
This property enables more flexible manipulation of tensor
representations without compromising model performance.
Unlike weight-only quantization, rotation-based quantization
effectively extends its benefits to IA and KV , which are
significant contributors to the memory and computational
costs of LLMs. As a result, this method achieves a more
comprehensive reduction in both memory footprint and com-
putational overhead, making it a compelling alternative for
low-bit inference scenarios [11]–[13].
In this work, we propose LightRot, a lightweight rotation-
based quantization scheme designed to optimize low-bit infer-
ence for LLMs. LightRot significantly reduces the computa-
tional burden by lowering the algorithmic complexity of the
rotation process, making it more practical for real-time and
resource-constrained environments. Additionally, the proposed
method enhances the accuracy of rotation-based quantization
by refining the rotation operation, ensuring minimal distortion
of the quantized tensors.
To complement the algorithm, we also introduce a dedicated
hardware architecture that accelerates the rotation process.
This architecture is optimized to handle the computational de-
mands of rotation-based quantization efficiently, while main-
taining a low area and power footprint. By addressing both
the algorithmic and hardware challenges, LightRot achieves
substantial improvements in memory efficiency, computational
cost, and overall inference performance, making it a compre-
hensive solution for low-bit LLM applications.
II. BACKGROUND ANDCHALLENGES
One of the most challenging aspects of quantizing LLMs
lies in the distribution of input activations (IA). The IA
distribution often varies significantly across channels, with
some channels exhibiting notably higher magnitudes compared
to others, forming what are referred to as outlier channels.
These outlier channels play a crucial role in determining the
overall accuracy of the model, as their improper handling
can lead to significant performance degradation. Interestingly,
the magnitudes of these outlier channels remain relatively
stable across tokens and batches, making them a consistent
characteristic of IA distributions. This stability can be effec-
tively leveraged during the quantization process to optimize
performance.
Addressing these unique characteristics, prior studies on
low-bit LLM inference, such as [5], [7]–[9], [11], [12], have
focused on developing methods to accurately and efficiently
quantize IAs or weights (W) while minimizing accuracy
loss. These works have advanced the field by incorporating
techniques that account for IA distribution properties, par-
ticularly outlier channels, which present both challenges and
opportunities for improved quantization.
A. Channel scale-aware Quantization
A straightforward approach to addressing the challenges of
IA quantization is to adjust the scaling factors for each channel
based on their saliency. Some methods [5], [8] adopt this
strategy by applying different scaling factors to each channel
according to its saliency, making the distributions across
channels more even. For example, one approach [8] leverages
the observation that weights (W) with flat distributions are
easier to quantize than activations (IA). By migrating the quan-
tization difficulty from activations to weights, these methods
smooth IA outliers through offline scaling, making them more
quantizable. Another approach [5] applies a similar strategy
during the generation stage, reducing weight precision while
maintaining IA in floating-point form to alleviate bottlenecks
caused by weight-efficient matrix accumulation.
However, while scaling factor methods ensure the range
of salient channels is preserved, they inherently limit the
resolution of the quantized data due to the inherent limitations
of scaling. This trade-off imposes constraints on their quanti-
zation effectiveness. To address this, mixed precision strategies
[7], [9], assign higher precision to salient channels and lower
precision to less critical ones. This approach achieves a
balance between maintaining accuracy and lowering effective
precision. However, it introduces additional challenges, such as
latency overhead on GPUs and multi-precision logic overhead
on NPUs, posing challenges in practical implementations.
B. Rotation-based Quantization
Rotation-based quantization offers an alternative approach
to addressing the challenges posed by IA outliers by transform-
ing the data distribution through matrix rotation. As shown in
Fig. 1 (b), a rotation matrix (e.g., Random Hadamard matrix) is
multiplied to the IA matrix, effectively redistributing outliers
across channels and flattening the overall distribution. This
operation minimizes the directional variance across channels,
making the IA data more quantizable. One key advantage of
this approach is the computational invariance guaranteed by

## PDF Page 3

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 3
Fig. 2: Applying Rotation in LLM Model with Online/offline Rotation.
Fig. 3: Challenges of Rotation-based Quantization
the rotational property of the Hadamard matrix. By applying
the inverse matrix to the weights (W), the overall computa-
tional correctness of the network is preserved, as proved in
[11].
In practical implementations, rotation matrices can be cat-
egorized into offline and online types, depending on whether
the rotation can be pre-merged with the weights. As illustrated
in Fig. 2, transformer layers typically involve four rotation
matrices (R1–R4). Among these, R1 and R2 can be pre-
merged with the weights during offline processing, reducing
runtime overhead. However, R3 and R4 require online rotation,
as they cannot be merged with the weights. Fortunately,
Hadamard matrices consist only of ±1 values, enabling online
rotation through simple addition operations on IA, without the
need for complex computations.
Some advanced methods, such as [12], further optimize
rotation-based quantization by employing learned rotation
matrices instead of random Hadamard matrices. While this
distribution-aware approach improves quantization perfor-
mance, it significantly increases computational complexity
and restricts its applicability to offline rotations. In contrast,
the proposed LightRot introduces a lightweight, distribution-
aware rotation algorithm that maintains low computational
complexity and extends its applicability to online rotations,
providing a more comprehensive and practical solution for
both offline and online rotations in low-bit LLM inference.
C. Challenges of Rotation-based Quantization Hardware
Despite its advantages, implementing rotation-based quan-
tization in hardware introduces significant challenges, as sum-
marized in Fig. 3. These challenges stem primarily from the
design of the rotation unit and the high cost of floating-point
(FP) operations required during rotation.
The first challenge is related to the datapath design of the
rotation unit. To process online Hadamard matrices (R 3 and
R4), a rotation unit is essential. Two primary approaches are
commonly used: matrix multiplication (MM)-based rotation
and fast Hadamard transform (FHT)-based rotation. The MM-
based approach multiplies the Hadamard matrix, consisting
only of+1and−1, with the IA tensor. While this requires
only addition operations, it involvesO(N 2)computations
for a vector of lengthN. On the other hand, FHT-based
rotation [14] employs a divide-and-conquer recursive algo-
rithm, significantly reducing the computational complexity to
O(Nlog 2 N).
However, FHT-based rotation can only be applied to di-
mensions that are powers of two, whereas many commercial
LLM architectures use non-power-of-two dimensions to op-
timize memory and computational efficiency. In these cases,
designers are forced to either rely solely on MM-based rotation
or combine MM-based and FHT-based approaches. Solely
using MM-based rotation results in high computational over-
head, with rotation operations accounting for up to 49.6%
of the multiply-accumulate (MAC) workload. Alternatively,
combining MM-based and FHT-based approaches introduces
a substantial hardware cost.
The second challenge stems from the high cost of FP oper-
ations in the rotation unit. While rotation-based quantization
allows layer computations within the NPU core to use efficient
INT operations, the rotation unit itself operates on IA before
quantization, requiring costly FP operations. FP units consume
significantly more resources, with power and area costs that
are25.9×and5.6×higher, respectively, compared to INT4
MAC units. Due to the high logic cost, even though FHT-
based rotation reduces the number of operations compared to
INT MAC, it still incurs significant energy consumption. This
results in over 35.7% energy overhead in the layer configu-
ration of the LLaMA2-7B model, making it a bottleneck for
energy-efficient LLM inference.
III. PROPOSEDLIGHTROTALGORITHM
In this section, we introduce the LightRot algorithm, de-
signed to support low-cost and high-accuracy low-bit quan-

## PDF Page 4

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 4
Fig. 4: Concept of Grouped Local Rotation.
Fig. 5: Rotation Operation and Rotation Unit Energy Reduc-
tion by GLR.
tized LLM inference. LightRot builds upon the existing ro-
tation algorithm [11] to maintain the performance of low-
bit quantized LLMs while simultaneously reducing rotation
costs through Grouped Local Rotation (GLR) and improving
rotation accuracy with Outlier Direction Aligning (ODA).
GLR reduces hardware costs by dividing rotation operations
into smaller groups and applying localized rotation within
each group. Meanwhile, ODA leverages the consistent outlier
distribution characteristics of LLMs and the properties of
Hadamard-based rotation to make post-rotation distributions
more quantizable, minimizing accuracy loss during quantiza-
tion.
A. Grouped Local Rotation
Quantized LLMs operate with quantized input activations
(IA) and weights (W) in each layer. The multiplication of IA
and W is performed in integer precision, enabling efficient
integer accumulation across thousands or tens of thousands
Fig. 6: Motivation of Outlier Direction Aligning.
of channel dimensions commonly found in LLM architectures
[2], [3]. However, to maintain accuracy, group quantization is
often applied, requiring FP16 precision scale factors and biases
[11]. Consequently, the output activation (OA) is computed in
FP precision and quantized for use as the IA in subsequent
layers.
For layers requiring online rotation, Hadamard matrices are
multiplied with IA before quantization. Despite Hadamard
matrices being composed solely of+1and−1, enabling
addition/subtraction-based computation, this operation must
still be performed in FP precision, incurring significant com-
putational costs. As illustrated in Fig. 4, online rotations
involvingR 4 matrices (e.g., between the first and second feed-
forward network (FFN) layers in transformer architectures)
introduce substantial computational overhead. In many LLM
models, gated linear units (GLU) or their variants, such as
SwiGLU [15], are used for accuracy enhancement between the
two FFN layers. Since activation rotations between these layers
cannot be merged into weights, the number of operations for
R4 becomesn×d 2
ffn, wherenis the number of tokens and
dffn is the FFN dimension. This results inn×d 2
ffn FP-Add
operations, making the reduction of rotation costs crucial.
GLR addresses this issue by dividing the IA into multiple

## PDF Page 5

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 5
Fig. 7: Concept of Outlier Direction Aligning.
groups and applying smaller rotation matrices to each group
instead of using a single large rotation matrix. The principle
of rotation-based quantization relies on redistributing outliers
across channels to enhance quantizability. GLR achieves suf-
ficient quantizability by dispersing outliers locally within each
group rather than across all channels. To implement this, GLR
partitions the IA intoGgroups, each consisting ofgchannels,
whereG=d ffn/g. For each group, ag×grotation matrix is
applied, resulting in a total ofGlocal rotations. Consequently,
the total number of FP-Add operations is reduced ton×d 2
ffn/G.
Fig. 5 summarizes the reduction in rotation operations and
energy achieved by GLR. Both matrix multiplication (MM)-
based and fast Hadamard transform (FHT)-based rotation units
are considered, following the discussion in Section II-C. For
non-power-of-two channel dimensions, FHT-based units re-
quire the integration of MM-based units, leading to inefficien-
cies. GLR mitigates this issue by usingg×grotation matrices,
allowinggto be chosen as a power-of-two dimension, even
ifd ffn is not. This enables FHT-only implementations. In our
benchmark evaluations,gwas set to 128 to match with the
group sizes for group quantizations in previous works [9],
[11], and GLR was tested on LLaMA2-7B/13B and LLaMA3-
8B models. With MM-based rotation units, GLR reduced
operations by 71–94×and energy by 96–127×. With FHT-
based rotation units, GLR reduced operations by 9–36×and
energy by 12–49×.
B. Outlier Direction Aligning
Fig. 6 illustrates the data distribution after applying GLR,
providing motivation for the Outlier Direction Aligning (ODA)
algorithm. IA quantization is particularly challenging due
to the presence of outliers, which rotation operations can
mitigate. However, the impact of outliers in practice is heavily
influenced by their magnitude. While most outliers fall within
100 times the inlier data range and can be easily dispersed by
rotation, certain extreme cases, termedoutstanding outliers
Fig. 8: Range Reduction with the ODA. Evaluated on the top
5% Outlier Group.
exhibit magnitudes thousands to tens of thousands of times
larger than the inlier range, making them difficult to disperse
effectively. These outstanding outliers significantly affect post-
rotation distributions.
Groups without outstanding outliers achieve near-normal
distributions after rotation, enabling improved quantizabil-
ity and accurate quantization. In contrast, groups containing
outstanding outliers exhibit uneven distributions even after
rotation. Due to the large magnitude of these outliers, they
dominate the rotated data, creating bimodal distributions where
the range is wasted, leading to significant quantizabilty drops
during quantization.
Fig. 7 illustrates the principle behind ODA, which addresses
this issue by leveraging the properties of Hadamard matri-
ces, commonly constructed using Sylvester construction [11].
Sylvester construction is a recursive method for generating
Hadamard matrices while maintaining orthogonality and com-
patibility with FHT algorithms. Starting from the base matrix:
H1 =
1 1
1−1

,

## PDF Page 6

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 6
larger Hadamard matrices are constructed recursively as:
Hn+1 =
Hn Hn
Hn −Hn

.
This method ensures that each row alternates between+1and
−1, except for the first row, which consists entirely of+1
values (the ”all-1-row”).
In rotation operations, outlier channels are multiplied by
the corresponding row of the Hadamard matrix. Outstanding
outliers result in wasteful range utilization, even when dis-
persed across channels. To address this, ODA aligns the largest
outlier in each group with the all-1-row of the Hadamard
matrix before performing rotation. By doing so, the channel
containing the outstanding outlier is multiplied solely by1,
while other channels are rotated normally using+1and
−1. This prevents bimodal distributions and ensures a more
gaussian, quantizable distribution after rotation.
However, while this approach effectively narrows the range,
it introduces a biased distribution, necessitating asymmetric
quantization, as expressed in the following equations:
qIA =round
IA−IA bias
IAscale

OA= 1
IAscale
·((IA·w)−(IA bias ·w))
Here, IAscale and IAbias are shared within the group, allowing
the second term, IA bias ·w, to become a constant multiplied by
the weights. Consequently, the channel-wise sum ofwcan be
precomputed offline at the group level, significantly reducing
the computation cost.
Furthermore, ODA requires a permutation step to align the
weights prior to rotation. However, as prior studies [5], [8],
[9], [12] have demonstrated, outlier indices remain consistent
across batches, allowing the permutation order to be pre-
determined using a calibration set, such as WikiText-2 per-
plexity benchmarks [16].
Fig. 8 summarizes the range savings achieved by ODA in
the top 5% outlier groups for the LLaMA2-7B model on the
WikiText-2 benchmark. These groups are highly critical to
accuracy due to their outstanding outliers. ODA effectively
reduces the range in these groups, achieving a minimum 1.97×
and maximum 28.1×reduction, with an average savings of
3.87×. The first layer showed the most significant range re-
duction, attributed to the higher prevalence of outstanding out-
liers compared to other layers. This reduced range eliminates
wasted capacity during quantization, enhancing quantizability.
IV. ALGORITHMEXPERIMENTS
In this section, we evaluate the performance of the pro-
posed LightRot algorithm using multiple benchmarks and
scenarios. The experiments demonstrate how the combined
features—Group Quantization (GQ), Grouped Local Rotation
(GLR), and Outlier Direction Aligning (ODA)—enhance per-
formance over existing baseline methods, particularly in low-
bit LLM inference tasks.
TABLE I: Perplexity Comparison on WikiText-2 Dataset
PPL↓Group Size LLaMa-2 LLaMa-3
7B 13B 8B
FP16 - 5.47 4.88 6.14
SmoothQuant [8] - 83.12 35.88 -
Quarot [11] - 6.10 5.40 -
Quarot [11] 128 5.93 5.26 -
SpinQuant [12] - 5.96 5.24 7.39
Rot Only - 6.11 5.38 7.93
Rot+GLR - 7.24 7.71 11.13
Rot+GLR+ODA - 6.74 5.73 10.9
Rot+GQ 128 5.87 5.22 7.30
Rot+GQ+GLR 128 5.80 5.14 7.12
Rot+GQ+GLR+ODA 128 5.73 5.08 6.98
INT4 for all IA, W, KV
INT4-INT4 opeartion for allQ, K, V, Projection, FFN
FP16-INT4 operation forQK T ,SV
(a)
(b)
(c)
Fig. 9: Evaluation with LLM-as-a-Judge [17]. Win/Loss Rate
against (a) Baseline Rotation Model (b) Proposed Model (c)
FP16 Baseline Model
A. Perplexity Evaluation on WikiText-2
Table 1 presents the perplexity (PPL) results on the
WikiText-2 dataset [16] for various configurations, demon-
strating the effectiveness of the proposed features (+GLR and
+ODA) in improving quantization quality while maintaining
low-bit inference efficiency.
The baseline rotation-only method achieved competitive
PPL values compared to existing approaches like SpinQuant
and Quarot. Also, using GLR and ODA together recovers
some accuracy, but without GQ, it still shows lower accuracy.

## PDF Page 7

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 7
However, the addition of GLR and ODA demonstrates clear
improvements in quantization performance. GLR significantly
reduces computational costs while maintaining accuracy, and
ODA further enhances performance by addressing the chal-
lenges posed by outstanding outliers.
When GLR is applied alone, there is a noticeable drop in
accuracy due to the lack of scale alignment between groups.
However, when GQ and GLR are used together with the
same group size, the accuracy improves significantly. This
improvement can be attributed to GQ’s ability to compensate
for the group-wise scale variations introduced by GLR. The
synergy between GQ and GLR ensures consistent quantization
quality across groups, highlighting the importance of jointly
applying these techniques for optimal performance.
To ensure a fair comparison, Quarot was also evaluated with
GQ applied. While Quarot demonstrated a minor PPL gap of
0.17 when group quantization was used, the proposed GLR
exhibited a much larger improvement, reducing the PPL gap
by 1.44. This stark contrast underscores the effectiveness of
GLR in addressing group-level challenges during rotation and
highlights its superiority over baseline methods.
Integrating all proposed features, including ODA, achieves
the best perplexity results across all configurations. The final
PPL values for the proposed method (+GQ+GLR+ODA) were
5.73 for LLaMA-2 (7B), 5.08 for LLaMA-2 (13B), and 6.98
for LLaMA-3 (8B). These results confirm that the proposed
LightRot algorithm achieves superior quantization quality and
inference performance compared to both baseline and state-
of-the-art methods.
B. Evaluation with LLM-as-a-Judge
Many existing quantization studies [11], [12] focus on
evaluating accuracy using limited metrics such as perplexity
or simple answering tasks. These evaluations often involve
short output token lengths, making it difficult to assess the
impact of KV cache quantization on long-form outputs. To
address these limitations, we employ MT-Bench [17] to eval-
uate model accuracy in realistic chat scenarios using win-loss
evaluations. This approach provides a more comprehensive
understanding of how quantization affects model performance
during extended interactions.
For this evaluation, we use conversational models
(LLaMA3-8B-instruct). By employing chat-optimized models,
the evaluation captures the interplay between quantization
techniques and model behavior in real-world applications.
As shown in Fig. 9 (a), we compare the proposed meth-
ods against the baseline rotation method (Quarot) using
win/lose rates. The proposed features (+GQ, +GQ+GLR,
+GQ+GLR+ODA) are incrementally added, and their impact
on performance is observed. With each added feature, the
baseline’s win rate consistently decreases, demonstrating the
effectiveness of the proposed techniques. Notably, when all
features are applied (+GQ+GLR+ODA), the baseline’s ad-
justed win rate drops to 32.2%, indicating clear superiority
of the proposed approach.
Similar to the analysis in the perplexity evaluation, applying
GLR alone leads to a reduction in win rate due to scale
misalignment between groups. However, when GQ and GLR
are applied together, the win rate improves significantly. This
is because GQ compensates for group-wise scale variations
introduced by GLR, ensuring a more consistent quantization
quality across groups. This synergy highlights the importance
of combining these techniques to achieve optimal perfor-
mance.
Fig. 9 (b) presents a comparison between the fully-featured
LightRot configuration (+GQ+GLR+ODA) and all other con-
figurations, including baseline and alternative quantization
methods. The proposed method maintains an adjusted win
rate exceeding 50% against all competitors, confirming its ro-
bustness and effectiveness. This consistency demonstrates that
LightRot not only handles standard quantization challenges
but also excels in more demanding evaluation settings.
Fig. 9 (c) compares the proposed methods against the
FP16 baseline. While FP16 naturally achieves the highest win
rate, the proposed LightRot configuration (+GQ+GLR+ODA)
remains relatively competitive compared to other quantized
configurations, demonstrating its ability to maintain strong
accuracy even under low-bit precision.
By leveraging MT-Bench and LLM-as-a-Judge evaluation
frameworks, this study highlights the practical advantages of
the proposed algorithm in real-world conversational scenarios,
where both short and extended outputs are critical.
V. PROPOSEDACCELERATOR
To validate the performance of the proposed LightRot algo-
rithm, we designed a dedicated hardware accelerator. Unlike
general-purpose hardware such as GPUs, the proposed acceler-
ator integrates specialized rotation and NPU units. This design
emphasizes the importance of LightRot in reducing rotation
costs, particularly in hardware with dedicated processing units.
In GPUs, rotation operations are handled as part of the
general datapath, where both rotation and neural network
computations utilize similar hardware resources. As a result,
the efficiency gap between these operations is relatively small,
and rotation overheads are less critical. However, in dedicated
accelerators, the disparity in hardware costs between floating-
point (FP) logic for the rotation unit and integer multiply-
accumulate (INT MAC) logic for the NPU becomes much
more significant, as discussed in Section II-C. This highlights
the necessity of minimizing FP overheads in rotation units
to maintain overall efficiency, making LightRot’s optimiza-
tions especially impactful in dedicated hardware designs. The
proposed hardware implementation thus serves as a focused
demonstration of LightRot’s ability to reduce computational
and energy costs in specialized accelerator environments.
A. Overall Architecture
The proposed accelerator is designed to maximize the effi-
ciency of low-bit LLM inference by integrating the LightRot
algorithm into a dedicated hardware architecture. As illustrated
in Fig. 10, the accelerator consists of two main components:
the NPU Core, which performs high-throughput integer-based
computations for quantized neural networks, and the Rotation
Unit (RU), which is optimized for floating-point operations

## PDF Page 8

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 8
Fig. 10: Overall Architecture.
required for rotation tasks. These components are intercon-
nected by a high-bandwidth interconnect network. The Global
Memory handles intermediate data storage for activations and
weights, while the Top Controller manages pipeline scheduling
and synchronization between the NPU Core and the Rotation
Unit.
The NPU Core is a highly optimized integer-based pro-
cessing unit designed for low-bit computations. It features
a 128×128 processing element (PE) array, organized into
16 sub-arrays of 32×32 PEs. Within each 32×32 PE sub-
array, a weight-stationary datapath is employed, where input
activations (IA) are broadcasted to 32 output channels, and
partial sums are accumulated through a 32-way reduction tree.
Between the 4×4 sub-arrays, a systolic datapath structure is
used, operating in a pipelined manner. This hybrid design
allows local operations to run in parallel while global opera-
tions follow a systolic flow, minimizing the pipeline register
count required for systolic datapath operations and ensuring
the critical path remains manageable.
Each NPU Core is equipped with 32KB of input activation
memory (IMEM) and 16KB of weight memory (WMEM) to
store intermediate data for low-bit matrix-vector computations.
Additionally, a scale and bias unit facilitates group quanti-
zation (GQ) by efficiently applying scale factors and biases
during arithmetic operations. These optimizations collectively
ensure high throughput for LLM inference while maintaining
low energy consumption.
The Rotation Unit (RU) is dedicated to performing online
rotation operations, a critical component of the LightRot algo-
rithm. FP memory stores input activations (IA) before rotation,
and INT memory holds the quantized IA after rotation. The
data flow within the RU begins with FP memory, where IA
is read and passed to the Gathering Unit. The Gathering Unit
performs permutation operations required for ODA, reordering
data as needed to optimize the subsequent rotation. The
reordered data is then processed by a Transposable Register
File (TRF) and an 8/16-way parallel Fast Hadamard Transform
(FHT) Unit, which executes the hierarchical rotation operation
with minimal energy and area overhead. After rotation, the
Quantization Unit quantizes the rotated IA and stores it in
INT memory, making it ready for use in the NPU Core.
This streamlined data flow ensures that rotation operations
are performed efficiently, with optimized support for GLR
and ODA, while minimizing overhead for subsequent low-bit
computations.
The Global Memory (GMEM) and Top Controller play
crucial roles in data management and task scheduling. The
GMEM includes a 1MB memory bank dedicated to storing
intermediate activations and weights, ensuring smooth data
transfer between components. The Top Controller utilizes a
RISC-based architecture to manage pipeline execution and
rotation scheduling. To further optimize coordination, the
pipelined rotation controller (PRC) ensures synchronization
between the NPU Core and the Rotation Unit (RU), effectively
hiding rotation latency and maintaining seamless operation
across computational stages.
This modular architecture fully capitalizes on the advantages
of the LightRot algorithm, with each component optimized for
its specific function in low-bit LLM inference. By combin-
ing an NPU Core tailored for integer-based neural network
computations with a specialized Rotation Unit for efficient
floating-point operations, the proposed accelerator delivers
high computational efficiency while effectively addressing the
challenges posed by rotation overhead.

## PDF Page 9

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 9
(a)
(b)
(c)
Fig. 11: Hierarchical FHT Operation with Transposable-RF
(TRF) for GLR.
B. Rotation Unit with Hierarchical FHT Operation
The Rotation Unit (RU) leverages a hierarchical Fast
Hadamard Transform (FHT) operation to efficiently handle
large-scale rotation tasks while minimizing area and energy
overhead. As shown in Fig. 11(a), the traditional one-step
FHT operation requires a large FHT unit, such as a 128-way
FHT, which introduces significant hardware complexity (e.g.,
896 adders). To address this, the proposed design employs
a two-step hierarchical FHT approach, breaking the rotation
operation into smaller units. In the 2-stage FHT unit, the size
of the small FHT unit was determined to match the target
group size of 128-way. For ease of hardware implementation,
a power-of-two number should be used. Among them, the
smallest number 16, whose square value is greater than 128
was selected for 2-stage operation.
In the first step, the RU uses a 16-way FHT Unit with 64
adders to perform partial rotations across smaller subgroups.
These partial results are then processed in the second step
using an 8-way FHT Unit with only 24 adders. By dividing
the operation into two stages, the RU significantly reduces
hardware requirements compared to a single large FHT unit.
This approach achieves a balance between computational
efficiency and hardware scalability, as illustrated in the right-
hand side of Fig. 11(a).
Fig. 11(b) highlights the data flow for the hierarchical FHT
operation, where the 8/16-way parallel FHT Unit and the
Transposable Register File (TRF) collaborate to support 2-step
rotation within a single rotation task. In the 2-step operation,
the first and second steps require data to be loaded with differ-
ent strides, which is efficiently managed using the 16×8 TRF’s
transposable datapath. Initially, 128 input activations (IA) are
loaded from FP-MEM into the TRF. During the first step, the
TRF performs row-by-row access to load 16 consecutive IAs
with a stride of 1. These values are then passed to the 16-way
FHT Unit for processing, and the resulting FHT outputs are
updated back into the corresponding rows of the TRF. In the
second step, the TRF switches to column-by-column access
with a stride of 16, loading 8 IAs at a time. These values
are processed by the 8-way FHT Unit, where half of the 16-
way FHT Unit is gated to operate in 8-way mode, saving
energy and hardware resources. The resulting outputs from
this step are written back to the respective columns of the
TRF. This hierarchical structure minimizes data movement,
reduces memory bandwidth requirements, and ensures high
throughput, making it an effective solution for hardware-
efficient rotation tasks.
The benefits of this design are further quantified in Fig.
11(c), where the hierarchical FHT operation (FHT-based +
TRF) achieves significant area and energy savings compared to
both matrix multiplication (MM)-based and single-step FHT-
based approaches. Specifically, the proposed design reduces
FHT logic area by 12.55 times compared to the 128-way FHT-
based rotation unit and energy by 1.82 times compared to the
16-way FHT-based rotation unit without TRF. These results
demonstrate that the hierarchical FHT operation effectively
balances performance and hardware efficiency, making it well-
suited for large-scale LLM inference tasks.
C. Gathering Unit for ODA
The Gathering Unit is designed to enable the reordering
of input activations (IA) during the loading process from FP-
MEM to the TRF, supporting the proposed ODA technique.
This unit ensures that outliers are identified and reordered
before being stored in the TRF, optimizing data distribution
for high quantizability with ODA.
As shown in Fig. 13, the Gathering Unit consists of key
components. The Channel Counter iterates through the 128
channels of IA to generate initial addresses. Simultaneously,
the Group ID Counter ensures that outliers are loaded as the
first entry in each group to facilitate ODA operations. The
Outlier Address Generator identifies outlier channels based
on precomputed indices stored in the Outlier Channel Table,
which are generated offline using calibration datasets. These
indices are sorted offline and accessed sequentially by the

## PDF Page 10

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 10
Fig. 12: Gathering Unit for ODA.
Group ID Counter and Table Counter. The Inlier Address
Generator handles the sequential generation of inlier addresses
by filtering out addresses that correspond to outlier channels.
The data flow begins with the Channel Counter, which
checks whether the current channel is the first in the group.
For the first channel in a group, the Group ID Counter directs
the Outlier Address Generator to fetch the data corresponding
to the outlier address assigned to the current group and loads
it from FP-MEM to the TRF. For all other channels, the Inlier
Address Generator sequentially generates inlier addresses.
To avoid outlier addresses, the Address Counter increments
sequentially while the Table Counter maintains the next outlier
address in the Outlier Buffer. Initially, the Table Counter
fetches the first outlier address and stores it in the Outlier
Buffer. When the Address Counter matches the value in the
Outlier Buffer, it skips that address (since it corresponds to
an outlier) and increments the Table Counter to fetch the next
outlier address into the Outlier Buffer. By keeping the outlier
addresses sorted in the Outlier Channel Table, the Outlier
Buffer always holds the nearest future outlier address. This
mechanism ensures that the Inlier Address Generator produces
only inlier addresses, avoiding conflicts with outliers.
This approach ensures that the ODA algorithm can effec-
tively align outliers to the all-1 row of the rotation matrix,
as discussed in Section III-C . By preprocessing the data at
the memory interface, the Gathering Unit minimizes runtime
overhead while supporting hierarchical FHT operations in the
RU.
VI. IMPLEMENTATIONRESULT
Fig. 13(a) summarizes the key specifications of the proposed
accelerator implemented in a 28nm logic CMOS process.
Operating at a frequency of 250 MHz and supply voltage of
0.9V , the accelerator includes 1430 KB of on-chip SRAM
and occupies a die area of 4.86 mm². It achieves a peak
performance of 1.64 TOPS for 4b-quantized operations and
an energy efficiency of 27.4 TOPS/W. These specifications
highlight the accelerator’s capability to deliver high computa-
tional performance and energy efficiency, specifically tailored
for 4b-quantized LLM inference tasks.
Fig. 13(b) illustrates the energy consumption per LLM
block across different configurations for the evaluated models:
LLaMA2-7B, LLaMA2-13B, and LLaMA3-8B. When com-
paring 8b w/o Rot to configurations using 4b + Rot, the
energy consumption initially increases due to the overhead
introduced by rotation operations. For example, straightfor-
wardly applying rotation results in significant power increases,
(a)
(b)
(c)
Fig. 13: (a) Chip Performance Summary (b) Energy Consump-
tion on LLaMA Prefilling Stage (Input Token Length = 128)
(c) Energy Breakdown
Fig. 14: Accuracy-Energy Comparison of Different Quantiza-
tion Configuration (LLaMMA2-7B)

## PDF Page 11

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 11
TABLE II: Comparison Table.
especially for larger models like LLaMA3-8B, where the
energy consumption reaches 31.3 mJ per block compared to
15.7 mJ for the 8-bit baseline.
The proposed GLR and ODA techniques, combined with the
FHT-based rotation unit, significantly reduce energy consump-
tion. These optimizations minimize the overhead of rotation
while maintaining high quantization accuracy. For instance, the
inclusion of GLR and ODA, alongside the hierarchical FHT
structure, achieves a dramatic reduction in energy usage. For
the LLaMA3-8B model, the energy consumption drops to 4.0
mJ, representing a 3.9× improvement compared to the baseline
configuration (8b w/o Rot). The combination of GLR and
ODA enables efficient management of rotation costs, ensuring
substantial energy savings while supporting 4-bit quantized
inference.
Fig. 13(c) illustrates the energy breakdown before and
after applying rotation optimizations. While neural network
computing energy is significantly reduced through rotation-
based quantization, MM-based rotation introduces substantial
energy overhead, making it inefficient. The adoption of FHT-
based rotation mitigates this issue to some extent, but it still re-
sults in noticeable overhead. The proposed LightRot approach
further optimizes the rotation unit, effectively minimizing the
associated energy cost to a negligible level, demonstrating
its superiority in enabling energy-efficient LLM inference.
Additionally, while on-the-fly activation quantization requires
floating-point division, this can be efficiently replaced with
comparison-based operations as proposed in [22], resulting in
an energy overhead of less than 3%.
Fig. 14 presents the accuracy-energy comparison of differ-
ent quantization configurations on the LLaMA2-7B model.
In smoothing-based quantization [8], the 4-bit configuration
achieves low energy consumption but suffers from a significant
perplexity drop. Conversely, the 8-bit smoothing-based quanti-
zation maintains higher accuracy but incurs substantial energy
overhead. In contrast, rotation-based quantization preserves
FP-level perplexity even at 4-bit precision while significantly
reducing energy consumption. Although naive rotation initially
introduces energy overhead compared to smoothing-based 4-
bit quantization, the proposed LightRot approach effectively
mitigates this overhead, achieving both high accuracy and
energy efficiency.
Table II provides a comparative analysis of the proposed
accelerator against previous state-of-the-art implementations
[18]–[21]. Existing processors relied heavily on optimization
techniques that are not tailored for low-bit LLM inference.
As a result, these designs typically employed higher precision
operations (e.g., INT8/INT12), which inherently limited their
energy efficiency, especially for power-critical applications.
Several existing accelerators have also been optimized for
INT4 [22], [25] or even lower-precision inference [26]. How-
ever, these approaches have primarily been validated on dis-
criminative models, with limited verification on LLMs, which
require significantly higher accuracy. Furthermore, to support
low-bit inference while avoiding excessive quantization errors,
many of these designs rely on mixed-precision [22], [25] or
arbitrary quantization [26]. While these techniques help miti-
gate accuracy loss, they also introduce substantial hardware
complexity, making them less efficient for dedicated LLM
acceleration.
These limitations highlight the significance of LightRot’s
approach, which is specifically optimized for low-bit LLM
inference while maintaining high accuracy. Unlike previous
accelerators that either relied on higher-precision quantization
or mixed-precision designs to mitigate quantization errors,
LightRot fully exploits rotation-based quantization to enable
efficient INT4 inference without requiring excessive precision
adjustments. By integrating GLR and ODA, the proposed
method effectively addresses outlier issues and maintains
competitive accuracy, as demonstrated in MT-Bench evalua-
tions. This specialized approach not only reduces the energy
overhead of rotation but also enhances the quantizability
of the data, enabling state-of-the-art energy efficiency. The
proposed design achieves 27.4 TOPS/W for INT4 operations,

## PDF Page 12

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 12
significantly outperforming previous works, demonstrating ef-
ficiencies ranging from 1.91–22.9 TOPS/W.
Moreover, most previous processors primarily evaluated
their performance on benchmarks such as GPT2 for language
modeling tasks. These benchmarks fail to capture the complex-
ity and real-world requirements of conversational applications.
In contrast, the proposed accelerator has been rigorously
evaluated using MT-Bench, a benchmark designed for chat
scenarios. This evaluation demonstrates the effectiveness of
the proposed architecture in real-world applications such as
conversation and chat tasks, further validating its practicality
for modern LLM-based systems.
By addressing the limitations of existing designs and fo-
cusing on real-world applicability, this work sets a new
standard for energy-efficient low-bit LLM inference, offering
a comprehensive solution for both language modeling and
conversational AI tasks.
VII. DISCUSSION
A. Comparison with Microscaling
Recently, the industry has introduced microscaling (MX)
[23] as a data format to support low-bit LLM inference.
Similar to traditional group quantization, MX applies a per-
vector scaling factor, but it uses a relatively small vector size
(32) while minimizing hardware costs with the scaling factor
in an exponent-only format (E8M0). This characteristic allows
MX to effectively cover a wide range of data values, making
it particularly advantageous for training rather than inference.
As noted in [24], the effectiveness of MX in handling
outliers during inference is inferior to rotation-based meth-
ods, resulting in lower accuracy. To address this limitation,
[24] proposed combining MX with asymmetric quantization.
However, this approach introduces additional overhead for
zero-point handling and requires a higher-precision scaling
factor, reducing compatibility with the existing MX standard
hardware.
Similar to [24], the proposed LightRot also employs asym-
metric quantization due to the application of ODA. However,
LightRot utilizes a larger group size (128), which significantly
reduces the overhead associated with zero-point and scaling
factor handling. This makes LightRot a more efficient solution
for low-bit LLM inference while maintaining compatibility
with practical hardware constraints.
VIII. CONCLUSION
This work presents LightRot, a novel lightweight rotation
scheme and dedicated hardware architecture for accurate low-
bit inference of large language models (LLMs). By integrating
the proposed GLR and ODA algorithms with a hierarchical
FHT-based rotation unit, the architecture addresses critical
challenges in low-bit quantization, including outlier handling
and the energy overhead of rotation operations. Through
rigorous evaluations, the proposed accelerator achieves a state-
of-the-art energy efficiency of 27.4 TOPS/W, surpassing prior
works that rely on higher precision inference methods. Unlike
existing accelerators focusing on traditional language mod-
eling benchmarks such as GPT2, this work demonstrates its
practicality on advanced LLMs like LLaMA2 and LLaMA3.
By leveraging MT-Bench, the proposed design also vali-
dates its effectiveness in real-world conversational scenarios,
showcasing its applicability to modern AI tasks. This work
paves the way for more energy-efficient and scalable hardware
solutions tailored to the demands of next-generation LLM
applications.
REFERENCES
[1] T. B. Brown, B. Mann, N. Ryder, M. Subbiah, J. Kaplan, P. Dhariwal, A.
Neelakantan, P. Shyam, G. Sastry, A. Askell, et al., ”Language Models
are Few-Shot Learners,” inAdvances in Neural Information Processing
Systems (NeurIPS), vol. 33, pp. 1877–1901, 2020.
[2] H. Touvron, L. Martin, K. Stone, et al., ”LLaMA 2: Open Foundation
and Fine-Tuned Chat Models,” inarXiv preprint, arXiv:2307.09288, 2023.
[Online]. Available: https://arxiv.org/abs/2307.09288
[3] A. Dubey, A. Jauhri, A. Pandey, et al., ”The Llama 3 Herd of Mod-
els,” inarXiv preprint, arXiv:2407.21783, 2024. [Online]. Available:
https://arxiv.org/abs/2407.21783
[4] A. Q. Jianget al., ”Mixtral of Experts,”arXiv preprint arXiv:2401.04088,
Jan. 2024. [Online]. Available: https://arxiv.org/abs/2401.04088
[5] J. Lin, J. Tang, H. Tang, S. Yang, W.-M. Chen, W.-C. Wang, G. Xiao, X.
Dang, C. Gan, and S. Han, ”AWQ: Activation-aware Weight Quantization
for On-Device LLM Compression and Acceleration,” inProceedings of
Machine Learning and Systems (MLSys), vol. 6, 2024.
[6] S. Kim, C. R. C. Hooper, A. Gholami, Z. Dong, X. Li, S. Shen, M.
W. Mahoney, and K. Keutzer, ”SqueezeLLM: Dense-and-Sparse Quan-
tization,” presented atICML 2024 Poster Session, May 2024. [Online].
Available: https://arxiv.org/abs/2309.05662
[7] C. Lee, J. Jin, T. Kim, H. Kim, and E. Park, ”OWQ: Outlier-Aware
Weight Quantization for Efficient Fine-Tuning and Inference of Large
Language Models,” inProceedings of the AAAI Conference on Artificial
Intelligence, vol. 38, no. 12, pp. 13355–13364, 2024. [Online]. Available:
https://doi.org/10.1609/aaai.v38i12.29237
[8] G. Xiao, J. Lin, M. Seznec, H. Wu, J. Demouth, and S. Han,
”SmoothQuant: Accurate and Efficient Post-Training Quantization for
Large Language Models,” inProceedings of the 40th International Con-
ference on Machine Learning (ICML), PMLR, vol. 202, pp. 38087–38099,
2023.
[9] Y . Zhao, C.-Y . Lin, K. Zhu, Z. Ye, L. Chen, S. Zheng, L. Ceze, A.
Krishnamurthy, T. Chen, and B. Kasikci, ”Atom: Low-Bit Quantization
for Efficient and Accurate LLM Serving,” inProceedings of Machine
Learning and Systems (MLSys), vol. 6, 2024.
[10] Y . Lin, H. Tang, S. Yang, Z. Zhang, G. Xiao, C. Gan, and S. Han,
”QServe: W4A8KV4 Quantization and System Co-design for Efficient
LLM Serving,” inarXiv preprint, arXiv:2405.04532, May 2024. [Online].
Available: https://doi.org/10.48550/arXiv.2405.04532
[11] S. Ashkboos, A. Mohtashami, M. L. Croci, B. Li, P. Cameron, M. Jaggi,
D. Alistarh, T. Hoefler, and J. Hensman, ”QuaRot: Outlier-Free 4-Bit
Inference in Rotated LLMs,” inarXiv preprint, arXiv:2404.00456, Apr.
2024. [Online]. Available: https://doi.org/10.48550/arXiv.2404.00456
[12] Z. Liu, C. Zhao, I. Fedorov, B. Soran, D. Choudhary, R. Krishnamoorthi,
V . Chandra, Y . Tian, and T. Blankevoort, ”SpinQuant: LLM Quantization
with Learned Rotations,” inarXiv preprint, arXiv:2405.16406, May 2024.
[Online]. Available: https://doi.org/10.48550/arXiv.2405.16406
[13] Y . Sun, R. Liu, H. Bai, H. Bao, K. Zhao, Y . Li, J. Hu, X. Yu, L. Hou, C.
Yuan, X. Jiang, W. Liu, and J. Yao, ”FlatQuant: Flatness Matters for LLM
Quantization,” inarXiv preprint, arXiv:2410.09426, Oct. 2024. [Online].
Available: https://doi.org/10.48550/arXiv.2410.09426
[14] A. Tseng, J. Chee, Q. Sun, V . Kuleshov, and C. De Sa, ”QuIP:
Even Better LLM Quantization with Hadamard Incoherence and Lattice
Codebooks,” presented atICML 2024 Poster Session, May 2024. [Online].
Available: https://arxiv.org/abs/2405.04532
[15] N. Shazeer, ”GLU Variants Improve Transformer,” inarXiv
preprint, arXiv:2002.05202, Feb. 2020. [Online]. Available:
https://arxiv.org/abs/2002.05202
[16] S. Merity, C. Xiong, J. Bradbury, and R. Socher, ”Pointer Sentinel
Mixture Models,” inProceedings of the 5th International Conference
on Learning Representations (ICLR), Toulon, France, 2017. [Online].
Available: https://arxiv.org/abs/1609.07843

## PDF Page 13

IEEE JOURNAL ON EMERGING AND SELECTED TOPICS IN CIRCUITS AND SYSTEMS, VOL. XX, NO. X, XX, 2025 13
[17] L. Zheng, W.-L. Chiang, Y . Sheng, S. Zhuang, Z. Wu, Y . Zhuang,
Z. Lin, Z. Li, D. Li, E. Xing, H. Zhang, J. E. Gonzalez, and I.
Stoica, ”Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena,” in
Advances in Neural Information Processing Systems (NeurIPS) Datasets
and Benchmarks Track, vol. 36, 2023.
[18] Y . Wang, Y . Qin, D. Deng, J. Wei, Y . Zhou, Y . Fan, T. Chen, H. Sun, L.
Liu, S. Wei, and S. Yin, ”A 28nm 27.5 TOPS/W approximate computing-
based transformer processor with asymptotic sparsity speculating and
out-of-order computing,” inProceedings of the 2022 IEEE International
Solid-State Circuits Conference (ISSCC), IEEE, pp. 1-3, 2022.
[19] T. Tambeet al., ”22.9 A 12nm 18.1TFLOPs/W Sparse Transformer
Processor with Entropy-Based Early Exit, Mixed-Precision Predication
and Fine-Grained Power Management,” inProceedings of the 2023 IEEE
International Solid-State Circuits Conference (ISSCC), San Francisco,
CA, USA, pp. 342-344, 2023.
[20] Y . Qinet al., ”Ayaka: A Versatile Transformer Accelerator With Low-
Rank Estimation and Heterogeneous Dataflow,”IEEE Journal of Solid-
State Circuits, pp. 1–15, 2024.
[21] S. Kim, S. Kim, W. Jo, S. Kim, S. Hong, and H.-J. Yoo, ”C-Transformer:
A 2.6-18.1µJ/Token Homogeneous DNN-Transformer/Spiking-
Transformer Processor with Big-Little Network and Implicit Weight
Generation for Large Language Models,” inProceedings of the 2024 IEEE
International Solid-State Circuits Conference (ISSCC), San Francisco,
CA, USA, Feb. 2024, doi: 10.1109/ISSCC49657.2024.10454330.
[22] S. Kim, J. Oh, J. So, Y . Choi, S. Kim, D. Im, G. Park, and H.-J. Yoo,
”EdgeDiff: 418.4mJ/inference Multi-modal Few-step Diffusion Model
Accelerator with Mixed-Precision and Reordered Group-Quantization,”
inProceedings of the 2024 IEEE International Solid-State Circuits
Conference (ISSCC), San Francisco, CA, USA, Feb. 2025.
[23] B. D. Rouhaniet al., ”Microscaling data formats for deep learning.” in
arXiv preprint arXiv:2310.10537, 2023b
[24] J. Leeet al., ”AMXFP4: Taming Activation Outliers with Asymmetric
Microscaling Floating-Point for 4-bit LLM Inference” inarXiv preprint
arXiv:2411.09909, 2024
[25] B. Kelleret al., ”A 95.6-TOPS/W Deep Learning Inference Accelerator
With Per-Vector Scaled 4-bit Quantization in 5 nm,” inIEEE Journal
of Solid-State Circuits, vol. 58, no. 4, pp. 1129-1141, April 2023, doi:
10.1109/JSSC.2023.3234893.
[26] S. Moon, H. -G. Mun, H. Son and J. -Y . Sim, ”Multipurpose Deep-
Learning Accelerator for Arbitrary Quantization With Reduction of Stor-
age, Logic, and Latency Waste,” inIEEE Journal of Solid-State Circuits,
vol. 59, no. 1, pp. 143-156, Jan. 2024, doi: 10.1109/JSSC.2023.3312615.
Sangjin Kim(Member, IEEE) received his B.S.,
M.S., and Ph.D. degrees in Electrical Engineering
from the Korea Advanced Institute of Science and
Technology (KAIST), Daejeon, South Korea, in
2019, 2021, and 2024, respectively. He is currently
a Postdoctoral Associate at KAIST.
His research interests include computing-in-
memory for low-power AI accelerators, processing-
in-memory for energy-efficient AI systems, and
hardware-software co-optimization for generative AI
models.
Yuseon Choi(Graduate Student Member, IEEE) re-
ceived his B.S. degree in Electrical Engineering from
Korea Advanced Institute of Science and Technology
(KAIST), Daejeon, South Korea, in 2024, where he
is currently pursuing the M.S. degree. His current
research interests include HW-SW co-optimization
for generative AI models, deep learning accelerators
for robotics, and energy-efficient system-on-chip de-
signs.
Jungjun Oh(Graduate Student Member, IEEE)
received the B.S. in electronic engineering from
Sungkyunkwan University, Seoul, South Korea, in
2024. He is currently pursuing an M.S. degree
in Graduate School of AI Semiconductor, Ko-
rea Advanced Institute of Science and Technology
(KAIST), Daejeon, South Korea. His current re-
search interests include hardware-aware optimiza-
tion algorithms and energy-efficient deep learning
processors.
Byeongcheol Kim(Graduate Student Member,
IEEE) received the B.S. in electronic engineer-
ing from Sogang University, Seoul, South Korea,
in 2018. He is currently pursuing the M.S. de-
gree in Graduate School of AI Semiconductor, Ko-
rea Advanced Institute of Science and Technology
(KAIST), Daejeon, South Korea. His current re-
search interests include energy-efficient processing-
in-memory accelerators and deep learning proces-
sors.
Hoi-Jun Yoo(Fellow, IEEE) graduated from the De-
partment of Electronics, Seoul National University,
Seoul, South Korea, in 1983. He received the M.S.
and Ph.D. degrees in electrical engineering from the
Korea Advanced Institute of Science and Technology
(KAIST), Daejeon, South Korea, in 1985 and 1988,
respectively.
Dr. Yoo has served as a member of the Exec-
utive Committee for the International Solid-State
Circuits Conference (ISSCC), the Symposium on
Very Large-Scale Integration (VLSI), and the Asian
Solid-State Circuits Conference (A-SSCC), the TPC Chair of the A-SSCC
2008 and the International Symposium on Wearable Computer (ISWC) 2010,
the IEEE Distinguished Lecturer from 2010 to 2011, the Far East Chair of the
ISSCC from 2011 to 2012, the Technology Direction Sub-Committee Chair of
the ISSCC in 2013, the TPC Vice-Chair of the ISSCC in 2014, and the TPC
Chair of the ISSCC in 2015. More details are available at http://ssl.kaist.ac.kr