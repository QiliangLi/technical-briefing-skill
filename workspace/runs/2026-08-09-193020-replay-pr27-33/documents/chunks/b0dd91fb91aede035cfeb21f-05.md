5 of 8 tested Mistral contexts, but at 25 Gbps and above it is benefi-
cial for all tested contexts. The maximum transfer-over-recompute
speedup rises from 2.86× at 10 Gbps to 7.14× at 25 Gbps and up to
113.88× at 400 Gbps. This gives a clear scheduling rule: transfer is
not always profitable on slow links, but it becomes decisively better
on RDMA-class GPU-cluster networks.
The baseline systems are structurally limited: dense and text-
passing approaches cannot choose between transfer and recompute
since KV state is not a transferable object. Local-prefix systems
only reuse cache within a server, lacking general policies for cross-
agent or cross-node transfer. As shown in Table 10, both vLLM
and SGLang manage KV internally but do not support stable public
KV export/import in this evaluation. In contrast, AAFLOW+ en-
ables state transfer as a core workflow operation, selecting transfer
only when it is more bandwidth-efficient than prompt replay, thus
achieving superior performance.
F.4 Experiment 4: Memory Efficiency
The goal is to compare peak KV memory as branch factor grows. A
stateful workflow should avoid duplicating the full shared prefix
for every branch.
18

## PDF Page 19

Table 8: Experiment 1: Mean TTFT by baseline with HF, vLLM, and SGLang backends and 1024 - 32768 context size.
HF Backend vLLM Backend SGLang Backend
Model Baseline Mean Speedup Mean Speedup Mean Speedup
TTFT(s) (slower) TTFT(s) (slower) TTFT(s) (slower)
Mistral AAFLOW+ 0.041 1.00×0.116 1.00×0.629 1.00×
Mistral dense prefill 2.017 49.2×20.026 172.6×7.396 11.8×
Mistral AAFLOW-text 2.057 50.2×20.425 176.1×7.531 12.0×
Mistral vLLM local prefix 0.437 10.7×4.211 36.3×2.013 3.2×
Mistral SGLang prefix 0.280 6.8×2.629 22.7×1.475 2.3×
Mistral KVCOMM 0.704 17.2×6.876 59.3×2.920 4.6×
Mistral DistServe style 0.123 3.0×0.197 1.7×0.710 1.1×
Mistral live vLLM serve n/a n/a 19.925 171.8×n/a n/a
Mistral live SGLang serve n/a n/a n/a n/a 6.781 10.8×
Llama3 AAFLOW+ 0.030 1.00×0.061 1.00×0.139 1.00×
Llama3 dense prefill 0.499 16.6×3.958 64.9×1.810 13.0×
Llama3 AAFLOW-text 0.509 17.0×4.036 66.2×1.843 13.3×
Llama3 vLLM local prefix 0.124 4.1×0.862 14.1×0.481 3.5×
Llama3 SGLang prefix 0.086 2.9×0.552 9.0×0.348 2.5×
Llama3 KVCOMM 0.187 6.2×1.383 22.7×0.704 5.1×
Llama3 DistServe style 0.052 1.7×0.082 1.3×0.161 1.2×
Llama3 live vLLM serve n/a n/a 3.901 64.0×n/a n/a
Llama3 live SGLang serve n/a n/a n/a n/a 1.674 12.0×
Table 9: Experiment 2: Scaling benchmark of AAFLOW+ versus nearest non-AAFLOW+ competitor, SGLang prefix with 32768
context size
AAF HF Backend AAF vLLM Backend AAF SGLang Backend
Model Age LOW+ SGLang Speed LOW+ SGLang Speed LOW+ SGLang Speed
nts total(s) total(s) up total(s) total(s) up total(s) total(s) up
Mistral 1 30.70 119.13 3.88×67.10 263.40 3.93×91.62 353.92 3.86×
Mistral 2 30.70 224.85 7.32×67.71 484.22 7.15×90.49 679.06 7.50×
Mistral 4 58.37 436.28 7.47×121.86 899.15 7.38×176.53 1338.65 7.58×
Mistral 8 113.71 859.14 7.56×238.75 1796.07 7.52×348.13 2654.54 7.63×
Mistral 16 224.39 1704.86 7.60×465.45 3532.56 7.59×701.29 5363.03 7.65×
Llama3 1 29.06 112.39 3.87×36.02 141.03 3.91×43.40 167.96 3.87×
Llama3 2 29.06 216.89 7.46×36.01 259.80 7.21×44.80 335.59 7.49×
Llama3 4 56.35 425.88 7.56×66.26 492.36 7.43×84.45 638.82 7.56×
Llama3 8 110.91 843.85 7.61×128.62 968.75 7.53×159.17 1211.65 7.61×
Llama3 16 220.05 1679.81 7.63×253.53 1926.11 7.60×329.07 2514.49 7.64×
The memory results(Table 11) show that AAFLOW+ achieves the
lowest peak KV footprint across all three backends because it rep-
resents forked state through explicit shared ownership and lineage.
For Mistral, the strongest gap appears against the fully duplicating
baselines: AAFLOW+ uses 8.355 GiB on HF, while AAFLOW-text
uses 53.986 GiB and DistServe style uses 50.995 GiB. Even the best
local-prefix baselines remain significantly higher, with vLLM-prefix
and SGLang-prefix both at 14.351 GiB, 14.591 GiB and KVCOMM
at 15.702 GiB. On Llama3, AAFLOW+ uses 4.210 GiB on HF, while
AAFLOW-text rises to 27.202 GiB and dense prefill to 25.188 GiB;
the nearest local-prefix baselines remain around 7.2 GiB.
The same ranking is preserved on vLLM and SGLang. On vLLM,
Mistral AAFLOW+ uses 8.290 GiB, while AAFLOW-text is 53.568 GiB
and KVCOMM is 15.580 GiB. On SGLang, Mistral AAFLOW+ again
uses 8.290 GiB, while AAFLOW-text is 53.268 GiB and KVCOMM
is 15.153 GiB. The advantage of AAFLOW+ lies in storing a single
shared prefix state and allocating only branch-specific continuation
states, while dense prefill and AAFLOW-text duplicate the entire
prefix. DistServe methods add extra branch and staging state, re-
sulting in memory usage similar to dense prefill. KVCOMM and
19

