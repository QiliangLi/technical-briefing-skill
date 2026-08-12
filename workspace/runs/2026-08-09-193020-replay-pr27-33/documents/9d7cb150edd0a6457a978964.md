## PDF Page 1

Deep Agentic Search for Repository-Level Code
Question Answering: An Empirical Study
Amirkia Rafiei Oskooei·Bora Ilci·
Alperen Kayim·Mehmet Egemen
Uzun·Berat Can·Kaan Emre Kara·
Ozan Orhan·Mehmet S. Aktas
AbstractCode agents spend much of their effort simply locating the right
code inside a repository. Two approaches dominate current practice. In Seman-
tic Search, the agent retrieves code blocks from a vector index built from the
repository in advance. In Deep Agentic Search (also known as grep-search by
subagent), a planning agent delegates the exploration to a separate subagent
that works in an isolated context window and returns only a condensed result.
The second design, which is considered good context engineering practice, ex-
ists to protect the main agent from context pollution (also known as context
rot), the loss of accuracy that occurs as unrelated material accumulates in
the context window. Recent code agents (such as Claude Code, Codex, Anti-
gravity, etc) have adopted it quickly, but there is little evidence on whether
it produces better answers. We compare the two approaches on SWE-QA, a
benchmark for repository-level code question answering. Semantic search an-
swered 65.2% of questions correctly against 46.2% for deep agentic search, and
it produced each correct answer at less than half the cost. To explain the gap,
we then coded every failed run into a taxonomy of failure modes. The taxon-
omy shows that deep agentic search did not remove failures but introduced a
new class of them: the single largest share of its failures, 41.8%, occurred at
the hand-off between the planner and its sub-agent, and these were usually
silent, ending in a fluent and confident answer that was wrong. Deep agentic
search addresses a real problem and is now the preferred design in many code
A. Rafiei Oskooei
Department of Computer Engineering, Yildiz Technical University, Istanbul, Turkey
Intellica Business Intelligence, Istanbul, Turkey
ORCID: 0009-0004-3490-550X
E-mail: amirkia.oskooei@std.yildiz.edu.tr, E-mail: amirkia.oskooei@intellica.net
B. Ilci (E-mail: bora.ilci@std.yildiz.edu.tr), A. Kayim (E-mail:
alperen.kayim@std.yildiz.edu.tr), M. E. Uzun (E-mail: egemen.uzun@std.yildiz.edu.tr),
B. Can (E-mail: berat.karakas@std.yildiz.edu.tr), K. E. Kara (E-mail:
kaan.kara@std.yildiz.edu.tr), O. Orhan (E-mail: ozan.orhan@std.yildiz.edu.tr), M. S.
Aktas (E-mail: aktas@yildiz.edu.tr)
Department of Computer Engineering, Yildiz Technical University, Istanbul, Turkey
arXiv:2608.01507v1  [cs.SE]  2 Aug 2026

## PDF Page 2

2 A. Rafiei Oskooei et al.
agents. However, our results show that the protection it offers may not be
free, and that for read-only questions over a repository that can be indexed,
retrieval was the stronger and cheaper option.
KeywordsCode Question Answering·Deep Agentic Search·Semantic
Search·Code Agents·Large Language Models·Context Engineering
Fig. 1The two paradigms compared in this study. (a) Semantic search, realised by a ReAct
agent, which retrieves pre-filtered chunks from a vector index built in advance. (b) Deep
Agentic search, realised by a Deep Agent, which builds no index and delegates exploration
to a sub-agent that works in its own context window and returns only a condensed result.
The designs differ in what reaches the main context of the agent that answers.

## PDF Page 3

Deep Agentic Search for Repo-Level Code QA 3
1 Introduction
Large language models have turned code agents into a primary interface for
software development. Developers increasingly write, understand, debug, and
maintain software through these agents, whether inside an integrated devel-
opment environment or at the command line. One task recurs throughout this
workflow, namely code question answering, which is the task of answering a
natural language question about a codebase. A question can concern a single
function, class, or snippet, or it can concern an entire repository. When the
scope is a whole repository the task becomes repository-level code question
answering, and it is the most demanding form of the task, because the infor-
mation needed to answer a question is spread across many files and must first
be located and then combined into a coherent answer. Both people and agents
rely on this task. Developers ask questions about code in order to understand
it before they extend, debug, or maintain it, and agents ask questions about
code, either on behalf of a developer or for their own planning, in order to
complete the tasks they are given.
Repository-level code question answering is costly for people and challeng-
ing for agents, and the difficulty grows with the size of the repository. The
root of the difficulty is that an agent reasons with a language model that has
a bounded context window and a fixed store of parametric knowledge, and
neither of these holds a faithful and current copy of the specific repository
at hand. Supplying more text is not a remedy on its own, because accuracy
declines as unrelated material accumulates in the context window, an effect
practitioners call context pollution, or context rot (Oskooei et al., 2026). For
each question, an agent must therefore decide which small part of a large
and evolving codebase to place in front of the model. This problem of curat-
ing the right context, commonly called context engineering, is where the two
paradigms we study diverge.
These two paradigms have become dominant in practice, and each is re-
alised by a distinct agent architecture (Fig. 1). The first is a ReAct agent that
uses Semantic search, retrieving from a vector index built in advance from the
repository. This is the established design behind the assistants embedded in
modern editors, such as Cursor. The second is a Deep Agent that uses Deep
Agentic search, also described by practitioners as grep search by an explorer
sub-agent, exploring the repository on demand with terminal style commands
and delegating the noisy part of that exploration to an isolated sub-agent that
returns only a condensed result. Keeping the raw output of the search out of
the main context in this way is a deliberate act of context engineering and
is widely regarded as good practice. This is the more recent design behind
assistants that operate at the command line, such as Claude Code, Gemini
CLI, and Codex (Liu et al., 2026; dos Santos et al., 2026). The two paradigms
embody a genuine design trade-off. Semantic search pays a one-time indexing
cost and then serves compact, pre-filtered context, but it can fragment code
and retrieve passages that are similar in wording yet irrelevant. Deep Agentic

## PDF Page 4

4 A. Rafiei Oskooei et al.
search pays no indexing cost and reads code in its natural structure, but it
can flood the model with raw output that must then be filtered out again.
Repository exploration is a large part of an agent’s work and consumes
a substantial share of its tool calls and tokens, so the choice between these
paradigms has direct consequences for accuracy, cost, and latency. Practition-
ers actively debate which paradigm is preferable, yet the debate rests largely
on intuition and experience. To our knowledge the two paradigms have not
been compared empirically for repository-level code question answering, and
in particular no study has set an index-based retrieval agent against a Deep
Agent that delegates repository exploration to an isolated sub-agent. This
study provides that comparison. We do not propose a new method and we
hold no prior preference for either paradigm. Our aim is not to recommend
one paradigm over the other, but to measure where each one succeeds, where
it fails, and at what cost, under the conditions we study.
We empirically compare these two paradigms, Semantic search and Deep
Agentic search, on a standard benchmark for repository-level code question
answering (Peng et al., 2026a). We organise the comparison around three re-
search questions.
–RQ1 (Accuracy): Which paradigm answers repository-level code questions
more accurately, Semantic search or Deep Agentic search?
–RQ2 (Cost and efficiency): What does each paradigm cost, and is any
difference in accuracy worth its cost?
–RQ3 (Behaviour and failure modes): How do the two paradigms behave,
and how and why does each one fail?
This paper makes three contributions. First, it provides an empirical com-
parison of Semantic search and Deep Agentic search for repository-level code
question answering across four language models on a standard benchmark.
Second, it provides a cost-aware analysis that reports token consumption,
monetary cost, latency, and the effective cost per correct answer, together
with a view of the trade-off between accuracy and cost. Third, it provides
a behavioural analysis of tool usage and trajectory length, and a taxonomy
of failure modes derived from the recorded execution traces. The remainder
of the paper is organised as follows. Section 2 provides background on the
memory and context limits that motivate both paradigms and on how each
paradigm works. Section 3 discusses related work. Section 4 describes the ex-
perimental design. Section 5 reports the results. Section 6 presents the failure
analysis. Section 7 discusses the findings, Section 8 states threats to validity,
and Section 9 concludes.
2 Background
This section provides the background needed to interpret the comparison. We
first define repository-level code question answering and explain why context,
rather than raw model capability, is the central constraint. We then describe

## PDF Page 5

Deep Agentic Search for Repo-Level Code QA 5
the agent architectures and the search paradigms they use, and we close by
positioning the two paradigms that our study compares.
2.1 LLMs for Repository-Level Code Question Answering
Code question answering is the task of answering a natural language ques-
tion about source code. Its scope can be narrow, such as a question about
a single function, class, or snippet, or wide, such as a question about an en-
tire repository. Repository-level code question answering is the widest and
most difficult form. A repository can contain hundreds of thousands of lines
of code across many files, and the facts needed to answer a single question,
for example how a class enforces validation or where a configuration value is
consumed, are typically scattered across several of those files. Answering the
question therefore has two parts. The agent must first locate the relevant code
within the repository, and it must then understand and combine that code
into a correct and coherent answer. The first part, locating the code, is what
separates repository-level questions from narrower ones, and it is where much
of an agent’s effort is spent. Both developers and agents perform this task. De-
velopers ask such questions to understand unfamiliar code before extending,
debugging, or maintaining it, and agents ask them, on behalf of a developer
or for their own planning, for the same reason.
An agent answers a question by prompting a language model, and the
model draws on two kinds of memory. Parametric memory is the knowledge
fixed in the model weights during training. Working memory is the context
window, which is the text supplied to the model at inference time. Parametric
memory alone is a poor basis for answering questions about a specific repos-
itory. Training a model on the full contents of large repositories is expensive,
and even where it is possible, repositories change rapidly, so a model trained
today becomes stale after the next commit and cannot be retrained after ev-
ery change. Models also recall specific facts from their parameters less reliably
than they read them from the context window, and answers produced from
parametric memory alone are more prone to fabrication (Yang et al., 2025). To
produce accurate and current answers, the relevant repository content must
be placed in the context window.
The context window, however, is bounded, and a large repository does not
fit within it and we need to be selective about what we put in it or summarize
chunks of it (Oskooei et al., 2025; Rafiei Oskooei et al., 2026). Supplying more
text is not a free remedy, because the quality of a model’s answer tends to
degrade as the input grows (Rando et al., 2025; Maharaj et al., 2026; Huang
et al., 2026). As the context lengthens, the model must find the few relevant
passages among many irrelevant ones, a difficulty often described as looking
for a needle in a haystack. The amount of text is not the only factor. Model
accuracy also falls as the proportion of irrelevant to relevant tokens rises,
an effect described as context pollution, or context rot, in which distracting
content crowds out the signal that the model needs. The effect is not confined

## PDF Page 6

