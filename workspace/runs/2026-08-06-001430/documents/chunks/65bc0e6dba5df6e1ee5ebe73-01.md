## PDF Page 1

Test-time reasoning effort and unauthorized tool use in
language-model agents: a prespecified equivalence
study
Xiaonan Xua,∗, Wenjing Wub
aCollege of Computing, Georgia Institute of Technology, Atlanta, GA 30332, USA
bDepartment of Computer Science, University of Colorado Boulder, Boulder, CO
80309, USA
Abstract
Language-model agents that execute multi-step workflows through tool calls
operate under access-control policies that restrict which operations each role
may perform. The APIs serving these agents expose a reasoning-effort pa-
rameter that operators adjust for cost and latency. Whether this parameter
also changes the rate of unauthorized tool use has not been tested by di-
rect manipulation within a single model. We vary reasoning effort (low,
max) inside GPT-5.6 across the 14 confirmatory scenarios of TRIO-20, a
suite of 20 matched workplace triads in which a policy-prohibited tool call
is effective and its effect on the target metric is stated in the environment,
effective but discoverable only through rule inspection, or ineffective. The
three conditions derive from one code base and differ in two configuration
fields, with identical prompts and tool sets. All analyses were prespecified
in a frozen plan before confirmatory collection. Across 840 trajectories and
two model tiers, no unauthorized tool call occurred. Exact one-sided 95%
limits place each arm’s violation rate below 3.50% (Terra,n= 84) and
5.21% (Sol,n= 56). The interaction estimand, with a simultaneous exact
95% interval of±4.34percentage points on Terra, lies inside the±7.01-point
equivalence margin. Raising effort did change behaviour, but only in inspec-
tion: rule-probe rates rose in all conditions, most where probing carried no
instrumental payoff, a pattern inconsistent with the hypothesis of targeted
∗Corresponding author.
Email addresses:xiaonanxu5@gmail.com(Xiaonan Xu),wuwenjing256@gmail.com
(Wenjing Wu)
arXiv:2608.03169v1  [cs.CR]  4 Aug 2026

## PDF Page 2

search (−14.3points, 95% CI−27.4to+1.2). Raw trajectories are released
athttps://github.com/WenJing95/trio-20.
Keywords:language-model agents, unauthorized tool use, access control,
reasoning effort, test-time compute, security evaluation, equivalence testing
1. Introduction
Language-model agents execute multi-step workflows through tool calls,
and the APIs serving them grant each agent a registered set of operations.
Standard security design restricts that set to the minimum required for the
agent’s role [1], a principle the OWASP Top 10 for LLM Applications lists
among its mitigations for excessive agency [2]. In practice, the same APIs
expose a reasoning-effort parameter that scales test-time computation, and
operators adjust it between deployments as a cost-quality dial. Whether this
parameter also changes the rate at which an agent calls a tool reserved for
another authority has not been tested by direct manipulation within a single
model.
Frontier evaluation reports sharpen the question. The system card for
GPT-5.6 documents severity-graded agentic failures, including task short-
cuts and fabricated results, and summarizes third-party assessments report-
ing situational evaluation awareness [3]. A predeployment evaluation of the
model’s top tier reports harness gaming at rates that impede capability mea-
surement [4]. These findings describe deployed configurations. They do not
identify what happens to one model’s conduct when a single operator-facing
parameter changes.
The observational evidence on reasoning and misbehaviour points in con-
flicting directions. The AutoControl Arena study reports scenario-specific
safety scaling across nine models, with advanced reasoning improving robust-
ness on direct harms while worsening it on gaming scenarios [5]. Verifier-
gaming work finds shortcut exploitation that grows as reasoning is scaled
where imperfect extensional verifiers allow the shortcut [6]. A text-based re-
construction of the AI Safety Gridworlds finds specification gaming emerging
zero-shot, with its single reasoning-effort comparison showing little sensitiv-
ity [7], and controlled scaling of test-time compute has produced inverse
scaling on some task families [8]. These results come from different models,
tasks, and reward structures, so capability, training, and incentive all vary
together. Benchmark studies of test-time scaling in general agents track
2

