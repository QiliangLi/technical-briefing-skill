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
Unlike prior in-BRAM compute approaches, recent work
has proposed integrating resistive RAM (ReRAM)-basedAna-
DSPCLBBRAMIMC
IMC
I/O
IMC
Fig. 1:Overview of the proposed IMC-enhanced heterogeneous
FPGA architecture. IMC hard blocks are embedded as dedicated
columns alongside CLBs, DSPs, and BRAMs.
log In-Memory-Computecore directly into the FPGA fabric,
achieving an order-of-magnitude efficiency improvement on
inference of convolutional neural network (CNN) workloads
[8], [9]. Such analog IMC blocks exploit Kirchhoff’s laws
to perform VMM operations directly inside the memory,
delivering significantly higher compute density and energy
efficiency than digital computation. Fig.1 shows an overview
of the IMC-enhanced FPGA architecture, where IMC blocks
are embedded as dedicated fabric columns and connected
to the global routing network. All inter-tile communication
occurs in the digital domain; digital-to-analog and analog-to-
digital conversion is handled internally within each IMC tile.
These efficiency gains are well demonstrated in CNN
inference, where layers primarily involve multiplying stati-
cally programmed weights with feature maps [10], [11]. In
contrast, modern Transformer-based [12] workloads exhibit
fundamentally different characteristics. Specifically, the Atten-
tion mechanism requires dynamic input matrix multiplication
(DIMM), in which both operands are computed at runtime.
Additionally, Attention involves multiple nonlinear operations,
such as exponentiation and activation, that are not natively
supported by prior IMC blocks. The computational complex-
ity of Attention scales quadratically with sequence length,
further amplifying its cost. In existing IMC approaches, the
entire Attention pipeline typically falls back to FPGA soft
logic, negating the benefits of integrated IMC acceleration. As
sequence length increases, Attention increasingly dominates
overall computation, emerging as a critical bottleneck that
cannot be alleviated simply by adding more IMC blocks.
To address this gap, we proposeNIFA, an FPGA architecture
integratesNL-DPEblock into FPGA fabric [13]. TheNL-
DPEblock integrates a ReRAM based crossbar with analog
content-addressable memories (ACAM) and no ADCs. The
block provides native support for nonlinear functions such as
arXiv:2607.15123v1  [cs.AR]  16 Jul 2026

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
and output. For N-bit precision, this requires N slices to
be fed sequentially. However, within the IMC core, each
stage is independent and operates in a pipelined fashion.
Analog computation is subject to device noise [16]. Noise-
aware training and calibration recover baseline accuracy under
realistic variation; NIFA adoptsAzure-Lily’s noise model [8].
IV. PROPOSEDSYSTEM
Recent IMC research has proposed an ADC-free IMC block,
NL-DPE, with native nonlinear computation capability [13],
[14], [17] and shows great efficiency compared to normal

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
which produces the digital output value based on the input. By
training different sets of ACAM thresholds, the same hardware
can be reconfigured to achieve different nonlinear functions,
which is analogous to how different crossbar weights imple-
ment different linear layers. It is also possible to program
the ACAM units such that they only map analog inputs to
digital values and not perform a nonlinear function. This
programmability is the key enabler of performing in-block
TABLE I: IMC Block Interface
Inputs Outputs
Signal Bits Desc. Signal Bits Desc.
clk 1 Clock data out 40 Out vector
reset 1 Reset dpe done 1 Op. done
data in 40 In vector MSB SA ready 1 MSB ready
dpe ctrl 2 DPE mode reg full 1 Output full
shift add ctrl 1 En. accum. shift add done 1 Accum. done
shift add bypass 1 Byp. accum. shift add bypass ctrl 1 Byp. status
w buf en 1 En. in. buf.
load input reg 1 Load in. reg
load output reg 1 Latch output
nonlinear functions. Both ACAM and crossbar weights are
static during the application runtime and are only configured
offline along with the bitstream generation.
While we focus on DL workloads in this paper, the NL-
DPE can be used for other non-DL workloads as well. E.g., the
crossbar’s dot-product capability can be used for digital signal
and image processing (FIR, FFT, Convolution). The pattern-
matching capability of ACAM can be used for routing-table
lookup and packet classification.
B. Noise & Precision Modeling
Like all analog in-memory computing, both the ReRAM
crossbar and the ACAM are subject to device noise, primar-
ily from imprecise conductance programming and read-time
conductance drifts. To compensate, we adopt the noise-aware
finetuning (NAF) methodology of [13], [17], which jointly
optimizes the crossbar weights and ACAM thresholds against
a hardware-calibrated noise model. NAF is performed entirely
in software prior to bitstream generation and requires no per-
device calibration after deployment. At INT8 precision, it
restores accuracy to within a few percent of the FP32 baseline
across both CNN and Transformer workloads, with essentially
no loss on BERT-Tiny [13].
C. IMC block interface and configuration
The IMC block exposes a set of control, data, and status
signals for coordinating data movement and execution. Table
I summarizes the interface with brief functional descriptions.
The 40-bit data interface on the IMC block is specifically
chosen to match the widest BRAM configuration in our FPGA
architecture (similar to Intel FPGA architectures). Unlike
Azure-Lily, which uses a 16-bit data interface, this enables
us to exploit the maximum possible memory bandwidth for
data transfer between BRAM and IMC block. The 40-bit data
interface does not necessarily mean a compute precision of 40
bits. For example, in our evaluations using INT8 precision, we
pack 5 elements in a single input vector thereby reducing the
data transfer time by 5x.
In the proposed architecture, weights and decision thresh-
olds are persistently stored within the ReRAM crossbar and
ACAM units, respectively. Programming these non-volatile
elements is analogous to initializing BRAM contents in a
baseline FPGA at boot time. Outside the IMC block hier-
archy, the standard FPGA configuration mechanism remains
unchanged. Instead, the IMC blocks embed dedicated write
logic and programming circuitry that interface directly with

