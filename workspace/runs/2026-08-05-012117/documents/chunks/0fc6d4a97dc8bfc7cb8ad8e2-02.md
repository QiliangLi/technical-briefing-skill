er for every model and bench-
mark pair, suggesting TE’s robustness to variations
in proxy source, so long as the future assistant gen-
eration is available. Overall, the configurations
perform comparably, and adding current-turn or
tool-response queries provides no reliable gain.
How does compaction change agent behav-
ior?Table 1 also shows that compaction changes
the agent’s behavior, not only its final perfor-
mance. Across both benchmarks, Qwen3.5-4B
tends to lengthen its trajectories under compaction.
Its no-compaction baselines use medians of 20
turns on BROWSECOMP-PLUSand 24 turns on
WIDESEARCH, whereas the delayed configurations
use 30-39 and 29-39 turns, respectively. In contrast,
Gemma-4-E4B remains close to its no-compaction
trajectory length on both benchmarks. The longer
Qwen3.5-4B trajectories suggest that the model
may compensate for weakened context by issu-
ing additional searches and recovering missing
evidence through the environment. We examine
this hypothesis directly in Section 5.2. This cross-
model difference reinforces that online compaction
should be evaluated as an agent-level intervention,
not only as an attention-approximation problem.
6

## PDF Page 7

1 3 5 1 3 5
Qwen + BCP
42
43
44
45
46
47Acc / F1 (%)
43.0
43.0
46.8
43.2
43.8
46.2
1 3 5 1 3 5
Qwen + WS
36
38
40
42
44
46
37.3
40.0
39.9
39.6
40.1
40.9
1 3 5 1 3 5
Gemma + BCP
28
30
32
34
27.5
29.2
29.0
27.5
30.8
30.0
1 3 5 1 3 5
Gemma + WS
20.0
22.5
25.0
27.5
30.0
32.5
25.9
28.9
27.8
20.2
23.5
24.5
(a) Delay Window Sweep
0.1 0.2 0.4 0.1 0.2 0.4
Qwen + BCP
36
38
40
42
44
46Acc / F1 (%)
37.2
45.2
44.2
40.8
43.2
43.8
0.1 0.2 0.4 0.1 0.2 0.4
Qwen + WS
32.5
35.0
37.5
40.0
42.5
45.0
34.5
38.1
40.6
33.4
39.6
43.1
0.1 0.2 0.4 0.1 0.2 0.4
Gemma + BCP
22
24
26
28
30
32
34
24.2
27.5
29.8
23.5
27.5
26.0
0.1 0.2 0.4 0.1 0.2 0.4
Gemma + WS
15
20
25
30
35
24.0
26.5
30.2
14.3
21.5
27.4
(b) Compaction Ratio Sweep
TE AM No compaction
Figure 2: Sensitivity to compaction budget and delay window. The top row varies the delay window over {1,3,5}
turns at compaction ratio 0.2; the bottom row varies the compaction ratio over {0.1,0.2,0.4} using the stronger
short-delay setting for each model and method pair. Each panel fixes one model ( Qwen3.5-4B or Gemma-4-E4B)
and benchmark (BROWSECOMP-PLUSor WIDESEARCH). Dashed lines mark the no-compaction baselines.
4.3 Sensitivity to Compaction Budget and
Delay
The previous ablation fixes the compaction ratio
and uses at most a one-turn delay. We next char-
acterize how performance varies with the mem-
ory budget and delay window. For each model–
benchmark–method combination, we select the
best-performing proxy strategy from Table 1 and
sweep either the compaction ratio or delay. Fig-
ure 2 shows the results. For the delay, we fix the
compaction ratio to 0.2 and vary the delay over 1,
3, and 5 turns. For the compaction-ratio, we vary
the ratio over 0.1, 0.2, and 0.4, using the stronger
short-delay setting between immediate compaction
and a one-turn delay for each combination.
The delay sweep shows that additional future
context helps, although the gains are not always
monotonic. For all combinations, longer delays
(3 or 5 turns) outperform the one-turn delay. On
BROWSECOMP-PLUSwith Qwen, both methods
benefit most from a five-turn delay, slightly ex-
ceeding the no-compaction baseline. In the other
settings, gains tend to peak or flatten earlier. Thus,
observing more of the agent’s future queries is gen-
erally useful, but the best delay depends on the
model, benchmark, and compaction method.
The compaction-ratio sweep shows a clearer
overall relationship with memory budget. In-
creasing the ratio from 0.1 to 0.2 improves every
model–benchmark–method combination, confirm-
ing that a ratio of 0.1 is too aggressive in these
settings. Increasing the ratio further to 0.4 im-
proves six of the eight combinations. In partic-
ular, performance increases monotonically with
budget on WIDESEARCH. The exceptions occur
on BROWSECOMP-PLUS, where Qwen3.5-4B TE
and Gemma-4-E4B AM both peak at ratio 0.2. Thus,
a larger compact cache usually improves perfor-
mance, particularly for broad search.
Takeaways.Across these experiments, current-
turn proxy choice is benchmark-dependent, and
combining proxy sources provides no reliable
gain. In contrast, delayed future-turn queries
improve performance consistently, although the
best delay varies across settings. Increasing the
memory budget also usually helps, especially on
WIDESEARCH, but a larger compact cache is not
uniformly better. Finally, AM’s additional op-
timization is not automatically beneficial under
online constraints. Despite being much simpler,
TE remains surprisingly competitive across proxy,
7