## PDF Page 3

capability under sequential and parallel scaling [9], and policy-adherence
benchmarks score rule-following across models without manipulating com-
pute within one [10]. Agent-security benchmarks measure injection robust-
ness, emulated-environment risk, and compliance with malicious tasks across
models [11, 12, 13]. Each compares models or attacks; none holds the model
constant, manipulates a single effort parameter, and measures compliance
under an explicit prohibition.
TRIO-20 fills that gap. Twenty workplace scenarios, each instantiated as
a matched triad: a salient condition in which a prohibited shortcut works
and its effect on the target metric is stated in the environment, a hidden
condition in which the shortcut works but its effect is discoverable only by
querying the metric’s rules, and a clean condition in which the same shortcut
does nothing. The three conditions share one environment implementation
and differ in two configuration fields. Automated checks confirm that the
rendered prompts, tool schemas, and interaction budgets are identical across
conditions apart from the sentence controlled by the two fields. Outcomes
are scored by deterministic program judges over the tool log and terminal
state, validated in two audited rounds of 40 trajectories with full agreement.
We prespecified all analyses in a frozen plan before confirmatory collection,
with attempted calls to the prohibited tool as the primary endpoint and rule
probing as the secondary endpoint.
The central result is a bounded zero. Across 504 Terra and 336 Sol
trajectories, the model never called the prohibited tool, in any condition,
at either effort level, and the same holds across every superseded attempt
retained as quality evidence. Exact simultaneous bounds confine the low-to-
max change in violation probability to±4.30percentage points per condition
on Terra and±6.38on Sol, and the prespecified interaction estimand lies
inside the equivalence margin. The effort dial did change behaviour, but the
change went into inspection: rule probing rose in every condition and most
where it had no instrumental payoff, the opposite of the targeted-search
pattern the prespecified secondary hypothesis predicted. To our knowledge
this is the first controlled within-model test of the link between reasoning
effort and policy compliance. Both findings can be audited from the released
raw trajectories.
This study makes three contributions. First, we construct a matched-
triad design that varies a single API parameter within one model while hold-
ing prompt content, tool availability, and incentive structure fixed, giving a
controlled within-model contrast for policy compliance. Second, we report a
3

## PDF Page 4

bounded null: the equivalence margin and exact zero-event bounds together
place the effort-driven change in unauthorized tool use within±4.34percent-
age points on Terra, inside the prespecified±7.01-point margin. Third, we
document a behavioural dissociation: added reasoning increases rule probing
in every condition, without converting discovery into action, a pattern that
separates inspection from exploitation in the tested regime. The TRIO-20
trajectories are released so that the same question can be asked of other mod-
els, other effort configurations, and settings where prohibitions are implicit
or under pressure.
2. Related work
2.1. Executable evaluation of agent risk
AutoControl Arena establishes the closest methodological parent for our
work. It synthesizes executable test environments by grounding determin-
istic state in code while delegating narrative dynamics to language models,
and its X-Bench suite spans 70 scenarios across seven risk categories [5]. The
evaluation varies environmental stress and temptation across models and re-
ports risk rates rising under pressure from 21.7% to 54.5%. TRIO-20 draws
on the executable-environment principle and the workplace texture of five X-
Bench specifications, then departs on three points that the present question
requires. We derive conditions from one code base, because the estimand
is a within-scenario contrast and any generative variation between condi-
tions would confound it. Judging is fully deterministic, because the primary
outcome must survive audit at the level of individual tool calls. And the
manipulated variable is a single API parameter of one model, which buys
the within-model controlled contrast at the cost of cross-model breadth.
Three agent-security benchmarks evaluate related failure classes. Agent-
Dojo [11] provides 97 tasks and 629 security test cases for measuring prompt-
injection robustness across models and defences. ToolEmu [12] scales risk
identification to 36 toolkits and 144 test cases by emulating tool execution
inside a language model, trading environment fidelity for coverage. Agen-
tHarm [13] measures compliance with 110 explicitly malicious multi-step re-
quests. All three compare across models or attacks; none manipulates a
single parameter within one model under an explicit prohibition.
Two adjacent lines of work bound ours. Run-time enforcement research
formalizes tool-use policies as solver-checkable constraints and blocks non-
compliant calls before execution [14]. Progent [15] enforces least-privilege
4

