# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: PDF Page 1

## PDF Page 1

PTStore(Prefix Tensor Store): Distributed Prefix
Caching and Replication for High Throughput
Inference Serving
Meghana Maghyastha1, Robert Underwood2, Randal Burns1, and Bogdan
Nicolae2⋆
1 Johns Hopkins University, USA –{meghana,randal}@cs.jhu.edu
2 Argonne National Laboraotory, USA –{runderwood,bnicolae}@anl.gov
Abstract.Inspired by the design of client caching in Content Delivery
Networks (CDNs), PTStore distributes and replicates popular tensors
that form reusable KV cache prefixes, which are the main technique
used by state of art approaches to accelerate inferences. This reduces the
latency of accessing the KV cache and alleviates load imbalance caused
by a disproportionately large number of requests on servers containing
populartensors.Furthermore,thankstodecentralization,PTStoreallows
the expansion of the size of the KV cache for LLM inference by orders of
magnitude. As a result, PTStore can execute inferences on long passage
Q&A datasets 5-6 times more efficiently than current baselines, which
do not aggregate memory across different nodes and GPUs and therefore
require regenerating the KV cache.
Keywords:distributed tensor storage·prefix caching and replication·
inference serving·scalable AI
1 Introduction
Large Language Models (LLMs) and foundation models (FMs) have revolution-
ized multiple domains by enabling the understanding and generation of human-
like text with remarkable fluency and coherence. These models, trained on vast
amounts of data, can perform a wide range of tasks: literature search [20], knowl-
edge distillation [5], and complex reasoning [2]. They enable researchers to nav-
igate complex scientific problems more efficiently.
LLM/FM training and fine-tuning pose a significant challenge by requiring
tens of thousands of GPUs for several months at a time. Until recently, these
workloads were dominating HPC data centers. However, inference workloads
have become the dominant workloads nowadays. With an exploding number of
LLM users, serving inference requests both efficiently and at scale is emerging
as an even bigger challenge. For example, at Meta, inferences are the largest AI
workload running on their HPC data centers, accounting for 65% of the energy
consumption, compared to 35% consumption for pre-training [4].
⋆ Corresponding author.
arXiv:2607.22648v1  [cs.AI]  25 Jun 2026

## Evidence locator: PDF Page 8

## PDF Page 8

8 M. Maghyastha et al.
cations link with. It exposes a C++ low-level API to issue the longest common
prefix (LCP) queries (which transparently broadcast and reduce the results)
and to read/write subsets of tensors. The client is responsible for interpreting
the metadata, which indicates that the server is hosting the relevant prefixes as
a composition of tensors. Based on the metadata, it loads and stores the prefixes
using optimized RDMA communications that progress with multiple servers in
parallel. To this end, we leveraged an optimized HPC-oriented remote proce-
dure calls (RPCs) strategy based on bulk RDMA operations, as provided by the
Mochi [19] collection of composable building blocks. Specifically, we useThal-
lium, which is a C++ wrapper on top of Mercury and Argobots.

## Evidence locator: PDF Page 3

## PDF Page 3

PTStore 3
1. We present a series of high-level design principles for a distributed repository
that integrates the above ideas(§ 4).
2. We detailPTStore, a research prototype that illustrates the design principles
through a practical implementation.PTStoreenables high I/O throughput
under concurrency and integrates seamlessly with other LLM runtimes (§ 5).
3. We run extensive experiments at scale highlighting the significant reduction
in I/O overheads and overall end-to-end runtime compared with other state-
of-the-art approaches (§ 6).
2 Background
Fig.1: Overview of shared KV caching for LLM inference. Multiple transformer
blocks access the KV cache to incrementally store and reuse KV results. The
KV cache may be shared by multiple LLM instances to exploit shared prefixes.
Just like in the case of regular deep learning models, LLM inferences are
based onforward passesthat take a prompt (a sequence of tokens) as input and
generate a reply as output. The reply is the most likely sequence of tokens that
continues the prompt, similar in scope to sequence-to-sequence models. Unlike
regular deep learning models, the reply is constructed iteratively, one token at
a time. This happens in two phases. First, theprefillphase generates the first
output token. Then, the output token is appended to the prompt, and the next
output token is generated in thedecodestep. The decoding step is repeated until
a maximum number of output tokens is reached or a special termination token
(<EOS>) is generated. The initial prefill and the successive decode steps run each
in a separate forward pass.
A key component of typical transformer architectures is the attention layers,
often organized in multiple heads [22]. This is illustrated in Figure 1. Attention
layers capture positional correlations between pairs of tokens using multipli-
cations of multi-dimensional matrices (denoted Q, K, and V), which can take
advantage of the massive parallelism offered by GPUs. After the prefill phase,
the prompt has only changed by one appended token. Thus, during the decode