6 A. Rafiei Oskooei et al.
to retrieved passages: in code translation, functional correctness peaks with
a small number of in-context examples and then declines as many more are
supplied, even when the context window is large enough to hold them (Oskooei
et al., 2026). Because the useful content is a small and shifting part of a large
repository, the core problem for every paradigm is to select what enters the
limited context window. This activity of curating the model’s context is often
called context engineering (Anthropic, 2025; LangChain, 2025), and it is the
lens through which we interpret the paradigms that follow.
2.2 Agent Architectures and Search Paradigms
The first family of solutions is Semantic search, realised through retrieval-
augmented generation (Lewis et al., 2020). The repository is divided into
chunks, an encoder model converts each chunk into a dense vector embed-
ding, and the chunks and their embeddings are stored in a vector index. When
a question arrives, it is embedded in the same space, and the chunks whose
embeddings are most similar to the question, measured by a similarity such
as cosine distance, are retrieved and placed in the context window for the
model to reason over. This approach keeps the context compact, because only
the most similar chunks are supplied, and it is inexpensive to keep current,
because only the chunks affected by a change need to be re-embedded, rather
than the whole model retrained. For these reasons it became a standard ap-
proach for repository-level code question answering (Gao et al., 2023). In its
agentic form the agent issues several retrieval queries in sequence rather than
a single query, refining what it asks for as it reasons. This is commonly built
as a ReAct agent (Yao et al., 2023), which follows a loop of reasoning, calling
a retrieval tool, and observing the result until it can answer.
Semantic search also has characteristic weaknesses, and they follow from
how the index is built. First, the quality of the answer is bounded by the qual-
ity of the retrieval, so when the retrieved chunks miss the relevant code the
model can only produce an incomplete or incorrect answer. Second, code is hi-
erarchical rather than linear, and dividing it into fixed-size chunks can split a
function, separate a class from its methods, or remove the surrounding scope
that a passage needs to be understood. An agent can request neighbouring
chunks, but reassembling structure in this way is indirect. Third, following a
dependency, such as moving from a class to the parent class it extends, calls
for exact identifier matching, whereas retrieval reduces the request to an ap-
proximate similarity search, which adds imprecision to a task that requires
precision. Fourth, in a large repository many code elements are worded sim-
ilarly, so a query can match a large number of superficially similar passages
and return results of low precision. Fifth, to compensate for this imprecision
an agent may retrieve many candidate chunks, which raises token consump-
tion and latency and can bury the correct passage among distractors, so that
the model misses information that is present but lost in the middle of a long
context.

## PDF Page 7

Deep Agentic Search for Repo-Level Code QA 7
The second family of solutions is Agentic search. Instead of consulting a
pre-built index, the agent is given access to the file system and explores it on
demand with terminal style commands such asgrep,find, andglob. This
mirrors how a developer navigates an unfamiliar codebase and removes the
indexing step entirely. It also addresses several of the weaknesses of Semantic
search. Because the agent reads files in their native form, it avoids the chunk
boundaries that fragment code. Because it can match identifiers exactly, it
can follow dependencies such as inheritance directly rather than through ap-
proximate search. Because it works on the live repository, it is always current
and needs no ingestion or re-indexing. And because it targets literal identifiers
and strings, it avoids returning a flood of merely similar passages in a large
codebase.
Agentic search introduces a difficulty of its own. Exploration commands
return large volumes of raw text, such as long file listings, directory trees, and
unfiltered source, and this output accumulates in the agent’s context window.
Compared with the compact, pre-filtered passages of Semantic search, this raw
material pollutes the context more quickly and pushes the agent toward the
same degradation described above, while also raising token consumption and
latency, because the agent must read through verbose output to find what
matters.
Deep Agentic search is a refinement that keeps the benefits of live explo-
ration while containing this cost. Rather than have a single agent manage
both high-level planning and low-level exploration, the agent is organised as a
hierarchy. A main orchestrator plans the task and maintains a task list, and it
delegates the noisy exploration loop to an isolated sub-agent. The sub-agent
has its own separate context window in which it runs the exploration com-
mands, absorbs the raw output, and filters it, and it returns only a condensed
result to the orchestrator. The orchestrator’s context therefore stays compar-
atively clean, and it can direct further exploration without accumulating the
raw material itself. This delegation is itself a deliberate act of context engi-
neering (Anthropic, 2025), and it is the design used by recent assistants that
operate at the command line. The two architectures are nested rather than
alternative (Fig. 2). A Deep Agent runs the same reasoning and tool-calling
loop as a ReAct agent, and extends it with planning, a virtual filesystem, and
the ability to delegate work to a sub-agent.
2.3 The Two Paradigms We Compare
Our study compares the two designs that are most widely deployed today. The
first is Semantic search, realised by a ReAct agent equipped with retrieval over
a pre-built vector index. In this study the agent has exactly three tools, namely
a repository structure lookup, a retrieval tool over the index, and a file reader,
matching the action space of the original benchmark protocol (Peng et al.,
2026a). It represents the indexing approach found in editor-based assistants
such as Cursor and Antigravity. The second is Deep Agentic search, realised by

## PDF Page 8

8 A. Rafiei Oskooei et al.
Fig. 2Agent architectures. A ReAct agent is a loop between a language model and a set
of tools. A Deep Agent contains that same loop and extends the tool set with planning, a
virtual filesystem, and the ability to delegate work to sub-agents.
a Deep Agent, a hierarchical architecture with an orchestrator that plans and
delegates and a sub-agent that explores in isolation. It represents the approach
found in command line assistants such as Claude Code, Gemini CLI, and
Codex (Liu et al., 2026; dos Santos et al., 2026). Exploration-based designs
that use terminal style tools without an index and without a sub-agent sit
between the two and have been examined separately (Sen et al., 2026; Zhang
et al., 2026d).
These two paradigms express opposite answers to the same context en-
gineering question. Semantic search pays a one-time indexing cost and then
serves compact, pre-filtered context, at the risk of fragmenting code and re-
trieving passages that are similar but irrelevant. Deep Agentic search pays no
indexing cost and reads code in its native structure, at the risk of importing
raw output that must be filtered, which the sub-agent delegation is designed
to contain. The remainder of the paper measures how these opposing risks
play out in accuracy, cost, and behaviour.
3 Related Work
Prior work relevant to our study falls into three groups: benchmarks that
define repository-level code question answering, systems that advance a single
search paradigm, and the smaller set of studies that compare search paradigms
directly. We review each group in turn and then state where our study differs.
Table 1 summarises the comparison along the dimensions that matter for our
contribution.
Benchmarks for repository-level code question answering.A first line of work
establishes the task and measures how well language models perform it. SWE-

## PDF Page 9

Deep Agentic Search for Repo-Level Code QA 9
T able 1Positioning against representative prior work. The columns are: Repo QA,
repository-level code question answering; Paradigm comp., a direct comparison of semantic
index-based search against agentic exploration-based search; Deep agent, the agentic side
is a Deep Agent in which a planning orchestrator delegates exploration to an isolated sub-
agent; Cost, a token, monetary, or latency analysis; Behaviour, an analysis of tool use or
trajectory; Failure, a systematic failure-mode taxonomy. Here✓denotes that the dimension
is addressed,∼that it is addressed in part, and×that it is not addressed.
Work Repo QA Paradigm comp. Deep agent Cost Behaviour Failure
SWE-QA ✓ ∼ × ∼ × ×
CoReQA✓× × × × ×
CodeRepoQA ✓ × × × × ×
StackRepoQA✓ ✓× × × ×
SWE-Explore ∼ ✓ × ∼ ∼ ∼
Is Grep All You Need?×✓× × ∼ ×
DeepRepoQA ✓ ✓ ∼ × × ×
RepoSearch-R1✓ ✓∼ × × ×
FastContext ✓ × ✓ ✓ × ×
Ours ✓ ✓ ✓ ✓ ✓ ✓
QA (Peng et al., 2026a) provides open-ended questions over whole Python
repositories and evaluates models under direct prompting, retrieval, and single-
agent frameworks, and later work published under the same name extends the
setting with multiple-choice questions (Elkoussy and Perez, 2026) and with
a training recipe for open models (Cai et al., 2026). Throughout this paper,
SWE-QA refers to the benchmark of Peng et al. (2026a), which is the dataset
we evaluate on. CoReQA (Chen et al., 2025) and CodeRepoQA (Hu et al.,
2025) build repository-level question sets from issue threads and maintainer
dialogues, and StackRepoQA (Alebachew et al., 2026) draws repository ques-
tions from community answers, while LongCodeBench (Rando et al., 2025)
instead stresses very long context windows. These benchmarks fix the task and
rank models, and where they vary the retrieval method they treat it as fixed
infrastructure rather than as the object of study. The comparisons reported
within the SWE-QA family in particular place retrieval against flat single
agents, not against a hierarchical agent, and they report accuracy rather than
a joint account of accuracy, cost, and failure. Adjacent benchmarks probe re-
lated capabilities, including code understanding that separates reasoning from
documentation memorization (Zhang et al., 2026b), code understanding and
comparison (Anonymous, 2025), coding-agent evaluation beyond issue reso-
lution (Raghavendra et al., 2026), developer-knowledge question answering
(Zhang et al., 2026a), contextualized question answering for coding assistants
(Mohammed et al., 2026), multi-domain coding question answering (Rahman
et al., 2025), repository documentation quality via question answering (Wang
et al., 2026b), and code information retrieval and search (Li et al., 2025b;
Gong et al., 2025).
Systems that advance a single search paradigm.A second line proposes and
improves one paradigm at a time. On the semantic side, retrieval-augmented
generation, introduced for knowledge-intensive natural language tasks (Lewis

## PDF Page 10

10 A. Rafiei Oskooei et al.
et al., 2020) and since surveyed in depth (Gao et al., 2023), including itera-
tive multi-step variants (Wang et al., 2025), is the basis of index-based code
assistants, and code-specific systems such as CoRAC (Choi et al., 2025) and
RepoWise (Kocadere et al., 2026) adapt retrieval to code question answering.
On the agentic side, the ReAct design (Yao et al., 2023) established the rea-
soning and acting loop that our Semantic search agent instantiates, and more
recent systems explore the repository dynamically rather than through an in-
dex: DeepRepoQA (Peng et al., 2026b) and RepoSearch-R1 (Li et al., 2025a)
navigate the repository with tree-search agents, and FastContext (Zhang et al.,
2026c) and ContextPilot (Gao et al., 2026) pair a lightweight explorer with
a separate generator that consumes its condensed output. A related group
of efficiency-oriented methods, including FastCode (Li et al., 2026b), SWE-
Pruner (Wang et al., 2026d), and LongCodeZip (Shi et al., 2025), reduces the
token cost of repository context. Graph-based retrieval agents add code-graph
structure to exploration (Shah et al., 2025; Hu et al., 2026; Usai et al., 2026),
general reasoning agents scale tool use (Li et al., 2026a), structured reasoning
improves the reliability of code agents (Ugare and Chandra, 2026), and further
context-pruning and compression methods trim retrieved code before it reaches
the model, including approaches that change its representation (Wang et al.,
2026a; Feng et al., 2026; Shi et al., 2026). Earlier code question answering
operated at the level of single functions or snippets, using fine-tuned mod-
els (Andryushchenko et al., 2024; Lopes et al., 2025) and retrieval-augmented
pipelines (Ahmed et al., 2024), with benchmarks measuring comprehension at
that scale (Havare et al., 2025). Each of these is a method contribution that
advances a single paradigm, typically with one model, and does not set one
paradigm against the other under matched conditions.
Direct comparisons of search paradigms.A third and smaller line compares
paradigms head to head, and it is closest to our study. The work asking whether
grep is all that is needed (Sen et al., 2026) finds that lexical exploration can
match or exceed vector retrieval inside agent harnesses, but it studies conver-
sational memory rather than code repositories. SWE-Explore (Zhang et al.,
2026d) compares classical retrieval against agentic exploration at repository
scale and finds exploration stronger, but it measures line-level localization for
downstream patching rather than the correctness of an answer. StackRepoQA
(Alebachew et al., 2026) compares retrieval, agentic, and graph augmentation
for repository question answering, but its agentic condition is a flat single
agent. In all three, the agentic side is a single agent rather than a Deep Agent,
and none of them pairs the comparison with a cost, a behaviour, and a failure
analysis.
Positioning.Our study occupies the cell that these three groups leave empty
(Table 1). To our knowledge, it is the first to set a Deep Agent that uses Deep
Agentic search, a planning orchestrator that delegates repository exploration
to an isolated sub-agent, against a ReAct agent that uses Semantic search,
on repository-level code question answering. This delegated-explorer design

