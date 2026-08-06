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

“Multi-level Recombination Operator” combines two cluster-
ingsB 1 andB 2, using a constrained version of Louvain+. Its
local move heuristic begins from an all-singleton clustering,
but it may only create clustersC x that satisfyB 1[u] =B 1[v]
andB 2[u] =B 2[v]for every vertex pairu, v∈C x. An
uncoarsening phase allows for inter-constraint-cluster vertex
movements.
Our new iteration method is similar, with one constraint
clustering in place of two. It differs in that the constraint
clustering is not further used to give an initial clustering of
the coarsest graph. The new method is conceptually similar
to iterated multilevel graph partitioning methods [20]. While
the Leiden paper showed that iterating Louvain in the former
way worsens the internal connectivity of clusters, our new
approach guarantees connected clusters in stable iterations.
In a sequential setting, the coarsening phase alone always
generates a clustering at least as good as the constraint. This is
due to the coarsening termination condition: any two clusters
in the coarsening output satisfyw ′(Cx, Cy)≤0, unlessC x
andC y are in different constraint clusters.
V. PARALLELMETHOD FORLEIDENGUARANTEES
Algorithm 5 gives an overview of pLeiden, our novel Leiden
parallelization, and can be compared to Algorithm 1.
Algorithm 5pLeiden: Overview of our parallel algorithm.
Input:G= (V, E). VectorC in.
Output:VectorC out.
1:l←0, C 0 ←C in
2: whileTRUEdo
3: δ←λCC(C l)
4: Cl ←LOCALMOVEPASSES(G l,C l)
5: ifλCC(C l) =δthen
6: Cl ←LOCALMOVEALT(G, C l)
7: if|C l|=|V l|then
8: Break out of while loop
9: B←PLEIDENR(G l, Cl)
10: Gl+1 ←GRAPHCONTRACTION(G l,B)
11: Cl+1 ←DOWNSAMPLE(G l+1, Cl)
12: l←l+ 1
13: whilel−1≥0do
14: l←l−1
15: Cl ←PROJECTCLUSTER(C l, Cl+1)
16:C out ←C 0
A. Parallel Local Move Phase
The only necessary trait of the local move heuristic for
Leiden’s proofs [3] is that it return an improved clustering
unless the input is node optimal. Our standard parallel im-
plementation cannot do this, so we provide an alternate one
that does. Essentially, we require a stricter version of the
afterburner filter. First, we gather all non-node-optimal vertices
in some arbitrary order, and determine their ideal clusters. Our
stricter afterburner considers all prior vertices in the order,
not just those immediately adjacent, which is necessary for
lambdaCC objectives. We determine the prefix of the order
which maximizes the change in the objective function, and
commit this prefix. This maximizing prefix is non-empty if
there are any non-node-optimal vertices.
This is possible inO(n)total work with some complex
usage of prefix sums, while the obviousO(n 2)approach
is much simpler. We only invoke this alternate local move
implementation when our standard local move implementation
fails to improve the clustering (see line 6 of Algorithm
5). In our testing, the number of non-node-optimal vertices
when this occurs was rarely more than 40. Thus, the simpler
O(n2)approach is likely faster than the more complex, higher
overheadO(n)approach.
B. Parallel Refinement Heuristic
1) Original Leiden Refinement Heuristic:We hereafter
refer to Leiden’s refinement heuristic as LeidenR; note that
the Leiden authors denote it REFINEPARTITION. LeidenR is
based upon cluster joining [19]; it performs a sequence of
non-negative moves such that the size of its clusters (except
for singleton clusters) strictly increase. All optimal clusterings
are reachable in this manner [3]. Beginning from a singleton
clustering, LeidenR visits each vertex in a random order. If
it visits a vertex in a singleton cluster, it randomly chooses
to move it to an adjacent cluster such that the objective does
not decrease (γ-connectivity). It can also randomly choose not
to move the vertex. Upon visiting a vertex not in a singleton
cluster, it skips it.
LeidenR also utilizes a constraint clusteringB, such that
vertices can only move to clusters in their same constraint
cluster. Additionally, LeidenR ignores vertices not satisfying
w′(u, B[u])≥0, and also does not move vertices to clusters
not satisfyingw ′(Cx, B[Cx])≥0. This is necessary for
subpartitionγ-density in stable iterations.
2) Our Parallel LeidenR Algorithm (pLeidenR):Our paral-
lel algorithm (algorithm 6) first generates a forest of spanning
trees; each tree induces a cluster. It then gathers the vertices of
each spanning tree and sorts them by an ordering. Once sorted,
we can ensure that the induced clusters satisfy LeidenR’s
aforementioned criteria.
To generate the spanning forest, we select a random edge
(u, v)fromu∈N(v)∪vfor each vertexvsuch thatB[u] =
B[v],w ′(u, v)≥0, andw ′(u, B[u])≥0. We then compute
a random ordering function mapping each vertex to[0, K)
for some large integerK≫ |V|. We subsample the edges
going from a higher order vertex to a lower order vertex, to
eliminate cycles. For vertices in singleton trees, we modify
their ordering byf new(v) = 2K−f old(v). This eliminates
most of the singleton trees, except those vertices that selected
self-loops. Each tree has expected logarithmic depth due to the
random ordering function. We can extract them efficiently in
parallel via pointer-chasing. Sorting the vertices of each tree
uses the same ordering function, so that each prefix of a sorted
tree represents a connected tree.
Lemma 1.pLeidenR can generate a clustering only if LeidenR
can generate it.

