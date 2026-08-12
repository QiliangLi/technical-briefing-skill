# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

## PDF Page 1

NIF A:Nonlinear IMC enhanced FPGAfor efficient
ML inference
Jiajun Hu 1, Ruthwik Reddy Sunketa 1, Lei Zhao 2, Archit Gajjar 2, Luca Buonanno 2, Aman Arora 1
1Arizona State University, Tempe, AZ, USA 2Hewlett Packard Enterprise Labs, Fort Collins, CO, USA
{jiajunh5, rsunketa, aman.kbm}@asu.edu{lei.zhao, archit.gajjar, luca.buonanno}@hpe.com
Abstract—Recent FPGAs have improved deep learning (DL)
inference efficiency by introducing tensor blocks and enabling
in-BRAM computation. ReRAM-based analog in-memory com-
puting (IMC) cores offer an order of magnitude higher compute
density and energy efficiency than conventional digital computa-
tion by performing vector-matrix multiplication (VMM) directly
within the ReRAM crossbar. Prior work has integrated such IMC
blocks into FPGAs for DL inference. However, conventional IMC
designs support only static-weight VMM, while nonlinear and
dynamic matrix-matrix multiplications (DIMM) are still handled
by the FPGA fabric. As a result, the benefits of IMC are largely
limited to static-weight DL models, whereas Transformer-based
models, which require frequent nonlinear and DIMM operations,
achieve only limited benefit. In addition, ADCs within the IMC
block consume more than 70% of area and power, further
limiting system efficiency and scalability. To address these issues,
we propose a novel FPGA architecture that integrates an ADC-
free IMC alternative into FPGAs, replacing the conventional
ADC with analog content-addressable memories (ACAMs) that
natively perform nonlinear operations inside the IMC block. To
fully utilize this new block, we conduct an FPGA-aware design-
space exploration that determines the optimal crossbar sizes while
balancing FPGA area, flexibility, and DL performance. We fur-
ther deploy an efficient mapping that uses ACAMs to efficiently
perform DIMM operations, extending architectural applicability
to Attention computation. Across CNN and Transformer-based
benchmarks, our proposed FPGA architecture achieves up to
40×and1.9×higher energy efficiency, and4.1×and2.5×
area efficiency. Overall, the proposed architecture significantly
improves the FPGA DL inference efficiency and shows robust
efficiency gain on Transformer-based workloads across long input
sequences, advancing domain-specialized FPGA design.
I. INTRODUCTION
As deep learning (DL) has been widely adopted across
modern applications, recent FPGA architectures have begun
integrating domain-specific blocks to improve DL inference
efficiency. A natural target isvector-matrix multiplication
(VMM), the dominant operation in DL workloads: early works
demonstrated that embedding a dedicatedmatrix multiplier
block directly into the FPGA fabric yields substantial ef-
ficiency gains [1], [2]. FPGA vendors have since followed
suit, incorporatingAI tensor blocksinto commercial devices,
validating the effectiveness of this approach [3]. Researchers
have also proposed in-memory compute (IMC) architectures
for FPGAs to reduce on-chip data movement through the
routing fabric and increase FPGA compute density [4], [5],
[6], [7]. While these works show speedups upto 3x for multiple
DNN workloads, the energy consumption remains high.

## Evidence locator: PDF Page 2

## PDF Page 2

