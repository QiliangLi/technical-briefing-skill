nlarges the KV state consumed
at every decoding step. KAP predicts a different scaling behavior: Graph-RAG priors should let
proposal-time consumption become increasingly selective as context grows, and the avoided access
should translate into throughput gains. To test both consequences, we construct nested evidence-
preserving prompts from 4K to 128K tokens and run the full-context baseline and GRAPHSPECon
the same complete prompt at every length.
Result discussion.Table 2 confirms both effects. As context length increases from 4K to 128K,
the proposal-visible KV ratio falls from 40.1% to 5.5%, while proposal acceptance remains near
0.95–0.96; over the same sweep, decode-throughput speedup rises from 1.08×to 1.19×. TTFT re-
mains close to the full-context baseline because GRAPHSPECpreserves the complete logical prompt
and targets decode-time KV consumption rather than prefill elimination. The result directly supports
KAP’s answer to the knowledge selection–runtime consumption gap: frontend knowledge relevance
can decouple proposal-time physical consumption from serialized context growth, and the resulting
access reduction translates into end-to-end decode gains.
12

## PDF Page 13

Table 2: RQ1 proposal-visible KV ratio and decode throughput over six context buckets. All entries
are averages over the evaluation set. Active KV/source andhare reported for GraphSpec;his the
Top-3 tolerant proposal acceptance rate.
Length Full-context TPS GraphSpec TPS Speedup Full-context TTFT GraphSpec TTFT Active KV/sourceh
4K 51.92 56.11 1.08×1.51s 1.56s 40.1% 0.958
8K 51.58 55.57 1.08×0.65s 0.87s 34.4% 0.957
16K 50.59 54.82 1.08×2.06s 2.17s 24.2% 0.957
32K 48.72 53.19 1.09×4.87s 4.92s 16.1% 0.956
64K 45.68 51.70 1.13×12.56s 12.71s 10.8% 0.962
128K 41.10 48.80 1.19×38.31s 37.90s 5.5% 0.953
Table 3: RQ2 final-answer quality across context lengths. GraphSpec and the full-context baseline
are evaluated with the same answer-level metric;his reported only as an execution diagnostic.
Length Full-context pass GraphSpec pass Full-context avg. sim. GraphSpec avg. sim. GraphSpech
4K 80.0% 80.2% 0.691 0.696 0.958
8K 82.6% 82.9% 0.715 0.716 0.957
16K 87.4% 87.4% 0.743 0.745 0.957
32K 86.9% 87.0% 0.744 0.749 0.956
64K 86.0% 87.9% 0.741 0.748 0.962
128K 84.6% 84.3% 0.728 0.732 0.953
5.3 RQ2: DOESGRAPHSPEC SUSTAIN EFFICIENCY GAINS WHILE PRESERVING ANSWER
QUALITY ACROSS CONTEXT LENGTHS?
RQ2 tests whether the benefits of KAP, as instantiated by GRAPHSPEC, persist across operating
scales rather than appearing only at a favorable context length. We combine the access and through-
put results from RQ1 with answer-level evaluation over the same 4K–128K sweep. GRAPHSPEC
changes proposal-time physical KV consumption, while the complete logical prompt remains avail-
able to full-context verification; a successful instantiation should therefore improve efficiency with-
out degrading final answers at any evaluated length. The Top-3 tolerant acceptance rate is reported
only as an execution diagnostic, not as the quality criterion.
Result discussion.Table 3 shows that GRAPHSPECpreserves answer quality across the full
context-length range. Its pass rate differs from the full-context baseline by at most 0.3 percent-
age points at five of the six lengths; at 64K it is 1.9 points higher, while average similarity remains
closely matched throughout. Thus, the efficiency gains in RQ1 are not obtained by trading away
answer quality. Combined with RQ1, where throughput improves by 1.08×–1.19×and proposal-
visible KV consumption falls as context grows, these results establish a consistent efficiency–quality
advantage across all evaluated lengths. The combined evidence validates the KAP approach in
GRAPHSPEC: physical knowledge consumption can be reduced to deliver systems gains without
sacrificing the answer quality anchored by the complete logical context.
5.4 RQ3: DOES THE RUNTIME ACCESS PLAN BRIDGE KNOWLEDGE SELECTION AND
RUNTIME CONSUMPTION?
RQ3 isolates the mechanism central to KAP: whether the same frontend knowledge is materialized
as a shortened prompt or compiled into a runtime access plan. Physical concat materializes the
same evidence selected by GRAPHSPECas a shortened prompt, holding evidence quality fixed while
removing the runtime access plan. Random concat removes Graph-RAG-guided selection, and Local
window replaces it with a position-based heuristic; both operate under comparable prompt budgets.
If evidence selection or prompt shortening alone were sufficient to close the knowledge selection–
runtime consumption gap, these alternatives would recover GRAPHSPEC’s quality–efficiency trade-
off.
Result discussion.Table 4 rejects that alternative. Physical concat is the decisive ablation: despite
materializing the same selected evidence in a 0.95K-token prompt, its pass rate falls to 73.9%,
compared with 87.9% for GRAPHSPEC. Random concat and Local window retain larger 7.8K-token
13

