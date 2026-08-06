## PDF Page 1

Formal Verification of Agentic Systems over Operational Data
Alejandro J. Mercado1∗, Alessio Lomuscio1,2
1Imperial College London
2Safe Intelligence
{a.mercado24, a.lomuscio}@imperial.ac.uk
Abstract
Agenticsystemsdrivenbylargelanguagemodels(LLMs)are
increasinglydeployedinreal-worldworkflowswheretheyact
on persistent operational data. Before deployment, these sys-
tems need to be verified against business requirements that
govern workflow execution and data evolution. However, ex-
isting approaches do not provide such system-level guaran-
tees, as they mainly constrain or analyse behaviour at the
agent’sinterfacelevel.Westudyheretheverificationofagen-
tic systems comprising a single LLM and a tool orchestration
harness over relational operational data. We formalise them
as Stateful Tool-Enabled Agentic Deployments (STEADs),
give their semantics, define the problem of verifying them
against First-Order Computation Tree Logic (FO-CTL) spec-
ifications, and show that it is undecidable. We identify suffi-
cient conditions for exact preservation of FO-CTL specifica-
tionsunderafinite-domainrestriction,overwhichverification
is PSPACE-complete. The key requirement is that renaming
opaque identifiers in the data must correspondingly rename
the selected tool calls. We show that LLM-driven agents can
violate this condition and introduce a canonical deployment
wrapperthatguaranteesitforarbitrarybaseagentswhilepre-
servingalready-equivariantbehaviour.Weprovethatcomput-
ing canonical representations required by this construction is
graph-isomorphism-hard.Finally,weillustrateourframework
onanLLMagentorchestratingacase-managementworkflow.
Agenticsystemsdrivenbylargelanguagemodels(LLMs)are
becoming increasingly autonomous, interacting with persis-
tent operational data to execute real-world tasks (Lu et al.
2025; Yao et al. 2023; Schick et al. 2023; Acharya, Kuppan,
and Bhaskaracharya 2025; Ali, Dornaika, and Charafeddine
2026).Recentworkmotivatestheiruseinbusinessworkflows
across domains such as retail, airlines, and telecommunica-
tions(Yaoetal.2024;Barresetal.2025).Beforedeployment
inhigh-stakessettings,thesesystemsmustbeverifiedagainst
business requirements governing the workflow and its data.
Existingapproachesmainlyfocusontheagent’sbehaviour
at the interface level. Monitoring and guardrail methods re-
strict the tool calls that an LLM may issue so that execu-
tionssatisfyagivensafetyspecification(Kamathetal.2025;
Wang et al. 2026). Complementary work synthesises com-
pliant agent strategies offline, but represents the underlying
process state propositionally (De Giacomo et al. 2026). In
∗Corresponding author.
parallel, research on agent security studies how attacks on
individualcomponentscanleveragetheLLMorchestratorto
affect the wider system (Kim et al. 2026).
However,theseapproachesdonotdirectlyaddressrequire-
ments over the persistent operational state. In a customer-
support workflow, for example, every request may be re-
quired to eventually reach completion, while critical opera-
tions may be permitted only after the required approval has
been recorded. Such requirements cannot in general be ex-
pressedsolelyoverindividualtoolcalls.Theymustinsteadbe
stated over the evolving operational data, capturing progress
as well as safety across complete workflow executions.
In this work, we study the verification of agentic systems
comprising a single LLM agent interacting with persistent
relational data through a tool orchestration harness. We for-
malise such a system as a Stateful Tool-Enabled Agentic
Deployment (STEAD), in which an LLM agent operating
under a fixed natural-language policy observes the current
operational data, selects an available tool call, and executes
it to update the state. We represent the operational state as
a sorted first-order relational structure and express business
requirements in First-Order Computation Tree Logic (FO-
CTL). FO-CTL can capture safety and progress properties
over evolving objects, as well as the branching induced by
the agent’s decisions and nondeterministic tool effects.
We define the verification problem for STEADs against
FO-CTL specifications and show that it is undecidable. We
thenidentifylocalsymmetryconditionsonthetoolinterface,
the LLM-based agent, and the tool semantics under which
the induced transition system, even when infinite-state, can
be verified exactly by restricting it to a sufficiently large fi-
nite domain. This yields an explicit finite transition system
over which verification is PSPACE-complete. The key con-
dition we identify for the agent isequivariance: consistently
replacinganopaqueidentifiersuchasuser17withuser10in
thedatamustinduceonlythecorrespondingobjectrenaming
within the selected tool call.
Through a case study, we show that LLMs can violate
equivariance. Applying our finite-verification result there-
forerequirescertifyingitateveryreachabledecisioncontext.
However,equivarianceisnotaclassicalrobustnessproperty:
it quantifies over all isomorphic states and requires exact
correspondence of structured tool calls. Instead, verification
for neural networks and language models is typically con-
arXiv:2608.03609v1  [cs.AI]  4 Aug 2026