## PDF Page 7

Proof.Assume that LeidenR visits the verticesv∈Vin
increasing order off(v), and moves eachvto the cluster
Cx containing the lesserf-valued vertices in the same tree as
v. COMMITWELLCONNECTEDPREFIXESsimulates LeidenR
under this assumption, verifying if LeidenR could perform
each move. More specifically, it verifiesw ′(v, Cx)≥0and
w′(Cx, B[Cx])≥0. This requires two separate prefix sums,
one overw(C x)and one overw(C x, B[Cx]). The longest
prefix of valid moves of each tree is committed as a cluster;
the remaining suffix is broken into singleton clusters (assume
that LeidenR chooses not to move the suffix vertices). Thus,
by construction of the algorithm, the lemma is true.
Lemma 2.pLeidenR can generate a clustering if LeidenR can
generate it.
Proof.Consider the LeidenR algorithm. For every vertexv,
setf(v) =i, wherevis theith vertex LeidenR will visit.
When LeidenR adds a vertexvto a clusterX, choose an edge
satisfyingw ′(u, v)≥0withu∈X, and setH[v] = (u, v).
Such an edge must exist, otherwise movingvtoXhas a
negative effect on the objective. Vertexuis either already
visited and thereforef(u)< f(v), or will not be in a
singleton-cluster when it is visited. When LeidenR visitsu
later, setH[v] = (u, u)andf(u) = 0. This ensures all chosen
edges satisfyf(u)< f(v). By giving pLeidenR thisHand
f, it will output the clustering generated by LeidenR. Observe
that pLeidenR may select thisHandfrandomly with a non-
zero probability.
Theorem 1.pLeiden provides all of the original Leiden
algorithm’s guarantees.
Proof.pLeidenR can generate a clustering if and only if
LeidenR can generate it, thus they are equivalent up to their
probabilities to generate a given clustering. As the original
proofs of Leiden’s guarantees [3] are independent of the
probability distribution over possible clusterings, replacing
LeidenR with pLeidenR preserves their correctness. As we
achieve the necessary traits of the local move heuristic as
discussed in section V-A, the theorem is true.
Algorithm 6pLeidenR: The parallel refinement algorithm of
pLeiden.
Input:G= (V, E). Constraint ClusteringB.seed.
Output:VectorC out.
1:H←[null]× |V|
2:U← {u|u∈V∧w ′(u, B[u])≥0}
3: forv∈Uin parallel do
4: Av ← {(u, v)|u∈(N(v)∪v)∩U∧B[u] =B[v]∧
w′(u, v)≥0}
5: H[v]←CHOOSERANDOM(A v)
6:f←RANDOMIZEDORDERINGFUNCTION(seed)
7:T←EXTRACTTREES(H, f)
8:T←SERIALIZEANDSORT(T, f)
9:C out ←COMMITWELLCONNECTEDPREFIXES(T)
VI. EMPIRICALRESULTS
A. Comparisons
We compare pLouvain and pLeiden to v-Louvain (com-
mit 91f2803) [6], GALA (commit e43bdea) [7], cuGraph’s
Louvain [32] (v26.02), cuGraph’s Leiden [33] (v26.02),
GVE-Louvain (commit e228af3) [5], GVE-Leiden (commit
f741a40) [10], and Networkit Louvain (v11.1.post1) and Lei-
den (v11.2) [27]. We are unable to compare to Parallel Corre-
lation Clustering [9], as their code could not build successfully.
GVE-Louvain outperforms all CPU and GPU parallel Louvain
implementations to which its authors compared. We consider
this test set to be representative of the current state-of-the-art in
shared-memory parallel Louvain and Leiden implementations.
We add an uncoarsening phase to pLeiden to produce
pLeiden+. Due to the uncoarsening phase, pLeiden+ has no
per-iteration guarantees;γ-separation andγ-connectivity are
instead guaranteed only in stable iterations.
B. Test Systems
We assess our implementations, as well as v-Louvain,
GALA, and cuGraph, on an Nvidia B200 GPU with 180GB of
VRAM. We assess GVE-Louvain/Leiden, and NetworKit Lou-
vain/Leiden on an AMD Ryzen 9950x3D CPU, and run each
with 32 threads. This system has 96GB of 6GT/s DDR5 RAM
in a dual-channel configuration. We compile GPU programs
with Cuda Toolkit version 12.8 (driver version 580.95.05) and
CPU programs with g++ 13.3.0.
C. Test Data and Configuration
We use a set of graphs [34] previously used to evalu-
ate graph partitioning methods on GPUs [11]. This test set
overlaps with the test sets of competitor works [6], [7],
[10], but with some additional preprocessing. Each graph is
symmetrized, with all edge weights set to 1, and only the
largest connected components retained. We run each program
on each graph 21 times (except for cugraph which we run 5
times), and collect the median clustering time and modularity
result. The synchronous implementations also lead to low
runtime variance. We measure quality in terms of modularity
as it is the most common objective function used to evaluate
Louvain and Leiden implementations, and the other programs
only have the ability to optimize for modularity. For our
programs, we compute the standard deviation in modularity,
and find it to be 0.0002 on average.
For pLouvain, pLeiden, and pLeiden+, we set the local
move heuristic pass limit to 6, with the temperature parameter
ϕ= 0.75for the first four passes andϕ= 0.25for the last
two. We leave all settings as default for the other programs,
except for NetworKit Leiden where we set the Leiden run
count to 1 for consistency with other Leiden implementations.
We use the modularity numbers given by the output of each
program where applicable and accurate (Our Louvain/Leiden,
v-Louvain, GVE-Louvain/Leiden, cugraph Louvain, GALA),
or compute the modularity values where none are given (Net-
worKit Louvain/Leiden) or are incorrect (cuGraph Leiden).