## Evidence locator: PDF Page 14

## PDF Page 14

14 M. Maghyastha et al.
12. Microsoft: DeepSpeed-FastGen: Introducing Mixtral, Phi-2, and Falcon support
with major performance and feature enhancements
13. Newman, M.E.: Power laws, pareto distributions and zipf’s law. Contemporary
physics46(5), 323–351 (2005)
14. Nie, X., Miao, X., Yang, Z., Cui, B.: Tsplit: Fine-grained gpu memory management
for efficient dnn training via tensor splitting. In: ICDE’22: The 2022 IEEE 38th
International Conference on Data Engineering. pp. 2615–2628 (2022)
15. Patel, P., Choukse, E., Zhang, C., Shah, A., Íñigo Goiri, Maleki, S., Bianchini, R.:
Splitwise: Efficient generative llm inference using phase splitting (2024)
16. Pope, R., Douglas, S., Chowdhery, A., Devlin, J., Bradbury, J., Heek, J., Xiao,
K., Agrawal, S., Dean, J.: Efficiently scaling transformer inference. Proceedings of
machine learning and systems5, 606–624 (2023)
17. Qin, R., Li, Z., He, W., Cui, J., Ren, F., Zhang, M., Wu, Y., Zheng, W., Xu,
X.: Mooncake: Trading more storage for less computation — a KVCache-centric
architecture for serving LLM chatbot. In: FAST’25: The 23rd USENIX Conference
on File and Storage Technologies. pp. 155–170. Santa Clara, USA (2025)
18. Rhu, M., Gimelshein, N., Clemons, J., Zulfiqar, A., Keckler, S.W.: vdnn: Virtu-
alized deep neural networks for scalable, memory-efficient neural network design
(2016)
19. Ross, R.B., Amvrosiadis, G., Carns, P., Cranor, C.D., Dorier, M., Harms, K.,
Ganger, G., Gibson, G., Gutierrez, S.K., Latham, R., Robey, B., Robinson, D.,
Settlemyer, B., Shipman, G., Snyder, S., Soumagne, J., Zheng, Q.: Mochi: Com-
posing Data Services for High-Performance Computing Environments. Journal of
Computer Science and Technology35(1), 121–144 (2020)
20. Tilwani, D., Saxena, Y., Mohammadi, A., Raff, E., Sheth, A., Parthasarathy, S.,
Gaur, M.: Reasons: A benchmark for retrieval and automated citations of scien-
tific sentences using public and proprietary llms. arXiv preprint arXiv:2405.02228
(2024)
21. Underwood, R., Madhyastha, M., Burns, R., Nicolae, B.: Evostore: Towards scal-
able storage of evolving learning models. In: HPDC’24: The 33nd International
Symposium on High-Performance Parallel and Distributed Computing. Pisa, Italy
(2024)
22. Vaswani,A.,Shazeer,N.,Parmar,N.,Uszkoreit,J.,Jones,L.,Gomez,A.N.,Kaiser,
L., Polosukhin, I.: Attention is all you need. In: NIPS’17: The 31st International
Conference on Neural Information Processing Systems. p. 6000–6010. Long Beach,
USA (2017)
23. Yang, Y., Yih, W.t., Meek, C.: Wikiqa: A challenge dataset for open-domain ques-
tion answering. In: Proceedings of the 2015 conference on empirical methods in
natural language processing. pp. 2013–2018 (2015)
24. Ye, Z.: flashinfer (2024)
25. Zheng, L., Yin, L., Xie, Z., Sun, C., Huang, J., Yu, C.H., Cao, S., Kozyrakis, C.,
Stoica, I., Gonzalez, J.E., Barrett, C., Sheng, Y.: Sglang: efficient execution of
structured language model programs. In: NIPS ’24: The 38th International Con-
ference on Neural Information Processing Systems (2024)
26. Zhong, Y., Liu, S., Chen, J., Hu, J., Zhu, Y., Liu, X., Jin, X., Zhang, H.: Distserve:
Disaggregating prefill and decoding for goodput-optimized large language model
serving (2024)
27.