## PDF Page 14

Table 4: RQ3 ablation of evidence selection and execution strategy on 64K contexts. “Full logical
prompt” indicates whether the original serialized context and logical positions are preserved. For
prompt-materialization baselines, accessed KV/source is the served-prompt ratio; for GraphSpec, it
is the proposal-visible KV ratio. Pass rate applies the pre-specified 0.5 threshold to LLM similarity,
as independently audited in Table 1.
Method Backend Full logical prompt Served prompt Accessed KV/source TPS TTFT Avg. sim. Pass rate
Full-context standardVLLM Yes 65.2K 100.0% 45.68 12.56s 0.741 86.0%GraphSpec GraphSpec Yes 64.9K 10.8% 51.70 12.71s 0.748 87.9%Physical concat standardVLLM No 0.95K 1.46% 52.82 1.95s 0.653 73.9%Random concat standardVLLM No 7.79K 12.0% 52.23 5.17s 0.491 49.7%Local window standardVLLM No 7.78K 12.0% 52.26 5.20s 0.469 47.1%
Table 5: RQ4 empirical consistency with the phase-boundary model. The retained ratiosdecreases
as context length grows, whilehremains high; consequentlyh−sincreases together with measured
throughput speedup.
Lengths h h−sActual speedup
4K 0.401 0.958 0.557 1.08×
8K 0.344 0.957 0.614 1.08×
16K 0.242 0.957 0.715 1.08×
32K 0.161 0.956 0.796 1.09×
64K 0.108 0.962 0.853 1.13×
128K 0.055 0.953 0.897 1.19×
prompts yet fall further to 49.7% and 47.1%, confirming that arbitrary or positional selection is not
an adequate substitute for graph-derived priors. Only GRAPHSPECimproves throughput over the
full-context baseline while retaining the complete logical context and comparable answer quality. In
this controlled comparison, the runtime access plan is therefore the operative bridge in KAP: it turns
frontend selection into backend-executable consumption, whereas evidence selection that terminates
in prompt materialization leaves the knowledge selection–runtime consumption gap unresolved.
5.5 RQ4: IS THE OBSERVED SPEEDUP TREND CONSISTENT WITH THE PHASE-BOUNDARY
ANALYSIS?
RQ4 evaluates the empirical consistency of the observed performance trend with the phase-boundary
analysis in Section 4. Without refitting the cost model to the measurements, we test its directional
implication that the positive-speedup regime becomes more favorable as proposal acceptance re-
mains high relative to the retained-KV ratio. We therefore tracks,h, the marginh−s, and measured
speedup across context lengths.
Result discussion.Table 5 is consistent with the phase-boundary prediction. As contexts grow,s
decreases from 0.401 to 0.055 whilehremains high, so the marginh−sincreases from 0.557 to
0.897. Measured speedup follows the same direction, rising from 1.08×to 1.19×. The agreement
supports the directional implication of the phase-boundary model: a larger KV-side acceptance–
retention margin corresponds to a more favorable regime for plan-guided execution. It thereby
closes the KAP analysis–system–experiment loop by connecting the compiler’s planning criterion,
the executor’s observed behavior, and end-to-end speedup.
6 RELATEDWORK
Retrieval-augmented generation and graph-guided retrieval.Retrieval-augmented generation
grounds LLM outputs in external knowledge by retrieving relevant passages or documents before
generation (Lewis et al., 2020; Guu et al., 2020). Generative retrieve-and-read systems such as
Fusion-in-Decoder and retrieval-enhanced language models such as RETRO integrate retrieved pas-
sages into generation (Izacard & Grave, 2021; Borgeaud et al., 2022). Dense retrieval methods
such as DPR improve open-domain retrieval by learning neural passage representations (Karpukhin
14

## PDF Page 15

et al., 2020), and multi-hop retrieval extends dense selection to complex questions requiring evi-
dence chains (Xiong et al., 2021). Graph-based retrieval and reasoning methods build structured
representations over entities, documents, or events for multi-hop QA (Tu et al., 2019; Edge et al.,
2024; Jimenez Gutierrez et al., 2024). These works improve thefrontend knowledge selectionstage.
KAP is complementary: it asks how the selected knowledge should be consumed by the LLM serv-
ing backend once it has been retrieved.
RAG serving and KV-cache reuse.General LLM serving systems improve batching, scheduling,
offloading, and cache reuse for autoregressive generation (Yu et al., 2022; Aminabadi et al., 2022;
Sheng et al., 2023; Kwon et al., 2023; Zheng et al., 2024). Recent RAG-specific systems optimize
serving by caching or reusing intermediate states of retrieved knowledge. RAGCache caches re-
trieved knowledge states in a hierarchy to reduce TTFT and improve throughput (Jin et al., 2024).
CacheBlend fuses cached knowledge chunks even when they are not strict prefixes of the input
(Yao et al., 2024), and TurboRAG precomputes KV caches for document chunks to accelerate RAG
prefill (Lu et al., 2025). RAGO studies systematic performance optimization for different RAG
pipelines through a structured RAGSchema abstraction (Jiang et al., 2025). These systems reduce
retrieval-generation latency, especially around prefill, scheduling, and cache reuse. In contrast, KAP
addresses the runtime-consumption side of knowledge-augmented inference: frontend knowledge
priors are compiled into executable access plans so that the backend can selectively consume knowl-
edge rather than uniformly processing the serialized prompt. Unlike pipeline schemas that organize
retrieval and generation components, the runtime access plan is a backend-consumed IR that governs
physical knowledge access during execution.
Prompt compression and long-context usage.Prompt compression methods reduce inference
cost at the input layer by shortening the serialized context before inference. LLMLingua and
LongLLMLingua compress prompts to reduce cost and latency while attempting to preserve task-
relevant information (Jiang et al., 2023; 2024b); Selective Context similarly prunes redundant con-
text for efficiency (Li et al., 2023). These methods are complementary to KAP: they transform the
prompt presented to the model, whereas KAP preserves the logical input and moves selection into
an executable runtime access plan. The distinction matters in long-context and graph-based QA
settings, where models can be sensitive to the position of relevant information (Liu et al., 2024)
and where evidence boundaries, provenance, or graph organization may carry reasoning value (Tu
et al., 2019; Xiong et al., 2021). GraphSpec therefore treats frontend priors not merely as prompt-
construction hints, but as runtime guidance for physical KV consumption.
KV-cache compression and sparse attention.A large body of work reduces the cost of long-
context inference by optimizing attention or compressing KV access. IO-aware kernels such as
FlashAttention reduce attention memory traffic (Dao et al., 2022). H 2O keeps heavy-hitter tokens
in the KV cache (Zhang et al., 2023); StreamingLLM identifies attention sinks for stable streaming
inference (Xiao et al., 2024); SnapKV and PyramidKV compress KV states by selecting impor-
tant tokens or allocating cache across layers (Li et al., 2024a; Cai et al., 2025). Quest performs
query-aware KV-page selection at inference time (Tang et al., 2024), while MInference accelerates
long-context prefill through dynamic sparse attention patterns (Jiang et al., 2024a). These methods
infer token or page importance from model-internal attention or query statistics. KAP instead uses
frontend knowledge priorsas the source of runtime access decisions, and GraphSpec applies sparse
access only to the proposal pass while using full-context verification to guard answer-level quality.
Accordingly, our evaluation isolates this orthogonal systems mechanism rather than providing an
exhaustive ranking of general-purpose KV-cache compression methods.
Speculative and self-speculative decoding.Speculative decoding accelerates generation by draft-
ing candidate tokens with a cheaper path and verifying them with a target model (Leviathan et al.,
2023; Chen et al., 2023). System-oriented extensions such as SpecInfer organize candidates into
token trees for speculative verification (Miao et al., 2024). Subsequent approaches improve draft-
ing through multiple decoding heads, feature-level prediction, early exits, or parallel decoding (Cai
et al., 2024; Li et al., 2024b; Elhoushi et al., 2024; Fu et al., 2024). Long-context variants pursue
several complementary routes: TriForce performs hierarchical speculation with dynamic sparse-KV
retrieval (Sun et al., 2024); RAPID drafts from shortened retrieval contexts (Chen et al., 2025);
QuantSpec uses hierarchically quantized weights and KV states for self-speculation (Tiwari et al.,
15

## PDF Page 16

2025); and LongSpec employs a learned memory-efficient drafter with a constant-sized KV cache
(Yang et al., 2026). GraphSpec adopts selected-KV proposal with full-context verification as one
concrete KAP executor policy. Its distinction lies in how the proposal view is produced: Graph-
RAG priors are compiled into a runtime access plan and a logical-position-preserving selected-KV
view, rather than being materialized as a shortened prompt or inferred solely within the drafting
mechanism.
7 LIMITATIONS
Our evaluation validates KAP through GRAPHSPEC, one concrete instantiation built with a Graph-
RAG knowledge-selection frontend and aVLLM serving backend. Therefore, our empirical evi-
dence does not exhaust the broader design space of runtime knowledge consumption. The reported
results are strongest for long-context QA workloads where graph-derived priors can be grounded in
evidence spans and realized as backend runtime objects. Other KAP instantiations may use differ-
ent frontends, plan compilers, access policies, verification mechanisms, or LLM serving backends,
and their effectiveness will depend on the quality of the knowledge priors, the compiler’s ability
to translate them into useful runtime access plans, and the backend’s ability to execute those plans
without excessive metadata, scheduling, or synchronization overhead. Future KAP instantiations
could realize runtime access plans through alternative sparse-access, tiered-KV, or disaggregated
execution mechanisms. Thus, our results establish KAP as a feasible serving paradigm and identify
a broader design space for future runtime knowledge-consumption systems.
8 CONCLUSION
We identified the knowledge selection–runtime consumption gap as an architectural mismatch in
knowledge-augmented LLM serving: knowledge-selection frontends produce high-value priors
about relevant knowledge, yet conventional LLM serving backends consume only the serialized
prompt and its full KV state. To bridge the gap, we introduced KAP, a paradigm for plan-driven
knowledge execution organized around a universal serving-time IR that compiles structured knowl-
edge priors into physical-access policies while preserving logical prompt semantics. GRAPHSPEC
provides a reference implementation with a Graph-RAG knowledge-selection frontend and aVLLM
serving backend. Our phase-boundary analysis and controlled long-context QA evaluation connect
knowledge selectivity, runtime consumption, and systems efficiency. Beyond GRAPHSPEC, KAP
provides a universal execution substrate for knowledge-selection–execution co-design across mul-
timodal, agentic, and deliberative long-context systems, where semantic knowledge selection and
physical context consumption must be optimized jointly.
REFERENCES
Reza Yazdani Aminabadi, Samyam Rajbhandari, Ammar Ahmad Awan, Cheng Li, Du Li, Elton
Zheng, Olatunji Ruwase, Shaden Smith, Minjia Zhang, Jeff Rasley, and Yuxiong He. Deepspeed-
inference: Enabling efficient inference of transformer models at unprecedented scale. InProceed-
ings of the International Conference for High Performance Computing, Networking, Storage and
Analysis, 2022. URLhttps://doi.org/10.1109/SC41404.2022.00051.
Sebastian Borgeaud, Arthur Mensch, Jordan Hoffmann, Trevor Cai, Eliza Rutherford, Katie Mil-
lican, George Bm Van Den Driessche, Jean-Baptiste Lespiau, Bogdan Damoc, Aidan Clark,
Diego De Las Casas, Aurelia Guy, Jacob Menick, Roman Ring, Tom Hennigan, Saffron Huang,
Loren Maggiore, Chris Jones, Albin Cassirer, Andy Brock, Michela Paganini, Geoffrey Irving,
Oriol Vinyals, Simon Osindero, Karen Simonyan, Jack Rae, Erich Elsen, and Laurent Sifre. Im-
proving language models by retrieving from trillions of tokens. InProceedings of the 39th In-
ternational Conference on Machine Learning, 2022. URLhttps://proceedings.mlr.
press/v162/borgeaud22a.html.
Tianle Cai, Yuhong Li, Zhengyang Geng, Hongwu Peng, Jason D. Lee, Deming Chen, and Tri
Dao. Medusa: Simple llm inference acceleration framework with multiple decoding heads. In
International Conference on Machine Learning, 2024. URLhttps://arxiv.org/abs/
2401.10774.
16

