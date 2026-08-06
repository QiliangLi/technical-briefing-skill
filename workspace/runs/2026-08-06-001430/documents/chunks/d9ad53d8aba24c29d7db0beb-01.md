## PDF Page 1

GPU-Accelerated Multilevel Graph Clustering: A
Parallel Perspective on Louvain and Leiden
Michael S. Gilbert
Dept. of Computer Science and Engineering
The Pennsylvania State University
University Park, PA, USA
msg5334@psu.edu
Kamesh Madduri
Dept. of Computer Science and Engineering
The Pennsylvania State University
University Park, PA, USA
madduri@psu.edu
Abstract—The sequential Louvain and Leiden algorithms are
widely used techniques for modularity-optimizing clustering (or
community detection) in large graphs. We present pLouvain and
pLeiden, two new GPU parallelizations. pLouvain is based on the
Louvain+ extension. pLeiden is the first parallel implementation
to provably preserve all quality guarantees of sequential Leiden.
We achieve this through a novel spanning-tree-based refine-
ment approach. Both pLouvain and pLeiden use a lightweight
symmetry-breaking technique that emulates an ordered traversal
of vertices. For pLouvain, we develop an alternative iteration
strategy to rectify the weak internal cluster connectivity observed
in Louvain/Louvain+. Further, both pLouvain and pLeiden
optimize the LambdaCC objective function, a generalization of
modularity and the related Constant Potts model.
On a collection of 57 graphs from 10 families, our results show
that pLouvain and pLeiden achieve geometric mean speedups
of 3.1x and 8.8x, respectively, over the current fastest open-
source parallelizations of Louvain and Leiden. For the clusterings
generated, pLouvain yields the highest modularity scores on
nearly all tested graphs. The subroutines within these two
multilevel approaches could aid in the parallelization of other
Louvain-based techniques.
I. INTRODUCTION
Graph clustering is the task of identifying dense sub-
structures in graphs. The applications range from protein
function analysis to recommendation systems [1]. Heuristic
methods such as the Louvain [2] and Leiden [3] methods ex-
ploit the common hierarchical structure of real-world graphs.
Louvain and Leiden are both multilevel methods, a class
of heuristics used to solve a variety of problems involving
sparse systems [4]. Both methods have become foundational
techniques in graph analysis.
Due to their popularity and the need to process large
graphs, a plethora of prior work has probed their potential
for parallelism. Despite Louvain’s almost two-decade long
existence, one such recent work [5] greatly improved upon
the efficiency of other parallel Louvain methods, by a factor
of at least twenty times on multicore systems and even six
times versus cuGraph’s GPU Louvain. A corresponding GPU
implementation [6] failed to generate significant performance
improvements on many graphs over the multicore version.
Another recent GPU implementation [7] is slower still ac-
cording to our experiments. pLouvain, our GPU Louvain
implementation, is the first to achieve substantial speedups
versus the state-of-the-art multicore CPU implementations.
pLouvain is based on Louvain+ [8], a simple extension to
Louvain that further develops the multilevel aspect of Louvain
to deliver superior quality. A prior parallel adaptation [9] of
Louvain+ targeted multicore CPUs using an asynchronous
approach. We find Louvain+ is particularly beneficial for
a synchronous approach, which is necessitated by the high
degree of concurrency on modern GPUs. pLouvain further
includes several GPU-centric enhancements to thelocal move
and graph contraction phases of Louvain.
The Leiden method has seen fewer attempts at paralleliza-
tion. Among them, none provably offer the core guarantees
that define the Leiden method. We present a novel approach
to Leiden’s refinement scheme built upon spanning trees,
which provides all the core guarantees. Our proof of this
claim observes that the original Leiden refinement scheme
can generate a clustering if-and-only-if our parallelization
pLeidenR can generate it. Furthermore, we extend Leiden in
the vein of Louvain+ to create pLeiden+.
In summary, the contributions of this work are as follows:
1) On an NVIDIA B200 GPU and a 57-instance graph
dataset, pLouvain achieves a 3.1x geometric mean
speedup over the fastest competitor [6].
2) pLeiden provably ensures the quality guarantees of Lei-
den, and is 8.8x faster (geometric mean) than a prior
parallelization [10].
3) pLouvain and pLeiden+ consistently outperform other
approaches in terms of quality (modularity).
4) We present an efficient symmetry-breaking technique
based on the Jet [11] graph partitioner’safterburnerfilter.
5) Our graph contraction implementation is≥15x faster by
geometric mean than state-of-the-art competitors [6], [7].
6) We give an improved iteration scheme to mitigate Lou-
vain’s weak internal cluster connectivity problem [3].
II. PROBLEMDEFINITION
LetG= (V, E)represent an undirected graph,Vdenoting
the vertex set andEdenoting the edge set. An edge is defined
as a pair(u, v), with verticesu, v∈V. Both vertices and
edges may have associated weights, denotedw(v)andw(u, v),
respectively. While a general definition ofwmaps each object
toR, we consider only positive integer weighting functions
for simplicity. We definew(u, v) = 0⇐ ⇒(u, v)/∈E.
arXiv:2608.01503v1  [cs.DC]  2 Aug 2026