exponentiation and activation, and delivers up to 30×energy
efficiency than conventional ADC-based IMC blocks [13],
[14]. Combined, these features significantly improve the per-
formance and energy-efficiency for Transformer-based work-
loads, reducing soft-logic based computation significantly.
This paper makes the following contributions:
•We proposeNIFA, a novel IMC-enhanced FPGA architec-
ture that provides in-block nonlinear functionality support
and shows up to 40×higher energy efficiency and 1.7×
higher throughput efficiency than SOTA for end-to-end
DL benchmarks.
•We conduct an FPGA-aware design space exploration
(DSE), which quantitatively evaluates the tradeoff be-
tween IMC block size, FPGA composition (percentage of
FPGA area occupied by IMC blocks), DL performance,
and FPGA flexibility using representative DL micro-
benchmarks and non-DL benchmarks.
•We present the first work that demonstrates using IMC
blocks on FPGA for DIMM in Transformer. We deploy
an efficient mapping that accelerates Attention compu-
tation in the log domain, combining the FPGA flexibil-
ity and IMC’s efficient in-block nonlinear functionality,
demonstrating 1.7×performance efficiency than SOTA
on BERT-Tiny on long sequence length.
II. RELATEDWORK
FPGA vendors have long integrated DSP slices and Block
RAMs to improve FPGA performance for common work-
loads. Recent studies propose incorporating domain-specific
hard blocks into FPGAs to further improve DL throughput.
Hamamu[15] andTensor Slices[1] replace a portion of
programmable logic with hardened matrix multipliers that
support multiple modes and precisions.Systolic Sparse Tensor
Slices[2] further extend this idea to accelerate structured
sparse workloads. While these approaches improve compute
throughput, the compute density of an FPGA still remains
relatively low compared to ASICs, and the data movement to
shuttle operands between RAM and compute blocks through
the global routing leads to significant energy consumption.
To mitigate these bottlenecks, some work embeds compute
units into BRAMs.CoMeFa[4] augments BRAMs with bit-
serial processing elements at the sense amplifier outputs,
enabling in-BRAM computation without external data move-
ment.BRAMACandM4BRAM[5], [6] add compact dummy
arrays and customized ALUs within the BRAM tile to support
MAC operations at mixed precision. All three achieve modest
throughput improvements on DL benchmarks by exploiting the
parallelism inherent in wide BRAM arrays.
Compared to digital IMC, ReRAM-based analog IMC offers
an order-of-magnitude higher compute density and energy
efficiency by exploiting physical mechanisms such as Kirch-
hoff’s law to perform computation directly within the memory.
Azure-Lily[8] integrates such an analog IMC block into
an FPGA fabric, demonstrating6.58×latency reduction and
8,741×energy efficiency improvement over CLB/DSP-only
ADC ArrayInput Buffer
AccumulationOutput Buffer
In-memory Computing Core
𝑰=𝑽×𝑮
ReRAM CrossbarDAC
G13
G11
G12
G21
G23
G22
G31
G33
G32
V1V2V3I1I2I3
V
I I		CurrentV		VoltageG		Conductance
DACDAC
Fig. 2:Example ReRAM-based IMC dot product engine performing
VMM:I=V×G. V1, V2 and V3 are input voltage vector applied
to each row. I1, I2 and I3 are resultant current accumulated in each
column.
implementations on CNN benchmarks. Modern DL bench-
marks such as Transformer based networks and LLMs are not
evaluated. The in-block ADC arrays, which consume over 70%
of the block area and energy, limit the system-level scalability
and efficiency. Furthermore, the design-space exploration is
limited to the block level and FPGA integration evaluation
such as area budget and flexibility-generality tradeoffs are not
evaluated.
Across all three lines of prior work, no existing FPGA hard
block provides native in-block support for nonlinear functions,
which must fall back to CLBs, creating a throughput bottle-
neck, especially for modern Transformer-style workloads. This
work, NIFA, integrates an IMC block which supports native
in-block nonlinear computation into FPGA, while evaluating
the benefits this feature provides for modern Transformer-
based workloads. We also perform a two-round FPGA-aware
DSE that systematically quantifies the tradeoff among DL
throughput, area budget, and general-purpose flexibility.
III. BACKGROUND
Fig. 2 shows a ReRAM-based IMC core, which consists of
input/output buffers, a ReRAM crossbar array, accumulation
logic, and ADC. The crossbar stores DNN weights as ReRAM
conductances and performs VMM in the analog domain. The
input vector is applied to the rows, and the accumulated
current at each column output is the dot product result. In
this figure, the output current in the first column is computed:
I1 =V1×G11 +V2×G12 +V3×G13. To avoid DACs
at the inputs, a bit-slicing technique is used: the inputs are
decomposed into single-bit slices, each fed into the crossbar
serially, and the partial results are accumulated to reconstruct
the full-precision output. In this example, the first bits of
V1,V2,V3are fed through the DAC and crossbar, then
accumulated with the following bits in the accumulation buffer
and output.

## Evidence locator: PDF Page 5

## PDF Page 5

System Scheduler
IMC Core
CLBs, DSPsOn-chip BRAM
Verilog-to-Routing ResourceusageFmax
IMC Arch Specs
RTL BenchmarksMapping Strategy
Input Specs
VMM
Layernorm Residual
DIMMQK^TScore x V softmax
ACAM mode
Hardware Primitives
Metrics TrackerPerformanceProfilerOutput AnalyticsIMC-FPGA SimulatorMaxpoolSoftmax
Fig. 6:Overview of our analytical simulator. VTR-reported Fmax
and resource counts are combined with the energy model to produce
per-layer latency and energy estimates.
DIMM stages, the crossbar is configured as an identity matrix
that buffers the input and only performs the nonlinear functions
through ACAM. Hence, the IMC block’s outputs are in the
linear domain and are then reduced to the final results using
CLBs. Softmax is computed using multiple IMC blocks with
ACAMs configured for either exp or log operations, as well
as CLB based operations (addition and division converted to
subtraction) as shown in the figure.
Using this mapping, the IMC blocks are reused at every
stage of the Attention pipeline rather than falling back to DSPs
and CLBs as in prior work, yielding significant performance
gains. However, this mapping also raises a numerical-accuracy
concern. As modeled in [13], a single transform is essentially
exact at INT8, with a per-transform mean-squared error (MSE)
on the order of10 −8, so individual transforms are not the con-
cern. Error accumulates only when transforms are chained. A
full log-domain multiply reaches an MSE of10 −5, and naively
cascading stages would place the exponentiation and logarithm
back-to-back that further amplifies the error.