## Evidence locator: PDF Page 4

## PDF Page 4

4 M. Maghyastha et al.
phase, it is enough to compute and incrementally store only the intermediate K
and V vectors of the new token (for each head and each layer), while reusing the
cached K and V vectors for all other tokens.
As more inference requests keep being served over time, it is often the case
that different inference requests, potentially belonging to different users, share
the same prefix (e.g., queries about the same text or conversations that build on
previous questions and answers) [9]. In this case, reusing the K and V vectors
corresponding to the longest common prefix between the prompt of a previous
request and the prompt of a new request accelerates the prefill similarly to how
reusing the K and V vectors accelerates the decode steps of the same request.
Thus, prefix caching is increasingly being employed as a core optimization to
improve the performance and scalability of inference serving.
3 Related Work
Inference frameworks such as vLLM [10] and DeepSpeed-MII [12] dramatically
decrease the time to first token (TTFT) and overall inference throughput thanks
to caching of intermediate results (K V vectors) of attention layer computations.
However, these techniques mostly focus on GPU memory and lack support for
aggregating distributed memory tiers. Multi-level caching using disaggregated
resource management is an aspect leveraged by systems like Splitwise [15], Dist-
Serve [26], and TetriInfer [6]. The latter separates the prefill and decode phases,
allowing their scheduling and batching on different compute nodes. SwapAdvi-
sor [7] uses genetic algorithms to control memory allocations and swap decisions.
vDNN [18] employs offloading and prefetching. TSPLIT [14] uses tensor splitting
to enable fine-grain control of the KV cache. vLLM [10] uses either recompute or
swap, implementing an all-or-nothing eviction policy configurable by the user.
On the other hand, STR [27] can dynamically combine both techniques. Most of
these approaches are complementary to our own work, focusing on KV caching
optimizations for independent queries. On the other hand, our approach focuses
ondistributed cachingof shared prefixes betweendifferentqueries.
Building on the concept of shared prefix management, systems like LMCache
[11], EvoStore [21], MoonCake [17] and SGLang [25] can be used to extend KV
caching beyond the boundaries of a single request. SGLang introduces Radix-
Attention, which treats the KV cache as a radix tree, allowing for automatic
and efficient sharing of overlapping prefixes between different prompts. While
RadixAttention excels at intra-node cache reuse, EvoStore specializes in captur-
ing evolving groups of tensors in a distributed fashion. While originally explored
for network architecture search, the same prefix sharing capabilities can be lever-
aged in the context of inference serving. Mooncake introduces a KVCache-centric
disaggregated architecture that utilizes a tiered storage hierarchy, spanning GPU
memory, local DRAM, and remote SSDs. Similarly, LMCache enables the shar-
ing of KV caches across different conversation sessions and even separate serv-
ing engine instances, significantly reducing redundant computations for popular
system prompts or long-context documents. However, these systems face critical

## Evidence locator: PDF Page 12

## PDF Page 12