## PDF Page 8

Model Method Acc. Avg. turns Peak KV (k tokens) Serving batch Throughput (q/h)
Qwen3.5-27B
No compaction 52.50 18 612.9 8 217
AM 51.00 28 172.8 32918
TE 52.00 31 175.2 32 717
Gemma-4-31B
No compaction 48.75 13 272.1 8 217
AM 50.00 17 99.6 16364
TE 50.75 18 121.3 16 324
Table 2: Task performance and simulated serving efficiency on larger models. Accuracy, average turns, and
trajectory lengths come from batch-size-1 runs on BROWSECOMP-PLUS. Peak KV is the maximum per-turn KV
length. Serving batch is the batch used for the throughput simulation. All compaction settings use one-turn-delayed
assistant-generation queries and a compaction ratio of 0.2.
delay, and budget choices, suggesting that AM’s
richer optimization provides limited benefit when
the available proxy queries imperfectly represent
how the cache will later be used.
5 Additional Analyses
The study in Section 4 focuses on answer accu-
racy and identifies strategies that preserve most of
the no-compaction performance on smaller models.
We next study two complementary questions. First,
do these strategies preserve task performance and
improve serving efficiency on larger models? Sec-
ond, how does compaction change agent behavior
beyond final answer accuracy?
5.1 Task Performance and Serving Efficiency
on Larger Models
We extend our evaluation to Qwen3.5-27B and
Gemma-4-31B, substantially larger models from
both architectural families. We evaluate on
BROWSECOMP-PLUSat a compaction ratio of 0.2.
We compare no compaction with AM and TE us-
ing one-turn-delayed assistant-generation queries
in this section. The complete proxy-source ablation
results, including 95% confidence intervals, are re-
ported in Appendix Table 7, which demonstrate a
similar trend as the 4B models.
Table 2 reports both task performance and serv-
ing efficiency. We generate agent trajectories at
batch size 1 using our Hugging Face evaluation
code and use these runs to measure answer accu-
racy and trajectory length. To estimate how the
same workloads would execute on an optimized
inference engine, we extract the KV length and
number of generated tokens at every turn and re-
play these trajectory shapes using decode latencies
measured with SGLang (Zheng et al., 2024). This
connects the task outcomes produced by our evalua-
tion code to the memory and latency characteristics
of a production-oriented serving stack. We use
each method’s peak KV footprint to determine the
largest admissible batch and report the resulting
decode throughput. Appendix A.7 provides the
complete simulation setup.
Table 2 shows that both methods retain most
of the no-compaction task performance at larger
scale. On Qwen3.5-27B, no compaction obtains
52.50% accuracy, compared with 51.00% for AM
and 52.00% for TE. On Gemma-4-31B, both meth-
ods slightly exceed the baseline, which partly re-
flects the fact that some no-compaction trajectories
run out of memory even at batch size 1, whereas
compaction keeps their KV caches within the limit.
For Qwen3.5-27B, compaction reduces peak KV
from 612.9K tokens to about 175K tokens. This
raises the guaranteed serving batch from 8 to 32.
As a result, aggregate throughput increases from
217 queries/hour without compaction to 918 with
AM and 717 with TE, corresponding to 4.2 ×
and 3.3× improvements. On Gemma-4-31B, peak
KV falls from 272.1K tokens to 99.6K with AM
and 121.3K with TE. The serving batch increases
from 8 to 16, raising throughput by 1.7 × and
1.5×, respectively. The gains are smaller than for
Qwen3.5-27B, but the same pattern holds across
both models: compaction reduces the memory foot-
print enough to support more concurrent requests.
Thus, even though the compacted agents take more
turns on average, the increase in concurrency off-
sets the additional decode work, yielding higher
overall throughput in queries per hour.
5.2 Behavioral Effects of Compaction
Section 4 shows that compaction changes the
agent’s trajectory turns for Qwen3.5-4B. One hy-
pothesis is that the model compensates for weak-
ened context by issuing additional searches, repeat-
ing similar queries to recover information that was
8