## PDF Page 2

strained to bounded perturbations around a fixed input (Liu
et al. 2021; Wang, Wang, and Yang 2022). We therefore
introduce a canonical deployment wrapper that guarantees
equivariance for any base agent while preserving already-
equivariantbehaviour.Thewrapperpresentsisomorphicde-
cision contexts to the LLM in the same canonical form and
maps the selected tool calls back to the original identifiers.
We prove that computing the shared canonical representa-
tions required by any such method, including ours, is graph-
isomorphism-hard. Finally, we illustrate the framework on
an LLM agent operating over a case-management workflow.
More concretely, our contributions are:
•We formalise STEADs, define their semantics and the
verificationproblemforFO-CTLspecifications,andshow
that verification is undecidable.
•For STEADs whose tool interface, agent policy, and tool
semanticsbehaveconsistentlyunderidentifierrenamings,
we show how to verify a given FO-CTL specification
exactly by constructing a sufficiently large finite-domain
restriction of the deployment, over which verification is
PSPACE-complete.
•WeshowthatLLM-basedagentsmayviolatetherequired
equivarianceconditionandintroduceacanonicaldeploy-
mentwrapperthatguaranteesitwhilepreservingalready-
equivariant behaviour. We further prove that computing
the canonical representations required by this construc-
tion is graph-isomorphism-hard.
•WeillustratetheframeworkonanLLM-basedagentoper-
atingoveracase-managementworkflowandverifysafety
and progress properties.
Related work.Recent benchmarks increasingly place
LLM agents in tool-enabled environments with persistent,
database-backed application state. AgentBench evaluates
agents that query and update a database through SQL calls,
while WebArena tests browser agents on web applications
backedbylivedatabases(Liuetal.2024;Zhouetal.2024).In
τ-bench andτ 2-bench, agents follow written policies while
updating airline, retail, and telecom databases through do-
main APIs (Yao et al. 2024; Barres et al. 2025). AppWorld
exposesdatabase-backedapplicationsthroughAPIsandeval-
uates agent tasks success, while ToolSandbox scores inter-
mediate and final milestones during stateful tool execution
(Trivedi et al. 2024; Lu et al. 2025). All these benchmarks
provideempiricalevaluationsratherthanformalguarantees.
Runtime enforcement provides guarantees at the agent’s
interface. Agent-C rejects tool calls violating temporal con-
straintsviaSMTchecks(Kamathetal.2025),AgentSpecand
GuardAgent enforce specified action rules (Wang, Poskitt,
andSun2025;Xiangetal.2025),ProbGuardestimatesfuture
risk from a learned behavioural model (Wang et al. 2026),
and ShieldAgent compiles regulatory text into probabilistic
logiccircuits(Chen,Kang,andLi2025).Furtherworkstud-
ies realizability, synthesis, and guardrailing of agent strate-
gies over propositional process specifications (De Giacomo
etal.2026).However,relevantobjectsmayneverappearina
monitored call, and blocking disallowed calls cannot ensure
that the agent eventually performs the actions required for
progress.
Data-aware and artifact-centric verification studies tem-
poral properties over evolving relational data (Deutsch et al.
2009, 2018; Calvanese, De Giacomo, and Montali 2013;
Calvaneseetal.2020).Verificationisundecidableingeneral
(Haririetal.2013),butfiniteabstractionsrecoverdecidabil-
ityforrestrictedclasses(Belardinelli,Lomuscio,andPatrizi
2012, 2014). The same abstraction principle extends more
generally to bounded generic transition systems (Calvanese
et al. 2018). All these approaches assume a symbolically
specified transition mechanism. In a STEAD, the transition
relation also depends on the LLM, which need not respect
thesymmetriesofthesymbolicinterfaceandtoolsemantics.
Preliminaries
We recall standard notions from relational data-aware ver-
ification, adapted here to a sorted domain. We model the
operational data as finite relational structures and workflow
executions as transitions between them. We assume a finite
set ofsortsSand an interpretation domainUsorted by a
fixed typingtp:U→S. We writeU S =tp −1(S)for the
values of sortS∈S.
Definition 1(Typed schema and instance).A relational
schema is a finite setD={P 1 :σ 1, . . . , Pm :σ m}of
relation symbols, wherePi has arityq i and sort signature
σi ∈S qi. AD-instanceoverUassigns to eachP i a finite,
well-sortedrelationD(P i)⊆U σi,1 ×· · ·×U σi,qi
.Theactive
domainad(D)isthesetofvaluesoccurringinsometupleof
D, andD(U)denotes the set of allD-instances overU.
Definition2(Statetransitionsystem).Astatetransitionsys-
tem overDis a tupleM=⟨U, D 0,→⟩, whereD 0 ∈ D(U)
andeverystateinReach(M)hasa→-successor.Thereach-
able statesReach(M)are the least set containingD0 and
closed under→.
To record transitions between states, we use the following
notation.LetD ′ beaprimedcopyofD.FortwoD-instances
D, D′,wewriteD⊕D ′ forthe(D ∪ D ′)-instancesatisfying
(D⊕D ′)(P) =D(P),(D⊕D ′)(P ′) =D ′(P).
We now introduce the notions needed to quotient these
states by their relational structure while preserving a finite
setC⊆Uof distinguished values.
Definition3(C-isomorphism).TwoD-instancesD 1, D2are
C-isomorphic, writtenD 1 ≃C D2, if there is a bijection
ι:ad(D 1)∪C→ad(D 2)∪Csuch thatι(c) =cfor every
c∈C,tp(u) =tp(ι(u))for everyu, and, for every relation
P∈ Dof arityqand tuple⃗ u∈(ad(D 1)∪C) q,
⃗ u∈D1(P)iffι(⃗ u)∈D 2(P).
Thus,C-isomorphic states have the same typed relational
structureandmaydifferonlyinthenamesassignedtovalues
outsideC. The definition extends to transition pairs through
D⊕D ′.Wenowboundthenumberofsuchvaluesoccurring
in each reachable state, sort by sort.
Definition4(C-boundedness).Forb= (b S)S∈S,withb S ∈
N,MisC-bounded bybif|(ad(D)\C)∩U S| ≤b S for
everyD∈Reach(M)andS∈ S.
WhenUis infinite, even aC-bounded system may have
infinitely many reachable states.