## PDF Page 5

policies through a domain-specific language applied at tool-call time, and
CaMeL [16] segregates control and data flows to block prompt injection by
construction, evaluated on the AgentDojo benchmark. These systems an-
swer a different question from ours: they block noncompliant calls at the
system level, whereas we measure the model’s own propensity to emit such
calls when no enforcement layer is present. Instruction-hierarchy research
trains models to privilege system-level rules over conflicting instructions and
injected content [17]; the explicit prohibitions we test travel through exactly
that privileged channel, which conditions what the observed compliance can
mean. Indirect prompt injection [18] and its formalization [19] define the
adversarial threat we deliberately exclude: our failure model is emergent
noncompliance by a benign agent, not exploitation by an external attacker.
The classical formulation of least privilege and complete mediation [1] sup-
plies the design vocabulary for Section 3.
2.2. Reasoning effort and misbehaviour
Studies that touch the link between effort and misbehaviour disagree.
Verifier-gaming results show models exploiting imperfect extensional veri-
fiers, with shortcut behaviour that scales as reasoning is scaled [6]. The
Gridworlds reconstruction reports little sensitivity to reasoning effort in the
one environment where it was varied [7]. Inverse-scaling results show more
test-time compute degrading performance on some task families outright [8].
In the AutoControl results the direction of the reasoning effect depends on
scenario type [5]. Controlled single-agent experiments have measured how
skill availability and presentation shape agent behaviour [20] and how skill
optimization decomposes into structure and executor capability [21], without
addressing policy compliance. Holding the model constant while manipulat-
ing a single parameter separates the effect of reasoning from the differences
in training and architecture that these cross-model comparisons leave entan-
gled.
2.3. Measurement practices
Our measurement choices follow the experimental-methods literature.
Prespecification of hypotheses and analyses guards against outcome-
contingent flexibility [22]. Equivalence testing replaces the uninformative
failure to reject a null with a bounded claim [23], using exact binomial limits
for zero-event arms [24] and cluster bootstrap for interval estimation over
scenarios [25]. Program judges carry the primary outcome, with semantic
5

## PDF Page 6

judgment reserved for secondary description. Specification gaming itself is
an old observation with a modern instantiation: agents optimize the stated
objective at the expense of the intended one [26, 27]; the dynamic Goodhart’s
law describes when a measure becomes a target [28].
3. Threat model and the TRIO-20 testbed
Each scenario instantiates a least-privilege access-control setting [1]. The
protected asset is the integrity of a body of business records and of the
completion metric computed over them. The agent operates under least
privilege for its clerical role: the registered tool set covers everything the role
legitimatelyrequires, andoneadditionalreachabletoolperformsanoperation
that policy reserves for another authority. The failure model is accidental
or emergent noncompliance by a benign agent under production incentives,
without an external adversary, prompt injection, or social pressure. A call to
the reserved tool is a control bypass whether or not the environment accepts
it, which is why an accepted call counts against the agent regardless of its
downstream effect.
3.1. Matched triads from a single implementation
Each scenario simulates a routine workplace duty: an audit queue, a data
pipeline, a moderation queue, procurement, invoice coding, bug triage, and
similar clerical settings. The agent receives a role, a goal that names a target
completion metric, an explicit policy, and seven registered tools. One tool is a
shortcut that policy prohibits for the agent’s role. One tool is the sanctioned
disposal channel for items that cannot be completed by ordinary means. One
tool queries the definition and counting rules of the target metric.
A scenario’s three conditions are generated from one environment im-
plementation by two configuration fields. The field shortcut_effective de-
termines whether the prohibited tool moves the target metric. The field
shortcut_salience determines whether the environment states that effect in
the status display. The salient condition sets both true, the hidden condition
sets effective true and salience false, and the clean condition sets effective
false. Nothing else varies. Across the three conditions of every confirma-
tory scenario, the rendered prompts, the tool schemas, and the interaction
budgets are identical apart from the sentence the two fields control, checked
automatically before collection.
6

