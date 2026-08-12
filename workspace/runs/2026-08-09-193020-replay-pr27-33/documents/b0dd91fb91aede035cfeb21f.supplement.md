# Targeted Evidence Supplement

This supplement contains only previously unread source sections that match explicit material evidence-gap terms. It is not the full source.

## Supplemental locator: PDF Page 9

## PDF Page 9

0
 5000
 10000
 15000
 20000
 25000
 30000
Context Length (tokens)
0.0
0.5
1.0
1.5
2.0
2.5
3.0
3.5
4.0TTFT (s)
TTFT vs Context Length by Baseline
AAFLOW+
aaﬂow_text
dense_preﬁll
distserve_style
kvcomm_preﬁx
sglang_preﬁx
vllm_local_preﬁx
Figure 7: Experiment-1: TTFT vs context length across mul-
tiple baselines. The curves confirm that text baselines scale
with context length, while AAFLOW+ grows slowly because
branch cost follows the transfer/resume path rather than
repeated prefill
Table 2: Experiment-1: Mean TTFT reduction and Through-
put with variation context grid and fixed 16 agents.
Model Baseline Mean TTFT (s) Relative to AAFLOW+
Mistral AAFLOW+ 0.041 1.00×
Mistral dense prefill 2.017 49.2×slower
Mistral AAFLOW-text 2.057 50.2×slower
Mistral vLLM local prefix 0.437 10.7×slower
Mistral SGLang prefix 0.280 6.8×slower
Mistral KVCOMM 0.704 17.2×slower
Mistral DistServe style 0.1233.0×slower
Llama3 AAFLOW+ 0.030 1.00×
Llama3 dense prefill 0.499 16.6×slower
Llama3 AAFLOW-text 0.509 17.0×slower
Llama3 vLLM local prefix 0.124 4.1×slower
Llama3 SGLang prefix 0.086 2.9×slower
Llama3 KVCOMM 0.187 6.

## Supplemental locator: PDF Page 11

## PDF Page 11

plus branch continuation state; dense and text baselines effectively
duplicate the prefix across branches. Table 4 and Figure 10 reports
mean peak KV memory across branch factors 1, 2, 4, 8, and 16. For
Mistral, AAFLOW+ averages 8.355 GiB peak KV memory. Dense,
AAFLOW-text, and DistServe-style average 49.987 GiB, or5.98× the
AAFLOW+ memory. vLLM-local and SGLang average 14.351 GiB
(1.72× AAFLOW+), and 14.591 GiB (1.74× AAFLOW+), while KV-
COMM averages 15.702 GiB (1.88×). The nearest competitor varies
with the branch factor. At branch factors 1, 2, and 4, KVCOMM
is closest to AAFLOW+. At branch factors 8 and 16, vLLM-local
becomes closest. Even then, AAFLOW+ uses less memory at every
branch factor.
Forked states initially share block references, so memory grows
with branch continuation rather than with full-context duplication.
The vLLM-local and SGLang profiles also reduce duplicate prefix
storage, but they are local-prefix baselines rather than distributed
state-object schedulers. SKVCOMM captures communication-oriented
prefix reuse but has a lower reuse fraction in this benchmark. The
result is that AAFLOW+ has the lowest peak memory in every
tested branch-factor setting.
6.10 Experiment 5: Throughput and Framework
Overhead
The fifth experiment measures effective throughput and frame-
work overhead Ω shown in Table 5. AAFLOW+ should improve
throughput by removing repeated prefill work and reducing text
serialization. In the benchmark schema, throughput is reported
as generated tokens per second, and Ω captures framework-side
scheduling, serialization, and orchestration overhead modeled by
the baseline adapters. AAFLOW+ achieves approximately 302 to-
kens/s on Mistral. The nearest throughput competitor is vLLM-
local/SGLang/DistServe-style at about 38–39 tokens/s. The resulting
throughput advantage is about7 .63×–8.04× against those nearest
competitors and roughly9 .47× against dense text prefill, although
dense text prefill has low overhead.
The throughput numbers are consistent with the aggregated com-
pute costs experiments. AAFLOW+ executes one measured prefill
and then reuses state; text baselines repeatedly pay the full context
construction and prefill cost. The explicit abstraction also keeps
framework overhead small in this simulation profile. KVCOMM
has a meaningful modeled communication overhead in these runs,
which explains the larger Ω values and lower throughput relative
to AAFLOW+.
7 RELATED WORK
Distributed Data Systems and Operator Abstractions:The de-
sign of AAFLOW [34] and our extension builds upon a long line of
work in distributed data systems, where computation is expressed
as compositions of operators over structured data. Systems such as
MapReduce [8], Spark [46], and Flink [5] demonstrate how declara-
tive data transformations can be compiled into efficient distributed
execution plans. More recent frameworks such as Modin [27] and
Cylon [40] extend this paradigm to high-performance dataframes,
emphasizing communication-aware execution and parallel process-
ing patterns [25, 26, 36]. AAFLOW adapts these ideas to agentic
Table 5: Experiment-5: Mean throughput and framework
overhead with fixed context grid and variation agents.
Model Baseline ThroughputΩ(s)
(tok/s)
Mistral AAFLOW+302.610.0075
Mistral dense prefill 31.940.0019
Mistral AAFLOW-text 31.84 11.1659
Mistral vLLM local prefix 38.81 0.0627
Mistral SGLang prefix 39.62 0.0657
Mistral KVCOMM 35.59 21.6770
Mistral DistServe style 37.62 0.0597
Llama3 AAFLOW+300.570.0075
Llama3 dense prefill 33.610.0019
Llama3 AAFLOW-text 33.54 6.7272
Llama3 vLLM local prefix 38.46 0.0627
Llama3 SGLang prefix 39.27 0.0657
Llama3 KVCOMM 36.16 13.0375
Llama3 DistServe style 37.46 0.0597
workflows by treating embedding, retrieval, reasoning, and mem-
ory operations as composable operators. Our work further extends
this abstraction by introducing stateful operators over KV cache,
effectively generalizing dataflow systems into stateflow systems.
Workflow Runtimes and Distributed Execution:A large
body of work has explored distributed workflow execution and
task scheduling. Systems such as Ray [24], Dask [30], and Parsl [4]
provide flexible task-based execution frameworks for parallel and
distributed workloads. HPC-oriented systems such as RADICAL-
Pilot [23, 31–33] and Pegasus [ 9] focus on large-scale scientific
workflows.

## Supplemental locator: PDF Page 20

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