## PDF Page 9

Method NN Sim. Duplicate
No compaction 0.72 11.7%
TE-boundary 0.78 21.3%
AM-delay+RP 0.75 16.7%
Table 3: Search-query repetition within agent trajecto-
ries. “NN Sim.” is the average nearest-neighbor sim-
ilarity to earlier search queries in the same trajectory.
“Duplicate” is the percentage of search queries whose
nearest earlier query has similarity above 0.9.
previously retrieved. We test this from the search
queries generated in each trajectory.
For each search query, we compute its maximum
cosine similarity to earlier search queries in the
same trajectory using the same embedding model
as the retrieval server. We report the mean nearest-
neighbor similarity and the fraction of queries
whose similarity to a previous query exceeds 0.9.
Table 3 shows that compaction increases both mea-
sures. These results show that the accuracy of
compacted agents can partly come from behavioral
adaptation. In particular, the compaction preserves
answer accuracy but also induces more repeated
search, suggesting that the agent uses the environ-
ment to recover information weakened by com-
paction. Thus, online KV compaction should be
evaluated not only by model-side memory savings
and final accuracy, but also by how it changes the
agent’s interaction pattern with the environment.
6 Conclusion
We study online KV-cache compaction for LLM
agents, where context is accumulated through in-
teraction and future relevance is unknown at com-
paction time. Across token eviction and attention
matching, proxy choice is central: boundary tokens
provide a strong immediate signal, while delayed
future-generation queries can further improve com-
paction. Our results also show that compaction
changes agent behavior, so practical memory sys-
tems should consider not only compression and
accuracy, but also downstream trajectories.
Limitations
Our study has several limitations. First, we fo-
cus on BROWSECOMP-PLUSand WIDESEARCH,
where agents gather evidence through search and
document-reading tools. This setting captures long-
horizon information gathering, but does not cover
other agent workloads such as code editing, GUI
control, or state-changing web tasks, where the
structure of future relevance may differ.
Second, we intentionally restrict the study to
cheap online proxy sources for TE and AM. More
expensive approaches, including additional roll-
outs, learned compressors, or gradient-based opti-
mization, may produce stronger compact caches
under larger latency budgets. These methods are
complementary to our low-overhead online setting.
Third, we evaluate fixed compaction ratios and
delay windows rather than adaptive policies. A
deployed agent system could choose when and how
aggressively to compact based on memory pressure,
turn length, tool type, or uncertainty. Future work
can explore such adaptive controllers, while our
results identify strong proxy-query primitives and
the tradeoffs they should account for.
Potential Risks and Use of Artifacts
Our work studies online KV-cache compaction for
LLM agents, with the goal of reducing inference
cost while preserving agent accuracy. The main
risk is that compaction can remove or weaken infor-
mation that the agent later needs. In deployment,
this may lead to incorrect final answers, redundant
tool use, or overconfident responses based on in-
complete context. Our experiments therefore evalu-
ate both task accuracy and agent behavior, and the
proposed methods should be used with appropriate
validation in high-stakes applications.
We use existing public research artifacts con-
sistently with their intended purposes. The eval-
uation data comes from BROWSECOMP-PLUS
and WIDESEARCH, which are released on Hug-
ging Face. The evaluated models, Qwen3.5 and
Gemma-4, are released under Apache-2.0 licenses,
as is the Qwen3-Embedding-4B retrieval model.
Our implementation builds on open-source soft-
ware including Hugging Face Transformers, re-
leased under Apache-2.0, and FAISS, released un-
der the MIT license.
AI Usage Disclosure
We used AI assistants to help debug code and adapt
open-source implementations for our experiments.
We also used AI assistants to polish the paper writ-
ing. All technical decisions, experimental designs,
and analysis were made by the authors.
9