## PDF Page 17

Zefan Cai, Yichi Zhang, Bofei Gao, Yuliang Liu, Yucheng Li, Tianyu Liu, Keming Lu, Wayne
Xiong, Yue Dong, Junjie Hu, and Wen Xiao. Pyramidkv: Dynamic kv cache compression based
on pyramidal information funneling. InConference on Language Modeling, 2025. URLhttps:
//openreview.net/forum?id=ayi7qezU87.
Charlie Chen, Sebastian Borgeaud, Geoffrey Irving, Jean-Baptiste Lespiau, Laurent Sifre, and John
Jumper. Accelerating large language model decoding with speculative sampling.arXiv preprint
arXiv:2302.01318, 2023. URLhttps://arxiv.org/abs/2302.01318.
Guanzheng Chen, Qilong Feng, Jinjie Ni, Xin Li, and Michael Qizhe Shieh. RAPID: Long-context
inference with retrieval-augmented speculative decoding. InProceedings of the 42nd Interna-
tional Conference on Machine Learning, volume 267 ofProceedings of Machine Learning Re-
search, pp. 8093–8107. PMLR, 2025. URLhttps://proceedings.mlr.press/v267/
chen25s.html.
Tri Dao, Dan Fu, Stefano Ermon, Atri Rudra, and Christopher R´e. FlashAttention: Fast and memory-
efficient exact attention with IO-awareness. InAdvances in Neural Information Processing
Systems, 2022. URLhttps://proceedings.neurips.cc/paper_files/paper/
2022/hash/67d57c32e20fd0a7a302cb81d36e40d5-Abstract-Conference.
html.
Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt,
Dasha Metropolitansky, Robert Osazuwa Ness, and Jonathan Larson. From local to global: A
graph rag approach to query-focused summarization.arXiv preprint arXiv:2404.16130, 2024.
URLhttps://arxiv.org/abs/2404.16130.
Mostafa Elhoushi, Akshat Shrivastava, Diana Liskovich, Basil Hosmer, Bram Wasti, Liangzhen
Lai, Anas Mahmoud, Bilge Acun, Saurabh Agarwal, Ahmed Roman, Ahmed Aly, Beidi Chen,
and Carole-Jean Wu. Layerskip: Enabling early exit inference and self-speculative decoding. In
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics, 2024.
URLhttps://aclanthology.org/2024.acl-long.681/.
Yichao Fu, Peter Bailis, Ion Stoica, and Hao Zhang. Break the sequential dependency of llm infer-
ence using lookahead decoding. InProceedings of the 41st International Conference on Machine
Learning, 2024. URLhttps://arxiv.org/abs/2402.02057.
Kelvin Guu, Kenton Lee, Zora Tung, Panupong Pasupat, and Ming-Wei Chang. REALM: Retrieval-
augmented language model pre-training. InProceedings of the 37th International Conference on
Machine Learning, 2020. URLhttps://proceedings.mlr.press/v119/guu20a.
html.
Gautier Izacard and Edouard Grave. Leveraging passage retrieval with generative models for open
domain question answering. InProceedings of the 16th Conference of the European Chap-
ter of the Association for Computational Linguistics: Main V olume, 2021. URLhttps:
//aclanthology.org/2021.eacl-main.74/.
Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, and Lili Qiu. Llmlingua: Com-
pressing prompts for accelerated inference of large language models. InProceedings of the
2023 Conference on Empirical Methods in Natural Language Processing, 2023. URLhttps:
//aclanthology.org/2023.emnlp-main.825/.
Huiqiang Jiang, Yucheng Li, Chengruidong Zhang, Qianhui Wu, Xufang Luo, Surin Ahn, Zhenhua
Han, Amir H. Abdi, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, and Lili Qiu. Minference 1.0:
Accelerating pre-filling for long-context llms via dynamic sparse attention. InAdvances in Neural
Information Processing Systems, 2024a. URLhttps://arxiv.org/abs/2407.02490.
Huiqiang Jiang, Qianhui Wu, Xufang Luo, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, and Lili
Qiu. Longllmlingua: Accelerating and enhancing llms in long context scenarios via prompt com-
pression. InProceedings of the 62nd Annual Meeting of the Association for Computational Lin-
guistics, 2024b. URLhttps://aclanthology.org/2024.acl-long.91/.
17

