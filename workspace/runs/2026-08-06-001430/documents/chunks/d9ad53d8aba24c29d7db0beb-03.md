al evaluation with 57 test
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