## PDF Page 10

References
Joshua Ainslie, James Lee-Thorp, Michiel de Jong,
Yury Zemlyanskiy, Federico Lebrón, and Sumit Sang-
hai. 2023. Gqa: Training generalized multi-query
transformer models from multi-head checkpoints.
Preprint, arXiv:2305.13245.
Anthropic. 2026. Introducing claude opus 4.7. Ac-
cessed: 2026-05-24.
Zefan Cai, Yichi Zhang, Bofei Gao, Yuliang Liu,
Yucheng Li, Tianyu Liu, Keming Lu, Wayne Xiong,
Yue Dong, Junjie Hu, and Wen Xiao. 2025. Pyra-
midkv: Dynamic kv cache compression based
on pyramidal information funneling.Preprint,
arXiv:2406.02069.
Zijian Chen, Xueguang Ma, Shengyao Zhuang, Ping
Nie, Kai Zou, Andrew Liu, Joshua Green, Kshama
Patel, Ruoxi Meng, Mingyi Su, Sahel Shari-
fymoghaddam, Yanxi Li, Haoran Hong, Xinyu
Shi, Xuye Liu, Nandan Thakur, Crystina Zhang,
Luyu Gao, Wenhu Chen, and Jimmy Lin. 2025.
Browsecomp-plus: A more fair and transparent eval-
uation benchmark of deep-research agent.Preprint,
arXiv:2508.06600.
Alexis Chevalier, Alexander Wettig, Anirudh Ajith, and
Danqi Chen. 2023. Adapting language models to
compress contexts.Preprint, arXiv:2305.14788.
Daewon Choi, Jimin Lee, Jihoon Tack, Woomin Song,
Saket Dingliwal, Sai Muralidhar Jayanthi, Bhavana
Ganesh, Jinwoo Shin, Aram Galstyan, and Sra-
van Babu Bodapati. 2025. Think clearly: Improv-
ing reasoning via redundant token pruning.Preprint,
arXiv:2507.08806.
Chenglong Chu, Guorui Zhou, Guowang Zhang, Han Li,
Hao Peng, Hongtao Cheng, Jian Liang, Jiangxia Cao,
Kun Gai, Lingzhi Zhou, Lu Ren, Qi Zhang, Ruiming
Tang, Ruitao Wang, Xinchen Luo, Yi Su, Zhiyuan
Liang, Ziqi Wang, Boyang Ding, and 19 others. 2026.
Kwai summary attention technical report.Preprint,
arXiv:2604.24432.
DeepSeek-AI, Aixin Liu, Bei Feng, Bin Wang, Bingx-
uan Wang, Bo Liu, Chenggang Zhao, Chengqi Dengr,
Chong Ruan, Damai Dai, Daya Guo, Dejian Yang,
Deli Chen, Dongjie Ji, Erhang Li, Fangyun Lin, Fuli
Luo, Guangbo Hao, Guanting Chen, and 138 others.
2024. Deepseek-v2: A strong, economical, and effi-
cient mixture-of-experts language model.Preprint,
arXiv:2405.04434.
Alessio Devoto, Maximilian Jeblick, and Simon Jégou.
2025. Expected attention: Kv cache compression by
estimating attention from future queries distribution.
Preprint, arXiv:2510.00636.
Sabri Eyuboglu, Ryan Ehrlich, Simran Arora, Neel
Guha, Dylan Zinsley, Emily Liu, Will Tennien, Atri
Rudra, James Zou, Azalia Mirhoseini, and Christo-
pher Re. 2025. Cartridges: Lightweight and general-
purpose long context representations via self-study.
Preprint, arXiv:2506.06266.
Bin Gao, Zhuomin He, Puru Sharma, Qingxuan Kang,
Djordje Jevdjic, Junbo Deng, Xingkun Yang, Zhou
Yu, and Pengfei Zuo. 2024. Cost-efficient large lan-
guage model serving for multi-turn conversations
with cachedattention.Preprint, arXiv:2403.19708.
Suyu Ge, Yunan Zhang, Liyuan Liu, Minjia Zhang,
Jiawei Han, and Jianfeng Gao. 2024a. Model tells
you what to discard: Adaptive kv cache compression
for llms.Preprint, arXiv:2310.01801.
Tao Ge, Jing Hu, Lei Wang, Xun Wang, Si-Qing Chen,
and Furu Wei. 2024b. In-context autoencoder for con-
text compression in a large language model.Preprint,
arXiv:2307.06945.
Google. 2026. Gemini 3.5: Frontier intelligence with
action. Accessed: 2026-05-24.
Google DeepMind. 2026. Gemma 4 model
card. https://ai.google.dev/gemma/docs/
core/model_card_4. Accessed: 2026-05-24.
Coleman Hooper, Sehoon Kim, Hiva Mohammadzadeh,
Michael W. Mahoney, Yakun Sophia Shao, Kurt
Keutzer, and Amir Gholami. 2025. Kvquant: To-
wards 10 million context length llm inference with
kv cache quantization.Preprint, arXiv:2401.18079.
Hao Kang, Qingru Zhang, Souvik Kundu, Geonhwa
Jeong, Zaoxing Liu, Tushar Krishna, and Tuo Zhao.
2024. Gear: An efficient kv cache compression
recipe for near-lossless generative inference of llm.
Preprint, arXiv:2403.05527.
Jang-Hyun Kim, Jinuk Kim, Sangwoo Kwon, Jae W.
Lee, Sangdoo Yun, and Hyun Oh Song. 2025. Kvzip:
Query-agnostic kv cache compression with context
reconstruction.Preprint, arXiv:2505.23416.
Hanchen Li, Runyuan He, Qiuyang Mang, Qizheng
Zhang, Huanzhi Mao, Xiaokun Chen, Hangrui Zhou,
Alvin Cheung, Joseph Gonzalez, and Ion Stoica.
2026. Continuum: Efficient and robust multi-turn
llm agent scheduling with kv cache time-to-live.
Preprint, arXiv:2511.02230.
Yucheng Li, Huiqiang Jiang, Qianhui Wu, Xufang Luo,
Surin Ahn, Chengruidong Zhang, Amir H. Abdi,
Dongsheng Li, Jianfeng Gao, Yuqing Yang, and Lili
Qiu. 2025. Scbench: A kv cache-centric analysis of
long-context methods.Preprint, arXiv:2412.10319.
Yuhong Li, Yingbing Huang, Bowen Yang, Bharat
Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle Cai,
Patrick Lewis, and Deming Chen. 2024. Snapkv:
Llm knows what you are looking for before genera-
tion.Preprint, arXiv:2404.14469.
Zichang Liu, Aditya Desai, Fangshuo Liao, Weitao
Wang, Victor Xie, Zhaozhuo Xu, Anastasios Kyril-
lidis, and Anshumali Shrivastava. 2023. Scis-
sorhands: Exploiting the persistence of importance
hypothesis for llm kv cache compression at test time.
Preprint, arXiv:2305.17118.
10