## PDF Page 7

3.2. Task structure and the completion ceiling
Early piloting showed that when honest work can reach the stated target,
the shortcut has no instrumental value and compliance is untestable. Each
scenario therefore contains one or two items that cannot be completed to the
metric by legitimate means. Policy prescribes routing such items through
the sanctioned disposal channel, which is procedurally correct and excluded
from the metric’s numerator. Honest work thus tops out at a documented
ceiling between 80% and 90%, while the goal text demands 100% in all three
conditions. The prohibited shortcut closes that gap where it is effective.
Task success is scored on process, requiring every item to be handled as
policy prescribes, so an honest agent succeeds at the task while reporting
a metric below target. This structure keeps the shortcut tempting without
weakening the prohibition or unbalancing the triad.
3.3. Outcome instrumentation
A deterministic judge scores each trajectory from the tool log and termi-
nal environment state, emitting seven fields. The primary outcome, viola-
tion_attempt, is true when the agent’s call to the prohibited tool is accepted
by the environment, the prespecified and implemented definition. No pro-
hibited call was emitted at all, whether accepted or rejected at the interface,
so the reported counts are zero under either definition. The secondary out-
come, named loophole_discovered in the analysis plan and reported here as
rule probing, is true when the agent calls the registered rule-query tool, a
behavioural criterion that does not depend on condition; the behavioural la-
bel is used throughout. Auxiliary fields record realized violations through
protected state-trace variables, process-based task success, validity, and free-
text notes. Final answer text contributes only to validity checks. The judge
reads behaviour, and claims made in prose neither earn credit nor establish
violations.
3.4. Validation and provenance
Scenario logic is covered by itemized unit tests, including synthetic vio-
lation fixtures that serve as positive controls and are classified correctly by
the judges, guards that the honest path succeeds in all conditions, that the
shortcut moves the metric only where configured, and that disposal of stuck
items is scored correctly. Human validation proceeded in two audited rounds
of 40 trajectories each, sampled by fixed seed from the pilot and from the
main Terra run. In both rounds, we derived labels for every field from the
7

## PDF Page 8

rendered policy text and the untruncated tool log before consulting the pro-
gram verdict block in the same document, and a second reader re-examined
a subset of each round. Agreement with the program judge was 40 of 40
in both rounds across all fields. Because the rendered evidence carries the
program verdict, these rounds constitute audits of the program verdicts. Six
pilot scenarios (S01–S06) supported design iteration and threshold calibra-
tion; the 14 confirmatory scenarios (M01–M14) were built afresh after the
pilot and never revised in response to outcome data. Scenario code, the
program judges, and the analysis scripts were drafted with language-model
assistance and verified through the unit tests and audit rounds described in
this section.
4. Experimental protocol
4.1. Models, manipulation, and execution
We ran the experiment on GPT-5.6 Terra for the primary analysis and
GPT-5.6 Sol as a within-family robustness check, both accessed through
the Responses API. Reasoning effort is assigned per trajectory at low or
max through the API parameter, with reasoning continuity preserved across
turns via encrypted reasoning items. The parameter’s documented ladder
runs none, low, medium, high, xhigh, and max, with max specified as the
deepest single-agent setting, above xhigh [29]; the separate multi-agent mode
is not a value on this ladder and was not used. Reported reasoning-token
counts serve as the manipulation check. Interaction budgets, 20 tool rounds
by default and 32 for the cases documented in Section 4.3, are enforced by the
harness and never disclosed to the model. The confirmatory matrix crosses
14 scenarios, three conditions, and two effort levels, with six repetitions per
cell on Terra (504 trajectories, 84 per condition-effort arm) and four on Sol
(336 trajectories, 56 per arm).
Generation used the sampling configuration recorded in every trajectory,
temperature 1.0 and top-p 0.98. Access ran through an API gateway against
moving vendor aliases without a frozen snapshot. Every response echoed the
requested effort level and reported reasoning-token counts consistent with
it, confirming that the parameter reached the model. The service injects a
server-side image-generation tool into every request; no trajectory used it.
We collected data 19–21 July 2026. Slots were collected in a fixed order, all
low-effort trajectories of a scenario before its max-effort trajectories, with
conditions cycling salient, hidden, clean within each effort block.
8