## Evidence locator: PDF Page 6

## PDF Page 6

TABLE III:IMC hard block comparison across three evaluation
architectures at 22nm tech node
PropertyProposed-1 Proposed-2 Azure-Lily
Crossbar (R×C) 1024×128 1024×256 512×128
ReRAM Cells per weight 4 4 1
ACAM Size / ADC Count 130×128 130×256 8 ADCs
I/O data-width 40-bit 40-bit 16-bit
Area (mm 2) 0.047 0.091 0.079
FPGA grid size (rows×cols) 3×7 5×8 6×5
Power (mW) 27.4 51.8 20.0
TOPS(int8) 16.4 32.8 0.91
Frequency(GHz) 0.9 0.9 0.92
from being biased toward any single resource profile. As
the IMCs are not utilized in these benchmarks, adding more
IMCs will reduce other FPGA resources leading to higher
routing congestion, the achievable Fmax therefore reflects the
flexibility cost due to IMC integration.
3) End-to-end benchmarks:For CNN evaluation, we use
ResNet-9 and VGG-11, the same benchmarks used byAzure-
Lily, enabling direct comparison. For Transformer evaluation,
we use BERT-Tiny (2 layers, 2 Attention heads, 128 hidden
dimension, 512 FFN intermediate). All benchmarks follow the
weight persistent methodology which is a common method for
DNN deployment on FPGAs [19].
D. Metrics
1) DSE:In Round 1, we rank crossbar sizes byEDAP,
aggregated via normalized geometric mean across workloads
in Table II (per-workload best= 1.0). In Round 2, we plot
a Pareto-front to evaluate the tradeoff between DL workload
throughput and architectural flexibility at each IMC area
budget. The architectural flexibility is measured byFlexScore
[18]. TheFlexScoremeasures how much IMC hard blocks
degrade non-DL workloads performance where IMC blocks
are not used. Each non-DL benchmark is synthesized through
VTR and its Fmax is recorded. Each benchmark’s Fmax is
normalized to its own zero-IMC baseline — for example,bgm
achieves 90 MHz vs its baseline 100 MHz, giving a ratio of
0.9. This ratio is theFlexscore. The overallFlexScoreof each
architecture at each area budget is the geometric mean across
the benchmarks. A geomeanflexscoreof 0.96 means the non-
DL workloads retain 96% of their baseline Fmax under this
given area budget and crossbar configuration.
2) Non-DSE:For non-DSE experiments, we implement
complete CNN models in RTL, along with BERT-Tiny models
across all evaluated sequence lengths. All reported metrics
are derived from VTR and our simulator. Energy is computed
analytically via the simulator inpJ. Area is reported by VTR in
Minimum Width Area Transistors (MWTA) and is converted
tomm 2. System latency is modeled by the simulator and
reported inns. We further derive three composite efficiency
metrics using these base metrics for system-level comparison
including: inferences per second (throughput), throughput per
mm2, and inferences per joule.
0.0 0.2 0.4 0.6 0.8 1.0 1.2
Normalized Geomean EDAP Score (best = 1.0)
#12  128x64
#11  128x128
#10  128x256
#9  1024x64
#8  256x256
#7  256x64
#6  256x128
#5  1024x256 *  115% of Azure-Lily DPE area
#4  512x64 *
#3  512x256 *  84% of Azure-Lily DPE area
#2  1024x128 *
#1  512x128 *
Fig. 7:Round 1 DSE: Crossbar sizes ranked byEDAP.
0% 10% 20% 30% 40%
Non-DL Perf. Degradation (1  FlexScore)
0.0
0.2
0.4
0.6
0.8
1.0
1.2
1.4
1.6DL Performance (inference/s)
Proposed-1
512×128
1024×128
512×64
Pareto front
Recommended: 1024×128
FPGA Area Cost = 23%
0% 10% 20% 30% 40%
Non-DL Perf. Degradation (1  FlexScore)
0.0
0.2
0.4
0.6
0.8
1.0
Proposed-2
512×256
1024×256
Pareto front
Recommended: 1024×256
FPGA Area Cost = 16%
0
5
10
20
25
30
45
IMC Area (% of FPGA)
Fig. 8:Round 2 DSE: Pareto-front evaluation of recommended
crossbar sizes forProposed-1andProposed-2across DL performance
and FPGA flexibility.
E. DSE Protocol
1) Round 1: Block Sizing.:We sweep 12 crossbar config-
urations (R∈ {128,256,512,1024},C∈ {64,128,256})
across all 6 FC workloads using VTR auto-layout. Each
configuration is ranked byEDAPgeomean across benchmarks.
From the results, we select the top-5 candidates for Round 2.
2) Round 2: FPGA Integration.:We fix the FPGA size and
sweep the IMC area budget by progressively replacing CLB,
DSP, and BRAM tiles proportionally by IMC tiles — all three
resource types lose the same fraction of capacity. Both DL
throughput andFlexScoreare measured, producing a Pareto-
front that identifies an appropriate balance of the FPGA area
consumed by IMC resources vs. other FPGA resources.
VI. RESULTS
A. Recommended Crossbar Sizes from DSE
Fig. 7 ranks 12 crossbar configurations byEDAPacross
the 6 FC workloads. A clear tier emerges: the top-5 including
512×128, 1024×128, 512×256, 512×64, and 1024×256 all
haveR≥512, enabling in-block activation on the majority of
workloads and eliminating CLB activation overhead. The top-
5 advance to Round 2, split into two groups evaluated with
identical workloads:Group 1contains configs #1, #2, and #4,
andGroup 2contains the two configs with area similar to
Azure-Lilyenabling a controlled block-level comparison.
Fig. 8 shows the Round 2 throughput–flexibility Pareto
fronts. From these, we select two operating points for end-
to-end evaluation:Proposed-1(1024×128, 23% FPGA area)
which achieves the best DL throughput at under 5% flexibility