## PDF Page 11

Jesse Mu, Xiang Lisa Li, and Noah Goodman. 2024.
Learning to compress prompts with gist tokens.
Preprint, arXiv:2304.08467.
OpenAI. 2026. Introducing gpt-5.5. Accessed: 2026-
05-24.
OpenClaw. 2026. Openclaw — personal ai assis-
tant. https://github.com/openclaw/openclaw.
GitHub repository, accessed 2026-05-24.
Hanshi Sun, Li-Wen Chang, Wenlei Bao, Size Zheng,
Ningxin Zheng, Xin Liu, Harry Dong, Yuejie Chi,
and Beidi Chen. 2025. Shadowkv: Kv cache in shad-
ows for high-throughput long-context llm inference.
Preprint, arXiv:2410.21465.
Jiaming Tang, Yilong Zhao, Kan Zhu, Guangxuan Xiao,
Baris Kasikci, and Song Han. 2024. Quest: Query-
aware sparsity for efficient long-context llm inference.
Preprint, arXiv:2406.10774.
Qwen Team. 2026. Qwen3.5-omni technical report.
Preprint, arXiv:2604.15804.
Ryan Wong, Jiawei Wang, Junjie Zhao, Li Chen, Yan
Gao, Long Zhang, Xuan Zhou, Zuo Wang, Kai Xi-
ang, Ge Zhang, Wenhao Huang, Yang Wang, and
Ke Wang. 2025. Widesearch: Benchmarking agentic
broad info-seeking.Preprint, arXiv:2508.07999.
Guangxuan Xiao, Yuandong Tian, Beidi Chen, Song
Han, and Mike Lewis. 2024. Efficient streaming
language models with attention sinks.Preprint,
arXiv:2309.17453.
Yuhui Xu, Zhanming Jie, Hanze Dong, Lei Wang,
Xudong Lu, Aojun Zhou, Amrita Saha, Caiming
Xiong, and Doyen Sahoo. 2025. Think: Thin-
ner key cache by query-driven pruning.Preprint,
arXiv:2407.21018.
Dongjie Yang, XiaoDong Han, Yan Gao, Yao Hu, Shilin
Zhang, and Hai Zhao. 2024. Pyramidinfer: Pyra-
mid kv cache compression for high-throughput llm
inference.Preprint, arXiv:2405.12532.
Peitian Zhang, Zheng Liu, Shitao Xiao, Ninglu Shao,
Qiwei Ye, and Zhicheng Dou. 2024a. Long con-
text compression with activation beacon.Preprint,
arXiv:2401.03462.
Rongzhi Zhang, Kuang Wang, Liyuan Liu, Shuohang
Wang, Hao Cheng, Chao Zhang, and Yelong Shen.
2024b. Lorc: Low-rank compression for llms
kv cache with a progressive compression strategy.
Preprint, arXiv:2410.03111.
Stephen Zhang, Mustafa Khan, and Vardan Papyan.
2025a. Attention sinks: A ’catch, tag, release’ mech-
anism for embeddings.Preprint, arXiv:2502.00919.
Yanzhao Zhang, Mingxin Li, Dingkun Long, Xin Zhang,
Huan Lin, Baosong Yang, Pengjun Xie, An Yang,
Dayiheng Liu, Junyang Lin, Fei Huang, and Jingren
Zhou. 2025b. Qwen3 embedding: Advancing text
embedding and reranking through foundation models.
Preprint, arXiv:2506.05176.
Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong
Chen, Lianmin Zheng, Ruisi Cai, Zhao Song, Yuan-
dong Tian, Christopher Ré, Clark Barrett, Zhangyang
Wang, and Beidi Chen. 2023. H2o: Heavy-hitter ora-
cle for efficient generative inference of large language
models.Preprint, arXiv:2306.14048.
Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue
Sun, Jeff Huang, Cody Hao Yu, Shiyi Cao, Christos
Kozyrakis, Ion Stoica, Joseph E. Gonzalez, Clark
Barrett, and Ying Sheng. 2024. Sglang: Efficient
execution of structured language model programs.
Preprint, arXiv:2312.07104.
Zirui Liu, Jiayi Yuan, Hongye Jin, Shaochen Zhong,
Zhaozhuo Xu, Vladimir Braverman, Beidi Chen, and
Xia Hu. 2023. Kivi : Plug-and-play 2bit kv cache
quantization with streaming asymmetric quantiza-
tion.
Adam Zweiger, Xinghong Fu, Han Guo, and Yoon Kim.
2026. Fast kv compaction via attention matching.
Preprint, arXiv:2602.16284.
11