## PDF Page 2

Theneighborhoodof a vertexvis the set of adjacencies of
V, denoted asN(v). LetC= (C 1, C2, C3, ..., Cx)denote
a clustering, with each clusterC i ⊂V. Each cluster must
be pairwise disjoint, and their union equal toV. LetC[v]
denote the cluster to which vertexvbelongs. We define
w(X) = P
v∈X w(v)for any vertex setX, andw(X, Y) =P
(u,v)∈X×Y\X w(u, v)for any two sets of verticesX, Y.
Symmetry of undirected graphs impliesw(X, Y) =w(Y, X)
whenX∩Y=∅. A singleton cluster is a cluster containing
only one vertex, while an all-singleton clustering is a clustering
consisting of only singleton clusters. We define thecutsetof a
clusteringCas the subset ofEsuch that the two vertices of an
edge are in different clusters ofC. We define theenvelopeof
C(notatedenv(C)) as the subset ofEsuch that both vertices
are in the same cluster, withcutset(C)∪env(C) =E.
A. LambdaCC
Graph clustering is typically formulated as an optimization
task for one of many possible objective functions. Many of
the most significant objective functions are unified by the
lambdaCC objective [12]:
λCC(C) =
X
Ci∈C
X
u,v∈Ci
u̸=v
(w(u, v)−λw(u)w(v))
=
X
(u,v)∈env(C)
w(u, v)−λ
X
Ci∈C
X
u,v∈Ci
u̸=v
w(u)w(v)
(1)
It rewards edges within a cluster, while penalizing every
pair of vertices within each cluster.λbalances the influence
of the reward versus the penalty. It is in the range[0,1],
and may be a function of graph parameters such as|E|
or|V|. While the form presented in the original lambdaCC
paper [12] is a minimization objective, we use an equivalent
maximization objective. MaximizingλCC(C)onGis equiva-
lent to maximizing P
Ci∈C
P
u,v∈Ci
u̸=v
w′(u, v)on alambdaCC
signed graph. This is a fully connected, undirected graph with
edge weights given byw ′(u, v) =w(u, v)−λw(u)w(v).
w′(u, v)>0only if(u, v)∈E.
w′ is a useful concept for defining clustering properties
and objective deltas. We will often usew ′ with respect to
vertex setsX, Y:w ′(X, Y) =w(X, Y)−λw(X)w(Y\X).
2w′(v, C[v])gives the individual contribution of a vertexvto
the overall objective, while2w ′(v, Ci)−2w ′(v, C[v])gives
the objective delta related to moving vertexvto clusterC i.
With proper choice ofwandλ, one can obtain objectives
including modularity [13], the Constant-Potts Model (CPM)
[14], the Absolute-Potts Model (APM) [15], label propagation
(λ= 0) [16], sparsest-cut, cluster deletion, and connected
components (λ=ϵ). Specifically, for modularity,w(v) =
|N(v)|,(u, v)∈E⇐ ⇒w(u, v) = 1, andλ= γ
2|E| ;γis the
modularity resolution parameter. It is NP-Hard to optimize or
approximate this objective for generalwandλ[12], which
it inherits from modularity [17] (where these are only NP-
Complete) via a reduction.
B. Leiden Guarantees
Leiden provides six guarantees at different timescales, and
defines each relative to an objective function. References toγ
in each property’s name are related to the resolution parameter
of the Constant Potts Model, but each term can be equivalently
defined relative to the lambdaCC signed graph.
γ-separation: For any two clustersC x, Cy in a clustering,
w′(Cx, Cy)≤0.
γ-connectivity: Every clusterC x can be decomposed into a
binary tree of vertex-sets, such that every set is a subset of its
parent and the union of its children. Every leaf node represents
a unique vertex inC x. For every node with two children
X1, X2,w ′(X1, X2)≥0.
Subpartitionγ-density:γ-connectivity with one extra condi-
tion: every nodeXin the tree must satisfyw ′(X, Cx)≥0.
Node optimality: For every vertexvand clusterC x,
w′(v, C[v])≥w ′(v, Cx)andw ′(v, C[v])≥0.
Uniformγ-density: For every clusterC x and every subsetX
of that cluster,w ′(X, Cx)≥0.
Subset Optimality: For every pair of clustersC x, Cy and every
subsetXofC x,w ′(X, Cx)≥w ′(X, Cy)andw ′(X, Cx)≥0.
This concise restating of Leiden guarantees in lambdaCC
notation is a new contribution of this paper.
III. BACKGROUND
A. Multilevel Clustering Algorithms
Heuristic algorithms are the predominant approach for opti-
mizing lambdaCC-related objectives on real-world graph data,
due to its computational hardness. The Louvain algorithm [2]
is one of the most widely used algorithms, as it produces
high-quality clusterings in linear time. Louvain exploits the
common hierarchical structure of clusters in real-world net-
works via a a multilevel algorithm. First, alocal move heuristic
greedily optimizes an initial all-singleton clustering. This local
move heuristic is computationally equivalent to running the
label propagation algorithm [16] on the lambdaCC signed
graph, up to the choice of initial clustering state and vertex
traversal order. Second, it generates a coarsened graph from the
optimized clustering, such that each coarse vertex represents
an entire cluster. Each coarse vertexxcorresponding to cluster
Cx has weight equal tow(C x). Letx, yrepresent two coarse
vertices corresponding to clustersC x, Cy, respectively. There
are edges(x, y)and(y, x)in the coarse graph with weight
w(Cx, Cy), if and only ifw(C x, Cy)>0. This process
terminates when the clustering isγ-separated. Every clustering
on a coarsened graph induces a clustering on the input graph;
the objective on each coarsened graph is monotonic with
respect to the objective on the input graph, and the difference
is a constant. The original Louvain algorithm avoids a delta
between coarse and input objectives by using weighted self-
loops for every coarse vertex. This is unnecessary; instead, one
may sum the constant objective deltas between each successive
coarse graph.
One notable extension of Louvain, Louvain+ [8], adds an
uncoarseningphase, which applies the local move heuristic