## PDF Page 8

TABLE I
A COLLECTION OF UNDIRECTED GRAPHS USED FOR PERFORMANCE
EVALUATION. WE PREPROCESS THE GRAPHS TO EXTRACT THE LARGEST
CONNECTED COMPONENT. THE NUMBER OF VERTICES(n),EDGES(m),
THE RATIO OF MAX VERTEX DEGREE(∆)TO AVERAGE DEGREE AFTER
PREPROCESSING(ROUNDED TO NEAREST INTEGER),AND THE
MODULARITYQWITH A BASELINE SEQUENTIALLOUVAIN+
IMPLEMENTATION ARE GIVEN. (‡: USE A“SYNCHRONOUS”VERSION.)
Graphn(×10 6)m(×10 6)∆/(2m/n)Q
grid8.0 16.0 1 0.9903
cube8.0 23.9 1 0.9611
delaunay238.4 25.2 5 0.9894
bubbles0018.3 27.5 1 0.9938
bubbles1019.5 29.2 1 0.9938
rgg224.2 30.4 2 0.9866
bubbles2021.2 31.8 1 0.9940
delaunay2416.8 50.3 4 0.9915
rgg238.4 63.5 3 0.9883
rgg2416.8 132.6 3 0.9899
ppa0.6 21.2 44 0.7424
cage155.2 47.0 3 0.8944
kmerV2a53.5 57.1 18 0.9914 ‡
kmerU1a64.7 66.4 17 0.9894 ‡
kmerP1a138.9 148.5 19 0.9761 ‡
kmerA2a170.4 179.9 19 0.9755 ‡
kmerV1r214.0 232.7 4 0.9537 ‡
feRotor0.1 0.7 9 0.9090
afShell1.5 25.6 1 0.8879
Hook14981.5 29.7 2 0.8939
Geo14381.4 30.9 1 0.8738
Serena1.4 31.6 5 0.8780
audikw0.9 38.4 2 0.9125
channel0504.8 42.7 1 0.8515
LongCoup1.5 42.8 13 0.8640
dielFilterV31.1 44.1 3 0.9260
MLGeer1.5 54.7 1 0.8189
Flan15651.6 57.9 1 0.8418
Bump29112.9 62.4 4 0.8573
CubeCoup2.2 62.5 1 0.8509
HV15R2.0 162.4 3 0.8359
Queen41474.1 162.7 1 0.7276
nlpkkt1203.5 46.7 1 0.9247
nlpkkt1608.3 110.6 1 0.9368
nlpkkt20016.2 216.0 1 0.9442
roadUSA23.9 28.9 4 0.9982
europeOsm50.9 54.1 6 0.9990
circuit5M5.6 27.0 132 864 0.8174 ‡
vasStokes2M2.1 48.4 29 0.8914
vasStokes4M4.3 97.7 25 0.9119
stokes11.3 258.0 38 0.9293 ‡
dblp100.2 0.7 38 0.8642
amazon080.7 3.5 112 0.8931
socPokec1.6 22.3 544 0.6903
citation2.9 30.3 480 0.8338
comLiveJournal4.0 34.7 854 0.7235
socLiveJournal4.8 42.8 1149 0.7319
ljournal085.4 49.5 1052 0.7662
hollywood091.1 56.3 109 0.7516
products2.4 61.8 337 0.8782
hollywood111.9 114.3 110 0.7537
Orkut3.1 117.2 437 0.6631
enwiki216.3 136.5 5324 0.6639
wbEdu8.9 44.2 2586 0.9907
ic047.3 149.1 6297 0.9630
uk0218.5 261.6 6879 0.9900
arabic0522.6 552.2 11 797 0.9896
In Fig. 1, we present the geometric mean across all graphs
of single-iteration runtimes, normalized by the runtime of
pLouvain. In Fig. 2, we present the average modularity delta
from pLouvain across all graphs. In Fig. 1 and Fig. 2, we
exclude instances where the competitor programs ran out
of memory (GVE-Louvain and GVE-Leiden on one graph,
Networkit Louvain on two graphs) or crashed (GALA on
three graphs) from the calculations for those programs. For
Fig. 2, we additionally exclude substantial outliers, which
differ from pLouvain by more than 0.2; this affects 2 graphs
for GALA, and 1 graph each for cugraph Louvain and Leiden.
In Fig. 3, we plot the runtime and modularity improvement
of performing 10 additional (11 total) iterations of pLouvain,
pLeiden, and pLeiden+ on the test set. The programs do
not necessarily reach stability in this number of iterations.
We include modularity results of clusterings obtained from
VieClus [18] by running on 24 processes with a 30-minute
time limit, one trial per graph. We run this experiment on
a system with 180 vCPUs (from an AMD EPYC 9655) with
740 GB of RAM; the process count is chosen to avoid running
out of memory for most graphs. A recent work [35] showed
that VieClus found clusterings of optimal modularity for every
graph that they tested, and in less than 25 seconds per graph.
Our test graphs are much larger, by six orders of magnitude in
some cases, so it is unlikely that VieClus can find the optimal
clusterings within a reasonable timeframe. Regardless, VieClus
serves as a compelling benchmark to compare with our iterated
methods.
In Table II, we conduct an ablation study of several key
aspects of pLouvain, to determine their effectiveness. We
showcase the following experiments:
1) No local move heuristic passes in the uncoarsening phase
(i.e. standard Louvain)
2) Standard Louvain, but with double the local move heuris-
tic passes in the coarsening phase
3) No symmetry breaking (afterburner filter disabled and
ϕ= 0)
4) Simulated annealing disabled (i.e.ϕ= 0)
5) Symmetry breaking with the MLH instead of the after-
burner filter. MLH is active in odd passes, and inactive
in even passes.ϕ= 0
6) Fused enumeration and argmax kernels in passes when
many vertices (>3%) are moved
7) Fused enumeration and argmax kernels in all passes
8) Gathering vertices by cluster membership in contraction
VII. ANALYSIS
A. Comparison to Parallel State of the Art
1) Runtime:The longest runtime of pLouvain on any graph
is just 0.5974 seconds. It is the fastest method on 55 of 57
graphs; the two smallest test graphs account for both cases
when pLouvain is not the fastest. It achieves a processing rate
of up to 6.1 billion nonzeroes per second ( 2m
t ). pLeiden is
35.3% slower by geometric mean than pLouvain; it is faster
than every competitor (Louvain or Leiden) on 52 of 57 graphs.