## PDF Page 4

Fig. 4:Overview of the two-round FPGA-aware DSE. Round 1
selects the best crossbar sizes based onEDAP. Round 2 sweeps IMC
area budget on a fixed FPGA grid, balancing the DL throughput and
flexibility.
the configuration chain. This localized configuration logic
uses the standard bitstream to program the ReRAM cells,
ensuring that the weights and ACAM thresholds are loaded
seamlessly as part of the overall chip configuration process.
Consequently, this approach requires no invasive changes to
the global FPGA configuration circuit or the conventional
bitstream generation toolchain. Programming ReRAM cells
also requires voltages and precise compliance currents that
exceed the nominal FPGA core logic voltage. Consequently,
integrating these macros requires dedicated internal power
rails to support the programming phase. A detailed physical
design and evaluation of this power delivery network, however,
remain beyond the scope of this paper.
D. FPGA-aware Design Space Exploration
We perform an FPGA-aware DSE to find the IMC configu-
ration that best balances DL performance and FPGA flexibility.
The DSE varies two inputs, the IMC crossbar size (R×C)
and the fraction of FPGA area allocated to IMC blocks, and
evaluates efficiency, throughput, and architectural flexibility.
We organize the DSE into two sequential rounds as shown in
Fig. 4, where Round 1 selects the crossbar size and Round 2
sweeps the area budget.
Round 1evaluates the area, energy and delay tradeoff of
different IMC crossbar configs. A crossbar withRrows and
Ccolumns holds a weight matrix ofR×Cand each column
has an ACAM attached. The row countRgoverns in-block
activation eligibility: a layer of input dimensionM×Kmaps
to a single block whenK≤R, allowing ACAM to operate
in activation mode and eliminating CLB activation overhead.
WhenK > R, multiple IMC blocks are needed and the
partial sums are reduced using CLBs. In this case, ACAM falls
back to ADC mode, and activation must be handled in CLBs.
At the same time, the column countCgoverns horizontal
tiling and per-block area, as the ACAM units count scales
linearly withCand each is significantly larger than crossbars.
These effects create a non-trivial tradeoff: largerRextends in-
block activation to more layers but increases block area; larger
Creduces horizontal tiling but incurs significant area cost.
Furthermore, a large crossbar will be underutilized for small
VMM workloads, whereas small crossbars may require more
𝐥𝐨𝐠𝑸𝒊,𝒌
𝐥𝐨𝐠	(𝑲𝒋,𝒌𝑻)Iexp𝑴)𝑸𝒊,𝒌∗𝑲𝒋,𝒌𝑻
Iexp𝑴 𝒆(𝑺𝒊,𝒋)𝑬=%𝒆(𝑺𝒊,𝒋)
Ilog𝒍𝒐𝒈(𝑬)
𝑺𝒊,𝒋−𝒍𝒐𝒈(𝑬)=𝒍𝒐𝒈(𝒆𝑺𝒊,𝒋𝑬)	
Softmax
DIMM2
𝑊' 𝑊(𝑊)
DIMM1X
WQlogX 𝐥𝐨𝐠𝑸
CrossbarACAMIMC Block
𝑴
𝑬&
DIMM1
Softmax
𝑺
𝐥𝐨𝐠	(𝑽𝒌,𝒋)Iexp
𝑺%𝒆𝑬𝒊,𝒋𝑽𝒌,𝒋𝑬DIMM2𝒍𝒐𝒈(𝒆𝑺𝒊,𝒋−𝑬)
𝑸𝑲𝑻
𝑬𝒊,𝒋$
𝒔𝒐𝒇𝒕𝒎𝒂𝒙𝑸𝑲𝑻𝑽
Attention Computation𝑺𝒊,𝒋
Fig. 5:Mapping strategy for Attention computation using the pro-
posed IMC-based FPGA.
soft logic to reduce results from multiple crossbars, resulting
in another area-performance tradeoff. Round 1 ranks candidate
sizes on representative fully-connected layer (FC) workloads
byEnergy-Delay-Area Product(EDAP).
Round 2determines the IMC area budget, i.e. the per-
centage of area of the FPGA spent on IMC blocks. On a
fixed FPGA grid, IMC columns are progressively substituted
for CLB, BRAM, and DSP columns. Each budget point is
evaluated along two axes simultaneously: (1) Throughput on
DL benchmarks, which increases with increasing IMC area,
and (2)FlexScore(based on [18]), the normalized frequency
degradation on non-DL benchmarks caused by the removal of
general FPGA resources. The resulting throughput–flexibility
Pareto front identifies balanced area budget for each IMC
configuration.
E. Attention-Head Mapping
Weight-persistence is a common approach used for FPGA-
based DL inference [19]. In this method, the pre-trained (aka
static) weights of layers such as convolutional layers and fully-
connected layers are stored on-chip to avoid external DRAM
transfers. These layers translate to VMM operations and can
be accelerated by the IMC core by storing the weights in
the crossbar during configuration time. However, Transformer-
based workloads pose a new challenge for IMC-enhanced
FPGAs. The Attention mechanism in Transformers requires
DIMM,QK T and score×V, whose operands are not static.
Furthermore,softmaxandlayernormintroduce nonlinear op-
erations between every Attention stage. In prior work, these
DIMM and nonlinear stages rely entirely on soft logic, limiting
the benefit of embedding more IMC blocks. In NIFA, however,
we leverage the ACAM, to convert expensive MAC operations
in DIMM to cheaper additions in the log domain, further
extending the throughput and energy gains of IMC integration
to the full Attention pipeline.
Fig. 5 illustrates the Attention head mapping onto the
proposed FPGA. Linear Q/K/V projections use IMC crossbars
with ACAM configured in log mode, producing log-domain
outputs. DIMM stages (QK T , score×V) operate entirely in
the log domain. In the log domain, multiplications are replaced
by additions (mapped to CLBs). In the IMC blocks used for

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
back-to-back that further amplifies the error. We therefore fuse
these inverse stages so that they cancel rather than compound.
At INT8, the log-domain DIMM and Softmax closely track
their full-precision counterparts, with no measurable accuracy
loss on BERT-Tiny[13].
V. METHODOLOGY
A. Tools Used
In this work, we use VTR [20] for FPGA frequency and
area evaluation. We also build a simulator for latency and
energy profiling. A block diagram of the simulator is shown in
Fig. 6. The mapping strategy for each end-to-end benchmark,
informed by its RTL implementation, is input to the simulator,
along with the specifications of the IMC block (such as
rows, columns, area, energy). A scheduling block follows
this mapping strategy and partitions the layers across three
compute paths: weight-persistent GEMMs on IMC blocks,
DIMM operations (QKT , softmax, score×V) on both the IMC
block and CLBs, and other operations such asLayerNorm,
Residual,Maxpoolingon the CLBs. A performance profiler
tracks inter- and intra-layer overlap, and a metrics tracker
produces the total energy and end-to-end latency by aggre-
gating per-layer metrics. The simulator models both ACAM
and ADC based IMC blocks. Each benchmark is implemented
in Verilog and synthesized through VTR to obtain Fmax and
resource counts, which are fed into the simulator as well. The
energy calculation in our simulator includes three components:
TABLE II:FC workloads and their representative DNN origins.
Workload K N Represents
fc 64×64 64 64 Early CNN layers, tiny FC
fc 128×128 128 128 Attention projection (Q/K/V)
fc 512×128 512 128 ResNet mid-depth conv range
fc 2048×256 2048 256 Deep CNN layers (ResNet, VGG)
fc 256×512 256 512 Transformer FFN, VGG conv5+
fc 512×512 512 512 Large FC, Transformer projection
IMC energy, FPGA soft logic energy, and routing energy. Our
simulator models energy consumption of all the components
in the IMC block including input buffer, crossbar, ACAM,
and output buffer. For the FPGA soft logic energy and routing
energy, we use the analytical model from [21], which estimates
energy from logic resource usage and total routed wirelength.
B. FPGA Architecture
We use the 22 nm Agilex-like FPGA architecture from [22],
the same architecture used byAzure-Lily[8], as a baseline
and augment it with our proposed IMC blocks. To model the
IMC area in VTR, we estimate the ReRAM crossbar area and
ACAM area from a 32 nm NL-DPE design evaluated in [13],
and then scale the results to 22 nm using technology-scaling
coefficients reported in [23]. Because the IMC block requires a
relatively small number of input and output ports, its footprint
is logic-bound rather than I/O-bound. Consequently, the area
overhead of the local routing crossbar within the IMC tile is
negligible compared to the core logic area. To integrate these
large hard blocks into the VTR grid, we model the IMC block
to span multiple standard FPGA tiles in both width and height.
To further reduce the impact of integrating large hard blocks on
the FPGA routing fabric, we preserve complete switch boxes
at all the intersections where routing channels cross through
the tile. All inputs and outputs of the IMC block are registered
and modeled with a 15% input connection flexibility (FC in)
and a 10% output connection flexibility (FC out).
C. Benchmarks
1) DL workloads for DSE:For DL throughput evaluation,
six GEMV-style FC layers are used, as summarized in Table II.
In addition to the core GEMV computation, each workload
includes an activation function. The varied FC sizes capture
the area-efficiency tradeoff across crossbar configurations:
larger crossbars consume more area but can perform activation
in-block, while smaller crossbars must pay the additional
cost of CLB-based activation. The FC dimensions are drawn
from representative CNN and Transformer layers, providing a
realistic measure of crossbar utilization across workload types.
2) Non-DL workloads for DSE:Four non-DL designs are
selected from the VTR benchmark suite:bgm,LU8PEEng,
stereovision1, andarm core.bgmis CLB-intensive stress-
ing routing and logic density;LU8PEEngis BRAM-heavy
representing memory-bound linear algebra;stereovision1is
DSP-dominant exercising compute-intensive pipelines; and
arm corecombines CLBs with BRAMs as a general-purpose
processor core. This selection ensures the evaluation covers
all major FPGA resource types, preventing theFlexScore

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