## PDF Page 20

Table 10: Experiment 3: Comparison of KV transfer cost to recomputing the prompt prefil.
Model Bandwidth Beneficial HF Backend vLLM Backend SGLang Backend
contexts Speedup vs Speedup vs Speedup vs
Recompute Recompute Recompute
Mistral 10 Gbps 5/8 2.46×2.54×2.86×
Mistral 25 Gbps 8/8 6.14×6.35×7.14×
Mistral 100 Gbps 8/8 24.54×25.39×28.55×
Mistral 200 Gbps 8/8 49.04×50.73×57.04×
Mistral 400 Gbps 8/8 97.90×101.29×113.88×
Llama3 10 Gbps 1/6 2.58×2.57×2.37×
Llama3 25 Gbps 6/6 6.44×6.43×5.92×
Llama3 100 Gbps 6/6 25.76×25.72×23.67×
Llama3 200 Gbps 6/6 51.48×51.39×47.30×
Llama3 400 Gbps 6/6 102.77×102.61×94.44×
Table 11: Experiment 4: Mean peak KV memory.
HF Backend vLLM Backend SGLang Backend
Model Baseline Mean peak Mean peak Mean peak
KV (GiB) KV (GiB) KV (GiB)
Mistral AAFLOW+ 8.355 8.290 8.290
Mistral dense prefill 49.987 49.600 49.510
Mistral AAFLOW-text 53.986 53.568 53.268
Mistral vLLM local prefix 14.351 14.240 14.113
Mistral SGLang prefix 14.591 14.338 14.142
Mistral KVCOMM 15.702 15.580 15.153
Mistral DistServe style 50.995 50.600 50.312
Llama3 AAFLOW+ 4.210 4.145 4.327
Llama3 dense prefill 25.188 24.800 24.212
Llama3 AAFLOW-text 27.202 26.784 26.319
Llama3 vLLM local prefix 7.231 7.120 6.851
Llama3 SGLang prefix 7.311 7.239 6.912
Llama3 KVCOMM 7.912 7.790 7.687
Llama3 DistServe style 25.695 25.300 25.128
local-prefix methods reduce duplication but lack explicit shared-
state ownership, preventing them from achieving AAFLOW+’s peak
memory efficiency.
F.5 Experiment 5: Throughput and Framework
Overhead
The goal is to measure effective generated-token throughput and
modeled framework overhead Ω. AAFLOW+ should improve work-
flow throughput by removing repeated prefill and reducing text
orchestration.
The throughput and overhead results (Table 12) show the clearest
split between workflow execution and raw serving. Among the
workflow rows, AAFLOW+ is best on every backend. For Mistral,
AAFLOW+ reaches 302.61 tok/s on HF, compared with 39.62 tok/s
for SGLang prefix, 38.81 tok/s for vLLM local prefix, 37.62 tok/s for
DistServe style, 35.59 tok/s for KVCOMM, and about 32 tok/s for
dense and AAFLOW-text. On vLLM, Mistral AAFLOW+ reaches
280.30 tok/s, while the strongest workflow competitor is 36.89 tok/s.
On SGLang, Mistral AAFLOW+ reaches 207.09 tok/s, while the
strongest workflow competitor is 27.10 tok/s. Llama3 shows the
same pattern: AAFLOW+ reaches 300.57/314.26/256.84 tok/s across
HF/vLLM/SGLang, whereas the strongest workflow competitor
stays near 39.27/41.35/33.61 tok/s.
The overhead values explain why AAFLOW+ keeps mean mod-
eled framework overhead fixed at 0.0075 s across both models and
all three backends. By contrast, AAFLOW-text and KVCOMM pay
much larger overheads: for Mistral, AAFLOW-text incurs 11.1659 s
on HF, 89.5948 s on vLLM, and 40.5748 s on SGLang, while KV-
COMM incurs 21.6770 s, 174.3231 s, and 78.9242 s. Dense prefill in-
curs minimal framework overhead but suffers from low throughput
due to repeated full-prefix computation. Local-prefix and DistServe-
style baselines also have modest overhead but fall short of AAFLOW+
because they retain workflow-level duplication of shared context.
20

