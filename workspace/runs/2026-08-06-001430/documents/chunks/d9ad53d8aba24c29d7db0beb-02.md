move heuristic is preserved and reused for all subsequent
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