12 M. Maghyastha et al.
(a) End-to-end comparison between the
approaches that support prefix caching.
(b) Breakdown of RDMA I/O overheads
vs. GPU compute
Fig.4: Inference using vLLM: Sequence length scalability (1k-8k tokens) mea-
sured as average time to first token (TTFT). Lower is better.
are less expensive and offset the benefit of reusing remote prefixes. Thus, for
small query lengths, vLLM’s baseline prefix caching is superior. However, start-
ing with 2k tokens, the opposite effect is visible:PTStoreoutperforms vLLM’s
prefix caching, and the difference between the two approaches keeps growing to
the point wherePTStoreis almost 2x faster for 8k tokens.
Also interesting to note is that the difference betweenPTStoreandEvoStore
depends on the sequence length. For 1k tokens, our approach is more than 2x
faster. For 8x tokens, our approach is 20% faster. As observed in Fig 4b, a zoom
on the breakdown of I/O vs. compute confirms again the advantage of our ap-
proach vs. EvoStore thanks to prefix replication. Furthermore, token distribution
also plays an important role, since the results in this case (SQUAD dataset) are
not consistent with the weak scalability experiment discussed in § 6.3 (WikiQA
dataset).
7 Conclusions
This paper introducedPTStore, a scalable distributed repository designed for
fine-grained prefix caching and replication to enhance LLM inference through-
put. By addressing the limitations of existing systems that lack support for
aggregating distributed memory tiers,PTStoreenables the efficient reuse of KV
cacheprefixesacrossmanyGPUsandcomputenodes.Ourdesignleveragesincre-
mental tensor storage to minimize redundancy, consolidated metadata for rapid
prefix queries, and an innovative replication strategy that optimizes local access
to popular “hot” prefixes. Experimental evaluations demonstrate thatPTStore
significantly reduces Time to First Token (TTFT) vs. state of art, up by an order
of magnitude, and remains scalable for a variable sequence length size. These
experiments prove its effectiveness in handling challenging high-throughput in-
ference serving at scale.

## Evidence locator: PDF Page 2

## PDF Page 2

2 M. Maghyastha et al.
LLM inferences are challenges because they involve two phases that use re-
sources in different ways: prefill and decode. During the prefill, the input prompt
is processed in parallel, which is compute-intensive and effectively utilizes the
GPU’s processing power to generate the first token. Then, successive tokens
are generated sequentially in auto-regressive fashion in decode steps. To avoid
recomputations associated with the attention mechanism (which captures cor-
relations between pairs of tokens, most of which do not change between decode
steps), a KV cache [16] is often employed to store the K and V vectors (reusable
intermediate attention results) of previously computed tokens. The KV cache
typically resides in the spare GPU memory not occupied by the model parame-
ters. The same principle can be applied across different inference requests that
share the same prefix. In this case, the K and V vectors of the longest common
prefix can be reused to accelerate the prefill by avoiding redundant attention
computations.
Limitations of state of art.Modern inference runtimes such as vLLM [10]
employ sophisticated KV cache techniques that allow non-contiguous alloca-
tion of blocks of GPU memory where the KV results of multiple requests that
are batched together and processed in parallel can be stored. To enable prefix
caching, a simple approach is to keep KV blocks in the KV cache for as long as
possible, subject to an eviction policy (e.g., apply LRU to KV blocks of requests
that finished). Then, if a new request arrives that shares a common prefix with
a previous request (either finished and not evicted yet or in progress), the blocks
corresponding to the longest common prefix can simply be reused (and marked
as such by increasing a reference counter). More sophisticated extensions to this
technique can be adopted where KV blocks are proactively flushed from GPUs
to the host memory (shared by all GPUs on the same compute node), which
extends the KV cache capacity of the individual GPUs and allows the reuse of
prefixes across requests served by different GPUs, at the expense of slower access.
Such an approach is implemented by runtimes such as LMCache [11]. However,
at scale, inference requests are served by a large number of GPUs distributed
over a large number of compute nodes. In this case, prefixes corresponding to
requests served by the GPUs on some nodes can be reused by the GPUs on other
nodes.

## Evidence locator: PDF Page 9

## PDF Page 9

PTStore 9
Workloads: LLM Inferences for Extractive Tasks.We use two question-
answer workloads that feature long inference queries. These workloads focus
on extractive tasks [1] in which the LLM needs to identify where in a given
document the answer to a specific question about the content of that document
is. The format of the inference query is a long prompt and short answer, which
emphasizes the prefill stage. For each text, there are multiple different questions,
resulting in large prefixes of the KV cache that can be reused across different
queries. Details of the datasets used for the two workloads are as follows:
1.WikiQA Dataset:The Microsoft WikiQA dataset [23] consists of 3000 ques-
tions in which each question is associated with a Wikipedia page that contains
the answer. The page lengths range from2,000to40,000tokens. We use this
dataset for scaling experiments because the pages used as context in the prefill
stage are long, which creates challenging long prefixes.
2.SQUAD Dataset:This dataset focuses on reading comprehension and in-
cludes 100,000 questions.