## PDF Page 21

Table 12: Experiment 5: Mean throughput and overhead. n/a = not applicable, as that specific baseline is tightly coupled with
that specific backend.
HF Backend vLLM Backend SGLang Backend
Model Baseline Throughput Mean Throughput Mean Throughput Mean
(tok/s)Ω(s) (tok/s)Ω(s) (tok/s)Ω(s)
Mistral AAFLOW+ 302.61 0.0075 280.30 0.0075 207.09 0.0075
Mistral dense prefill 31.94 0.0019 22.78 0.0019 20.99 0.0019
Mistral AAFLOW-text 31.84 11.1659 22.62 89.5948 20.91 40.5748
Mistral vLLM local prefix 38.81 0.0627 36.11 0.0627 26.54 0.0627
Mistral SGLang prefix 39.62 0.0657 36.89 0.0657 27.10 0.0657
Mistral KVCOMM 35.59 21.6770 29.67 174.3231 24.03 78.9242
Mistral DistServe style 37.62 0.0597 35.23 0.0597 25.93 0.0597
Mistral live SGLang serve n/a n/a n/a n/a 591.14 0.0
Mistral live vLLM serve n/a n/a 704.08 0.0 n/a n/a
Llama3 AAFLOW+ 300.57 0.0075 314.26 0.0075 256.84 0.0075
Llama3 dense prefill 33.61 0.0019 25.83 0.0019 25.65 0.0019
Llama3 AAFLOW-text 33.54 6.7272 25.65 47.4580 25.54 23.4720
Llama3 vLLM local prefix 38.46 0.0627 40.48 0.0627 32.92 0.0627
Llama3 SGLang prefix 39.27 0.0657 41.35 0.0657 33.61 0.0657
Llama3 KVCOMM 36.16 13.0375 33.45 92.3380 29.63 45.6145
Llama3 DistServe style 37.46 0.0597 39.49 0.0597 32.15 0.0597
Llama3 live vLLM serve n/a n/a 801.55 0.0 n/a n/a
Llama3 live SGLang serve n/a n/a n/a n/a 673.26 0.0
Although live vLLM and SGLang show higher raw throughput,
these reflect optimized server performance, not explicit distributed
state transfer. Thus, AAFLOW+ leads among workflow systems in
this evaluation, with its remaining gap to live serving attributable
to explicit accounting of distributed state-transfer costs, rather than
concealing them within local engines.
21