## PDF Page 3

Stateful Tool-Enabled Agentic Deployment
We now formalise the deployment whose behaviour is to be
verified: a single LLM agent operating over persistent rela-
tional data through a tool interface. The resulting model lets
us define the verification problem over the induced transi-
tionsystemand,crucially,decomposetherequiredrenaming
symmetry into local conditions on the agent, tool interface,
and tool semantics.
Agentic Deployment
We represent the state as aD-instance in the sense of Defi-
nition 1. In a similar fashion, we represent tools as follows:
letΩbe a finite set oftool schemas, where eachω∈Ω
carries a sort signatureσω ∈S ar(ω). Agrounded tool call
is a well-sorted expressionω(⃗ u). We writeToolsΩ(U)for
all possible grounded tool calls whose parameters lie inU,
andTools Ω(D)forthosewhoseparametersliestrictlyinthe
active domainad(D).
We model the workflow at the points where the agent
chooses a tool call. At each such point, the deployed LLM-
basedagentreceivesatextualpresentationofthecurrentop-
erationalstateD,andaharnessmapsitsoutputtoagrounded
tool call exposed by the interface. We abstract the complete
deployedagent,includingbothpresentationandoutputmap-
ping, by its resulting tool-call policy. The interface is deter-
minedbyAPIspecificationsandanyguardrailsimplemented
on top. The execution produces a successor state according
tothetoolsemantics,possiblynondeterministically.Wenow
present the precise formal definition:
Definition 5(Stateful Tool-Enabled Agentic Deployment).
AStateful Tool-Enabled Agentic Deployment(STEAD) is a
tuple
A=⟨E,T,Π⟩
consisting of a persistent stateE, a tool spaceT, and an
LLM agent policyΠ, where:
•E=⟨D, U, D 0⟩defines thepersistent state.Dis a typed
relational schema andUis the interpretation domain,
withD 0 ∈ D(U)as the initial database instance.
•T=⟨Ω, τ,Offer⟩defines thetool space, which governs
what actions are possible and how they affect the state:
–Schemas:The finite setΩof available tool schemas.
–Semantics:τ:D(U)×Tools Ω(U)→2 D(U) defines
the tool effects on the state. We writeD
a
− →D′ for
D′ ∈τ(D, a).
–Interface:The tools enabled by the system at a given
state are defined byOffer:D(U)→2 ToolsΩ(U), with
∅ ̸=Offer(D)⊆ {a∈Tools Ω(D) :τ(D, a)̸=∅}for
every reachableD.
•Π :D(U)×2 ToolsΩ(U) →2 ToolsΩ(U) defines the LLM-
based agent policy, with∅ ̸= Π(D, A)⊆Afor every
D∈ D(U)and nonemptyA⊆Tools Ω(D).
The induced database transition system is given by
D→ Π,Offer D′ ⇐ ⇒ ∃a∈Π(D,Offer(D)) :D
a
− →D′.
Bythenon-emptinessconditionsonOffer,Π,andtheeffects
of offered calls, this transition relation is serial.
We define the pair(D, A)as adecision context, where
D∈ D(U)and∅ ̸=A⊆Tools Ω(D).AtstateD,theSTEAD
exposes(D,Offer(D)).WhiletheLLMitselfprocessesonly
text,ΠrepresentsthecompleteLLM-basedagent,including
the harnesses that present the state and map the LLM output
to a valid grounded tool call. Thus,(D, A)is the input to
the LLM-based agent, not necessarily the literal input to
the LLM. For example, a fixed deployment may present the
LLM with a fixed natural-language policy followed by a
serialization ofD, while usingAto enforce a valid tool call
through greedy constrained decoding.
We assume that the LLM-based agent is Markovian with
respect to the decision context and thatDexposes all re-
lational facts relevant to the agent. Interaction history, re-
trievedinformation,userrequests,orcontrollermemorymay
be recorded as relational facts inD, which may itself be a
task-relevant view of a richer operational environment.
The Verification Problem
The transition system induced by a STEAD is the object of
verification. Its states record the evolving operational data,
while its branches capture the agent’s possible selections
andthepossibleeffectsofitstools.Weexpressrequirements
overthissysteminFirst-OrderComputationTreeLogic(FO-
CTL), which combines first-order quantification over opera-
tional objects with branching-time modalities.
Definition 6(FO-CTL).Given a sorted set of variables
Var= U
S∈S VarS and a finite constant setCon⊆U,
well-sorted FO-CTL formulas overDare
φ::=t=t ′ |P(t 1, . . . , tq)| ¬φ|φ→φ| ∀x φ
|AX φ|A φ U φ|E φ U φ,
witht∈Var∪Con. We useEX, AF, EF, AG, EGas
standard, writecon(φ)for the constants inφ, and callφa
sentencewhen it has no free variables.
Satisfaction(M, D, σ)|=φfollows the standard
branching-time semantics (Clarke, Emerson, and Sistla
1986) with active-domain quantification: a quantified vari-
ablex∈Var S ranges overad(D)∩U S, while assignments
are retained across temporal modalities. For a sentenceφ,
we writeM |=φwhen it holds at the initial stateD0.
Definition 7(Verification problem).LetM A =
⟨U, D0,→ Π,Offer⟩be the transition system induced by a
STEADA. Given an FO-CTL sentenceφ, the verification
problem is to determine whetherMA |=φ.
Full proofs of all results are provided in the Appendix.
Theorem8(Undecidability).TheSTEADverificationprob-
lem is undecidable.
Proof sketch.Undecidabilityalreadyholdsforfinitelyspec-
ified relational data-centric systems with nondeterministic
services and propositional invariantsG p(Hariri et al. 2013,
Thm. 5.1, full-version proof). We encode any such system
as a STEAD with one nullary tool, always offered and se-
lected,whoseinducedtransitionrelationisthereflexiveclo-
sureoftheoriginalone.Thisaddsnoreachablestates,soG p
holds in the source exactly whenAG pholds in the induced
STEAD.