## PDF Page 7

TABLE IV:FPGA implementation results for CNN benchmarks.
Proposed-1 Proposed-2 Azure-Lily
ResNet-9
IMCs 19 (6%) 12 (13%) 35 (13%)
DSPs 0 0 0
CLBs 61 (0.4%) 63 (0.4%) 185 (2%)
BRAMs 28 (5%) 28 (6%) 16 (2%)
Fmax 168 MHz 158 MHz 215 MHz
VGG-11
IMCs 85 (29%) 44 (49%) 148 (57%)
DSPs 0 0 0
CLBs 99 (1%) 101 (1%) 212 (2%)
BRAMs 30 (6%) 30 (7%) 12 (2%)
Fmax 133 MHz 138 MHz 154 MHz
Proposed-1 Proposed-2 Azure-Lily
0
50
100
150
58 pJ
110 pJ
1400
1600 1573 pJ
Energy Breakdown
49% 44%
6%
51% 46%
3%
34%
61%
4%
Area Breakdown
Proposed-1
0.047 mm²
Proposed-2
0.091 mm²
Azure-Lily
0.079 mm²
Crossbar ACAM ADC Other
27×
14×
Fig. 9:Block-level energy and area comparison.
degradation andProposed-2(1024×256, 21% FPGA area),
a configuration whose IMC block area is comparable to
Azure-Lily’s IMC block, enabling a controlled comparison that
shows our advantage at similar silicon cost. Other points yield
negligible throughput gain while flexibility degrades sharply,
confirming the importance of the DSE.
B. Block-Level Evaluation
Table III summarizes the three IMC block configurations.
Both proposed configs useR=1024with a 40-bit data inter-
face and 4 ReRAM cells per weight, enabling signed ACAM
operations.Azure-LilyusesR=512with a 16-bit data interface
and 1 cell per weight. Fig. 9 compares the energy per VMM
operation and the area breakdown of each IMC block. Notably,
ADC energy dominates inAzure-Lily, makingProposed-1and
Proposed-2significantly more energy efficient while providing
higher throughput due to their larger crossbar. In contrast, in
the proposed designs, ACAM occupies an area comparable to
the crossbar, whereas the ADC accounts for about 60% of
the block area inAzure-Lily. This result indicates that ACAM
provides both better area and energy efficiency than ADCs.
C. CNN Evaluation
Table IV reports the resource usage and Fmax obtained from
VTR for each CNN benchmark. For these benchmarks, we use
an FPGA grid size of 150x150 for all configurations. Fig. 10
summarizes area, energy efficiency, and end-to-end speedup,
all normalized toAzure-Lily. Both proposed configurations
achieve3–4×higher area efficiency on ResNet-9 and VGG-
11. The improvement in energy efficiency is significantly
larger: bothProposed-1andProposed-2achieve over30×
higher energy efficiency thanAzure-Lily. This gain is partly
due to ACAM eliminating the separate CLB-based activation
passes required byAzure-Lilyafter each IMC pass, leading to
TABLE V:FPGA implementation results for BERT-Tiny.
Proposed-1 Proposed-2 Azure-Lily
N=128
IMCs 40 36 18
DSPs 10 10 30
BRAMs 150 150 54
CLBs 659 655 380
Fmax 132 MHz 130MHz 131MHz
N=2048
IMCs 280 148 18
DSPs 10 10 150
BRAMs 270 270 234
CLBs 728 732 694
Fmax 134 MHz 136 MHz 136 MHz
ResNet-9 VGG-11
0
1
2
3
4
5Inference/s/mm²
4.1×
3.4×
3.0×
3.5×
ResNet-9 VGG-11
0
10
20
30
40
50Inference/J
38.6× 40.0×
33.1×
38.5×
ResNet-9 VGG-11
0.0
0.5
1.0
1.5
2.0Speedup
1.7×
1.4×1.4× 1.4×
Proposed-1 Proposed-2 Azure-Lily
Fig. 10:CNN benchmark efficiency. Left: Area efficiency
(Inference/s/mm2). Middle: Energy efficiency (Inference/J). Right:
Overall speedup
additional area and energy savings that may exceed the block-
level energy differences shown in Fig. 9. Overall, the proposed
configurations deliver a1.4–1.7×end-to-end speedup across
ResNet-9 and VGG-11. Concretely, the CNN energy advan-
tage stems from two block-level effects: replacing the ADC
with the ACAM cuts the conversion energy by∼27×(Fig. 9),
and folding the activation into the ACAM removes the separate
CLB activation pass thatAzure-Lilyruns after every IMC pass.
Together these account for the>30×end-to-end CNN energy
efficiency overAzure-Lily.
D. BERT Evaluation
While the CNN results confirm the system-level benefits,
the more distinctive contribution of NIFA lies in Transformer
inference, where ACAM’s nonlinear capabilities extend to
activation, DIMM, and softmax stages. We conduct a detailed
sensitivity study on BERT-Tiny across sequence lengths to
evaluate how system-level benefits scale with the Attention
head’sO(N 2)cost. Table V reports the resource usage and
Fmax obtained from VTR for the largest and smallest sequence
lengths evaluated for BERT-Tiny. All BERT-Tiny benchmarks
are mapped onto an FPGA grid of 255×255, the minimum grid
size required to fit all designs. As described in Section IV-E,
Attention head computation is accelerated by converting mul-
tiplications into additions in the log domain which results in
notably higher CLB utilization for the proposed configurations
compared toAzure-Lily. Notably, all three architectures share
the same LayerNorm implementation, which requires two
multiplications per layer. Across the five LayerNorm layers
in BERT-Tiny, this accounts for dedicated 10 DSPs.

