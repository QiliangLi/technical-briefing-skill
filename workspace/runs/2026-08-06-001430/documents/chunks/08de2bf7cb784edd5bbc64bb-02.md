-labellingof an instance
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

Equivariant Wrapper
Let bΠbe an arbitrary base agent policy. Given a canonical
witnessσ∈Lab B(D), the wrapper renames both the state
and its offered calls, queries the base agent on the resulting
canonical context, and transports its selection back:
(D, A)
σ
− − →(canB(D), σ(A))
bΠ
− − →bR
σ−1
− − − →σ−1(bR),
where bR= bΠ(canB(D), σ(A)).
The canonical instance is unique, but its witnessing la-
belling may not be unique. Different witnesses may there-
fore map the same canonical call back to different concrete
calls. For example, if two ticketst1, t2 are indistinguishable
inD,thecanonicalcallclose(ν t
1)maymapbacktoclose(t 1)
under one witness and toclose(t2)under another. Choos-
ing one witness through an arbitrary tie-break can therefore
break equivariance.
This ambiguity is not unique to our canonicalisation pro-
cedure: no singleton-valued equivariant policy can select a
call moved by an automorphism of its decision context.
Proposition 17(No equivariant symmetry breaking).Let
OfferbeB-equivariant and letΠbe aB-equivariant agent
withΠ(D,Offer(D)) ={a}. Thenα(a) =afor everyB-
automorphismαofD.
Proof sketch.For anyB-automorphismαofD, offered-
tool equivariance givesα(Offer(D)) =Offer(D). Hence
agent equivariance yields{a}= Π(D,Offer(D)) =
α(Π(D,Offer(D))) ={α(a)}.
The general wrapper therefore retains the selections ob-
tained through all canonical witnesses:
Πcan(D, A) =
[
σ∈LabB(D)
σ−1

bΠ(canB(D), σ(A))

.(1)
Theorem 18(Enforcement and preservation).For every
base agentbΠ, Eq.(1)defines a validB-equivariant agent
Πcan. Furthermore, if bΠis alreadyB-equivariant, then
Πcan =bΠ.
Proof sketch.For everyσ∈Lab B(D), the base policy re-
turns a nonempty subset ofσ(A), whose inverse image un-
derσis a nonempty subset ofA; validity follows by tak-
ing the union. IfD≃ B D′, the two states have the same
canonical instance by Lemma 16, and their canonical wit-
nesses correspond by composition with the isomorphism.
Theresultingselectionsaftertheyaremappedbacktherefore
correspond exactly, establishingB-equivariance. Finally, if
bΠis alreadyB-equivariant, then for everyσ∈Lab B(D),
bΠ(canB(D), σ(A)) =σ( bΠ(D, A)),soeveryterminEq.(1)
equalsbΠ(D, A).
WhenbΠisnotequivariant,Π can neednotpreserveitsout-
putontheoriginalpresentation.Nevertheless,everywrapped
call is obtained by transporting back a call selected bybΠon
aB-isomorphic presentation of the same relational decision
context.Thus,thewrapperenforcesindependencefromiden-
tifier names while retaining only behaviour exhibited by the
base agent within that isomorphism class.
Computational Cost
A direct implementation of Eq. (1) may enumerate up toQ
S nS(D)!sort-preserving canonical labellings. More effi-
cientcanonical-labellingproceduresmayavoidthisenumer-
ation, but the underlying canonicalisation problem remains
graph-isomorphism-hard.
Lemma 19(Cost boundary).Any map choosing a com-
monB-isomorphic representative for each≃ B-class is a
complete invariant of≃B. Computing such a map is graph-
isomorphism-hard, even for a fixed one-sorted schema with
a single binary relation over an infinite domain.
Proof sketch.The representative property gives both direc-
tions of a complete invariant:B-isomorphic instances share
a representative, while instances sharing a representative
are bothB-isomorphic to it. For hardness, fix the schema
{P:S×S}withU S \Binfinite. Encode each graph by
representing its vertices as distinct sort-Svalues outsideB,
addingP(u, u)foreveryvertexandbothP(u, v)andP(v, u)
for every edge. The self-loops retain isolated vertices, and
the resulting instances areB-isomorphic exactly when the
original graphs are isomorphic. Comparing their computed
invariants therefore decides graph isomorphism.
Deterministic Deployment Preservation
The canonical wrapper may produce set-valued policies,
whichweinterpretasnondeterministicdeployments:ateach
decision point, one returned call is executed, while verifica-
tion accounts for every call that may be selected. As Propo-
sition 17 shows, an arbitrary deterministic tie-break need
not preserve equivariance. We therefore identify when the
wrapper preserves singleton-valuedness.
Definition 20(Action-rigidity).A decision context(D, A)
isB-action-rigidifα(a) =afor everyB-automorphismα
ofDand everya∈A.
Action-rigidity requires only that the symmetries of the
state fix the calls available to the agent.
Proposition 21(Singleton preservation under action-rigid-
ity).Ifthebaseagent bΠissingleton-valuedandeveryreach-
able decision context(D,Offer(D))isB-action-rigid, then
Πcan(D,Offer(D))is a singleton.
Proof.Forσ, σ ′ ∈Lab B(D), letα=σ ′−1 ◦σ, aB-
automorphism ofD. Action-rigidity givesσ(Offer(D)) =
σ′(Offer(D)), so the singleton base policy selects the same
canonical callba. Sinceσ′−1(ba)∈Offer(D),α −1 fixes it,
and henceσ −1(ba) =α −1(σ′−1(ba)) =σ ′−1(ba). Thus all
witnesses return the same call.
A deployment may therefore use any canonical labelling,
query once, and map the result back, exactly realising
Πcan(D,Offer(D)). This is the implementation used in the
following worked example.
Worked Example
We use a small relational case-management workflow for
customerrefundrequeststoillustratethecanonicalwrapper,
the hypotheses of Theorem 13, the finite restriction, and the
resulting verification on a concrete STEAD.

## PDF Page 7

Workflow and deployment.Each request is represented
by a casecwith one refund taskt.PartOf(t, c)links
them;Handler(c, s)records the serviceshandling the
case, andApprover(s, a)pairs it with its approval service
a.CaseStatus(c, q),Approved(t, a), andRefundIssued(t)
record progress.
The initial state fixes two service configurations: handler
services 1 is paired with approval servicea 1, and han-
dler services 2 with approval servicea 2, as recorded by
Approver(s1, a1)andApprover(s 2, a2). No case is initially
recorded, and throughout execution the current state con-
tains facts for at most one case–task pair.ingest_case
creates a fresh pair and its initialPartOf,Handler, and
CaseStatusfacts. It is the only nondeterministic tool
effect: the case is routed to either handler, and fresh
case and task identifiers are chosen, with their concrete
names differing only by renaming. While the refund is
pending, the interface offersissue_refund(t)and
obtain_approval(t,a)for either approvera. After
issuance, it offersresolve_case(c), and after resolu-
tion,archive_case(c),whichremovesthecase-specific
facts and restores the initial state.obtain_approvalis
idempotentandremainsofferedwhiletherefundispending,
so an agent may repeat it forever and prevent progress.
We deploy Qwen3-4B under greedy structured decoding
through the canonical wrapper of the previous section. The
baselinepolicyaskstheagenttocompleteeachcasebutdoes
not explain how to derive the required approver or require
approval before refund issuance. Complete tool semantics
and prompts are given in the Appendix.
Specifications.Authorizationrequireseveryissuedrefund
to have been approved by the approval service paired with
the case handler. Progress requires every open case to be
eventually resolved on all executions:
φauth =AG∀t, c, s, a.
 
RefundIssued(t)∧PartOf(t, c)
∧Handler(c, s)∧Approver(s, a)→Approved(t, a)

,
φprog =AG∀c.
 
CaseStatus(c,open)
→AFCaseStatus(c,resolved)

.
Finite model construction.Repeated case intake over the
infinite case and task domains admits executions containing
indefinitelymanyidentifiers,althoughonlyonecaseandtask
areactiveatatime.LettherigidsetbeB={open,resolved}
andC=B∪ad(D 0).Freshcaseandtaskvalueslieoutside
ad(D)∪C.Henceb case =b task = 1,andeitherspecification
contains at most one case variable and one task variable, so
Theorem 13 requires three case and three task representa-
tives. The finite service and status domains are retained in
full,soU f consistsofCplusanythreecasevaluesandthree
task values, giving 12 values overall.
The wrapper uses the following canonical serialization.
Under the fixed canonical ordering, the active case and task
arepresentedasCASE_1andTASK_1;whicheverhandler–
approver pair receives the case is presented asSERVICE_1
andSERVICE_2, while the other pair is presented as
SERVICE_3andSERVICE_4.Thusallidentifierandrout-
ing variants of each active phase induce the same decision
context.AtD 0,thetwoservicepairsareinterchangeable,but
theonlyofferedcallisthenullaryingest_case().Oncea
caseisactive,itsHandleredgedistinguishestheselectedpair.
Everyofferedcallisthereforefixedbyeveryautomorphism,
soaction-rigiditykeepsthewrappedpolicysingleton-valued.
The tool interface guards and tool effects are expressible
in first-order logic and mention only constants inC, so they
commute with renamings, while the wrapper provides agent
equivariance. Theorem 13 establishes that verification over
Mf =M A ↾U f is exact for both specifications. The Ap-
pendix gives the complete STEAD specification and shows
that the required local conditions hold.
WebuildthereachablepartofM f bybreadth-firstexplo-
ration over concrete states onUf. At each discovered state
D,wecomputeOffer(D),canonicalizethedecisioncontext,
map the wrapped agent’s selected call back toD, and add
every successor inτ(D, a)whose values lie inU f. Case
intake branches over two handlers and nine fresh case–task
pairs, giving 18 successors ofD0; the wrapped agent then
drives each deterministically through issuance, resolution,
andarchival.Theexplorationthereforereaches55statesand
72 transitions, while canonicalization reduces the 55 result-
ingdecisioncontextstofourdistinctbase-agentqueries:case
intake, pending refund, refund issued, and resolved.
Verification result.We use a simple explicit-state eval-
uator that computes FO-CTL satisfaction sets bottom-up
over this graph. First-order subformulas are evaluated over
the finite sorted domain, and temporal operators are eval-
uated by standard CTL state-labelling and fixpoint proce-
dures (Clarke, Emerson, and Sistla 1986). The evaluator re-
futesφ authandcertifiesφ prog.Thecounterexampleingestsa
casewithtasktandimmediatelycallsissue_refund(t),
although the case handler’s paired approverahas not ap-
provedt.ByTheorem13,theseresultstransferexactlytothe
wrapped infinite-domain deployment.
Discussion and Conclusion
Toourknowledge,thisworkprovidesthefirstformalframe-
work for pre-deployment verification of an LLM-driven
agenticsystemagainstfirst-ordertemporalrequirementsover
evolving operational data. Rather than working at the inter-
face level, which significantly restricts the guarantees one
can establish over the system, the framework verifies the
complete behaviour induced by a fixed agent, its tools, and
the persistent state, including both safety and progress prop-
erties.Ourresultsidentifyagentequivarianceasthespecific
obstacle to applying relational finite-abstraction techniques
and show how to enforce it by construction without altering
already-equivariant behaviour.
Futureworkcanextendtheframeworktoricheragenticar-
chitectures, including multiple interacting agents, persistent
memory, and more complex interactions with the environ-
ment. Finite abstractions may also support the derivation of
maximally permissive, data-aware restrictions on the tools
offeredtoanagent,providingaverifiedlayerreusableacross
deployments.Animmediatenextstepistoimprovescalabil-
itybybuildingonexistingworkincanonicalisation(McKay
and Piperno 2014) and verification (Calvanese et al. 2020).

## PDF Page 8

Acknowledgements
Alejandro Mercado is supported by an Imperial College
London President’s PhD Scholarship. Alessio Lomuscio is
partially supported by the Royal Academy of Engineering
via a Chair of Emerging Technologies.
References
Acharya, D. B.; Kuppan, K.; and Bhaskaracharya, D. 2025.
Agentic AI: Autonomous Intelligence for Complex Goals -
A Comprehensive Survey.IEEE Access, 13: 18912–18936.
Ali,M.A.;Dornaika,F.;andCharafeddine,J.2026. Agentic
AI: a comprehensive survey of architectures, applications,
and future directions.Artif. Intell. Rev., 59(1): 11.
Barres, V.; Dong, H.; Ray, S.; Si, X.; and Narasimhan, K.
2025.τ 2-Bench: Evaluating Conversational Agents in a
Dual-Control Environment. arXiv:2506.07982.
Belardinelli, F.; Lomuscio, A.; and Patrizi, F. 2012. An Ab-
straction Technique for the Verification of Artifact-Centric
Systems. In Brewka, G.; Eiter, T.; and McIlraith, S. A.,
eds.,Principles of Knowledge Representation and Reason-
ing:ProceedingsoftheThirteenthInternationalConference,
KR 2012, Rome, Italy, June 10-14, 2012. AAAI Press.
Belardinelli, F.; Lomuscio, A.; and Patrizi, F. 2014. Verifi-
cationofAgent-BasedArtifactSystems.J.Artif.Intell.Res.,
51: 333–376.
Calvanese,D.;DeGiacomo,G.;andMontali,M.2013.Foun-
dationsofdata-awareprocessanalysis:adatabasetheoryper-
spective. In Hull, R.; and Fan, W., eds.,Proceedings of the
32ndACMSIGMOD-SIGACT-SIGARTSymposiumonPrin-
ciplesofDatabaseSystems,PODS2013,NewYork,NY,USA
- June 22 - 27, 2013, 1–12. ACM.
Calvanese, D.; De Giacomo, G.; Montali, M.; and Patrizi,
F. 2018. First-orderµ-calculus over generic transition sys-
temsandapplicationstothesituationcalculus.Inf.Comput.,
259(3): 328–347.
Calvanese, D.; Ghilardi, S.; Gianola, A.; Montali, M.; and
Rivkin, A. 2020. SMT-based verification of data-aware pro-
cesses: a model-theoretic approach.Math. Struct. Comput.
Sci., 30(3): 271–313.
Chen,Z.;Kang,M.;andLi,B.2025. ShieldAgent:Shielding
Agents via Verifiable Safety Policy Reasoning. In Singh,
A.; Fazel, M.; Hsu, D.; Lacoste-Julien, S.; Berkenkamp, F.;
Maharaj, T.; Wagstaff, K.; and Zhu, J., eds.,Forty-second
InternationalConferenceonMachineLearning,ICML2025,
Vancouver, BC, Canada, July 13-19, 2025, Proceedings of
Machine Learning Research. PMLR / OpenReview.net.
Clarke, E.M.; Emerson, E. A.;and Sistla, A. P.1986. Auto-
maticVerificationofFinite-StateConcurrentSystemsUsing
TemporalLogicSpecifications.ACMTrans.Program.Lang.
Syst., 8(2): 244–263.
De Giacomo, G.; Kampik, T.; Kirchdorfer, L.; Montali, M.;
and Weinhuber, C. 2026. Formal Foundations of Agentic
Business Process Management. arXiv:2604.17347.
Deutsch,A.;Hull,R.;Li,Y.;andVianu,V.2018. Automatic
verification of database-centric systems.ACM SIGLOG
News, 5(2): 37–56.
Deutsch, A.; Hull, R.; Patrizi, F.; and Vianu, V. 2009. Au-
tomatic verification of data-centric business processes. In
Fagin, R., ed.,Database Theory - ICDT 2009, 12th Inter-
national Conference, St. Petersburg, Russia, March 23-25,
2009, Proceedings, volume 361 ofACM International Con-
ference Proceeding Series, 252–267. ACM.
Hariri, B. B.; Calvanese, D.; De Giacomo, G.; Deutsch,
A.; and Montali, M. 2013. Verification of relational data-
centric dynamic systems with external services. In Hull, R.;
and Fan, W., eds.,Proceedings of the 32nd ACM SIGMOD-
SIGACT-SIGARTSymposiumonPrinciplesofDatabaseSys-
tems, PODS 2013, New York, NY, USA - June 22 - 27, 2013,
163–174. ACM.
Kamath, A.; Zhang, S.; Xu, C.; Ugare, S.; Singh, G.; and
Misailovic, S. 2025. Enforcing Temporal Constraints for
LLM Agents. arXiv:2512.23738.
Kim,J.;Liu,X.;Wang,Z.;Qiu,S.;Li,B.;Guo,W.;andSong,
D. 2026. The Attack and Defense Landscape of Agentic AI:
A Comprehensive Survey. arXiv:2603.11088.
Liu,C.;Arnon,T.;Lazarus,C.;Strong,C.A.;Barrett,C.W.;
and Kochenderfer, M. J. 2021. Algorithms for Verifying
Deep Neural Networks.Found. Trends Optim., 4(3-4): 244–
404.
Liu, X.; Yu, H.; Zhang, H.; Xu, Y.; Lei, X.; Lai, H.; Gu, Y.;
Ding, H.; Men, K.; Yang, K.; Zhang, S.; Deng, X.; Zeng,
A.; Du, Z.; Zhang, C.; Shen, S.; Zhang, T.; Su, Y.; Sun,
H.; Huang, M.; Dong, Y.; and Tang, J. 2024. AgentBench:
Evaluating LLMs as Agents. InThe Twelfth International
Conference on Learning Representations, ICLR 2024, Vi-
enna, Austria, May 7-11, 2024. OpenReview.net.
Lou, Q.; Liang, X.; Xue, J.; Zhang, Y.; Xie, R.; and Zheng,
M. 2024. CR-UTP: Certified Robustness against Universal
Text Perturbations on Large Language Models. In Ku, L.;
Martins, A.; and Srikumar, V., eds.,Findings of the Asso-
ciation for Computational Linguistics, ACL 2024, Bangkok,
Thailand and virtual meeting, August 11-16, 2024, volume
ACL 2024 ofFindings of ACL, 9863–9875. Association for
Computational Linguistics.
Lu, J.; Holleis, T.; Zhang, Y.; Aumayer, B.; Nan, F.; Bai, H.;
Ma,S.;Ma,S.;Li,M.;Yin,G.;Wang,Z.;andPang,R.2025.
ToolSandbox:AStateful,Conversational,InteractiveEvalua-
tionBenchmarkforLLMToolUseCapabilities.InChiruzzo,
L.;Ritter,A.;andWang,L.,eds.,FindingsoftheAssociation
for Computational Linguistics: NAACL 2025, Albuquerque,
NewMexico,USA,April29-May4,2025,FindingsofACL,
1160–1183. Association for Computational Linguistics.
McKay, B. D.; and Piperno, A. 2014. Practical graph iso-
morphism, II.J. Symb. Comput., 60: 94–112.
Mizrahi, M.; Kaplan, G.; Malkin, D.; Dror, R.; Shahaf, D.;
andStanovsky,G.2024. StateofWhatArt?ACallforMulti-
PromptLLMEvaluation.Trans.Assoc.Comput.Linguistics,
12: 933–949.
Schick, T.; Dwivedi-Yu, J.; Dessì, R.; Raileanu, R.; Lomeli,
M.;Hambro,E.;Zettlemoyer,L.;Cancedda,N.;andScialom,
T. 2023. Toolformer: Language Models Can Teach Them-
selvestoUseTools. InOh,A.;Naumann,T.;Globerson,A.;

## PDF Page 9

Saenko,K.;Hardt,M.;andLevine,S.,eds.,AdvancesinNeu-
ral Information Processing Systems 36: Annual Conference
on Neural Information Processing Systems 2023, NeurIPS
2023, New Orleans, LA, USA, December 10 - 16, 2023.
Sclar, M.; Choi, Y.; Tsvetkov, Y.; and Suhr, A. 2024. Quan-
tifying Language Models’ Sensitivity to Spurious Features
in Prompt Design or: How I learned to start worrying about
prompt formatting. InTheTwelfth InternationalConference
on Learning Representations, ICLR 2024, Vienna, Austria,
May 7-11, 2024. OpenReview.net.
Trivedi, H.; Khot, T.; Hartmann, M.; Manku, R.; Dong, V.;
Li, E.; Gupta, S.; Sabharwal, A.; and Balasubramanian, N.
2024. AppWorld: A Controllable World of Apps and Peo-
ple for Benchmarking Interactive Coding Agents. In Ku,
L.; Martins, A.; and Srikumar, V., eds.,Proceedings of the
62nd Annual Meeting of the Association for Computational
Linguistics (Volume 1: Long Papers), ACL 2024, Bangkok,
Thailand, August 11-16, 2024, 16022–16076. Association
for Computational Linguistics.
Wang, H.; Poskitt, C. M.; and Sun, J. 2025. AgentSpec:
Customizable Runtime Enforcement for Safe and Reliable
LLM Agents. arXiv:2503.18666.
Wang, H.; Poskitt, C. M.; Wei, J.; and Sun, J. 2026. Prob-
Guard:ProactiveRuntimeMonitoringforLLMAgentSafety
via Probabilistic Prediction. arXiv:2508.00500.
Wang, X.; Wang, H.; and Yang, D. 2022. Measure and Im-
prove Robustness in NLP Models: A Survey. In Carpuat,
M.; de Marneffe, M.; and Ruíz, I. V. M., eds.,Proceed-
ings of the 2022 Conference of the North American Chapter
of the Association for Computational Linguistics: Human
Language Technologies, NAACL 2022, Seattle, WA, United
States, July 10-15, 2022, 4569–4586. Association for Com-
putational Linguistics.
Xiang, Z.; Zheng, L.; Li, Y.; Hong, J.; Li, Q.; Xie, H.;
Zhang, J.; Xiong, Z.; Xie, C.; Yang, C.; Song, D.; and Li, B.
2025. GuardAgent:SafeguardLLM AgentsviaKnowledge-
Enabled Reasoning. In Singh, A.; Fazel, M.; Hsu, D.;
Lacoste-Julien, S.; Berkenkamp, F.; Maharaj, T.; Wagstaff,
K.;andZhu,J.,eds.,Forty-secondInternationalConference
onMachineLearning,ICML2025,Vancouver,BC,Canada,
July 13-19, 2025, volume 267 ofProceedings of Machine
Learning Research. PMLR / OpenReview.net.
Yang, A.; Li, A.; Yang, B.; Zhang, B.; Hui, B.; Zheng, B.;
Yu,B.;Gao,C.;Huang,C.;Lv,C.;Zheng,C.;Liu,D.;Zhou,
F.;Huang,F.;Hu,F.;Ge,H.;Wei,H.;Lin,H.;Tang,J.;Yang,
J.; Tu, J.; Zhang, J.; Yang, J.; Yang, J.; Zhou, J.; Zhou, J.;
Lin, J.; Dang, K.; Bao, K.; Yang, K.; Yu, L.; Deng, L.; Li,
M.; Xue, M.; Li, M.; Zhang, P.; Wang, P.; Zhu, Q.; Men,
R.; Gao, R.; Liu, S.; Luo, S.; Li, T.; Tang, T.; Yin, W.; Ren,
X.; Wang, X.; Zhang, X.; Ren, X.; Fan, Y.; Su, Y.; Zhang,
Y.; Zhang, Y.; Wan, Y.; Liu, Y.; Wang, Z.; Cui, Z.; Zhang,
Z.; Zhou, Z.; and Qiu, Z. 2025. Qwen3 Technical Report.
arXiv:2505.09388.
Yao, S.; Shinn, N.; Razavi, P.; and Narasimhan, K. 2024.
τ-bench: A Benchmark for Tool-Agent-User Interaction in
Real-World Domains. arXiv:2406.12045.
Yao, S.; Zhao, J.; Yu, D.; Du, N.; Shafran, I.; Narasimhan,
K.R.;andCao,Y.2023. ReAct:SynergizingReasoningand
Acting in Language Models. InThe Eleventh International
ConferenceonLearningRepresentations,ICLR2023,Kigali,
Rwanda, May 1-5, 2023. OpenReview.net.
Ye, M.; Gong, C.; and Liu, Q. 2020. SAFER: A Structure-
free Approach for Certified Robustness to Adversarial Word
Substitutions. In Jurafsky, D.; Chai, J.; Schluter, N.; and
Tetreault, J. R., eds.,Proceedings of the 58th Annual Meet-
ing of the Association for Computational Linguistics, ACL
2020, Online, July 5-10, 2020, 3465–3475. Association for
Computational Linguistics.
Zhou, S.; Xu, F. F.; Zhu, H.; Zhou, X.; Lo, R.; Sridhar, A.;
Cheng, X.; Ou, T.; Bisk, Y.; Fried, D.; Alon, U.; and Neu-
big, G. 2024. WebArena: A Realistic Web Environment
for Building Autonomous Agents. InThe Twelfth Interna-
tionalConferenceonLearningRepresentations,ICLR2024,
Vienna, Austria, May 7-11, 2024. OpenReview.net.

## PDF Page 10

Appendix
This appendix follows the order of the main paper. Sections A and C give full proofs of its theoretical results; Sections B
and D provide the exact formal and experimental details underlying the two examples; Section E gives reproduction details.
Numbering of definitions and results follows the main paper.
A Supplement to “Stateful Tool-Enabled Agentic Deployment”
This appendix proves the two verification results of the main paper: undecidability of the STEAD verification problem, and
exact preservation of FO-CTL specifications under a finite-domain restriction.
A.1 Undecidability
Theorem 8 (Undecidability, restated).The STEAD verification problem is undecidable.
The problem is understood over finitely specified deployments: schema, tool schemas, interface, tool semantics, and agent
policy are each given by a finite description.
Proof.Verification of finitely specified relational data-centric systems with nondeterministic services against propositional
invariantsG pisundecidable(Haririetal.2013,Thm.5.1,full-versionproof).LetSbesuchasystem,withschemaD,domain
U,initialinstanceD 0,andtransitionrelation⇒ S inducedbyitsfiniteprocessspecification.Underthenondeterministic-service
semanticsasourcestateisarelationalinstance,so⇒ S isarelationonD(U);theone-sortedcaseisaspecialcaseofoursetting.
Construct the STEAD
AS =

⟨D, U, D0⟩,⟨{step}, τ,Offer⟩,Π

,
whose only tool schema is nullary, with unique grounded callstep(), and put, for everyD∈ D(U),
Offer(D) ={step()},Π(D, A) =A, τ(D,step()) ={D} ∪ {D ′ :D⇒ S D′}.
The finite process specification ofS, together with the identity effect, is a finite symbolic description ofτ, so the translation is
effective. SinceD∈τ(D,step())for everyD, the offered call always has a nonempty effect, as Definition 5 requires. By that
definition,
D→ Π,Offer D′ ⇐ ⇒D ′ ∈τ(D,step())⇐ ⇒D=D ′ orD⇒ S D′,
so→ Π,Offer is the reflexive closure of⇒S and the two systems have the same reachable states. Readingpas the corresponding
closed first-order state formula, bothG pandAG passert thatpholds at every reachable state, from which we have
S |=G p⇐ ⇒ M AS |=AG p.
A.2 Exact Finite Verification
Theorem13(Exactfiniteverification,restated).LetφbeanFO-CTLsentence,letC⊆Ubefinitewithcon(φ)∪ad(D 0)⊆C
and putR=Reach(M A). Assume thatMA isC-bounded byb= (b S)S∈S, thatOfferandΠareC-equivariant onR, and
thatτisC-tool-uniform onR. Then every finite sorted subdomainUf withC⊆U f ⊆Uand satisfying, for each sortS,
(Uf)S =U S or|(U f)S| ≥2b S +|C∩U S|+ var S(φ),
induces a finite state transition system such that
MA |=φ⇐ ⇒ M A ↾U f |=φ,
wherevar S(φ)counts the sort-Svariables ofφ. FO-CTL verification over an explicitly given restriction is PSPACE-complete
in combined complexity.
Throughout this subsection we fix the data and hypotheses of the theorem and write
M=M A =⟨U, D 0,→⟩,M f =M↾U f =⟨U f , D0,→ f ⟩,
abbreviating→ Π,Offer by→. We putC S =C∩U S, letVbe the variables occurring inφ, and letV S be those of sortS, so
|VS|= var S(φ).
ForD∈R, ¯D∈Reach(M f), and sort-correct assignmentsν:V→Uand¯ν:V→U f, we write(D, ν)≡( ¯D,¯ν)when
there is a sort-preserving bijection
γ:ad(D)∪C∪ν(V)− →ad( ¯D)∪C∪¯ν(V)
that fixesCpointwise, restricts to a witness forD≃C ¯D, and satisfiesγ(ν(x)) = ¯ν(x)for everyx∈V.
The following three lemmas establish the properties labelled(R),(T), and(M)in the proof sketch of Theorem 13.

## PDF Page 11