## PDF Page 4

We now identify conditions under which verification re-
duces exactly to model checking a finite restriction. If its in-
duced transition system isC-bounded and its tool interface,
agentpolicy,andtoolsemanticscommutewithC-preserving
renamings, then restricting the deployment to a sufficiently
large finite domain preserves FO-CTL exactly. The theorem
gives the required domain sizes and isolates agent equivari-
ance as the key condition on the LLM agent. We assume
US ̸=∅for all sorts.
Definition 9(C-equivariant tool interface).OfferisC-
equivariantonS⊆ D(U)if, for everyι:D 1 ≃C D2
withD 1, D2 ∈S,
Offer(D2) =ι(Offer(D 1)),
whereι(ω(u 1, . . . , uk)) =ω(ι(u 1), . . . , ι(uk)).
Definition 10(C-tool-uniform semantics).τisC-tool-
uniformonSif, wheneverD, D ′, ¯D∈S, ¯D′ ∈ D(U),
a∈Tools Ω(D),D
a
− →D′, andD⊕D ′ ≃C ¯D⊕ ¯D′ viaι,
then ¯D
ι(a)
− − →¯D′.
Definition 11(C-equivariant agent).ΠisC-equivarianton
Sif, for everyι:D 1 ≃C D2 withD 1, D2 ∈Sand every
nonemptyA⊆Tools Ω(D1),
Π(D2, ι(A)) =ι(Π(D 1, A)).
Definition 12(Finite-domain restriction).LetU f ⊆Ube
a finite sorted subdomain withad(D 0)⊆U f. TheU f-
restrictionofM A =⟨U, D 0,→ Π,Offer⟩is
MA ↾U f =⟨U f , D0,→ f ⟩,
with→ f=→Π,Offer ∩
 