## PDF Page 3

again to the result of each recursive call to further improve
the clustering. Refer to Algorithm 1 for an overview. VieClus
[18], a memetic algorithm for clustering, and a multicore CPU
parallel work [9] implement this innovation. When discussing
our implementation of Louvain+, we refer to thecoarsening
phase, which is everything that occurs prior to the uncoarsen-
ing phase. Separately, an analysis [19] of multilevel clustering
variants verified the importance of local moving during the
uncoarsening.
The Leiden algorithm [3] is another improvement upon
Louvain, motivated by the observation that Louvain generates
poorly internally-connected clusters. To address this, it applies
a refinement heuristic after the local move heuristic. This
refinement is similar tosolution-based coarseningschemes
from graph partitioning [20]: it exclusively generates sub-
clusters of those given by the local move heuristic. The output
of the refinement is used for the graph coarsening operation,
and the output of the local move heuristic is used to initialize
the clustering of the coarse graph, instead of a singleton
clustering. Leiden can be fed any input clustering as a starting
point; by feeding itself its own output, it can beiterated. This
is also true of Louvain, but the Leiden authors claim it rarely
benefits from more than one additional iteration [3]. We will
later demonstrate an alternative way to iterate Louvain that is
superior to the one considered by the Leiden authors.
After every iteration, Leiden guaranteesγ-separability and
γ-connectivity of the clustering. After a stable iteration (one
which does not improve the clustering), Leiden guarantees
subpartitionγ-density and node optimality. It guarantees
uniformγ-density and subset optimality asymptotically, via
randomization.
Algorithm 1Overview of the Louvain and Louvain+ algo-
rithms.
Input:UndirectedG(V, E) =G 0.n=|V|.
Output:VectorC out mappingVto{1,2, ..., c}for some
integerc≤ |V|.
1:l←0
2: whileTRUEdo
3: Cl ←SINGLETONCLUSTERING(V l)
4: Cl ←LOCALMOVEPASSES(G l,C l)
5: if|C l|=|V l|then
6: Break out of while loop
7: Gl+1 ←GRAPHCONTRACTION(G l,C l)
8: l←l+ 1
9: whilel−1≥0do
10: l←l−1
11: Cl ←PROJECTCLUSTER(C l, Cl+1)
12: Cl ←LOCALMOVEPASSES(G l,C l)▷only Louvain+
13:C out ←C 0
B. Parallel Implementations
Most research on parallel Louvain methods focuses on
the local move heuristic. The local move heuristic presents
two primary challenges [21] for parallel implementations that
motivate a variety of approaches. These challenges are: 1) race
conditions due to vertex state updates, and 2) destructive inter-
actions within a set of simultaneous vertex moves that reduce
its cumulative objective delta. Synchronous approaches avoid
race conditions, but require symmetry-breaking techniques to
mitigate destructive interactions. Bulk synchronous parallel
(BSP) [22] approaches process all vertices simultaneously and
do not update vertex states until after processing every vertex.
Such approaches use explicit symmetry-breaking heuristics,
like the minimum label heuristic (MLH) [5], [6], [23]. Some
synchronous approaches [7], [21], [24], [25] use batches;
vertices within a batch are concurrently processed, one batch at
a time1, and apply state updates between batches. Techniques
for batching include distance-1 coloring [25], distance-2 col-
oring [21], degree-based bucketing [7], and partitioning [24].
Batches provide an implicit form of symmetry-breaking, but
limit the potential degree of parallelism. The different batching
tactics and explicit symmetry-breaking heuristics address the
problem of destructive interactions to varying degrees.
A third approach is asynchronous parallel [5], [6], [9],
wherein vertex states are updated as they are processed. Prior
work has shown that asynchronous algorithms converge more
quickly than synchronous algorithms [9], presuming a CPU-
level degree of concurrency. Unfortunately, asynchronous al-
gorithms are subject to race conditions, which lead to quality
losses and slower convergence with increasing concurrency.
They are therefore ill-suited to GPUs, and our evaluation of
such approaches in the empirical results section shows this.
Several works [6], [7], [23], [24], [26] have examined
parallel Louvain for GPUs. Each of these approaches utilizes
one of the aforementioned schemes. We detail the two most
efficient approaches of these, v-Louvain [6] and GALA [7]. v-
Louvain utilizes a asynchronous approach for the local move
heuristic, while GALA uses a batch-synchronous approach.
Both group vertices into buckets by their degree, to enable
processing with specialized kernels. v-Louvain uses two buck-
ets, and processes low-degree vertices with a single thread,
and high-degree vertices with entire thread blocks. GALA
uses more buckets with greater granularity; its kernels are
more specialized towards each bucket in terms of thread-
block size, warp-level primitive usage, and shared vs global
memory usage. For symmetry breaking, v-Louvain integrates
the MLH in every fourth pass, whereas GALA relies only on
batching. GALA additionally implements a pruning scheme to
reduce the total amount of work in each pass. Regarding graph
contraction, both first gather vertices by cluster id (GALA does
not mention this in their paper, but we confirm via inspection
of their code). We discuss the detriments of this preprocessing
in section IV-B.
The Leiden algorithm is significantly more challenging
to implement in parallel, due to its quality guarantees. We
highlight that no existing parallel implementation provides
each of the original quality guarantees. GVE-Leiden’s [10]
parallel version of Leiden’s refinement has race conditions
1In [24], multiple batches are concurrently processed, one batch per GPU