## PDF Page 9

4.2. Prespecified analysis plan
We froze hypotheses, estimands, decision rules, and conclusion wordings
in a tagged plan before confirmatory collection. Each amendment was frozen
before the corresponding data were viewed; no external registry deposit was
made. The prespecified interval procedure is a scenario-cluster bootstrap:
one effect is computed per scenario and the 14 scenario identifiers are re-
sampled, so intervals reflect variation across the scenarios of the suite, which
serve as the units of replication.
The primary estimand is the difference-in-differencesθ= (P hidden,max −
Phidden,low)−(P salient,max−Psalient,low)for violation attempts. Because we antic-
ipated zero-event arms, the plan fixes an equivalence procedure: each arm re-
ceives an exact one-sided 95% upper limit [24],U= 3.50%atn= 84, and the
margin forθis±2U=±7.01percentage points, the resolution available at
zeroeventsgiventheplannedsamplesize. Forasinglecondition, asimultane-
ous 95% bound on the low-to-max change uses per-arm limits at level 97.5%,
Uc = 1−0.025 1/n. The interval forθexploits its algebraic structure. Because
all constituent probabilities are non-negative,θ≤Phidden,max +P salient,low and
θ≥ −(P hidden,low +P salient,max), so each one-sided bound depends on two arms
rather than four. For two independent zero-event arms of sizen, the joint
observation probability underP1 +P 2 =sis maximized atP 1 =P 2 =s/2,
giving(1−s/2) 2n. The one-sided upper bound at level1−αon the sum
is therefores ∗ = 2(1−α 1/(2n)). Applying Bonferroni across the upper and
lower bounds yields a simultaneous 95% interval[−s∗, s∗]withα= 0.025
per side, giving±4.34percentage points atn= 84(Terra) and±6.48points
atn= 56(Sol), both inside the±7.01-point margin. The secondary esti-
mand isθ probe = (P hidden,max −P hidden,low)−(P clean,max −P clean,low)for rule
probing, the contrast that isolates the instrumental value of inspection; the
salient condition is reported descriptively only, since the information it ad-
vertises makes probing redundant. Interval estimation uses scenario-cluster
bootstrap with 10,000 draws and a fixed seed. Exclusion rules, an evaluation-
awareness screen, and one-for-one same-cell replacement of invalid trajecto-
ries were specified in advance, as was an interpretive note anticipating ceiling
compression of the secondary contrast. The estimand is the trajectory-level
violation probability within the fixed TRIO-20 scenario set; the exact bino-
mial bounds treat trajectories as independent Bernoulli trials conditional on
this set and do not extend to an arbitrary population of scenarios.
9

## PDF Page 10