D(Uf)× D(U f)

.
Theorem13(Exactfiniteverification).LetφbeanFO-CTL
sentence, letC⊆Ube finite withcon(φ)∪ad(D 0)⊆C
and putR=Reach(M A). Assume thatMA isC-bounded
byb= (b S)S∈S, thatOfferandΠareC-equivariant onR,
and thatτisC-tool-uniform onR. Then every finite sorted
subdomainU f withC⊆U f ⊆Uand satisfying, for each
sortS,
(Uf)S =U S or|(U f)S| ≥2b S +|C∩U S|+ var S(φ),
induces a finite state transition system such that
MA |=φ⇐ ⇒ M A ↾U f |=φ,
wherevar S(φ)counts the sort-Svariables ofφ. FO-CTL
verification over an explicitly given restriction is PSPACE-
complete in combined complexity.
Proof sketch.WriteM=M A andM f =M↾U f. Since
→f ⊆→Π,Offer,
Reach(Mf)⊆R.(R)
ForD, D ′, E∈RandE ′ ∈ D(U), supposeD→D ′
andD⊕D ′ ≃C E⊕E ′ viaι, whose restriction to the
pre-states witnessesD≃ C E. Ifa∈Π(D,Offer(D))
witnessesD→D ′, thenι(a)∈ι(Π(D,Offer(D))) =
Π(E, ι(Offer(D))) = Π(E,Offer(E)).Tool uniformity
givesE
ι(a)
− − →E′, hence
D→D ′ ∧D⊕D ′ ≃C E⊕E ′ =⇒E→E ′.(T)
LetVbe the variables occurring inφ. ForD∈R, ¯D∈
Reach(Mf), and sort-correctν:V→Uand¯ν:V→
Uf, write(D, ν)≡( ¯D,¯ν)when a sort-preserving bijection
betweenad(D)∪C∪ν(V)andad( ¯D)∪C∪¯ν(V)fixes
C, witnessesD≃ C ¯D, and mapsν(x)to¯ν(x)for every
x∈V. If(D, ν)≡( ¯D,¯ν)andD→D ′, this witness
extends sortwise to the post-state: for every sortS, 
ad(D⊕D ′)∪C∪ν(V)

∩US
 ≤2b S+|C∩U S|+varS(φ),