## PDF Page 9

TABLE II
ABLATIONSTUDY OF PLOUVAIN. SLOWDOWN IS CALCULATED AS THE
GEOMETRIC MEAN OF RUNNING TIME RATIO COMPARED TO THE DEFAULT
PLOUVAIN RUN(LOWER VALUES MEANS FASTER). THE MODULARITY
DELTA GIVES THE AVERAGE DIFFERENCE FROM THE BASELINE(HIGHER IS
BETTER).
Experiment Slowdown Mod. delta
Default pLouvain1 0
Louvain (i.e., no uncoarsening)0.775× −0.0126
Louvain, 2x LMH Passes1.16× −0.0082
pLouvain, no symmetry breaking +ϕ= 0 1.407× −0.4133
pLouvain, no simulated annealing (i.e.ϕ= 0)0.982× −0.0014
pLouvain, MLH +ϕ= 0 0.94× −0.0017
pLouvain, fused kernel (>3%vertices moved)1.001×0.0001
pLouvain, fused kernel (all passes)1.058×0.0001
pLouvain, gathered contraction1.371×0
1x
1.35x
1.69x
3.08x
4.8x
9.51x
11.9x
34.2x 39.4x 42.6x
55.1x
1
10
100
pLouvainpLeidenpLeiden+vLouvain
GALA
GVE LouvainGVE Leiden
NetworKit LeidencuGraph LeidenNetworKit LouvaincuGraph Louvain
Graph Clustering Approach
pLouvain geomean speedup
Fig. 1. Running time comparison of clustering algorithms.
−0.0124
3e−04
−0.0243
−0.0114
−0.0135 −0.0131
−0.0144
−0.0094
−0.0154
−0.0097
−0.02
−0.01
0.00
pLouvainpLeidenpLeiden+vLouvain
GALA
GVE LouvainGVE Leiden
NetworKit LeidencuGraph LeidenNetworKit LouvaincuGraph Louvain
Graph Clustering Approach
Avg. modularity delta over pLouvain
Fig. 2. Modularity comparison of clustering algorithms.
10.3x
8x
10.9x
0.0
2.5
5.0
7.5
10.0
12.5
pLouvain_11pLeiden_11pLeiden+_11
Graph Clustering Approach
Geomean slowdown compared to pLouvain
0.0012
5e−04
0.0013
0.0013
0.0000
0.0005
0.0010
0.0015
pLouvain_11pLeiden_11pLeiden+_11VieClus_30m
Graph Clustering Approach
Avg. modularity delta over pLouvain
Fig. 3. Running time (left) and modularity (right) comparisons with 10
additional (11 total) iterations.
pLeiden+ is 25.1% slower by geometric mean than pLeiden,
and is faster than every competitor on 43 of 57 graphs.
pLeiden and pLeiden+ are slower than pLouvain in part
due to the additional cost to compute pLeidenR (13.8% of
pLeiden’s runtime on average), and in part due to the slower
coarsening rate than pLouvain. pLeiden and pLeiden+ process
29.1% more edges by geometric mean as a result of their
slower coarsening rate than pLouvain. This trend is common to
any implementation of Leiden; the original Leiden algorithm
only manages to be faster than the original implementation
of Louvain due to vertex pruning techniques and early ter-
mination within the local move heuristic. These techniques
are commonplace in the implementations of Louvain in our
comparison set, and within our own implementations.
2) Modularity:pLouvain and pLeiden+ both achieve higher
modularity than any competitor on 56 of 57 graphs, and
the best overall method on every graph is either pLouvain
or pLeiden+. pLeiden achieves higher modularity than any
competitor on only 14 of 57 graphs, and overall performs in
the middle of the pack. pLeiden performs worse than pLouvain
and pLeiden+ due to the lack of an uncoarsening phase and a
local move heuristic pass count that is tuned for the presence
of uncoarsening.
v-Louvain’s modularity results are worse than GVE-
Louvain by a wide margin; both are asynchronous algorithms
with largely similar design choices. This demonstrates that
asynchronous approaches scale poorly to the massive concur-
rency of the B200 GPU. GALA performs better in terms of
modularity vs v-Louvain. However, it is substantially worse
than all competitors on the grid graph and circuit5M, two
outliers which we exclude from GALA’s Fig. 2 data. It
is synchronous, but degree-based batching is its only form
of symmetry-breaking. This is ineffective when one batch
contains almost all vertices; 99.9% of vertices in the grid graph
and 92.9% of vertices in circuit5M have degree 4.