## PDF Page 8

P1
P2
AL
P1
P2
AL
P1
P2
AL
P1
P2
AL
P1
P2
AL
0
20
40
60
80
100Energy Breakdown (%)
128 256 512 1024 2048
35%
21%
12%
P1
P2
AL
P1
P2
AL
P1
P2
AL
P1
P2
AL
P1
P2
AL
0.0
0.5
1.0
1.5
2.0Per-component breakdown
128 256 512 1024 2048
1.9× 1.8× 1.7× 1.7× 1.7×
128 256 512 10242048
1.0
1.2
1.4
1.6
1.8
2.0Total energy ratio
1.4×
1.7×
Sequence Length (N)
DIMM
Proj+FFN
Other Crossbar
Conversion (ACAM/ADC)
Rest FPGA Fabric Azure-Lily / Proposed-1
Azure-Lily / Proposed-2
Overall
DIMM only
Fig. 11:BERT-Tiny energy analysis across sequence lengths. Left: Energy breakdown by operation. Middle: Energy breakdown by hardware
component. Right: Total energy ratio ofAzure-LilyoverProposed-1andProposed-2.
12825651210242048
2
4
6
Speedup
12825651210242048
1.0
1.5
2.0
2.5
Inference/s/mm²
12825651210242048
1.0
1.5
2.0
Inference/J
1.4×
1.7×
Sequence Length (N)
Proposed-1 Proposed-2 Azure-Lily
Fig. 12:BERT-Tiny speedup and efficiency (normalized toAzure-
Lily) across sequence lengths. Left: end-to-end speedup. Middle: Area
efficiency. Right: Energy efficiency.
We note that the proportion of DIMM operations within the
total Attention FLOPs grows drastically with sequence length.
From about 50% at sequence length of 256 it approaches100%
at sequence lengths>=4096. This trend makes it essential
to efficiently accelerate the Attention mechanism as the model
scales.
1) Energy Breakdown:Fig. 11 reveals the source and
scalability of the energy advantage across three panels. The
left panel shows that DIMM operations dominate BERT-Tiny
energy at every sequence length, with the non-DIMM share
shrinking from 35% atN=128to 12% atN=512, confirming
DIMM as the system energy bottleneck. The middle panel de-
composes per-element DIMM energy into crossbar, conversion
peripheral, and fabric components. Two trends stand out: first,
Azure-Lily’s ADC-based conversion is far more expensive than
ACAM; second, its fabric energy share is significantly larger
because DIMM operations fall back to DSPs, whereas the
proposed architectures accelerate DIMM in the log domain via
ACAM and CLBs which consumes substantially less power
than DSPs. Together, these factors produce an energy ratio
that starts at1.9×and converges to a persistent∼1.7×floor
asNgrows, demonstrating that the advantage scales robustly
withO(N 2)Attention cost. The right panel confirms this:
as DIMM dominates total energy, the system ratio converges
to the DIMM ratio, withAzure-Lilyconsuming∼1.4×and
∼1.7×the energy ofProposed-1andProposed-2.
2) End-to-End Efficiency:Fig. 12 presents the speedup and
efficiency normalized toAzure-Lily. The left subfigure shows
the end-to-end speedup againstAzure-Lily. As N grows, both
proposed configurations deliver similar, consistently increasing
speedup. Area efficiency (middle sub-figure) increases con-
sistently with sequence length for both proposed configura-
tions:Proposed-1rises from1.0×atN=128to∼2.4×at
N=2048, andProposed-2follows a similar trajectory. AsN
grows, DIMM operations increasingly dominate total compute,
and the ACAM-based IMC block’s throughput advantage
compounds accordingly. The monotonically increasing trend
demonstrates strong scalability in both area utilization and
sequence length. Energy efficiency (right sub-figure) tells a
consistent story: both configurations converge to stable floors:
1.4×forProposed-1and1.7×forProposed-2as observed
in the per-component energy analysis (Fig. 11). These results
confirm that the proposed architecture’s end-to-end efficiency
advantage stands robustly asO(N 2)Attention cost grows.
VII. CONCLUSION
In this work, we presentNIFA, a heterogeneous FPGA ar-
chitecture that integrates ADC-free, ACAM-based analog IMC
blocks as first-class hard blocks, enabling native nonlinear
computation inside the IMC core. A systematic two-round
FPGA-aware DSE jointly optimizes the trade-off between
FPGA area, DL throughput, and architectural flexibility, and
an efficient mapping extends the IMC block’s applicability
to dynamic-input matrix multiplications in Transformer At-
tention operation. Across CNN and BERT-Tiny benchmarks,
the proposed architecture demonstrates significant energy and
performance efficiency over state-of-the-art analog IMC based
FPGA architectures. Most importantly, this advantage holds
as input sequence length grows atO(N 2), confirming the
architecture is efficient and scalable.
VIII. ACKNOWLEDGEMENTS
This work was supported in part by National Science
Foundation (grant number 2417658). Any opinions, findings,
conclusions, or recommendations are those of the authors and
not of the funding institutions. The authors acknowledge the
use of AI assistants to assist with manuscript drafting and
to support code development and debugging. All core ideas,
experimental designs, and scientific conclusions are entirely
the original work of the authors.