so either(U f)S =U S, and the sort-Spart of the witness
extends to a permutation ofUS, or|(U f)S| ≥2b S +|C∩
US|+ varS(φ)leavesenoughunusedvaluesin(U f)S.Writ-
ing ¯D′ ∈ D(U f)for the image ofD ′ under the extension,
(T) with (R) gives
(D, ν)≡( ¯D,¯ν)∧D→D ′ =⇒
∃ ¯D′. ¯D→ f ¯D′ ∧(D ′, ν)≡( ¯D′,¯ν), (M)
and analogously in the reverse direction, using (R) to place
thefinitesuccessorinRandthesameper-sortcounttoextend
theinversewitnessintoU.Iterating(M)matchesrunsinboth
directions. By (R) and seriality ofM, every reachable finite
statehasaconcretesuccessor,which(M)ontheidentitypair
maps intoM f. HenceM f is serial on its reachable states.
It is finite because the finite domainUf and finite schemaD
admit only finitely many instances.
A sorted adaptation of the isomorphism-invariance argu-
mentin(Belardinelli,Lomuscio,andPatrizi2012)yields,by
structural induction on each subformulaψ:
(D, ν)≡( ¯D,¯ν) =⇒
(M, D, ν)|=ψ⇐ ⇒(M f , ¯D,¯ν)|=ψ

. (I)
Atomsarepreservedbybijectivity,assignmentcompatibility,
andstateisomorphism,sincethewitnessfixeseveryconstant
incon(ψ)⊆C.Booleancasesareimmediate.Thecase∀x S
uses the bijection between the sort-Sactive domains, under
which updatedassignments remain≡-related.TheAXcase
uses both directions of (M), whileE UandA Utransfer
witnessingandarbitraryruns,respectively,inbothdirections.
AtD 0, the identity relates every sort-correctν:V→U f to
itself; sinceφis a sentence, the result follows.
PSPACE membership follows by on-the-fly polynomial-
spaceevaluation,whilehardnessalreadyholdsforfirst-order
model checking on a one-state serial system.
Theorem 13 is constructive. The reachable part of the
restrictionisobtainedbyordinaryforwardenumerationfrom
D0,applyingtheoriginaltoolinterface,agentpolicy,andtool
semantics while retaining successors overUf.
Boundedness is a standard structural restriction in data-
aware verification and is often natural in agentic workflows:
the system may keep only a bounded number of active
records, the orchestration layer may expose only a bounded
task-local view, and the LLM context window limits how
much data can be presented at each decision point. The
tool interface and tool semantics can usually be shown to
respect renamings directly from their specifications. Thus,
the LLM-based agent introduces the new bottleneck: The-
orem 13 additionally requires its selected calls to commute
withrenamingsofopaqueidentifiers.Thenextsectionshows
that this agent-side hypothesis cannot simply be assumed.

## PDF Page 5