## PDF Page 11

Deep Agentic Search for Repo-Level Code QA 11
mirrors how command-line assistants offload exploration to a smaller explorer
agent, and it is distinct from the flat single agents used in the prior comparisons
above. We further accompany the accuracy comparison with three analyses
that prior work reports at most in part: a cost and efficiency analysis in tokens
and dollars that includes the cost per correct answer, an analysis of agent
behaviour through tool use and trajectory length, and a systematic taxonomy
of failure modes. The combination of the Deep Agentic search paradigm with
these three analyses, across four language models on a shared benchmark, is
what distinguishes our study from the work reviewed above.
4 Experimental Design
This empirical study was conducted as a collaborative research effort between
Intellica Business Intelligence and researchers at Yildiz Technical University.
We compare two agent architectures, a ReAct agent that uses Semantic search
and a Deep Agent that uses Deep Agentic search. Each question is answered
in a fresh conversation thread, so that no question can contaminate another,
and only the repository targeted by the question is available to the agent. All
execution traces are recorded, including tool calls, planner steps, sub-agent
actions, and token accounting. Each research question is served by a specific
part of this design: the graded answer quality and the paired statistical tests
for RQ1, the token and cost measurements for RQ2, and the recorded traces,
from which we derive tool usage, trajectory length, and a taxonomy of failure
modes, for RQ3.
4.1 Agent Implementation
We compare two agent architectures. The first is a ReAct agent that uses the
Semantic search paradigm. It is the established reasoning and acting design,
and we use the ReAct agent harness from LangChain to implement SWE-QA
Agent, restricting it to the three tools of the original benchmark protocol: a
repository structure lookup, a retrieval tool over a vector index, and a file
reader. It has no shell access, no filesystem writing, and no planning tools.
The vector index is built once per repository by splitting each file into chunks,
embedding the chunks with an encoder model, and storing them for similar-
ity retrieval at query time. The second is a Deep Agent that uses the Deep
Agentic search by subagent paradigm. It is a more recent hierarchical design,
and we use the Deep Agent harness from the Deep Agents framework, also
from LangChain, with its default toolset, which includes planning, a virtual
filesystem, and sub-agent delegation. The retrieval configuration for the ReAct
agent, namely chunk size, overlap, index, similarity threshold, and embedding
model, and the full tool contract of the Deep Agent, are given in Appendices A
and B. Figure 3 sets the two action spaces side by side.
The two action spaces are not identical, and they cannot be. The differ-
ence in tools is not a confound that sits alongside the paradigms; it is what

## PDF Page 12

12 A. Rafiei Oskooei et al.
constitutes them. A ReAct agent that was given planning, a task list, and
a delegable sub-agent would be a Deep Agent, and a Deep Agent stripped
of those and handed a vector index would be a ReAct agent. Equalising the
tool sets would therefore not produce a cleaner comparison, it would collapse
the two conditions into one. What we hold fixed instead is everything that is
not constitutive of the paradigms: the same fifteen repositories, the same 720
questions, the same four models, the same judge, and the same rubric, with
each model compared against itself across the two architectures so that the
contrast is paired within a model rather than across models.
We also fixed the framework. Both agents are built on LangChain, using its
ReAct agent harness for the first and its Deep Agents harness for the second,
rather than pairing a research implementation against a commercial assistant.
LangChain is open source, model-agnostic, and not tied to a single vendor’s
models or editor, and it is at the time of writing the most widely used frame-
work for building agents, which makes it a neutral common substrate and one
whose defaults a reader can inspect. Using each harness with its default tool
contract, rather than a tuned variant of our own, also keeps the comparison
closer to what a practitioner adopting either paradigm would actually run.
Both harnesses remain choices, and Section 8 states what follows from that.
Fig. 3The action spaces of the two agents. Both act on the same target repository, and
they differ in what they are allowed to do to it. The ReAct agent is held to the three tools
of the benchmark protocol, namely a file reader, a repository structure lookup, and retrieval
over the vector index. The Deep Agent has the default tool set of its harness, which replaces
retrieval with terminal style exploration and adds planning and delegation to a sub-agent.

## PDF Page 13

Deep Agentic Search for Repo-Level Code QA 13
4.2 Models
We run both architectures with four language models. Three come from a sin-
gle widely used family, namely Gemini 2.5 Flash, Gemini 2.5 Pro, and Gem-
ini 3 Flash. Sampling within one family lets us observe the paradigm effect
across different capability tiers and across model generations while holding the
provider fixed. The fourth, Qwen3-235B, is a strong open-weight model from
a different vendor with a different architecture, and it serves as a cross-vendor
check that any effect we observe is not specific to a single provider. Within
the Deep Agent, the orchestrator and the sub-agent use the same model. This
yields eight conditions, four models crossed with the two architectures. Model
access, temperature, and provider details are given in Appendix C. We derive
monetary cost from measured token counts using a single price sheet, expressed
in USD per one million tokens as input and output: Gemini 2.5 Flash at 0.30
and 2.50, Gemini 2.5 Pro at 1.25 and 10.00, Gemini 3 Flash at 0.50 and 3.00,
and Qwen3-235B at 0.22 and 0.88. Reasoning tokens are billed at the output
rate. Because monetary cost depends on prices that change over time, we also
report the underlying token counts, which are price-independent.
4.3 Dataset
We use SWE-QA (Peng et al., 2026a), a benchmark for repository-level code
question answering over widely used open-source Python projects. Our evalu-
ation covers 15 Python repositories with 48 questions each, for a total of 720
questions per condition. Twelve of these repositories are drawn from SWE-
bench and three from SWE-bench-Live, which is built from more recent issues.
The repositories span a wide range of sizes, from small libraries of about 13
thousand lines of Python to large projects of more than 800 thousand lines. The
questions fall into four interrogative categories, namely What, Why, Where,
and How, in roughly equal proportion. We use the dataset and its rubric as
published and do not modify either.
4.4 Evaluation
Answers are graded by an LLM judge, Claude Sonnet 4.6, which comes from a
different provider and a different model family than every answering model, so
no condition is graded by its own model or by a relative of it. The judge scores
each answer on the five SWE-QA dimensions, namely correctness, complete-
ness, relevance, clarity, and reasoning. The five dimension scores are combined
into a total on a 0 to 100 scale, and each answer receives a three-class verdict,
namely Pass, Partial, or Fail, using the benchmark thresholds of Pass at 70
or above, Partial from 50 up to 70, and Fail below 50. The verdict bands are
applied consistently across all conditions. The full judge prompt and the score
aggregation are given in Appendix D.

## PDF Page 14

14 A. Rafiei Oskooei et al.
Because the two architectures answer the same questions, we compare them
with paired tests within each model. We test the Pass rate difference with the
exact McNemar test and the score difference with the Wilcoxon signed-rank
test. We report Cliff’s delta as a non-parametric effect size for the score differ-
ence, with a 95% bootstrap confidence interval, and the paired standardised
mean differenced z. To control the family-wise error rate across the four mod-
els, we report Benjamini and Hochberg false discovery rate corrected values.
To check that the automatic judge is a sound proxy for human judgement,
we validated it against an independent human panel on a stratified sample.
Three external software engineers, each with at least two years of professional
experience and none a co-author of this paper, rated a sample of 800 answers
drawn evenly across the eight conditions, that is 100 answers per condition,
from the same fifteen repositories. The raters were blind to the condition, the
architecture, and the model behind each answer. Each rater independently as-
signed a Pass, Partial, or Fail verdict, using the same three outcome categories
as the main study, together with a holistic score on a 0 to 100 scale. We then
compared the human panel against the LLM judge.
Table 2 reports the agreement. The internal agreement of the panel was
almost perfect on the verdict, with a Fleiss’ kappa of 0.81. Agreement between
the human majority and the LLM judge was substantial on the verdict, with
a Cohen’s kappa of 0.74, and strong on the numeric score, with a Pearson
correlation of 0.83 and a mean absolute difference of 5.2 points on the 0 to
100 scale. Agreement was slightly lower on Deep answers than on Semantic
answers, for example a kappa of 0.69 against 0.78 on the verdict, which is
consistent with the greater length and complexity of Deep answers. On the
scale of Landis and Koch (1977), these values fall in the substantial to almost
perfect range, which supports the use of the automatic judge as a reliable
proxy for human judgement across both paradigms.
5 Results
This section reports the results on accuracy, cost, and agent behaviour; a
dedicated failure analysis follows in Section 6. Table 3 summarises accuracy,
efficiency, and cost for all eight conditions. Throughout, we refer to the Se-
mantic search paradigm as Semantic and to the Deep Agentic search paradigm
as Deep.
5.1 Accuracy and answer quality
Our first research question concerns accuracy. Pooled across the four models,
Semantic answered a larger share of questions correctly than Deep. Semantic
reached a Pass rate of 65.2% against 46.2% for Deep, and a Fail rate of 21.9%
against 34.4% for Deep (Fig. 5). The ordering held for every individual model
(Fig. 6, Table 3): Semantic obtained a higher Pass rate and a higher mean
score than Deep in all four cases.

## PDF Page 15