## PDF Page 9

REFERENCES
[1] A. Arora, S. Mehta, V . Betz, and L. K. John, “Tensor slices to the rescue:
Supercharging ML acceleration on FPGAs,” inProc. ACM/SIGDA Intl.
Symp. on Field-Programmable Gate Arrays (FPGA), 2021.
[2] E. Taka, N.-C. Huang, C.-C. Chang, K.-C. Wu, A. Arora, and D. Mar-
culescu, “Systolic sparse tensor slices: FPGA building blocks for sparse
and dense AI acceleration,” inProceedings of the 2025 ACM/SIGDA
International Symposium on Field Programmable Gate Arrays, FPGA
’25, (New York, NY , USA), p. 159–171, Association for Computing
Machinery, 2025.
[3] M. Langhammer, E. Nurvitadhi, S. Gribok, and B. Pasca, “Stratix 10
NX architecture,”ACM Trans. Reconfigurable Technol. Syst., vol. 15,
Aug. 2022.
[4] A. Arora, T. Anand, A. Borda, R. Sehgal, B. Hanindhito, J. Kulkarni,
and L. K. John, “CoMeFa: Compute-in-memory blocks for FPGAs,”
inProc. IEEE Intl. Symp. on Field-Programmable Custom Computing
Machines (FCCM), 2022.
[5] Y . Chen and M. S. Abdelfattah, “BRAMAC: Compute-in-BRAM archi-
tectures for multiply-accumulate on FPGAs,” inProc. IEEE Intl. Symp.
on Field-Programmable Custom Computing Machines (FCCM), 2023.
[6] Y . Chen, J. Dotzel, and M. S. Abdelfattah, “M4BRAM: Mixed-precision
matrix-matrix multiplication in FPGA block RAMs,” in2023 Interna-
tional Conference on Field Programmable Technology (ICFPT), pp. 69–
78, 2023.
[7] X. Wang, V . Goyal, J. Yu, V . Bertacco, A. Boutros, E. Nurvitadhi,
C. Augustine, R. Iyer, and R. Das, “Compute-capable block RAMs
for efficient deep learning acceleration on FPGAs,” in2021 IEEE
29th Annual International Symposium on Field-Programmable Custom
Computing Machines (FCCM), pp. 88–96, 2021.
[8] A. Gajjar, R. Sunketa, L. Zhao, O. Eldash, A. Natarajan, G. Pedretti,
A. Arora, P. Faraboschi, J. Ignowski, and L. Buonanno, “Azure-lily:
An FPGA architecture with analog IMC engines for efficient AI,”ACM
Trans. Archit. Code Optim., Feb. 2026.
[9] A. Gajjar, L. Zhao, O. Eldash, A. Natarajan, X. Sheng, G. Pedretti,
A. Arora, P. Faraboschi, J. Ignowski, and L. Buonanno, “Analog in-
memory computing enhanced FPGA for high-throughput and energy-
efficient acceleration,” in2025 IEEE 33rd Annual International Sym-
posium on Field-Programmable Custom Computing Machines (FCCM),
pp. 290–290, 2025.
[10] L. Buonanno and M. Carminati, “Analog computing: from fundamentals
to applications,” in2025 IEEE International Symposium on Circuits and
Systems (ISCAS), pp. 1–6, 2025.
[11] P. Chi, S. Li, C. Xu, T. Zhang, J. Zhao, Y . Liu, Y . Wang, and Y . Xie,
“PRIME: A novel processing-in-memory architecture for neural network
computation in ReRAM-based main memory,” in2016 ACM/IEEE 43rd
Annual International Symposium on Computer Architecture (ISCA),
pp. 27–39, 2016.
[12] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez,
L. Kaiser, and I. Polosukhin, “Attention is all you need,” inAdvances
in Neural Information Processing Systems (NeurIPS), 2017.
[13] L. Zhao, G. Pedretti, Z. Mao, R. R. Sunketa, A. Arora, L. Buonanno,
J. Ignowski, and P. Faraboschi, “NL-DPE: An analog in-memory non-
linear dot product engine for efficient CNN and LLM inference,”arXiv
preprint arXiv:2511.13950, 2025.
[14] L. Zhao, A. Natarajan, L. Buonanno, A. Gajjar, R. Roth, S. Serebryakov,
J. Moon, O. Eldash, J. Ignowski, and G. Pedretti, “RACE-IT: A
reconfigurable analog computing engine for in-memory transformer
acceleration,” in2025 IEEE 43rd International Conference on Computer
Design (ICCD), pp. 103–110, 2025.
[15] A. Arora, Z. Wei, and L. K. John, “Hamamu: Specializing FPGAs for
ML applications by adding hard matrix multiplier blocks,” in2020
IEEE 31st International Conference on Application-specific Systems,
Architectures and Processors (ASAP), pp. 53–60, 2020.
[16] R. Mao, B. Wen, M. Jiang, J. Chen, and C. Li, “Experimentally-validated
crossbar model for defect-aware training of neural networks,”IEEE
Transactions on Circuits and Systems II: Express Briefs, vol. 69, no. 5,
pp. 2468–2472, 2022.
[17] L. Zhao, L. Buonanno, A. Natarajan, J. Ignowski, and G. Pedretti,
“Noise aware finetuning for analog non-linear dot product engine,” in
Proceedings of the NeurIPS 2024 Workshop on Machine Learning with
New Compute Paradigms, 2024.
[18] T. Tan, E. Nurvitadhi, A. Dasu, M. Langhammer, and D. Chiou,
“FlexScore: Quantifying flexibility,”IEEE Computer Architecture Let-
ters, vol. 20, no. 1, pp. 58–61, 2021.
[19] J. Fowers, K. Ovtcharov, M. Papamichael, T. Massengill, M. Liu, D. Lo,
S. Alkalay, M. Haselman, L. Adams, M. Ghandi, S. Heil, P. Patel,
A. Sapek, G. Weisz, L. Woods, S. Lanka, S. K. Reinhardt, A. M.
Caulfield, E. S. Chung, and D. Burger, “A configurable cloud-scale
DNN processor for real-time AI,” in2018 ACM/IEEE 45th Annual
International Symposium on Computer Architecture (ISCA), pp. 1–14,
2018.
[20] M. A. Elgammal, A. Mohaghegh, S. G. Shahrouz, F. Mahmoudi,
F. Kos ¸ar, K. Talaei, J. Fife, D. Khadivi, K. Murray, A. Boutros, K. B.
Kent, J. Goeders, and V . Betz, “VTR 9: Open-source CAD for fabric
and beyond FPGA architecture exploration,”ACM Trans. Reconfigurable
Technol. Syst., vol. 18, Aug. 2025.
[21] A. Arora, A. Bhamburkar, A. Borda, T. Anand, R. Sehgal, B. Hanindhito,
P.-E. Gaillardon, J. Kulkarni, and L. K. John, “CoMeFa: Deploy-
ing Compute-in-Memory on FPGAs for Deep Learning Acceleration,”
ACM Transactions on Reconfigurable Technology and Systems, vol. 16,
pp. 50:1–50:34, July 2023.
[22] A. Arora, A. Boutros, D. Rauch, A. Rajen, A. Borda, S. A. Damghani,
S. Mehta, S. Kate, P. Patel, K. B. Kent, V . Betz, and L. K. John, “Koios:
A deep learning benchmark suite for FPGA architecture and CAD re-
search,” in2021 31st International Conference on Field-Programmable
Logic and Applications (FPL), pp. 355–362, 2021.
[23] A. Stillmaker and B. Baas, “Scaling equations for the accurate prediction
of CMOS device performance from 180nm to 7nm,”Integration, vol. 58,
pp. 74–81, 2017.