Case Study: Agent Equivariance
We exhibit a concrete LLM decision context violating the
agent-equivariance hypothesis of Theorem 13. We adapt an
airline cancellation task fromτ-bench (Yao et al. 2024) to
a fixed, single-turn decision context containing one account
and three reservations, whose concrete identifiers we denote
byr 1, r2, r3. Unlike the original benchmark setting, which
involves a multi-turn interaction with a simulated user and
databaseAPIs,wepresenttheagentdirectlywiththerelevant
cancellationpolicyandaserializationoftherelationalfacts,
and ask it to issue a single structured tool call. Reservations
r1 andr 3 satisfy the cancellation policy, whereasr2 does
not. The offered setA=Offer(D)contains the calls that
cancel any nonempty subset of these identifiers. We instan-
tiate the agent with Qwen3-1.7B (Yang et al. 2025) under
greedydecodingandgrounditswell-formedJSONoutputto
its corresponding offered call. Complete records, prompts,
groundingdetails,andreproductioninstructionsaregivenin
the Appendix.
Letρrename only the account username
amelia_davis_8890inDtoea0q883c_00yla6i6.
The replacement was found by a stochastic search over
admissible usernames, using the model’s log-probability
margin between the policy-compliant and policy-violating
calls to rank candidates. Since the username is an opaque
relational key that does not affect cancellation eligibility,ρ
witnessesD≃ C ρ(D). Nevertheless, the LLM selects:
amelia_davis_88907− →cancel(r 1, r3),
ea0q883c_00yla6i67− →cancel(r 1, r2, r3).
Becauseρfixes the reservation identifiers,ρ(A) =A
andρ(a) =afor everya∈A. Agent equivariance would
therefore requireΠ(ρ(D), A) =ρ(Π(D, A)) = Π(D, A).
Instead, the agent additionally selects the ineligible reserva-
tionr 2 in the renamed context, soC-equivariance fails.
Thedependenceonanopaqueidentifierisconsistentwith
the broader evidence that LLM behaviour can vary under
meaning-preserving changes in prompt presentation (Sclar
et al. 2024; Mizrahi et al. 2024). However, applying The-
orem 13 requires the property to hold at every reachable
decision context and under every consistent identifier re-
naming. Existing verification methods typically certify that
anoutputremainsunchangedoveraboundedinputregionor
a predefined perturbation set (Liu et al. 2021; Wang, Wang,
and Yang 2022; Ye, Gong, and Liu 2020; Lou et al. 2024),
while equivariance requires the selected call to change cor-
respondingly over an unbounded group of renamings. We
therefore enforce the theorem’s remaining agent-side condi-
tion by construction.
Equivariance by Construction
To discharge the remaining agent-side hypothesis of The-
orem 13 without certifying the LLM post hoc, we enforce
equivariance at the deployment boundary as follows: each
decision context is renamed to a canonical representative
beforequeryingthebaseagent,andtheselectedcallistrans-
ported back to the original identifiers. Isomorphic contexts
are therefore presented identically to the agent.
Themainchallengeisthatacanonicalrepresentativemay
admit several witnessing labellings, corresponding to auto-
morphismsoftheoriginalstate,andchoosingonearbitrarily
can break equivariance. We therefore define a general set-
valued wrapper and then identify a sufficient condition un-
der which a singleton-valued base policy remains singleton-
valued after wrapping.
Canonical Decision Contexts
We canonicalize relative to a fixed finite setB⊆Ucon-
taining the values whose identity may affect the agent’s be-
haviour,suchasopenandresolved.Allotheractiveval-
ues are treated as generic identifiers whose particular names
should not matter. For a verification task(D0, φ), letCbe
anyfinitesetsuchthatB∪con(φ)∪ad(D 0)⊆C.Sinceevery
C-isomorphismisalsoaB-isomorphism,anyB-equivariant
wrapper is alsoC-equivariant. The same wrapped deploy-
ment therefore satisfies the agent-equivariance requirement
for any FO-CTL specification.
For each sortS, fix an ordered sequence of pairwise dis-
tinct canonical valuesν S
1 , νS
2 , . . .∈U S \Bthat is long
enough for the instances under consideration, and fix a total
order⪯onD(U), for example, induced by a fixed serializa-
tion of ground atoms. LetnS(D) =
 
ad(D)\B

∩U S
 .
Definition 14(B-labelling).AB-labellingof an instance
Dis aB-isomorphic instanceD ′ such that, for every sort
S∈S,
(ad(D′)\B)∩U S ={ν S
1 , . . . , νS
nS(D)}.
Definition 15(Canonical instance).Thecanonical instance
ofDis its leastB-labelling:
canB(D) = min⪯{D′ :D ′ is aB-labelling ofD}.
We write
LabB(D) ={σ:σwitnessesD≃ B canB(D)}
for its canonical labelling witnesses.
Every instance has at least one and at mostQ
S nS(D)!
distinctB-labellings. Hencecan B(D)is well defined and
LabB(D)isnonempty.Weassumethatthefixedserialization
of every reachable canonical decision context fits within the
base agent’s context window.
Lemma 16(Completeness of canonical instances).The fol-
lowing properties hold:
1.can B(D) = canB(D′)if and only ifD≃B D′; and
2. any two witnesses inLab B(D)differ by aB-
automorphismofD.Consequently,Lab B(D)isasingle-
ton if and only ifDhas no nontrivialB-automorphism.
Proof sketch.B-isomorphic instances have the same set
ofB-labellings and therefore the same minimum; con-
versely, instances with the same canonical instance areB-
isomorphic through it. Forσ, σ′ ∈Lab B(D),σ ′−1 ◦σis a
B-automorphism ofD, and composing any canonical wit-
nesswithsuchanautomorphismyieldsanotherwitness.

## PDF Page 6