Deep Agentic Search for Repo-Level Code QA 15
T able 2Judge validity: agreement between the independent human panel and the LLM
judge on a stratified sample of 800 answers, 100 per condition. The upper block reports the
three-class verdict and the lower block reports the harmonized 0 to 100 score. The panel-
internal row uses Fleiss’ kappa and the human against judge rows use Cohen’s kappa. MAD
is the mean absolute difference in score points.
Categorical verdict (Pass, Partial, Fail)
Comparison N Exact agr. (%)κ[95% CI]
Human panel (Fleiss’κ, three raters) 800 88.5 0.81 [0.78, 0.84]
Human majority vs LLM judge, pooled 800 84.0 0.74 [0.70, 0.78]
Semantic conditions only 400 87.0 0.78 [0.72, 0.84]
Deep conditions only 400 81.0 0.69 [0.63, 0.75]
Numeric score (harmonized 0 to 100)
Comparison N Pearsonr[95% CI] SpearmanρMAD
Human mean vs LLM judge, pooled 800 0.83 [0.81, 0.85] 0.81 5.2
Semantic conditions only 400 0.86 [0.83, 0.88] 0.85 4.1
Deep conditions only 400 0.79 [0.75, 0.82] 0.76 6.8
T able 3Master comparison per condition: accuracy (Pass/Partial/Fail, mean judge score
/100), efficiency (tokens, tool calls, median latency), and cost. The token columns report
prompt and completion tokens only. Reasoning tokens are billed at the completion rate and
are included in the cost, so the cost column is not the product of the two token columns
and the list prices.
Model Search Pass % Partial % Fail % Score In-tok Out-tok Tools Lat (s) Mean$/q$/Pass
Gemini 2.5 FlashSemantic 48.4 15.7 35.9 61.6 303k 1k 9.7 329 0.1029 0.213Deep Agentic 42.8 14.0 43.1 53.7 524k 4k 20.6 106 0.1868 0.436
Gemini 2.5 ProSemantic 54.2 14.7 31.1 63.9 404k 1k 11.4 400 0.5675 1.048Deep Agentic 44.2 17.1 38.7 57.2 466k 4k 15.5 152 0.6749 1.526
Gemini 3 FlashSemantic 89.3 5.4 5.3 89.2 254k 3k 8.6 101 0.1601 0.179Deep Agentic 39.7 27.2 33.1 58.3 577k 3k 44.6 262 0.3407 0.858
Qwen 3 235BSemantic 68.8 15.8 15.4 77.0 34k 1k 3.5 42 0.0085 0.012Deep Agentic 58.2 19.0 22.8 69.3 761k 2k 40.1 105 0.1693 0.291
The size of the advantage varied considerably by model. The paired within-
model comparison (Table 4, Fig. 7) shows a Pass rate difference in favour of
Semantic of 5.6 percentage points for Gemini 2.5 Flash, 10.0 for Gemini 2.5
Pro, 10.6 for Qwen3-235B, and 49.6 for Gemini 3 Flash. All four McNemar
tests and all four Wilcoxon tests remained significant after false discovery rate
correction. The effect size on the score, measured by Cliff’s delta, was about
0.14 for the two Gemini 2.5 models, 0.24 for Qwen3-235B, and 0.76 for Gemini
3 Flash. We therefore describe the accuracy result as consistent in direction
across all four models, modest in magnitude for the Gemini 2.5 pair, and large
only for Gemini 3 Flash.
Because the Pass rate is defined by a fixed cutoff, part of a difference
expressed in percentage points reflects where the score distributions sit relative
to that cutoff rather than the size of the underlying difference. This is most
visible for Gemini 3 Flash, where a score difference of 30.9 points corresponds
to a Pass rate difference of 49.6 percentage points, because a large share of
its answers falls close to the threshold. We therefore repeated the comparison

## PDF Page 16

16 A. Rafiei Oskooei et al.
across the full range of plausible cutoffs (Fig. 4). Sweeping the Pass threshold
from 50 to 90 changes the magnitude of the gap considerably, from 27.8 to
63.1 percentage points for Gemini 3 Flash and from 7.4 to 19.6 for Qwen3-
235B, but it does not change the ordering. Semantic exceeded Deep at every
threshold for every model, and the smallest gap anywhere on the grid was 3.8
percentage points. The threshold-free measures reported above, namely the
Wilcoxon test on the scores and Cliff’s delta, do not depend on this choice,
and we treat them as the primary evidence for the accuracy result.
Fig. 4Sensitivity of the accuracy comparison to the Pass threshold. Each line is the Pass
rate of Semantic minus the Pass rate of Deep for one model, as the cutoff is swept from 50
to 90 on the 0 to 100 judge scale. The dashed line marks the benchmark cutoff of 70. The
magnitude of the gap depends on the cutoff, but every line stays above zero, so the ordering
does not.
T able 4Paired within-model comparison of Semantic against Deep. Positive values indicate
that Semantic is higher. The Pass rate difference is in percentage points and the score
difference is on a 0 to 100 scale, each with a 95% bootstrap confidence interval. The McNemar
value is corrected for false discovery rate across the four models.
Model N Pass diff (pp) McNemarqScore diff Cliff’sδ d z
Gemini 2.5 Flash 720 5.6 [1.3, 9.8] 1.2×10 −2 8.0 [5.3, 10.6] 0.137 [0.090, 0.186] 0.220
Gemini 2.5 Pro 720 10.0 [5.4, 14.6] 4.5×10 −5 6.7 [4.2, 9.4] 0.138 [0.089, 0.188] 0.190
Gemini 3 Flash 720 49.6 [45.6, 53.3] 3.4×10 −93 30.9 [29.0, 33.0] 0.760 [0.727, 0.793] 1.125
Qwen3-235B 720 10.6 [6.4, 14.9] 2.9×10 −6 7.7 [5.9, 9.7] 0.235 [0.191, 0.283] 0.296
The verdict distribution (Fig. 8) shows that Deep did not simply convert
Pass answers into Partial answers; it also produced a larger share of out-
right failures for every model. The score distributions (Fig. 9) make the same
point at finer resolution: Semantic concentrates mass in the high score region,

## PDF Page 17

Deep Agentic Search for Repo-Level Code QA 17
whereas Deep carries more mass in the low tail, most visibly for Gemini 3
Flash.
The advantage was not uniform across repositories (Fig. 10). Pooling scores
across the four models, Deep exceeded Semantic on only one of the fifteen
repositories, django, by 3.0 points. Semantic led on the remaining fourteen, by
margins of up to 22.9 points on streamlink. This heterogeneity indicates that
Deep can be competitive on a particular repository, but that such cases were
the exception rather than the rule in our sample. The advantage of Seman-
tic did narrow as repository size grew, and across the fifteen repositories that
trend was statistically detectable (Spearman’s rho of−0.69,p= 0.004, against
repository size in thousands of lines of Python). It did not reverse anywhere in
our range: the largest repository in the sample, sympy at about 861 thousand
lines of Python, still favoured Semantic by 13.7 points, and the single reposi-
tory on which Deep led is mid-sized rather than large. We therefore read the
size relationship as a narrowing margin rather than as a crossover, and note
that establishing where, if anywhere, it crosses would need repositories larger
than the ones studied here.
Across the five quality dimensions (Fig. 11), Semantic scored higher than
Deep on all five when pooled over the four models. The smallest gap was on
relevance (about 10 points on the 0 to 100 scale) and the remaining four gaps
were comparable, between about 13 and 15 points. Because the five dimensions
carry equal weight in the total, we also examined correctness on its own, where
Semantic led for every model, by between 7.3 and 30.2 points. Individual
models showed some variation in which dimension separated the paradigms
most, but no dimension favoured Deep on average.
Finally, the advantage held across all four question types (Fig. 12). Pooled
over models, the Semantic Pass rate exceeded the Deep Pass rate for What,
Why, Where, and How questions, with a fairly uniform gap of roughly 17
to 20 percentage points. Both paradigms found Why questions easiest and
How questions hardest, which suggests that question type shifts the absolute
difficulty for both paradigms without changing which paradigm is preferable.
Fig. 5Overall outcome pooled across the four models. Semantic answers a larger share of
questions at the Pass level and a smaller share at the Fail level than Deep.

## PDF Page 18

18 A. Rafiei Oskooei et al.
Fig. 6Pass rate of Semantic and Deep for each model. Semantic is higher for every model,
with the largest gap on Gemini 3 Flash.
Fig. 7Paired effect sizes of Semantic relative to Deep with 95% confidence intervals. Pos-
itive values favour Semantic. Every result remains significant after false discovery rate cor-
rection.
5.2 Computational cost and efficiency
Our second research question concerns computational and monetary cost. Deep
was more expensive than Semantic on the token and dollar measures for ev-
ery model (Table 3). Deep consumed more input tokens than Semantic in all
four cases; the difference was smallest for the Gemini 2.5 pair and largest for
Qwen3-235B, where Semantic used about 34 thousand input tokens per ques-
tion against about 761 thousand for Deep. The mean dollar cost per question
was higher for Deep than for Semantic for every model.

## PDF Page 19

Deep Agentic Search for Repo-Level Code QA 19
Fig. 8Verdict distribution for all eight conditions. Deep shifts mass from Pass toward Fail
relative to Semantic for every model.
Fig. 9Judge score distribution per condition, with the Pass and Fail thresholds marked.
Semantic concentrates mass at high scores, while Deep carries more mass in the low tail.
Because Deep was both less accurate and more costly, it did not lie on
the efficient frontier of the accuracy against cost trade-off. Figure 13 places
the eight conditions in the accuracy and cost plane: the Semantic conditions
occupy the upper-left region of higher accuracy at lower cost, while the Deep
conditions sit lower and to the right. The same pattern appeared at the repos-
itory level (Fig. 13), where the Semantic points for each model clustered at
lower cost than the corresponding Deep points. The practitioner-facing view,

## PDF Page 20

20 A. Rafiei Oskooei et al.
Fig. 10Mean judge score by repository for all eight conditions on a common 0 to 100 scale.
Deep matched or exceeded Semantic on only one of the fifteen repositories.
the cost per correct answer, tells the same story (Fig. 14): for every model,
Deep cost more per Pass than Semantic, for example 0.179 against 0.858 dol-
lars for Gemini 3 Flash and 0.012 against 0.291 dollars for Qwen3-235B. Pooled
across the four models, a correct answer cost 0.32 dollars with Semantic against
0.74 dollars with Deep, so Deep was about 2.3 times more expensive for each
question it answered correctly.
Latency did not order the two paradigms consistently. The median latency
was lower for Deep than for Semantic for the Gemini 2.5 pair and higher for
Deep for Gemini 3 Flash and Qwen3-235B (Table 3). Latency was also heavy-
tailed and was affected by the execution environment, so we treat tokens and
dollar cost as the primary cost measures and interpret latency cautiously.
A natural question is whether the extra effort that Deep spends is simply
the price of harder questions, or whether it buys accuracy. Figure 15 plots
the per-question score against the amount of effort, measured by total input
tokens and by total tool calls. For both paradigms the fitted slope is flat to
negative: spending more tokens or making more tool calls was not associated
with higher scores. This relationship is correlational, and it partly reflects that

## PDF Page 21

Deep Agentic Search for Repo-Level Code QA 21
Fig. 11Per-dimension quality profile. Left: mean judge sub-score on each of the five di-
mensions for every model, comparing Semantic and Deep Agentic search. Right: the five
dimensions pooled across the four models. Semantic is higher than Deep Agentic on every
dimension.
Fig. 12Pass rate by question type for each model. Semantic exceeds Deep for every question
type, with a roughly uniform gap.
harder questions require more effort and also score lower, so we do not interpret
it causally. It does show, however, that within our data additional effort was
not accompanied by additional accuracy.
We also tested whether the cost gap grows with repository size, since one
might expect dynamic exploration to scale worse than a pre-built index on
larger repositories. Figure 16 plots the per-question ratio of Deep to Seman-

## PDF Page 22