## PDF Page 10

B. Ablation Study
pLouvain is both extremely efficient and very high quality.
Table II provides insight into the contribution of certain design
choices towards this result. Without any symmetry breaking,
pLouvain converges 41% slower to drastically worse solutions.
Disabling simulated annealing leads to worse solutions by
one sixth of the difference between pLouvain and the closest
competitor (cugraph Leiden), with a 1.8% decrease in runtime.
Using MLH in place of the afterburner filter (thus losing
compatibility with the simulated annealing techniques of [28])
similarly leads to worse solutions by one fifth of the difference
between pLouvain and its nearest competitor, but also brings
slightly faster runtimes by 6.4% as a tradeoff. We observe that
80% of the quality benefit of the afterburner filter versus MLH
is because it enables simulated annealing, whereas simulated
annealing contributes a minority of the slowdown versus MLH.
Our results show little difference between kernel fission
and fusion for passes when the number of moves is large.
In contrast, we observe a positive effect (5.8%speedup) with
kernel fission for small move sets. Kernel fission permits a
more efficient enumeration update kernel for small move sets,
which are very common in the uncoarsening phase.
Graph contraction takes just 6.5% of pLouvain’s runtime on
average and exceeds 10% of the runtime on just two graphs.
At most, it accounts for 12.6% of the total pLouvain runtime.
Versus the vertex-gathering-based contraction ablation exper-
iment, pLouvain is 37.1% faster, and shows a 3.85x speedup
for contraction specifically. pLouvain’s graph contraction is
15.5x faster than that of v-Louvain by geometric mean, and
15.1x faster than that of GALA.
Uncoarsening is the most important reason for pLouvain’s
high quality. By performing the local move heuristic within
the uncoarsening phase, the runtime increases by just 29.0%,
but the modularity increases by 0.0127, which is more than
the difference between pLouvain and its nearest competitor (as
well as the difference to pLeiden). It effectively performs twice
the local move heuristic passes that standard Louvain would
with the same pass limit, therefore we compare to standard
Louvain with double the pass limit. That configuration is
16.0% slower than pLouvain, with 0.0082 lower modularity
on average (0.0012 higher than cugraph Leiden). More local
move heuristic passes can be performed more cheaply and
to greater effect in the uncoarsening phase. This is especially
important for synchronous algorithms that require more passes
than asynchronous algorithms.
C. Iterating our Methods
pLeiden is slower and lower quality than pLouvain, and
pLeiden+ is slower but of roughly similar quality to pLou-
vain. However, Leiden’s greatest strengths are the additional
guarantees it obtains over successive iterations.
1) Modularity:Fig. 3 shows that pLeiden, across 11 total
iterations, produces lower modularity results than pLouvain
with the same iteration count. This is a consequence of
no uncoarsening in pLeiden, which is consistent with the
single iteration experiments. In contrast, iterated pLeiden+
produces superior results to iterated pLouvain, and on average
very slightly outperforms VieClus given 30 minutes with 24
processes.
2) Runtime:While pLeiden is slower than pLouvain for the
first iteration, Fig. 3 shows that 11 total iterations of pLeiden
are 28.8% faster by geomean than the same iteration count for
pLouvain. As pLouvain begins from a singleton clustering on
all iterations, successive pLouvain iterations see only slight
speedups versus the first iteration. pLeiden begins from the
given input clustering, therefore the local move heuristic
has much less work to do in successive iterations. Iterated
pLeiden+ is 36.3% slower than iterated pLeiden, a larger
difference than between their first iteration runtimes. This is
likely because there is a smaller difference between local move
heuristic passes in the coarsening versus the uncoarsening for
successive pLeiden+ iterations.
3) Versus VieClus:Iterated pLeiden+ exceeds or matches
VieClus’ quality on 26 of 57 graphs. Iterated pLouvain exceeds
or matches VieClus’ quality on 23 graphs. We expect that
VieClus would eventually beat iterated pLeiden+ on these
graphs given enough time, but the time requirement for that
to occur may be significant. Given the runtime constraints of
our experiments, VieClus is limited by the speed with which
it computes initial population and offspring clusterings.
VIII. CONCLUSION
We develop pLouvain and pLeiden, novel GPU-parallel
implementations of Louvain+ and Leiden, respectively. Both
benefit from our high-performance synchronous implementa-
tion of the local move heuristic. We find that uncoarsening
is vital given the synchronous local move. pLeiden provably
ensures each of the six original Leiden guarantees.
We conduct an extensive empirical evaluation with 57 test
graph instances from 10 families. Our performance results are
obtained primarily on an NVIDIA B200 GPU and a 16-core
AMD Ryzen 9950x3D CPU.
Our graph contraction scheme achieves substantial speedups
over comparable GPU-parallel methods. Optimizations such as
the afterburner filter for symmetry breaking, kernel fission,
and gather-free contraction, contribute to improvements in
runtime or quality. Our parallel implementation of the Leiden
refinement scheme accounts for only a small fraction of
pLeiden’s running time.
Our novel iteration scheme for Louvain+ guarantees basic
internal connectivity of clusters upon reaching stability. We
additionally construct a GPU-parallel uncoarsening extension
to Leiden, pLeiden+. It also ensures the Leiden guarantees,
except the per-iteration guarantees are delayed until stable
iterations.
With just 10 iterations, pLouvain and pLeiden+ are both
competitive with the memetic clustering algorithm VieClus.
There is thus potential for a memetic clustering algorithm on
the GPU based around pLouvain or pLeiden+. Another poten-
tial use-case for our programs is layered-label propagation for
graph compression [15].