## PDF Page 4

which lead to violations of the guarantees. A prior implemen-
tation (NetworKit Leiden) [27] locks entire clusters to avoid
such a scenario, which severely restricts the attainable degree
of parallelism; the author of that work stated that speedups
beyond 32 threads on a 128-core system were negligible. Fur-
thermore, its refinement implementation lacks randomization
of the cluster joining operation, so it fails to guarantee subset
optimality and uniformγ-density asymptotically. While GVE-
Leiden’s authors observed that NetworKit Leiden produced
disconnected clusters [10], this was fixed in v11.2.
IV. PARALLELLOUVAIN
We utilize the modified Louvain structure explored in [8],
which we outline in Algorithm 1. Line 12 represents the
primary distinction between Louvain+ and Louvain. There are
two reasons we choose this approach:
1) The quality as measured by modularity is improved
versus standard Louvain [8], [9].
2) The local move heuristic is cheaper during the uncoars-
ening phase. There are far fewer clusters to consider, and
a smaller proportion of vertices are not node optimal.
There is an opportunity to replace some of the expensive
passes of the local move heuristic during the coarsening with
cheaper passes during the uncoarsening. This is especially
important for synchronous approaches such as the one we out-
line, which require more passes to converge than asynchronous
approaches favored by CPU-oriented algorithms. Each of our
algorithms assumes the graph is stored in memory in the
compressed sparse row (CSR) format.
A. Local Move Heuristic
We implement the local moving phase of the Louvain
algorithm with a bulk-synchronous design. See Algorithm 2
for a sketch of our approach.
1) Afterburner Filter:We adapt the Jet label propagation
algorithm [11] to consider lambdaCC objectives. It integrates
a symmetry-breaking technique called theafterburner filter
(see algorithm 3), which deprioritizes destructive interactions
between adjacent vertices and prioritizes constructive inter-
actions. In comparison, the simpler MLH entirely forbids
simultaneous moves which destructively interact via their ad-
jacencies. By considering constructive interactions, the after-
burner filter can move vertices which are in a locally-optimal
cluster (governed by theϕparameter), for potential global
objective improvements. Most significantly, as our empirical
evaluation shows, this enables some basic simulated annealing
techniques as in [28] and [29]. The afterburner filter does
not consider interactions between non-adjacent vertices, a
common limitation of the symmetry-breaking heuristics of
which we are aware.
The ordering referenced on line 5 is a function of the
precomputed objective deltas for each candidate move: greater
objective deltas are earlier in the ordering. If two candidate
moves have objective deltas that differ by less than someϵ
(which we set as 0.1), then tiebreaking is performed by a
hash function of the vertex ids. The loop beginning on line 4
specifies a thread-block level reduction on theδ v variable.
Algorithm 2pLouvain: Parallel local move heuristic.
Input:G= (V, E). VectorC in. Temperature parameterϕ.
Output:VectorC out.
1:C←C in,C out ←C in
2: ifCis an all-singleton clusteringthen
3: DS←G ▷ DStracksw(v, u)
4: else
5: DS←ENUMERATE(G, C)▷ DStracksw(v, C x)
6: fori= 1, . . . ,limitdo
7: L←[]▷empty movelist
8: D←[null]*|V|▷destination clusters
9: forv∈Vin parallel do
10: D[v]←argmaxC\C[v]ofw ′(v, Ci)
11: ifw ′(v, C[v])<0andw ′(v, D[v])<0then
12: D[v]← ∅▷new singleton cluster
13: ifw ′(v, D[v])≥(1−ϕ i)w′(v, C[v])then
14: appendvtoL
15: L←AFTERBURNERFILTER(G, L, C, D)
16: if|L|>0.05|V|andCnot an all-singleton clustering
then
17: DS←UPDATEAFFECTED(G, L, C, D)
18: else
19: DS←RECOMPUTEAFFECTED(G, L, C, D)
20: C←UPDATE(L, C, D)▷ApplyDforL
21: ifλCC(C)> λCC(C out)then
22: Cout ←C
Algorithm 3The “afterburner” filter used in local move.
Input:G= (V, E). Candidate movesL. Current clustering
C. Destination clustersD.
Output:Filtered movesM.
1:M←[]▷empty movelist
2: forv∈Lin parallel do
3: δv ←w ′(v, D[v])−w ′(v, C[v])▷Precomputed
4: foru∈N(v)in parallel do
5: ifu∈Landord(u)< ord(v)then
6: ifC[v] =C[u]then
7: δv ←δ v +w ′(u, v)
8: else ifD[v] =C[u]then
9: δv ←δ v −w ′(u, v)
10: ifC[v] =D[u]then
11: δv ←δ v −w ′(u, v)
12: else ifD[v] =D[u]then
13: δv ←δ v +w ′(u, v)
14: ifδ v ≥0then
15: appendvtoM
2) Kernel Fission:The most costly subtask of the local
move heuristic is the enumeration of adjacent clusters and
respectivew(v, C i)for each vertex, followed closely by the
argmax operation to select the best destination cluster. The