22 A. Rafiei Oskooei et al.
tic effort against repository size. We found no significant association between
the overhead ratio and repository size, but with only fifteen repositories the
interval is wide, so we treat this as inconclusive rather than as evidence of no
relationship. What the data do show is that the Deep overhead was present at
every repository size in our sample rather than appearing only on the largest
repositories.
Fig. 13Accuracy against cost. Bottom: the eight conditions in the accuracy and cost plane;
Semantic conditions occupy the higher-accuracy, lower-cost region and the dashed line marks
the efficient frontier. Top: the same trade-off at the repository level, one panel per model,
each point a repository (dashed line marks Pass at 70).
5.3 Agent behaviour
Our third research question concerns how the two architectures behave and
how they fail. This subsection reports the two behavioural measures, tool usage
and trajectory length; the analysis of how and why the agents fail follows in
Section 6.
Tool usage.The tool-usage distribution (Fig. 17) shows how each architec-
ture spent its actions. Semantic distributed its calls across only three tools,
principally retrieval (43.6%) and file reading (43.2%), with the remainder on

## PDF Page 23

Deep Agentic Search for Repo-Level Code QA 23
Fig. 14Effective cost per correct answer. For every model, the Deep point sits at a higher
cost per Pass than the Semantic point.
Fig. 15Per-question score against effort, measured by input tokens and by tool calls, with
ordinary least squares fits. Slopes are flat to negative for both paradigms.
structure lookup (13.3%). Deep had a larger toolset, and once the actions of
its delegated sub-agent are counted alongside the planner’s own, the great ma-
jority of its activity was ordinary reading and searching: file reading (41.6%)
and text search (29.1%) together accounted for more than two thirds of its
calls, followed by task-list writing (10.9%), directory listing (8.3%), sub-agent
delegation (7.0%), and file globbing (3.1%).
Counting delegations as a share of all calls understates how much of the
work they govern, because a delegation is a single call that opens an entire
sub-agent trajectory. Of the 2,878 Deep runs, 2,395 delegated at least once,
2.1 times per run on average, and each delegation ran about ten further calls
of its own. Taken together, 68.8% of all Deep tool calls were issued inside a
delegated sub-agent rather than by the planner. Measured within the planner’s
own context, delegation was its second most frequent action at 22.4%, behind

## PDF Page 24

24 A. Rafiei Oskooei et al.
Fig. 16Ratio of Deep to Semantic per-question effort against repository size, pooled over
models. No significant association is detected, though with fifteen repositories the test is
underpowered and the result is inconclusive.
only task-list writing. The deep agent therefore spent most of its budget on
the same reading and searching operations that are available in principle to a
simpler agent, but it spent it at one remove, with more than two thirds of that
activity taking place in a context the planner never saw directly. Section 6
returns to this point, because the hand-off that governs those two thirds is
also where the largest share of Deep failures occurred.
Trajectory length and success.The relationship between trajectory length and
success (Fig. 18) followed a diminishing-returns pattern in both architectures.
Once a run was under way, the Pass rate fell as the number of tool calls
per question grew, and it did so over a much longer range for Deep, whose
trajectories extend well past fifty calls once the actions of its sub-agent are
counted. The very shortest Deep trajectories are the exception, and they are
low for a different reason: they are dominated by runs that stalled before doing
any real work. Away from that end, longer trajectories were associated with
lower rather than higher success, which is consistent with the reading that
questions requiring extended exploration are also the harder questions and
that extended exploration did not recover them.
6 Failure Analysis
This section answers the remainder of our third research question, namely how
and why each architecture fails. We coded every failure and then examine the
resulting distributions and what they reveal.

## PDF Page 25

Deep Agentic Search for Repo-Level Code QA 25
Fig. 17Tool-call distribution by paradigm, pooled across the four models, counting the
calls of the delegated sub-agent alongside the planner’s own. Deep spreads its calls across
more tools but is dominated by reading and searching. Delegation is 7.0% of its calls, yet
those calls open the sub-agent trajectories in which 68.8% of all Deep tool calls are made.
Fig. 18Pass rate against the number of tool calls per question. Bins containing fewer than
ten questions are omitted as too sparse to interpret. In both paradigms, longer trajectories
were associated with lower Pass rates.
6.1 Failure Analysis Methodology
We coded every failure, defined as a run with a Fail verdict, on two orthogonal
axes. The mechanism axis records the root behavioural cause of the failure,
and the symptom axis records what was wrong with the answer, so that the
mechanism does not depend on the answer content and the symptom does not
depend on how the answer was produced. Each failure was distilled from its
recorded trace into a compact record holding the question, the reference an-
swer, the judge’s rationale, the agent’s answer, and the cleaned tool sequence,
and every record was then coded on both axes by Claude Sonnet 4.6. To vali-

## PDF Page 26

26 A. Rafiei Oskooei et al.
date this coding, two of the authors independently coded a stratified random
sample of 400 failures, about a quarter of the failure set. Agreement between
the two authors, measured by Cohen’s kappa, was 0.86 on the symptom (90.5%
raw agreement) and 0.78 on the mechanism (83.5% raw agreement), and agree-
ment between their consensus labels and the automatic coding was 0.82. On
the scale of Landis and Koch (1977) these values are substantial to almost
perfect. Disagreements between the authors were resolved by discussion to
consensus after review of the full execution traces.
6.2 Failure taxonomy
The taxonomy has six mechanism codes and five symptom codes. The mecha-
nisms are a coordination breakdown, in which the planner to sub-agent hand-
off fails to produce or integrate a usable result and which is possible only for
the Deep Agent; a retrieval or localization miss, in which substantial search
and read effort never surfaces the correct file or entity; insufficient grounding,
in which a confident answer is produced after little or no reading; evidence
misinterpreted, in which the agent reads the correct file but misreports or
overreaches in synthesis; a non-terminating loop, in which the control loop
cycles or stalls without producing an answer; and an evidence-gathering fail-
ure, in which tool calls return errors and the run never obtains the material it
needs. The symptoms are no answer; premise denial, a claim that the requested
code does not exist; a wrong entity or mechanism, a confident answer about
the wrong file or mechanism; factually incorrect, a wrong statement about the
right entity; and incomplete or shallow, an on-topic answer that omits most
of the required detail.
6.3 Failure distributions
Figure 19 reports the failure mechanism by architecture. The association is
very strong, with a chi-square of 508.8 on five degrees of freedom and a
Cramer’sVof 0.56. Part of that association is definitional, because a co-
ordination breakdown can only arise in a hierarchical design. Restricting the
comparison to the five mechanisms available to both architectures removes
that component, and the association remains large, with a chi-square of 147.2
on four degrees of freedom and a Cramer’sVof 0.35. The largest share of
Deep failures is the coordination breakdown, at 41.8% of them and none for
Semantic, because a flat retrieval agent has no planner to sub-agent hand-off
that can break. Semantic failures instead concentrate in retrieval and local-
ization. The symptom is associated with the architecture much less strongly
(Fig. 20, chi-square 43.8, Cramer’sVof 0.16), so the two architectures pro-
duced wrong answers of broadly similar shape while reaching them through
different mechanisms. Figure 21 traces which mechanism leads to which symp-
tom, and the mapping is close to deterministic for several mechanisms: the

## PDF Page 27

Deep Agentic Search for Repo-Level Code QA 27
non-terminating loop flows almost entirely to no answer, while the coordina-
tion breakdown fans mostly to a confident but wrong entity. Table 5 gives the
full numbers, including the severity of each mechanism, measured by the mean
judge score among its failures. Two mechanisms often end without a usable
answer. The non-terminating loop scores close to zero, at a mean of 3.3, and
the evidence-gathering failure scores higher at 18.8 but still well below the
content mechanisms, which cluster near thirty.
Fig. 19Failure mechanism by architecture, as a percentage of each architecture’s own
failures. Semantic is on the left and Deep on the right. The two architectures fail through
different mechanisms.
Fig. 20Answer symptom by architecture, as a percentage of each architecture’s own fail-
ures. The symptom differs between the architectures far less than the mechanism does.

## PDF Page 28

28 A. Rafiei Oskooei et al.
Fig. 21How each failure mechanism maps to an answer symptom, pooled across both
architectures. Ribbon width is proportional to the number of failures.
T able 5Full failure-analysis results. Upper block: the six failure mechanisms, each as a
percentage of the architecture’s own failures with counts in parentheses, together with the
pooled share of that mechanism that produced no answer and its mean judge score. Lower
block: the five answer symptoms by architecture. The failure set contains 1,621 failures, 631
for Semantic and 990 for Deep. Mechanism by architecture:χ 2 = 508.8, Cramer’sV= 0.56;
over the five mechanisms available to both architectures,χ 2 = 147.2, Cramer’sV= 0.35.
Symptom by architecture:χ 2 = 43.8, Cramer’sV= 0.16. Agreement on a stratified 400-
failure subsample: Cohen’s kappa 0.86 (symptom) and 0.78 (mechanism) between the two
author annotators, and 0.82 between their consensus and the automatic coding.
Mechanism Semantic Deep No answer (%) Mean score
Coordination breakdown 0.0 (0) 41.8 (414) 9.4 30.5
Retrieval or localization miss 53.6 (338) 24.4 (242) 6.0 29.0
Insufficient grounding 18.1 (114) 6.0 (59) 4.6 33.3
Evidence misinterpreted 17.1 (108) 5.4 (53) 0.0 38.4
Non-terminating loop 2.9 (18) 13.5 (134) 98.7 3.3
Evidence-gathering failure 8.4 (53) 8.9 (88) 62.4 18.8
Symptom Semantic Deep
Wrong entity or mechanism 48.2 (304) 42.3 (419)
No answer 12.7 (80) 24.2 (240)
Factually incorrect 15.2 (96) 15.1 (149)
Premise denial 14.9 (94) 8.5 (84)
Incomplete or shallow 9.0 (57) 9.9 (98)
6.4 Key findings
The Semantic search signature.Semantic failures were about finding and read-
ing the right code rather than reasoning about it. Its largest mechanism was
a retrieval or localization miss, in 53.6% of Semantic failures, and these were
high-effort misses, with a mean of 12.6 tool calls spent on searches that never
resolved to the right file. A further 18.1% answered on too little evidence, and

## PDF Page 29

Deep Agentic Search for Repo-Level Code QA 29
17.1% read the genuinely correct file but misread it, the last of these reading
roughly four times as many files as a retrieval miss, which indicates that the
correct material was in the context and was misread rather than never found.
At the level of the answer, Semantic was also more likely than Deep to declare
that the requested code did not exist, in 14.9% of its failures against 8.5%,
though this gap was not uniform across the four models.
The Deep Agent signature.Deep failures were dominated by the coordination
machinery itself. Coordination breakdown accounted for 41.8% of Deep failures
and has no counterpart in a flat retrieval agent, and a further 13.5% were non-
terminating loops. Deep was also far more likely to return nothing at all, in
24.2% of its failures against 12.7% for Semantic. The coordination breakdown
itself, however, was usually not a visible blank: in 91% of these cases the agent
still returned a fluent, confidently worded answer rather than reporting that
anything had gone wrong, so the breakdown was not apparent from the output
alone. A hierarchical delegation that yields fluent but ungrounded answers of
this kind is consistent with the general difficulty of transferring decisions and
context across an agent-to-agent hand-off, rather than with a reasoning error
about the code.
Silent and visible failures.The two signatures also differ in how visible they
are. Semantic tended to fail with a fluent, confident, and wrong answer, whereas
Deep failed either with such a confident wrong answer from a coordination
breakdown or, more often than Semantic, with no answer at all. The deep
architecture therefore did not remove failures; it added a class of failure, in its
coordination, that a flat retrieval agent cannot have, and that failure is often
silent.
7 Discussion
Our central result runs against the prevailing direction of practice. For read-
only repository-level code question answering, across four models and fifteen
repositories, an index-backed Semantic search agent matched or exceeded a
delegation-based Deep Agentic search agent in accuracy while costing less.
The momentum in industry is toward more elaborate Deep Agentic search, so
a finding that the simpler and older paradigm is at least as accurate calls for
an explanation rather than a restatement of the numbers.
We read the failure analysis as an account of why the additional machinery
did not pay off. The premise of Deep Agentic search is a form of context
engineering (Anthropic, 2025): a sub-agent absorbs the noisy exploration and
returns a condensed result, so that the orchestrator can reason over clean
material. That same hand-off, however, is where the paradigm most often broke
in our data. The dominant Deep failure was a coordination breakdown that
has no analogue in a flat agent, and it was usually silent, producing a confident
but wrong answer rather than a visible error. This is consistent with a growing