## PDF Page 11

ACKNOWLEDGEMENTS
This research is supported in part by NSF grants 1955971
and 2437873. We thank the reviewers for their helpful com-
ments.
REFERENCES
[1] S. Fortunato, “Community detection in graphs,”Physics reports,
vol. 486, no. 3-5, pp. 75–174, 2010.
[2] V . D. Blondel, J.-L. Guillaume, R. Lambiotte, and E. Lefebvre, “Fast
unfolding of communities in large networks,”J. Stat. Mech., vol. 2008,
p. P10008, Oct. 2008.
[3] V . A. Traag, L. Waltman, and N. J. van Eck, “From Louvain to Leiden:
guaranteeing well-connected communities,”Sci. Rep., vol. 9, p. 5233,
Mar. 2019.
[4] S.-H. Teng, “Coarsening, sampling, and smoothing: elements of the
multilevel method,” inAlgorithms for Parallel Processing(M. T. Heath,
A. Ranade, and R. S. Schreiber, eds.), pp. 247–276, Springer, 1999.
[5] S. Sahu, K. Kothapalli, and D. S. Banerjee, “High-performance imple-
mentation of Louvain algorithm with representational optimizations,” in
Complex Networks & Their Applications XIII(H. Cherifi, M. Donduran,
L. M. Rocha, C. Cherifi, and O. Varol, eds.), (Cham), pp. 127–139,
Springer Nature Switzerland, 2025.
[6] S. Sahu, “CPU vs. GPU for community detection: Performance insights
from GVE-Louvain andν-Louvain,” 2025. arXiv:2501.19004.
[7] Z. Wang, X. Lin, X. Li, P. Wang, Z. Meng, H. Liu, C. Tian, and S. Zhong,
“Swift unfolding of communities: GPU-accelerated Louvain algorithm,”
inProceedings of the 30th ACM SIGPLAN Annual Symposium on
Principles and Practice of Parallel Programming, PPoPP ’25, (New
York, NY , USA), p. 441–454, Association for Computing Machinery,
2025.
[8] O. Gach and J.-K. Hao, “Improving the Louvain algorithm for commu-
nity detection with modularity maximization,” inArtificial Evolution
(P. Legrand, M.-M. Corsini, J.-K. Hao, N. Monmarch ´e, E. Lutton,
and M. Schoenauer, eds.), (Cham), pp. 145–156, Springer International
Publishing, 2014.
[9] J. Shi, L. Dhulipala, D. Eisenstat, J. Ł ˘acki, and V . Mirrokni, “Scalable
community detection via parallel correlation clustering,”Proceedings of
the VLDB Endowment, vol. 14, no. 11, pp. 2305–2313, 2021.
[10] S. Sahu, K. Kothapalli, and D. S. Banerjee, “Fast Leiden algorithm for
community detection in shared memory setting,” inProceedings of the
53rd International Conference on Parallel Processing, ICPP ’24, (New
York, NY , USA), p. 11–20, Association for Computing Machinery, 2024.
[11] M. S. Gilbert, K. Madduri, E. G. Boman, and S. Rajamanickam,
“Jet: Multilevel graph partitioning on graphics processing units,”SIAM
Journal on Scientific Computing, vol. 46, no. 5, pp. B700–B724, 2024.
[12] N. Veldt, D. F. Gleich, and A. Wirth, “A correlation clustering framework
for community detection,” inProceedings of the 2018 World Wide Web
Conference, pp. 439–448, 2018.
[13] M. E. Newman and M. Girvan, “Finding and evaluating community
structure in networks,”Physical review E, vol. 69, no. 2, p. 026113,
2004.
[14] V . A. Traag, P. Van Dooren, and Y . Nesterov, “Narrow scope for
resolution-limit-free community detection,”Phys. Rev. E, vol. 84,
p. 016114, Jul 2011.
[15] P. Boldi, M. Rosa, M. Santini, and S. Vigna, “Layered label propaga-
tion: A multiresolution coordinate-free ordering for compressing social
networks,” inProc. 20th Int’l. Conf. on World Wide Web (WWW), 2011.
[16] U. N. Raghavan, R. Albert, and S. Kumara, “Near linear time algorithm
to detect community structures in large-scale networks,”Physical Review
E, vol. 76, no. 3, p. 036106, 2007.
[17] U. Brandes, D. Delling, M. Gaertler, R. Gorke, M. Hoefer, Z. Nikoloski,
and D. Wagner, “On modularity clustering,”IEEE Transactions on
Knowledge and Data Engineering, vol. 20, no. 2, pp. 172–188, 2008.
[18] S. Biedermann, M. Henzinger, C. Schulz, and B. Schuster, “Memetic
Graph Clustering,” inProceedings of the 17th International Symposium
on Experimental Algorithms (SEA’18), LIPIcs, Dagstuhl, 2018. Techni-
cal Report, arXiv:1802.07034.
[19] R. Rotta and A. Noack, “Multilevel local search algorithms for modu-
larity clustering,”ACM J. Exp. Algorithmics, vol. 16, July 2011.
[20] C. Walshaw, “Multilevel refinement for combinatorial optimisation prob-
lems,”Ann. Oper. Res., vol. 131, pp. 325–372, Oct. 2004.
[21] H. Qie, S. Li, Y . Dou, J. Xu, Y . Xiong, and Z. Gao, “Isolate sets partition
benefits community detection of parallel Louvain method,”Sci. Rep.,
vol. 12, p. 8248, May 2022.
[22] S. Ghosh, M. Halappanavar, A. Tumeo, A. Kalyanaraman, H. Lu,
D. Chavarri `a-Miranda, A. Khan, and A. Gebremedhin, “Distributed
Louvain algorithm for graph community detection,” in2018 IEEE
International Parallel and Distributed Processing Symposium (IPDPS),
pp. 885–895, 2018.
[23] R. Forster, “Louvain community detection with parallel heuristics on
GPUs,” in2016 IEEE 20th Jubilee International Conference on Intelli-
gent Engineering Systems (INES), pp. 227–232, 2016.
[24] H.-Y . Chou and S. Ghosh, “Batched graph community detection on
GPUs,” inProceedings of the International Conference on Parallel
Architectures and Compilation Techniques, PACT ’22, (New York, NY ,
USA), p. 172–184, Association for Computing Machinery, 2023.
[25] M. Halappanavar, H. Lu, A. Kalyanaraman, and A. Tumeo, “Scalable
static and dynamic community detection using grappolo,” in2017 IEEE
High Performance Extreme Computing Conference (HPEC), pp. 1–6,
2017.
[26] M. Naim, F. Manne, M. Halappanavar, and A. Tumeo, “Community
detection on the GPU,” in2017 IEEE International Parallel and Dis-
tributed Processing Symposium (IPDPS), pp. 625–634, 2017.
[27] F. Nguyen, “Leiden-based parallel community detection,” Bachelor’s
thesis, Karlsruhe Institute of Technology, 2021.
[28] P. Sanders and D. Seemaier, “Brief announcement: Distributed uncon-
strained local search for multilevel graph partitioning,” inProceedings
of the 36th ACM Symposium on Parallelism in Algorithms and Archi-
tectures, SPAA ’24, (New York, NY , USA), p. 443–445, Association for
Computing Machinery, 2024.
[29] R. Krause, L. Gottesb ¨uren, and N. Maas, “Deterministic parallel high-
quality hypergraph partitioning,” in2025 Proceedings of the Conference
on Applied and Computational Discrete Algorithms (ACDA), pp. 222–
236.
[30] P. Hijma, S. Heldens, A. Sclocco, B. Van Werkhoven, and H. E. Bal,
“Optimization techniques for GPU programming,”ACM Computing
Surveys, vol. 55, no. 11, pp. 1–81, 2023.
[31] D. Salwasser, D. Seemaier, L. Gottesb ¨uren, and P. Sanders, “Tera-scale
multilevel graph partitioning,” in2025 IEEE International Parallel and
Distributed Processing Symposium (IPDPS), pp. 285–296, 2025.
[32] A. Zaheri and C. Hastings, “Scaling and validating louvain in cugraph
against massive graphs,” 2022.
[33] R. Ratzel, “How to accelerate community detection in python using
gpu-powered leiden,” 2025.
[34] M. Gilbert, K. Madduri, E. G. Boman, and S. Rajamanickam, “Graph
dataset for ‘Jet: Multilevel graph partitioning on graphics processing
units’,” 2024. doi:10.26207/pffm-mc36.
[35] C. Ans ´otegui, V . P. Ramaswamy, S. Szeider, and H. Xia, “Uncovering
and verifying optimal community structure in complex networks: A
maxsat approach,” inInternational Conference on Computational Sci-
ence, pp. 35–49, Springer, 2025.

## PDF Page 12

Appendix: Artifact Description
IX. OVERVIEW OFCONTRIBUTIONS ANDARTIFACTS
A. Paper’s Main Contributions
C1 On an NVIDIA B200 GPU and a 57-instance graph
dataset, pLouvain achieves a 3.1x geometric mean
speedup over v-Louvain.
C2 pLeiden offers quality guarantees equivalent to Leiden,
and is 8.8x faster (geometric mean) than a prior paral-
lelization.
C3 pLouvain and pLeiden+ consistently outperform other
approaches in terms of quality (modularity).
C4 We present an efficient symmetry-breaking technique
based on the Jet graph partitioner’safterburnerfilter.
C5 Our graph contraction implementation is≥15x faster
by geometric mean than state-of-the-art competitors v-
Louvain and GALA.
C6 We give an improved iteration scheme to mitigate Lou-
vain’s weak internal cluster connectivity problem.
B. Computational Artifacts
A1 https://doi.org/10.5281/zenodo.18717935
A2 https://doi.org/10.5281/zenodo.18719087
Artifact ID Contributions Related
Supported Paper Elements
A1 C1−6 Table 2
Figures 1-3
A2 C1−6 Table 2
Figures 1-3
X. ARTIFACTIDENTIFICATION
A. Computational ArtifactA 1
Relation To Contributions
This artifact contains the code for pLouvain, pLeiden, pLei-
den+, and the ablation experiments. The ablation experiments
are contained in appropriately named branches in the git
repository linked from the DOI. This artifact is necessary for
experiments showcased in Table 2 and Figures 1-3.
Expected Reproduction Time (in Minutes)
Compilation should take 5-10 minutes, including dependen-
cies.
Artifact Setup (incl. Inputs)
Hardware:The programs should run on any Nvidia GPU
since the Turing architecture. It has been tested on a B200,
RTX 4090, and an RTX 5090.
Installation and Deployment:The code depends on the
Kokkos (https://github.com/kokkos/kokkos) framework,
version≥4.7.0. It also depends on KokkosKernels
(https://github.com/kokkos/kokkos-kernels), version≥4.7.0.
To compile, Cuda Toolkit version≥12.0 and CMake version
≥3.28 are required.
B. Computational ArtifactA 2
Relation To Contributions
This artifact contains scripts to generate all of the running
time and clustering modularity results underlying Table 2,
and Figures 1-3, as well as some miscellaneous quantities in
section VII. Additionally, it contains the data produced by
our experiments, organized into 3 levels of granularity. At the
finest level, we have individual running times and modularity
results for each combination of graph and program. At the
next level, we aggregate these results by Table/Figure. At the
coarsest level, we have the headline numbers used to create
each Table/Figure.
Expected Results
The geometric mean runtimes should be, from shortest
to longest: pLouvain, pLeiden, pLeiden+, v-Louvain, GALA,
GVE Louvain, GVE Leiden, Networkit Leiden, cuGraph Lei-
den, Networkit Louvain, and cuGraph Louvain. The average
modularity results should be (outliers excluded), from highest
to lowest: pLeiden+, pLouvain, cuGraph Leiden, cuGraph
Louvain, GALA, pLeiden, GVE Leiden, GVE Louvain, Net-
workit Leiden, Networkit Louvain, and v-Louvain.
For the multiple iteration experiments, pLeiden 11 should
be fastest but lowest quality, pLeiden+ 11 should be slowest
but highest quality, and pLouvain 11 should be in the middle
for both runtime and quality.
VieClus quality results should be slightly lower than pLei-
den+ 11 quality.
The results obtained by running our scripts should be similar
to our results in idpds26 results.tar.gz.
Expected Reproduction Time (in Minutes)
Compilation of ours and competitor code should take up to
20 minutes. Computational time for GPU experiments includ-
ing competitors should take 6-8 hours. Computational time for
CPU competitors should take 6-8 hours. Computational time
for VieClus should take about 2-3 days.
Artifact Setup (incl. Inputs)
Hardware:GPU experiments are run on the Nvidia B200,
rented from cloud provider Verda (https://verda.com/). Run-
time results vary to a small degree (<5%) depending on
which GPU you get assigned. We believe this is because some
instances have slower CPUs than others, leading to longer
kernel launch latencies. All of our GPU results, except for the
”gathered contraction” ablation experiment, were generated on
the exact same instance. For that specific experiment, we reran
the baseline pLouvain experiment on the same instance for
normalization purposes.
CPU experiments are run on a consumer grade system
having an AMD Ryzen 9950x3d 16-core CPU and 96GB of
DDR5 dual-channel memory.
The VieClus experiment is run on a 180-vcore cloud in-
stance from Verda.

## PDF Page 13

Software:Our code is detailed in artifactA 1.
Competitor Software:
1) v-Louvain (https://github.com/puzzlef/louvain-
communities-cuda)
2) GALA
3) GVE Louvain (https://github.com/puzzlef/louvain-
communities-openmp)
4) GVE Leiden (https://github.com/puzzlef/leiden-
communities-openmp)
5) Networkit Louvain v11.1.post1 and Leiden v11.2
(https://networkit.github.io/)
6) cuGraph Louvain and Leiden
(https://github.com/rapidsai/cugraph) v26.02
7) VieClus v1.1 (https://github.com/VieClus/VieClus)
Datasets / Inputs:The test graph dataset is available at
https://scholarsphere.psu.edu/resources/fd9ba209-a0cd-4f33-
994b-c22ae3bcb243/downloads/35163?download=true. It
contains a superset of the graphs listed in Table 1, represented
in the Metis file format. The ”data setup.sh” script handles
the process of downloading, decompressing, and de-archiving
the dataset. It also creates matrix marketplace format copies
of the graph files.
Installation and Deployment:We compiled ours and com-
peting software with Cuda Toolkit version 12.8 and g++
13.3.0. For VieClus, we used OpenMPI version 4.1.6. Run
the ”setup gpu.sh” script followed by the ”setup our code.sh”
script to install our code’s dependencies and build our code.
Run the ”setup competitors gpu.sh” script to build v-Louvain
and GALA. Run the ”setup cpu competitors.sh” to build
GVE-Louvain and GVE-Leiden. The latter two scripts clone
our forks of these programs, which include an improved data
collection process and some bugfixes for GALA.
For the cuGraph and Networkit programs, you will first need
to install conda/miniconda, then install rapidsai::cugraph and
conda-forge::networkit.
For VieClus, you can run ”setup and run vieclus.sh” which
handles both the program building and experiment execution.
Artifact Execution
First, you must clone the appropriate git repositories,
compile code, and download/uncompress the graph dataset.
You can do this with the aforementioned scripts. Second, you
will run our experiment scripts, which run our code and the
competitors on each graph, and output the runtime/modularity
datapoints. These scripts include: ”run our experiments.sh”,
”run gpu competitor experiments.sh”,
”run cpu competitor experiments.sh”,
”conda gpu competitors.sh”, ”conda cpu competitors.sh”,
and ”setup and run vieclus.sh”.
Artifact Analysis (incl. Outputs)
In our analysis, we aggregate the raw datapoints into
spreadsheets by Table/Figure. This is a manual process, which
involves copying columns from the results files and pasting
them into a spreadsheet. We collect headline numbers from
these spreadsheets, including the geometric mean runtimes and
mean modularity deltas from pLouvain. The headline numbers
are the basis of Table 2 and Figures 1-3.