## Evidence locator: PDF Page 3

## PDF Page 3

`
Crossbar
Input BufferAccumulation
Output Buffer
NL-DPE BlockVACAMACAMACAM…I
V2 ≤5.95V1 >1.75Y=1V0<0.2V0>4.1Y=1.2Y=0.3Y=2.1Y=1.4
X> 4.1
X>1.75≤1.75
>1.75≤2.5≤5.95
XY=2.3Y=1.2
Y=0
V0=7.45V1=0.45V2=3.25
Analogue CAM RowsMatchingDigital output
Fig. 3:Left: Block-level architecture ofNL-DPEshowing ReRAM
crossbar and ACAM units. Right: An example trained decision-tree
mapped to the ACAM unit.
ADC-based IMC blocks. We integrate this block into the
FPGA fabric as a first-class hard block, unlocking its nonlinear
functionality for CNN and Transformer workloads. ReRAM
and the FPGA’s CMOS logic are fabricated in different layers
and do not interfere: the ReRAM cells are a back-end-of-line
(BEOL) deposit in the metal interconnect above the transistors,
decoupled from the front-end transistor node. The FPGA’s
programmable fabric can therefore remain at the leading-edge
CMOS node while the ReRAM cells occupy the metal layers
above, incurring no logic-density penalty.
A. NL-DPE Block Architecture
Fig. 3 shows the block-level architecture of theNL-DPE
block. Each block contains a ReRAM crossbar of sizeR×C,
input/output buffers, and an array ofCACAM units that
replace the conventional ADC peripheral. Unlike theAzure-
LilyIMC block, which uses a single ReRAM cell per weight,
each weight in the NL-DPE crossbar is encoded with four
ReRAM cells to directly support signed MAC operations. This,
however, does not increase the area of the overall crossbar
significantly as the ReRAM cells contribute a small fraction of
overall crossbar area. For weight-persistent VMM operations,
the crossbar computes VMM in the same manner asAzure-
Lily, but accumulated in the analog domain through ratioed
capacitors before entering the ACAM. The ACAM maps the
analog inputs to digital values while simultaneously applying
a nonlinear activation function (ReLU, tanh, etc.).
The ACAM is itself a small ReRAM array whose cells
are programmed with trained thresholds encoding a piecewise
decision tree as shown in fig. 3. Each ACAM unit is connected
to one crossbar column and accepts analog input and performs
a nearest-neighbor search over its programmed thresholds. In
the figure, the ACAM weights on each row represent the
threshold values stored in the decision tree. All the ACAM
units together form a grid-style content-address memory,
which produces the digital output value based on the input.