## PDF Page 30

30 A. Rafiei Oskooei et al.
argument among practitioners that multi-agent systems are fragile (Cognition,
2025) precisely because decisions and context do not transfer reliably across an
agent-to-agent boundary. On a task whose difficulty is dominated by locating
and correctly reading the right code, introducing that boundary added a class
of failure that outweighed whatever it was meant to prevent.
Accuracy, however, is not the only reason a practitioner would reach for
Deep Agentic search, and our study is not positioned to observe the others.
The purpose of the paradigm is to keep the main reasoning context uncluttered
by delegating the raw exploration elsewhere. In a modern agentic workflow a
session is long-running and spans many tasks, and a developer cannot reset the
context after every question without discarding the state that has accumulated
over the session. Under those conditions, keeping the orchestrator’s context
clean has value in its own right (Manus, 2025; LangChain, 2025), independent
of the correctness of any single answer. Our experiments isolate one read-
only question at a time, a setting in which that benefit cannot express itself
as accuracy. We therefore read our result narrowly: on single-question, read-
only question answering over an indexable repository, the accuracy cost of the
coordination outweighs its context-hygiene benefit. Whether the balance shifts
in a long, multi-task session is a question our design cannot answer, and we
regard it as an important open one.
A second boundary condition concerns whether an index exists at all. Se-
mantic search presupposes that the repository can be indexed in advance.
Agents that operate from a terminal often work over a filesystem that is too
large, too volatile, or too arbitrary to index ahead of time, and in that regime
dynamic exploration is not a preference but a necessity. That boundary is
not only about size. A repository changes, and an index is a snapshot of it.
Where the working tree moves quickly, on a branch under active development
or in a pipeline that builds many commits a day, the index has to be rebuilt
or incrementally updated to stay faithful, and an answer served from a stale
index is wrong in a way that is difficult to notice. The monetary side of that
upkeep is minor, since only the chunks a change touches need re-embedding
and embedding all fifteen repositories in full cost under one dollar in total,
but the operational side is real, because change detection, invalidation, and
re-embedding are infrastructure that has to be built, run, and monitored. Live
exploration carries none of it. It reads whatever is on disk at the moment it is
asked, so it is never stale and needs no warm-up, and that is a genuine advan-
tage of the exploration paradigm that neither our accuracy nor our cost figures
capture. Our measurements were taken on fixed repository snapshots, which
is what the benchmark defines and is also the condition most favourable to
an index. Deep Agentic search remains the primary option wherever an index
is impractical, or would be stale by the time it is queried. Our comparison is
therefore about the regime in which both paradigms are genuinely available,
namely a stable and indexable codebase queried in a read-only fashion, and it
should not be read as a general verdict against exploration.
Taken together, these considerations point to a pragmatic reading rather
than a winner. For the common case of read-only question answering over

## PDF Page 31

Deep Agentic Search for Repo-Level Code QA 31
an indexable repository, an index-backed retrieval agent is the stronger and
cheaper default, and the heavier orchestration of a deep agent should be jus-
tified by needs that a single-answer accuracy metric does not capture, such as
context hygiene across long sessions, environments that cannot be indexed, or
tasks that write and execute code. A design that follows naturally from our re-
sults is a hybrid that retains a cheap semantic index for retrieval and reserves
delegated exploration for the questions, repositories, or tasks that genuinely
require it. We leave the construction and evaluation of such a router to future
work.
8 Threats to Validity
Construct validity.Each paradigm is instantiated through one harness. We
deliberately chose widely used, general-purpose open-source implementations
rather than a harness tuned by a model provider to its own family, so that nei-
ther paradigm benefited from provider-specific optimisation. Other harnesses
implement delegation differently, and our results should be read as applying to
this pairing rather than to every possible implementation of the two paradigms.
The two paradigms differ in both their tool space and their orchestration, and
these two aspects co-vary by design. We therefore read the comparison as one
between two cohesive, real-world paradigm bundles, one standing for index-
backed assistants and one for exploration-based assistants, rather than as a
single-factor ablation, because that is the level at which the choice is made in
practice.
Within that reading, a harness still carries design decisions that are not
part of the paradigm it implements, including the wording of its system prompt,
how its tool descriptions are phrased, how sub-agent results are summarised
before they are returned, and how many steps it permits. These choices are
known to affect agent behaviour, and configuration is itself an object of study
for deployed coding agents (dos Santos et al., 2026; Liu et al., 2026), so a
different implementation of the same paradigm could shift the size of the gap
we report. We did not run a sensitivity analysis across alternative deep agent
harnesses, such as other production agent frameworks (Wang et al., 2026c),
and we do not claim that the magnitude we measure is invariant to that choice.
Three things bound what this can explain. The harness is held constant across
all four models within a paradigm, so any overhead it imposes is a fixed prop-
erty of that arm rather than something that varies with the comparison. The
direction of the result is the same for all four models and for both vendors,
which a quirk of one model’s interaction with one prompt would not produce.
And the failure analysis locates the dominant Deep mechanism at the planner
to sub-agent hand-off, which is the defining structural feature of the paradigm
rather than an incidental setting of the harness. We regard a systematic com-
parison across harnesses as the natural next study rather than as a gap this
one silently leaves open.

## PDF Page 32

32 A. Rafiei Oskooei et al.
Internal validity.Answers were graded by an automatic judge, which raises
the risk that the judge rather than the answer drives the result. We addressed
this in three ways: the judge is drawn from a different provider and a different
model family than any answering model, so it can neither prefer its own out-
puts nor favour a family it belongs to, and the one comparison that a family
preference could in principle distort, between models of different families, is
not a comparison this study makes, since every contrast is paired within a sin-
gle model; we validated it against an independent human panel on a stratified
sample and found substantial to almost perfect agreement (Section 4, Table 2);
and we report a non-parametric effect size alongside each significance test. Be-
cause every comparison is paired within a model and varies only the paradigm,
incidental factors such as answer length act on both conditions at once, and
in our data the deep agent scored lower rather than higher, so any preference
of the judge for longer answers would work against our conclusion rather than
for it. Latency was heavy-tailed and sensitive to the execution environment,
so we base no conclusion on it.
External validity.Our evidence comes from a single benchmark, SWE-QA,
four language models, and Python repositories, so the findings may not trans-
fer to other benchmarks, other models, or other languages. Covering more
models would strengthen the claim, but running the benchmark and, more
importantly, coding agent behaviour and failures from execution traces carry
a substantial cost in computation and in manual effort, which bounds how
much a single study can cover. We therefore report our findings within the
boundary of these models, this benchmark, and these harnesses. These reposi-
tories are widely used and are likely to be represented in model training data.
Our design limits what that can do to the comparison: every comparison is
paired within a model on the same question, so both paradigms draw on the
same parametric knowledge, and memorisation raises both arms rather than
creating a difference between them. As a further check we split the reposito-
ries by provenance, since twelve are drawn from SWE-bench and three were
added later from SWE-bench-Live to reduce leakage. Semantic led on both
subsets for every model, and the pooled advantage was somewhat larger on
the three later repositories, 15.9 against 12.7 points, which is the opposite of
what an advantage driven by memorisation would predict. We treat this as a
descriptive check rather than a test, since the later subset contains only three
repositories and all fifteen are long-standing projects whose code may predate
the model cutoffs, so we do not claim that contamination is excluded, only
that we find no sign of an asymmetric effect. Repository sizes were measured
on the current default branch as a proxy for the benchmark snapshot.
Conclusion validity.We drew on four models and used paired, non-parametric
tests, applying Benjamini and Hochberg false discovery rate correction across
the family of comparisons and reporting bootstrap confidence intervals for
the effect sizes. The direction of the accuracy result was the same for all
four models, which makes it unlikely to be an artifact of a single model or

## PDF Page 33

Deep Agentic Search for Repo-Level Code QA 33
of multiple testing. Because questions are nested within repositories rather
than fully independent, we repeated the comparison with a bootstrap that
resamples whole repositories, and the score difference remained in favour of
Semantic for all four models, with every interval excluding zero. Because the
Pass rate depends on a fixed cutoff, we also swept that cutoff from 50 to 90
and found that the direction of the difference held for every model at every
threshold (Fig. 4), so the result is not an artifact of the particular threshold
used by the benchmark.
9 Conclusion and Future Work
We presented an empirical comparison of Semantic search and Deep Agen-
tic search for repository-level code question answering. Across four language
models and fifteen Python repositories, we measured accuracy, cost, agent
behaviour, and failure modes on the SWE-QA benchmark.
The results were consistent in direction. For every one of the four models,
Semantic search matched or exceeded Deep Agentic search in accuracy, and ev-
ery paired difference remained significant after false discovery rate correction,
with a magnitude that ranged from modest for the Gemini 2.5 pair to large
for Gemini 3 Flash. Semantic search also consumed fewer input tokens and
cost less per correct answer for every model, and the additional effort spent by
the deep agent was not associated with higher accuracy. The failure analysis
accounts for the gap rather than merely restating it: the deep agent did not
remove failures but added a class of coordination failure, absent from a flat
retrieval agent and often silent, that its extra machinery did not offset on this
task. These findings apply to read-only question answering over repositories
that can be indexed in advance, and they should not be extended to multi-turn
code editing or to tasks that execute code. Within that setting, they offer a
data-driven counterpoint to the current preference for more elaborate Deep
Agentic search over index-backed retrieval, at least for read-only question an-
swering over an indexable repository, while leaving room for Deep Agentic
search where an index is impractical or where a long, multi-task session places
a premium on keeping the orchestrator’s context clean.
Several directions follow from this study. A compute-matched baseline that
equalises the token budget across the two paradigms would separate the effect
of the search strategy from the effect of the compute it consumes. Extending
the comparison beyond Python and to a contamination-controlled benchmark
would test how far the findings generalise. Finally, our results motivate a
hybrid design that keeps a cheap semantic index for routine retrieval and
reserves delegated exploration for the questions, repositories, or tasks that
genuinely require it, and building and evaluating such a router is the natural
next step.
AcknowledgementsThis work is supported by the Scientific and Technological Research
Council of Turkey (TUBITAK). The authors are grateful for the resources and opportunities

## PDF Page 34