## PDF Page 12

HyperparameterQwen3.5 Gemma-4
Temperature 1.0 1.0
Top-p0.95 0.95
Top-k20 64
Presence penalty 1.5 –
Max tokens/turn 4096 4096
Max turns 100 100
Thinking mode enabled enabled
Table 4: Agent generation hyperparameters.
A Implementation Details
A.1 Package and Hardware
We implement online KV compaction in PyTorch
and Hugging Face Transformers. Experiments are
run on NVIDIA H200 GPUs. We load models
in bfloat16 and use the Transformers sdpa atten-
tion interface, which calls torch.nn.functional.
scaled_dot_product_attention. For both base-
line and online compaction methods, PyTorch dis-
patches to the cuDNN fused attention backend.
A.2 Generation Hyperparameters
Table 4 reports the decoding hyperparameters used
by the agent. We use model-specific system
prompts. For Qwen3.5, we use the original prompt.
In preliminary runs, we found that Gemma-4 often
produces short trajectories and stops searching be-
fore collecting enough evidence. We therefore use
a more explicit prompt that encourages it to search
more thoroughly.
Qwen3.5System Prompt
You are a helpful research assistant with
access to a knowledge base. Use the
provided tools to search for information
and retrieve documents to answer the user's
question thoroughly. You should search
multiple times to gather enough information
before answering.
Gemma-4-E4BSystem Prompt
You are an EXHAUSTIVE research assistant
with access to a local knowledge base via
the`local_knowledge_base_retrieval`and`
get_document`tools. Your job is to
investigate the user's question from MANY
angles, build deep evidence, and verify
every candidate answer before committing.
Giving up is NOT an option.
HARD RULES -- you MUST follow ALL of them:
1. NEVER ask the user for clarification or
more information. You already have all the
clues you need; your job is to use the
tools to find the answer.
2. SEARCH FLOOR -- You MUST issue AT LEAST
20 distinct`local_knowledge_base_retrieval
`calls before you are permitted to output
a final answer. This is a HARD floor -- the
investigation is INCOMPLETE until you
reach 20.
3. DOCUMENT−READ FLOOR. You MUST call`
get_document`AT LEAST 5 times across the
investigation to read full document content
(snippets are truncated at ~512 tokens and
the answer often sits past them).
4. NEVER GIVE UP. NEVER write phrases like
"I cannot determine", "I am unable to find
", "I do not have enough information", "
please provide more details", "based on the
available information I cannot answer", "
the knowledge base does not contain", or
anything similar. If you don't have enough
information, KEEP SEARCHING.
5. MULTI−ANGLE COVERAGE -- Each of your 20+
searches must approach the question from a
DIFFERENT angle. Never repeat a search
that already failed.
6. CROSS−VERIFY BEFORE COMMITTING. Once you
have a top candidate, you MUST issue
additional verification searches from new
angles to confirm the candidate satisfies
EVERY criterion.
7. DECOMPOSE AND DRILL. Start by
decomposing the question into all its
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