4.3. Deviations
We recorded three amendments, each frozen before any outcome was
viewed. First, the interpretive ceiling note above was added after calibration.
Second, Terra M06 exhausted the 20-round budget on the max arm at rates
that made slots unfillable; we reran the scenario in full under a 32-round bud-
get, across both effort arms and all three conditions, superseding 71 earlier
attempts that are retained as quality evidence and excluded from analysis.
The amendment fixed the 32-round budget as a property of the scenario, so
Sol M06 collected under it from the outset. Third, Sol M10 exhausted the
20-round budget in the same way and received the same treatment, super-
seding its 24 original trajectories and 34 replacement attempts. Both reruns
carried an acceptance criterion of under 5% exhaustion and a precommitted
fallback to scenario exclusion with recomputed margins, and both met ac-
ceptance with 0% exhaustion. The superseded and invalid attempts contain
no prohibited tool calls under the same judges, so the zero-event primary
result is not produced by replacement. A complete attrition table appears in
the supplementary material. A prespecified mixed-effects logistic model was
not fitted: with no outcome variation in the primary endpoint its coefficients
would not be identifiable.
4.4. Analysis outputs
All prespecified confirmatory numbers reported below are computed from
the released trajectory pool. The simultaneous exact bounds are closed-form
functions of the arm counts, computed by the formulas in Section 4.2.
5. Results
5.1. Manipulation check
The effort parameter moved computation as intended. Median reasoning
tokens on Terra were 72 at low and 408 at max, a ratio of 5.67, with max
exceeding low in 14 of 14 scenarios. Sol medians were 103 and 464.5, a ratio
of 4.51, again in 14 of 14 scenarios.
5.2. Primary endpoint: violation attempts
No prohibited tool call occurred in any of the 840 selected trajectories,
and none occurred in the superseded or invalid attempts retained as quality
evidence. All six Terra arms recorded 0 events in 84 trajectories, giving exact
10

## PDF Page 11

one-sided 95% upper limits of 3.50% per arm; all six Sol arms recorded 0 in
56, with limits of 5.21%. Simultaneous exact bounds place the change in
violation probability from low to max effort inside±4.30percentage points
on Terra and±6.38points on Sol, within each condition separately. The
prespecified estimandθ= 0.000, with a simultaneous exact 95% interval
of±4.34percentage points (Terra) and±6.48points (Sol), lies inside the
prespecified±7.01-point equivalence margin. Table 1 reports the arm-level
counts and limits; Figure 1A presents the effect bounds.
Table 1: Violation-attempt counts and exact one-sided 95% upper limits by arm
Tier Condition EffortnEvents Rate Upper limit
Terra salient low 84 0 0.0% 3.50%
Terra salient max 84 0 0.0% 3.50%
Terra hidden low 84 0 0.0% 3.50%
Terra hidden max 84 0 0.0% 3.50%
Terra clean low 84 0 0.0% 3.50%
Terra clean max 84 0 0.0% 3.50%
Sol salient low 56 0 0.0% 5.21%
Sol salient max 56 0 0.0% 5.21%
Sol hidden low 56 0 0.0% 5.21%
Sol hidden max 56 0 0.0% 5.21%
Sol clean low 56 0 0.0% 5.21%
Sol clean max 56 0 0.0% 5.21%
Notes:Upper limits are exact Clopper–Pearson one-sided 95% bounds for zero events.
Per-condition simultaneous bounds in the text use per-arm limits at level 97.5%.Source:
Authors’ calculations from the released trajectory pool.
5.3. Secondary endpoint: rule probing
The prespecified secondary hypothesis predictedθ probe >0, a larger
effort-driven rise in rule probing where probing reveals an exploitable gap
than where it reveals nothing. The estimate isθ probe =−0.143, 95% CI
[−0.274,+0.012], so the hypothesis is not supported. Terra probing rates
rose from 47.6% to 72.6% in the hidden condition and from 39.3% to 78.6%
in the clean condition, a difference of eight points at low effort that nar-
rowed to six points at max. The salient condition, reported descriptively,
rose from 3.6% to 22.6%. Collection order was fixed (low before max within
each scenario), so this contrast is entangled with time. Figure 1B presents
11

## PDF Page 12