34 A. Rafiei Oskooei et al.
provided by the council for this research. The study was carried out in collaboration be-
tween the R&D Center of Intellica Business Intelligence and researchers at Yildiz Technical
University.
A Agent harnesses and tool contracts
A.1 Semantic search (ReAct agent)
The Semantic search agent uses the ReAct agent harness from LangChain (create agent())
in the LangChain (version 0.3 and later) and LangGraph ecosystem.
– Library reference.LangChain standard agent implementation
(langchain.agents.create agent).
– T ool contract.Restricted strictly to the three tools defined in the SWE-QA bench-
mark:get repo structure,search rag, andread file. The agent has no shell access,
no filesystem writing, and no planning tools.
A.2 Deep Agentic search (Deep Agent)
The Deep Agentic search architecture uses the Deep Agent harness from the official
langchain-deep-agentslibrary.
– Library reference.Officiallangchain-deep-agentsrepository (https://github.com/
langchain-ai/deep-agents).
– T ool contract.The default toolset of the framework, comprising task-list planning
(write todos), sub-agent delegation (task), text search (grep), file listing and glob-
bing (ls,glob), and file reading (read file). The orchestrator and the sub-agent are
instantiated with the same model.
B RAG ingestion and retrieval configuration
B.1 Chunking strategy
– Splitter.RecursiveCharacterTextSplitterconfigured for source code.
– Chunk size.500 tokens (about 2,000 characters).
– Chunk overlap.50 tokens (about 200 characters), to preserve context continuity across
chunk boundaries.
B.2 Embedding model
– Model.Dense vector embeddings usingtext-embedding-3-small(1,536 dimensions).
– Normalization.L2 normalized vectors for cosine distance.
B.3 Indexing and vector database
– Database engine.Chroma vector database, instantiated separately per repository.
– Retrieval metric.Cosine similarity.
– T op-kchunks.k= 10 chunks retrieved persearch ragcall.
– Scope.Each repository is indexed prior to benchmark execution, so the ingestion cost
is paid once per repository.

## PDF Page 35

Deep Agentic Search for Repo-Level Code QA 35
C Model parameters and execution environment
C.1 Inference hyperparameters
To ensure comparability across all conditions, deterministic sampling parameters were en-
forced.
– T emperature.0.0 (greedy decoding) across all four answering models (Gemini 2.5
Flash, Gemini 2.5 Pro, Gemini 3 Flash, and Qwen3-235B) and the judge.
– T op-pand top-k.1.0 and default.
– Presence and frequency penalty .0.0.
– T ermination.Each question was bounded by a wall-clock limit of 900 seconds and a
recursion limit of 80 steps on the agent graph. At roughly ten seconds for a tool call
and its observation, the two bounds are of the same order, so neither is redundant. A
run reaching either bound was kept in the results as a failure rather than retried.
C.2 API providers and endpoints
– Gemini models.Gemini 2.5 Flash, Gemini 2.5 Pro, and Gemini 3 Flash are served
through Google Cloud Vertex AI using thegoogle-genaiandlangchain-google-genai
SDKs.
– Qwen3-235B.Served through an open-weight cloud inference provider (Azure AI
Foundry endpoints).
– Judge.Claude Sonnet 4.6, served through the Anthropic API. The judge therefore runs
on a different provider from every answering model as well as being a different model.
C.3 Execution environment and software dependencies
– Python environment.Python 3.11 or later, managed withuv.
– Core libraries.langchain(≥0.3.0),langgraph(≥0.2.0),langchain-deep-agents, and
pydantic(≥2.0).
– Operating system.Ubuntu Linux 22.04 LTS (x86 64).
– Filesystem isolation.Every question is executed in an isolated thread with a clean
workspace containing only the target repository. Cross-repository access is blocked.
D Judge evaluation and rubric
D.1 Judge prompt template
The judge model is Claude Sonnet 4.6, which is independent of the four answering models
and of their providers. The evaluation prompt is reproduced below.
You are an expert software engineering evaluator. Your task
is to grade a candidate LLM agent’s answer to a code question
about a repository against the reference ground-truth answer.
[QUESTION]
{question}
[REFERENCE ANSWER]
{reference_answer}

## PDF Page 36

36 A. Rafiei Oskooei et al.
[CANDIDATE ANSWER]
{candidate_answer}
Evaluate the candidate answer across 5 dimensions on a 0-10
integer scale:
1. Correctness: Does the answer correctly state technical
facts and mechanisms?
2. Completeness: Does the answer address all parts of the
question?
3. Relevance: Is the content directly focused on the question
without fluff?
4. Clarity: Is the explanation well-structured and easy to
follow?
5. Reasoning: Is the step-by-step logic sound and supported
by code evidence?
Output your evaluation in valid JSON format:
{
"correctness": <0-10>,
"completeness": <0-10>,
"relevance": <0-10>,
"clarity": <0-10>,
"reasoning": <0-10>,
"rationale": "<brief explanation>"
}
D.2 Score harmonization and verdict
The five dimension scores are combined into a total on a 0 to 100 scale:
Total = 2×(Correctness + Completeness + Relevance + Clarity + Reasoning).
The verdict follows the benchmark thresholds:
– Pass.Total score≥70.
– Partial.50≤Total score<70.
– F ail.Total score<50.
E Cost of running the study
Table 6 reports what it cost to produce the measurements in this paper, covering agent
inference for all eight conditions and the one-time construction of the vector indexes. All
figures are estimates derived from measured token counts and published prices. Agent in-
ference dominates. Index construction is negligible by comparison: embedding all fifteen
repositories, about 21 million tokens in total, costs under$1, and that cost is paid once per
repository and then amortised over every question and every condition. Charging the entire
index cost to a single Semantic condition would add about$0.0006 per question, which does
not change any of the cost comparisons reported in Section 5.

## PDF Page 37

Deep Agentic Search for Repo-Level Code QA 37
T able 6Estimated cost of the study in USD, covering agent inference and index construc-
tion. Per-question figures are means over the questions in that condition. All values are
estimates derived from measured token counts and published prices.
Model Paradigm Per question Total
Gemini 2.5 Flash Semantic$0.103$74.09
Gemini 2.5 Flash Deep$0.187$134.53
Gemini 2.5 Pro Semantic$0.568$408.58
Gemini 2.5 Pro Deep$0.675$485.26
Gemini 3 Flash Semantic$0.160$115.24
Gemini 3 Flash Deep$0.341$245.32
Qwen3-235B Semantic$0.009$6.12
Qwen3-235B Deep$0.169$121.92
Agent inference, all eight conditions$1591.06
Vector index construction, 15 repositories (one time)$0.43
Total$1591.49

## PDF Page 38

38 A. Rafiei Oskooei et al.
References
Ahmed M, Dorrah M, Ashraf A, Adel Y, Elatrozy A, Mohamed BE, Gomaa W (2024)
CodeQA: Advanced programming question-answering using LLM agent and RAG. In:
2024 6th Novel Intelligent and Leading Emerging Sciences Conference (NILES), pp 494–
499, DOI 10.1109/NILES63360.2024.10753267
Alebachew YB, Leary H, Vaishampayan S, Brown C (2026) Beyond code snippets: Bench-
marking LLMs on repository-level question answering. URLhttps://arxiv.org/abs/
2603.26567,2603.26567
Andryushchenko G, Ivanov V, Makharev V, Tukhtina E, Valeev A (2024) Leveraging large
language models in code question answering: Baselines and issues. In: Analysis of Images,
Social Networks and Texts (AIST 2024), Springer, DOI 10.1007/978-3-031-97019-1 1
Anonymous (2025) CodeInsightBench: A benchmark for advanced code understanding
and comparison in large language models. URLhttps://openreview.net/forum?id=
ThNHBP1qk9, openReview submission, under double-blind review
Anthropic (2025) Effective context engineering for AI agents.https://www.anthropic.com/
engineering/effective-context-engineering-for-ai-agents, anthropic Engineering
Blog
Cai S, Lyu Z, Ni Y, Chen X, Zhou B, Zhu S, Lu Y, Wang H, Ruan C, Schneider B,
Zhang W, Li X, Zheng A, Zhang Y, Nie P, Chen W (2026) SWE-QA-pro: A represen-
tative benchmark and scalable training recipe for repository-level code understanding.
In: Annual Meeting of the Association for Computational Linguistics (ACL 2026), URL
https://arxiv.org/abs/2603.16124,2603.16124
Chen J, Zhao K, Liu J, Peng C, Liu J, Zhu H, Gao P, Yang P, Deng S (2025) CoReQA:
Uncovering potentials of language models in code repository question answering. URL
https://arxiv.org/abs/2501.03447,2501.03447
Choi Y, Na C, Lee JH (2025) CoRAC: Integrating selective API document retrieval with
question semantic intent for code question answering. In: Proceedings of the 2025 Con-
ference of the Nations of the Americas Chapter of the Association for Computational
Linguistics: Human Language Technologies (Volume 1: Long Papers), pp 12620–12635,
DOI 10.18653/v1/2025.naacl-long.628
Cognition (2025) Don’t build multi-agents.https://cognition.ai/blog/
dont-build-multi-agents, cognition Blog
Elkoussy L, Perez J (2026) SWE-QA: A dataset and benchmark for complex code under-
standing. URLhttps://arxiv.org/abs/2604.24814,2604.24814
Feng J, Qin Z, Gao C, Wang R, Wang C, Ma Y, Xie X (2026) On the effectiveness of
context compression for repository-level tasks: An empirical investigation. URLhttps:
//arxiv.org/abs/2604.13725,2604.13725
Gao S, Wang C, Li S, Peng Y, Lyu MR (2026) ContextPilot: Code context engineering
with memory-augmented exploration agents. In: Proceedings of the Third International
Workshop on Large Language Models for Code (LLM4Code ’26)
Gao Y, Xiong Y, Gao X, Jia K, Pan J, Bi Y, Dai Y, Sun J, Wang M, Wang H (2023) Retrieval-
augmented generation for large language models: A survey. URLhttps://arxiv.org/
abs/2312.10997,2312.10997
Gong J, Wu Y, Liang L, Wang Y, Chen J, Liu M, Zheng Z (2025) CoSQA+: Enhancing code
search evaluation with a multi-choice benchmark and test-driven agents. IEEE Transac-
tions on Software Engineering URLhttps://arxiv.org/abs/2406.11589,2406.11589
Havare J, Chaudhary S, Ramakrishnan G, Maharajan K, Tamilselvam S (2025) A code
comprehension benchmark for large language models for code. URLhttps://arxiv.org/
abs/2507.10641,2507.10641
Hu R, Peng C, Ren J, Jiang B, Meng X, Wu Q, Gao P, Wang X, Gao C (2025) CodeRepoQA:
A large-scale benchmark for software engineering question answering. In: Companion
Proceedings of the ACM Web Conference 2025 (WWW ’25 Companion), URLhttps:
//arxiv.org/abs/2412.14764,2412.14764
Hu Y, Su T, Zhao L, Zhu B, Haque H (2026) LARGER: Lexically anchored repository graph
exploration and retrieval. URLhttps://arxiv.org/abs/2605.16352,2605.16352

## PDF Page 39