## PDF Page 18

Wenqi Jiang, Suvinay Subramanian, Cat Graves, Gustavo Alonso, Amir Yazdanbakhsh, and Vidushi
Dadu. Rago: Systematic performance optimization for retrieval-augmented generation serving.
InProceedings of the 52nd Annual International Symposium on Computer Architecture, 2025.
URLhttps://arxiv.org/abs/2503.14649.
Bernal Jimenez Gutierrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, and Yu Su. Hipporag: Neu-
robiologically inspired long-term memory for large language models. InAdvances in Neural
Information Processing Systems, 2024. URLhttps://arxiv.org/abs/2405.14831.
Chao Jin, Zili Zhang, Xuanlin Jiang, Fangyue Liu, Xin Liu, Xuanzhe Liu, and Xin Jin.
Ragcache: Efficient knowledge caching for retrieval-augmented generation.arXiv preprint
arXiv:2404.12457, 2024. URLhttps://arxiv.org/abs/2404.12457.
Vladimir Karpukhin, Barlas O ˘guz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi
Chen, and Wen-tau Yih. Dense passage retrieval for open-domain question answering. InPro-
ceedings of the 2020 Conference on Empirical Methods in Natural Language Processing, 2020.
URLhttps://aclanthology.org/2020.emnlp-main.550/.
Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph
Gonzalez, Hao Zhang, and Ion Stoica. Efficient memory management for large language model
serving with pagedattention. InProceedings of the 29th Symposium on Operating Systems Prin-
ciples, 2023. URLhttps://doi.org/10.1145/3600006.3613165.
Yaniv Leviathan, Matan Kalman, and Yossi Matias. Fast inference from transformers via spec-
ulative decoding. InInternational Conference on Machine Learning, 2023. URLhttps:
//proceedings.mlr.press/v202/leviathan23a.html.
Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal,
Heinrich K ¨uttler, Mike Lewis, Wen-tau Yih, Tim Rockt ¨aschel, Sebastian Riedel, and Douwe
Kiela. Retrieval-augmented generation for knowledge-intensive nlp tasks. InAdvances in Neural
Information Processing Systems, 2020. URLhttps://arxiv.org/abs/2005.11401.
Yucheng Li, Bo Dong, Frank Guerin, and Chenghua Lin. Compressing context to enhance inference
efficiency of large language models. InProceedings of the 2023 Conference on Empirical Meth-
ods in Natural Language Processing, 2023. URLhttps://aclanthology.org/2023.
emnlp-main.391/.
Yuhong Li, Yingbing Huang, Bowen Yang, Bharat Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle
Cai, Patrick Lewis, and Deming Chen. Snapkv: Llm knows what you are looking for before
generation. InAdvances in Neural Information Processing Systems, 2024a. URLhttps://
arxiv.org/abs/2404.14469.
Yuhui Li, Fangyun Wei, Chao Zhang, and Hongyang Zhang. Eagle: Speculative sampling requires
rethinking feature uncertainty. InInternational Conference on Machine Learning, 2024b. URL
https://arxiv.org/abs/2401.15077.
Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, and
Percy Liang. Lost in the middle: How language models use long contexts.Transactions of
the Association for Computational Linguistics, 2024. URLhttps://aclanthology.org/
2024.tacl-1.9/.
Songshuo Lu, Hua Wang, Yutian Rong, Zhi Chen, and Yaohua Tang. Turborag: Accelerating
retrieval-augmented generation with precomputed kv caches for chunked text. InProceedings
of the 2025 Conference on Empirical Methods in Natural Language Processing, 2025. URL
https://aclanthology.org/2025.emnlp-main.334/.
Xupeng Miao, Gabriele Oliaro, Zhihao Zhang, Xinhao Cheng, Zeyu Wang, Zhengxin Zhang, Rae
Ying Yee Wong, Alan Zhu, Lijie Yang, Xiaoxiang Shi, Chunan Shi, Zhuoming Chen, Daiyaan Ar-
feen, Reyna Abhyankar, and Zhihao Jia. Specinfer: Accelerating generative large language model
serving with tree-based speculative inference and verification. InProceedings of the 29th ACM
International Conference on Architectural Support for Programming Languages and Operating
Systems, 2024. URLhttps://dl.acm.org/doi/10.1145/3620666.3651335.
18

## PDF Page 19