## PDF Page 5

standard approach across several recent works [6], [7] fuses
these into one kernel. We differ from these other works by
employing kernel fission [30] to create separate kernels for
the enumeration and argmax operations. This enables further
tuning and optimizations on a per kernel basis, which are
incompatible with a single fused kernel. There is a small
tradeoff of one additional sequential read from global memory
in the argmax kernel.
3) Enumeration Kernel:As in [6], we maintain a hash
table in global memory for each vertex, with size given by
its degree. The total capacity among all hash tables is equal
to|E|; similar allocations are common for graph partitioning
[11], [31]. We designate a special memory location for each
vertex to accumulate its connection strength to its current
cluster. This enables the use of a reduction operation to
accumulate this value, in place of high-contention atomic
operations. For vertices within a viable range of degrees,
we build the hashtables in shared-memory before copying
them to global memory; all other vertices use global memory
exclusively.
After each pass, we recompute the hash tables of each
moved vertex and its adjacencies. If the number of vertex
moves is small (less than 3-5% of all vertices), it is beneficial
to instead modify the hash tables of the adjacent vertices
directly in global memory. This specialized kernel can’t be
fused with the argmax kernel. It is most relevant to the
uncoarsening phase, which usually sees only a small fraction
of all vertices undergo a move.
For the first pass of the local move heuristic during the
coarsening, the adjacent clusters for each vertex will be exactly
equal to its adjacent vertices. Thus, in the first pass only, we
skip the enumeration kernel and pass the input graph directly
to the argmax kernel.
B. Graph Contraction
We adopt an approach to parallel graph contraction defined
in a recent graph partitioning work [11]. This approach is
given in Algorithm 4. The central idea is to create hash
tables for each coarse vertex, and then for each edge in the
input graph, insert the corresponding coarse edge into the
appropriate hash table. Edges inducing self-loops in the coarse
graph are ignored, as cluster sizes are tracked separately. The
sum of degrees of the constituent input vertices for each coarse
vertex gives a loose upper bound for its hash table size. For
typical input graphs, the number of insertions into each hash
table is at least one order of magnitude smaller than this upper
bound. This upper bound tightens with each coarsening phase.
To extract the edges ofG c from the hash tables, we perform
a single stream-compaction operation on the unified hash table
arrays to select non-null entries. Before this, we need to count
the number of such entries to allocate memory forG c, and
on a per-coarse-vertex basis to compute the coarse offsets.
We integrate the counting of unique entries into the hashtable
insertion operation.
In contrast to v-Louvain [6] and GALA [7], we don’t
gather fine vertices into groups by coarse vertex membership.
Gathering vertices in this way is common for sequential
contraction schemes, where it enables the stream-compaction
operation to occur concurrently with the hashtable operations.
In a non-sequential context, this optimization isn’t possible.
The prior GPU works allocate work units per coarse vertex;
a work unit can be a single thread, a warp, a thread-block,
or a full thread-grid, depending on the sum of input degrees.
Compared to our approach, in which we allocate work units
per fine vertex, this exacerbates the load imbalance between
work units, and reduces the potential for latency hiding.
Algorithm 4The parallel graph contraction algorithm.
Input:G= (V, E). The cluster arrayC. Cluster countn c.
Output:G c = (V c, Ec)
1:bound←[0]∗(n c + 1)
2: forv∈Vin parallel do
3: bound[C[v]]←bound[C[v]] +|N(v)|
4:offset←EXCLUSIVEPREFIXSUM(bound)
5:H k ←[null]∗ |E|▷per-vertex hash tables
6:H v ←[0]∗ |E|
7: forv∈Vin parallel do
8: hk ←H key[offset[C[v]]..offset[C[v] + 1]]
9: hv ←H val[offset[C[v]]..offset[C[v] + 1]]
10: foru∈N(v)in parallel do
11: ifC[v]̸=C[u]then
12: i←INSERTORLOOKUP(h k,C[u])
13: hv[i]←h v[i]+w(u, v)
14:G c ←STREAMCOMPACTION(H k, Hv)
C. Miscellaneous Detail
1) Memory Reuse:In order to reduce the number of
large memory allocations and deallocations, we reuse memory
where possible. The memory for the hash tables needed for the
local move heuristic is preserved and reused for all subsequent
calls, as the coarser graphs will never need more memory for
this than the input graph. Additionally, we reuse this same
memory for the hash tables in the graph contraction operation.
The only memory which must be allocated dynamically is for
storing each coarse graph; all other auxiliary memory can be
allocated in advance.
2) Degree-Specialized Kernels:Like v-Louvain [6] and
GALA [7], we group vertices into buckets by degree for
processing by kernels tuned to each bucket. We use three
buckets, for low, medium, and high degree vertices. We spe-
cialize the enumeration, argmax, afterburner, and contraction
kernels, with the argmax and afterburner kernels using higher
thresholds for each bucket than the other two.
D. Note on Iterating Louvain+
We detail a new method for iterating Louvain, using Lou-
vain+. The old method, detailed by the Leiden authors [3],
iterates Louvain by feeding it an input clustering, which in turn
is fed into the local move heuristic in place of an all-singleton
clustering. VieClus [18] implies an alternate approach, but we
do not believe this was explicitly detailed. In that work, their

## PDF Page 6