Deep Agentic Search for Repo-Level Code QA 39
Huang D, Wang C, Tang H, Tang Z, Guo L, Ru D, Yuan R, Zhu Z, Li X, Wang Z, Zhang
C, Gui A, Zan W, Zhang J, Cao X, Wang J, Cai X, Cao Y (2026) ATLAS: All-round
testing of long-context abilities across scales. URLhttps://arxiv.org/abs/2605.28079,
2605.28079
Kocadere MO, Comert YE, Yazici S, Karacay SG, Yildiz IB, Erdogan TG (2026) RepoWise:
A hybrid RAG-based conversational system for software repository analysis. In: 2026
8th International Congress on Human-Computer Interaction, Optimization and Robotic
Applications (ICHORA), IEEE, DOI 10.1109/ICHORA69329.2026.11537220
Landis JR, Koch GG (1977) The measurement of observer agreement for categorical data.
Biometrics 33(1):159–174, DOI 10.2307/2529310
LangChain (2025) Context engineering for agents.https://blog.langchain.com/
context-engineering-for-agents/, langChain Blog
Lewis P, Perez E, Piktus A, Petroni F, Karpukhin V, Goyal N, K¨ uttler H, Lewis M, Yih Wt,
Rockt¨ aschel T, Riedel S, Kiela D (2020) Retrieval-augmented generation for knowledge-
intensive NLP tasks. In: Advances in Neural Information Processing Systems (NeurIPS),
URLhttps://arxiv.org/abs/2005.11401,2005.11401
Li G, Liu Y, Qin Z, Wang Y, Zhong J, Zhi C, Li B, Huang F, Li Y, Deng S (2025a)
Empowering RepoQA-agent based on reinforcement learning driven by monte-carlo tree
search. URLhttps://arxiv.org/abs/2510.26287,2510.26287
Li X, Dong K, Lee YQ, Xia W, Zhang H, Dai X, Wang Y, Tang R (2025b) CoIR: A
comprehensive benchmark for code information retrieval models. In: Proceedings of the
63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long
Papers), pp 22074–22091, DOI 10.18653/v1/2025.acl-long.1072
Li X, Jiao W, Jin J, Dong G, Jin J, Wang Y, Wang H, Zhu Y, Wen JR, Lu Y, Dou Z
(2026a) DeepAgent: A general reasoning agent with scalable toolsets. In: Proceedings of
the ACM Web Conference 2026 (WWW ’26), URLhttps://arxiv.org/abs/2510.21618,
2510.21618
Li Z, Li Z, Chen Y, Shi H, Li J, Chen J, Bai H, Huang C (2026b) FastCode: Fast and cost-
efficient code understanding and reasoning. URLhttps://arxiv.org/abs/2603.01012,
2603.01012
Liu J, Zhao X, Shang X, Shen Z (2026) Dive into Claude Code: The design space of today’s
and future AI agent systems. URLhttps://arxiv.org/abs/2604.14228,2604.14228
Lopes EDS, de Oliveira HTA, de Souza Gazolli KA (2025) Exploring T5-based code QA
systems to support teaching programming in portuguese and english. In: 2025 LI Latin
American Computer Conference (CLEI), DOI 10.1109/CLEI67442.2025.11420747
Maharaj K, Menon N, Saxena A, Tamilselvam S (2026) Robustness and reasoning fidelity
of large language models in long-context code question answering. URLhttps://arxiv.
org/abs/2602.17183,2602.17183
Manus (2025) Context engineering for AI agents: Lessons from building manus.https://
manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus,
manus Blog
Mohammed F, Ayad F, Maniatis P, Chandra S, Dinella E (2026) RubberDuckBench: A
benchmark for AI coding assistants. In: Proceedings of the 3rd International Workshop
on Large Language Models for Code (LLM4Code ’26), URLhttps://arxiv.org/abs/
2601.16456,2601.16456
Oskooei AR, Yukcu S, Bozoglan MC, Aktas MS (2025) Repository-level code understanding
by LLMs via hierarchical summarization: Improving code search and bug localization. In:
Computational Science and Its Applications, ICCSA 2025 Workshops, Proceedings, Part
I, Springer, Berlin, Heidelberg, pp 88–105, DOI 10.1007/978-3-031-97576-9\ 6
Oskooei AR, Cosdan KB, Isiktas H, Aktas MS (2026) When many-shot prompting fails: An
empirical study of LLM code translation. In: Proceedings of the 1st Workshop on Code
Translation, Transformation, and Modernization (ReCode ’26), Association for Comput-
ing Machinery, New York, NY, USA, pp 38–43, DOI 10.1145/3786180.3788314
Peng W, Shi Y, Wang Y, Zhang X, Shen B, Gu X (2026a) SWE-QA: Can language models
answer repository-level code questions? In: Liakata M, Moreira VP, Zhang J, Jurgens
D (eds) Findings of the Association for Computational Linguistics: ACL 2026, Asso-
ciation for Computational Linguistics, San Diego, California, United States, pp 8230–
8245, DOI 10.18653/v1/2026.findings-acl.402, URLhttps://aclanthology.org/2026.

## PDF Page 40

40 A. Rafiei Oskooei et al.
findings-acl.402/
Peng W, et al. (2026b) DeepRepoQA: Code agent exploration and plan-search via monte
carlo tree search, under review at ICLR 2026
Rafiei Oskooei A, Yukcu SS, Bozoglan MC, Aktas MS (2026) Natural language summa-
rization enables multi-repository bug localization by LLMs in microservice architectures.
In: Proceedings of the 3rd International Workshop on Large Language Models for Code
(LLM4Code), pp 197–205
Raghavendra M, Dan S, Calvo MR, He YY, Mols JB, Anand G, McCollum C, Arakelyan
E, Bharadwaj V, Park A, Da J, Rezaei M, Liu B, Kenstler B, He Y (2026) SWE at-
las: Benchmarking coding agents beyond issue resolution. URLhttps://arxiv.org/abs/
2605.08366,2605.08366
Rahman S, Hameed A, Srivastava G, Danish SM (2025) RefactorCoderQA: Benchmarking
LLMs for multi-domain coding question solutions in cloud and edge deployment. URL
https://arxiv.org/abs/2509.10436,2509.10436
Rando S, Romani L, Sampieri A, Kyuragi Y, Franco L, Galasso F, Hashimoto T, Yang J
(2025) LongCodeBench: Evaluating coding LLMs at 1m context windows. URLhttps:
//arxiv.org/abs/2505.07897,2505.07897
dos Santos HVF, Costa V, Montandon JE, Valente MT (2026) Decoding the configuration
of AI coding agents: Insights from Claude Code projects. In: Proceedings of the 2026
International Workshop on Agentic Engineering (AGENT@ICSE ’26), Association for
Computing Machinery, New York, NY, USA, pp 63–67, DOI 10.1145/3786167.3788412
Sen S, Kasturi A, Lumer E, Gulati A, Subbiah VK (2026) Is Grep all you need? how agent
harnesses reshape agentic search. URLhttps://arxiv.org/abs/2605.15184,2605.15184
Shah P, Ghosh R, Singhal A, Dutta D (2025) RANGER: Repository-level agent for graph-
enhanced retrieval. URLhttps://arxiv.org/abs/2509.25257,2509.25257
Shi Y, Qian Y, Zhang H, Shen B, Gu X (2025) LongCodeZip: Compress long context for
code language models. In: Proceedings of the IEEE/ACM International Conference on
Automated Software Engineering (ASE), DOI 10.1109/ASE63991.2025.00020
Shi Y, Xie C, Sun Z, Chen Y, Zhang C, Yun L, Wan C, Zhang H, Lo D, Gu X (2026)
CodeOCR: On the effectiveness of vision language models in code understanding. URL
https://arxiv.org/abs/2602.01785,2602.01785
Ugare S, Chandra S (2026) Agentic code reasoning. URLhttps://arxiv.org/abs/2603.
01896,2603.01896
Usai N, Montagnini D, Iliev KI, Camanzo R (2026) LogicLens: Leveraging semantic code
graph to explore multi repository large systems. URLhttps://arxiv.org/abs/2601.
10773,2601.10773
Wang J, Chen X, Zhu W, Li H, He Z, Cai F, Carreon-Rascon AS, Dong X, Luo F (2026a)
Context pruning for coding agents via multi-rubric latent reasoning. URLhttps://arxiv.
org/abs/2605.15315,2605.15315
Wang L, Chen H, Yang N, Huang X, Dou Z, Wei F (2025) Chain-of-retrieval augmented
generation. URLhttps://arxiv.org/abs/2501.14342,2501.14342
Wang X, Hu R, Gao C, Gao P, Peng C (2026b) Evaluating repository-level software
documentation via question answering and feature-driven development. URLhttps:
//arxiv.org/abs/2604.06793,2604.06793
Wang X, Rosenberg S, Michelini J, Smith C, Tran HH, Nyst E, Malhotra R, Zhou X, Chen V,
Brennan R, Neubig G (2026c) The OpenHands software agent SDK: A composable and
extensible foundation for production agents. In: Proceedings of Machine Learning and
Systems 8 (MLSys 2026), URLhttps://proceedings.mlsys.org/paper_files/paper/
2026/hash/8ae9cf363ea625161f885b798c1f1f78-Abstract-Conference.html
Wang Y, Shi Y, Yang M, Zhang R, He S, Lian H, Chen Y, Ye S, Cai K, Gu X (2026d)
SWE-pruner: Self-adaptive context pruning for coding agents. URLhttps://arxiv.org/
abs/2601.16746,2601.16746
Yang J, Zhang W, Li Y, Guo S, Wang H, Liu A, Zhang G, Wang Z, Li Z, Liu X, Lv W
(2025) CodeSimpleQA: Scaling factuality in code large language models. URLhttps:
//arxiv.org/abs/2512.19424,2512.19424
Yao S, Zhao J, Yu D, Du N, Shafran I, Narasimhan K, Cao Y (2023) ReAct: Synergiz-
ing reasoning and acting in language models. In: International Conference on Learning
Representations (ICLR), URLhttps://arxiv.org/abs/2210.03629,2210.03629

## PDF Page 41

Deep Agentic Search for Repo-Level Code QA 41
Zhang J, Guo L, Wang Y, Liu M, Chen J, Ma Y, Shi E, Zhuo TY, Zhang H, Zheng Z
(2026a) SimpleDevQA: Benchmarking large language models on development knowledge
QA. In: Findings of the Association for Computational Linguistics: ACL 2026, URL
https://arxiv.org/abs/2512.08867,2512.08867
Zhang J, Qu J, Du H, Sun Z, Yang Y, Zhao Q (2026b) Code-QA-Bench: Separating
code reasoning from documentation memorization in repository-level QA. URLhttps:
//arxiv.org/abs/2605.29277,2605.29277
Zhang S, Wang M, Shi Y, Wang Y, Gu X, Yao Y, Gong T, Chen S, Fu R, Agarwal A, Garg
S, Ryan G, Merkel C, Huang Y, Fu S (2026c) FastContext: Training efficient repository
explorer for coding agents. URLhttps://arxiv.org/abs/2606.14066,2606.14066
Zhang S, Wang Y, Liang J, Shi Y, Zeng W, Wang M, He S, Xu N, Ye S, Cai K, Gu
X (2026d) SWE-explore: Benchmarking how coding agents explore repositories. URL
https://arxiv.org/abs/2606.07297,2606.07297