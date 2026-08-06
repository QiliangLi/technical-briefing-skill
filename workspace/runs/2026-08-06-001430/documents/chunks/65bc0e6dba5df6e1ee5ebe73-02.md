0%
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

the rates; per-scenario effects and leave-one-scenario-out estimates appear in
the supplementary material.
−10 −5 0 5 10
Low-to-max effect on violation
probability (percentage points)
T erra salient
T erra hidden
T erra clean
Sol salient
Sol hidden
Sol clean
θ (T erra)
θ (Sol)
±4.30
±4.30
±4.30
±6.38
±6.38
±6.38
±4.34
±6.48
prespecified margin for θ (±7.01 pp)
All point estimates = 0.0
A Violation-effect bounds
low max
Reasoning effort
0.0
0.2
0.4
0.6
0.8
1.0Rule-probe rate
hidden
clean
salient
θprobe = −0.143
95% CI [−0.274, +0.012]
B Rule probing by effort
hidden
clean
salient
Figure 1: Primary and secondary endpoints. Panel A shows, on the effect scale in percent-
age points, the low-to-max change in violation probability for each condition, with every
point estimate at 0.0: simultaneous exact 95% bounds of±4.30points per Terra condition
and±6.38points per Sol condition, each within its condition separately, and the prespec-
ified interaction estimandθunder its exact two-arm simultaneous bound of±4.34points
(Terra) and±6.48points (Sol); dashed lines mark the prespecified±7.01-point margin,
which applies toθ. Arm-level counts and limits appear in Table 1. Panel B shows Terra
rule-probe rates by condition and effort with scenario-cluster bootstrap 95% bands; the
salient series is descriptive.
5.4. Sensitivity and replication
Excluding the rerun scenario M06 leaves the primary result unchanged
and the secondary at−0.128 [−0.269,+0.026]. The evaluation-awareness
screen produced zero candidates. Supplementary Table S2 reports a miss-
ingness construction that treats every superseded or invalid attempt as a
violation; all retained logs contain zero prohibited calls. On Sol the pri-
mary result replicates: zero events in all arms, per-arm limits of 5.21%, and
per-condition simultaneous bounds of±6.38points. The secondary contrast
on Sol is+0.018 [−0.107,+0.125]: probing reached 100% in the hidden and
clean max arms and 94.6% in the salient max arm, the ceiling anticipated by
the prespecified interpretive note, under which the contrast loses resolution.
12

## PDF Page 13

6. Discussion
The central contribution is a bounded zero supported by an audited mea-
surement procedure. Within matched environments, under an explicit pro-
hibition delivered through the system prompt, and across a roughly fivefold
change in reasoning computation, no violation attempt occurred in 840 tra-
jectories. For operators who deploy GPT-5.6 in benign clerical settings with
clearly stated policy, the effort dial can be tuned for latency and cost without
a measurable compliance penalty.
The secondary result, while not supporting its prespecified hypothesis,
shows where the added computation went. We expected added reasoning to
behave like directed search, flowing preferentially toward information with
instrumental value. The data show the opposite allocation: added reasoning
raised probing in every condition, most of all where it had no instrumental
payoff. That reading bears on the frontier evaluation reports [3, 4]: in the
tested regime of explicit system-level prohibitions without external pressure,
raising effort alone produced no violations.
Read together with the split literature, the results are consistent with the
prohibition gating the conversion of discovery into action, a comparison that
crosses studies rather than arising within the design. In verifier-gaming set-
tings the verifier itself rewards the shortcut, and exploitation grows with rea-
soning [6]. Here the hidden and salient conditions place an effective shortcut
behind an explicit rule, and their 560 trajectories contain zero attempts, with
the 280 clean-condition trajectories as the control. The environment in be-
tween, where prohibitions are implicit, stale, or in tension with incentives, is
where an effort effect on conduct remains most plausible and where extending
the matched-triad design with a pressure axis [5] would be most productive.
Run-time privilege enforcement [14, 15, 16] and propensity measurement of
the kind reported here answer complementary questions; a testbed combining
them would show how enforcement changes the effort-compliance surface.
Limitations.We tested one model family at two tiers, in a benign cler-
ical regime, and scored behavioural outcomes from tool calls. Intermediate
effort levels were not sampled; our conclusions concern the endpoint con-
trast. Collection order was fixed, with all low-effort trajectories preceding
max-effort trajectories within each scenario, so every effort contrast is en-
tangled with collection time. Access ran through an API gateway against
moving vendor aliases without a frozen snapshot. The 14 confirmatory sce-
narios share one shortcut-prohibition template across clerical domains. The
13

## PDF Page 14

explicit, system-level prohibitions we tested represent one end of a clarity
spectrum; settings with ambiguous, implicit, or conflicting policies remain
untested.
7. Conclusion
Scaling GPT-5.6’s reasoning effort from its lowest to its deepest single-
agent setting leaves unauthorized tool-call attempts at zero across 840 tra-
jectories in matched least-privilege environments and two model tiers. Exact
simultaneous bounds confine the effort-driven change in violation probability
to±4.30percentage points per condition on Terra. Added reasoning raises
rule probing in all conditions, without converting inspection into action. The
TRIO-20 trajectories are released so that the same question can be asked of
other models, other effort configurations, and settings where prohibitions are
ambiguous or under external pressure.
Ethics statement
This study involves no human participants and no personal data. All
trajectories are interactions between a language model and simulated clerical
environments.
Funding
This research did not receive any specific grant from funding agencies in
the public, commercial, or not-for-profit sectors.
CRediT authorship contribution statement
Xiaonan Xu:Conceptualization, Methodology, Investigation, Writing –
original draft.Wenjing Wu:Software, Validation, Formal analysis, Writing
– review & editing.
Declaration of competing interest
We declare no competing financial interests or personal relationships that
could have influenced this work.
14

## PDF Page 15

Data availability
The 840 confirmatory trajectories are openly available athttps:
//github.com/WenJing95/trio-20. The scenario suite, program judges,
analysis code, frozen analysis plan, and validation records are available from
the corresponding author on reasonable request.
Declaration of generative AI and AI-assisted technologies in the
manuscript preparation process
During the preparation of this work the authors used Anthropic Claude
in order to support drafting and editing of the manuscript. After using this
tool, the authors reviewed and edited the content as needed and take full
responsibility for the content of the published article. The use of language-
model assistance for scenario implementation, program judges, and analysis
code is described in Section 3.4.
References
[1] J. H. Saltzer, M. D. Schroeder, The protection of information in com-
puter systems, Proceedings of the IEEE 63 (1975) 1278–1308.
[2] OWASP, LLM06:2025 Excessive Agency, OWASP Top 10 for LLM
Applications, accessed August 2026.https://genai.owasp.org/
llmrisk/llm062025-excessive-agency(2025).
[3] OpenAI, GPT-5.6 System Card, accessed July 2026.https://
deploymentsafety.openai.com/gpt-5-6(2026).
[4] METR, Summary of METR’s Predeployment Evaluation of
GPT-5.6 Sol, accessed July 2026.https://metr.org/blog/
2026-06-26-gpt-5-6-sol/(2026).
[5] C. Li, P. Lu, X. Pan, F. Barez, M. Yang, AutoControl Arena: Synthe-
sizing Executable Test Environments for Frontier AI Risk Evaluation,
arXiv preprint arXiv:2603.07427 (2026).
[6] L. Helff, Q. Delfosse, D. Steinmann, R. Härle, H. Shindo,
P. Schramowski, W. Stammer, K. Kersting, F. Friedrich, LLMs Gam-
ing Verifiers: RLVR can Lead to Reward Hacking, arXiv preprint
arXiv:2604.15149 (2026).
15

## PDF Page 16

[7] Ö. V. Çağatan, X. Zhao, Reward Hacking in Language Model Agents:
Revisiting AI Safety Gridworlds, arXiv preprint arXiv:2606.15385
(2026).
[8] A. P. Gema, A. Hägele, R. Chen, A. Arditi, J. Goldman-Wetzler,
K. Fraser-Taliente, H. Sleight, L. Petrini, J. Michael, B. Alex, P. Min-
ervini, Y. Chen, J. Benton, E. Perez, Inverse Scaling in Test-Time Com-
pute, Transactions on Machine Learning Research (2025).
[9] X. Li, R. Ming, P. Setlur, A. Paladugu, A. Tang, H. Kang, S. Shao,
R. Jin, C. Xiong, Benchmark Test-Time Scaling of General LLM Agents,
arXiv preprint arXiv:2602.18998 (2026).
[10] J. Kirmayr, L. Stappen, E. André, CAR-bench: Evaluating the Con-
sistency and Limit-Awareness of LLM Agents under Real-World Un-
certainty, in: Proceedings of the 64th Annual Meeting of the Associ-
ation for Computational Linguistics (Volume 1: Long Papers), Asso-
ciation for Computational Linguistics, 2026, pp. 40599–40618,https:
//doi.org/10.18653/v1/2026.acl-long.1886.
[11] E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer,
F. Tramèr, AgentDojo: A Dynamic Environment to Evaluate Prompt
Injection Attacks and Defenses for LLM Agents, in: Advances in Neural
Information Processing Systems 37, 2024, pp. 82895–82920.
[12] Y. Ruan, H. Dong, A. Wang, S. Pitis, Y. Zhou, J. Ba, Y. Dubois,
C. J. Maddison, T. Hashimoto, Identifying the Risks of LM Agents with
an LM-Emulated Sandbox, in: International Conference on Learning
Representations, 2024.
[13] M. Andriushchenko, A. Souly, M. Dziemian, D. Duenas, M. Lin,
J. Wang, D. Hendrycks, A. Zou, J. Z. Kolter, M. Fredrikson, Y. Gal,
X. Davies, AgentHarm: A Benchmark for Measuring Harmfulness of
LLM Agents, in: International Conference on Learning Representations,
2025.
[14] Cailin Winston, Claris Winston, René Just, Solver-Aided Verification
of Policy Compliance in Tool-Augmented LLM Agents, arXiv preprint
arXiv:2603.20449 (2026).
16

## PDF Page 17

[15] T. Shi, J. He, Z. Wang, L. Wu, H. Li, W. Guo, D. Song, Pro-
gent: Programmable Privilege Control for LLM Agents, arXiv preprint
arXiv:2504.11703 (2025).
[16] E. Debenedetti, I. Shumailov, T. Fan, J. Hayes, N. Carlini, D. Fabian,
C. Kern, C. Shi, A. Terzis, F. Tramèr, Defeating Prompt Injections
by Design, in: IEEE Conference on Secure and Trustworthy Machine
Learning (SaTML), 2026.
[17] E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, A. Beutel, The
Instruction Hierarchy: Training LLMs to Prioritize Privileged Instruc-
tions, arXiv preprint arXiv:2404.13208 (2024).
[18] K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, M. Fritz,
Not What You’ve Signed Up For: Compromising Real-World LLM-
Integrated Applications with Indirect Prompt Injection, in: Proceedings
of the 16th ACM Workshop on Artificial Intelligence and Security, 2023,
pp. 79–90.
[19] Y. Liu, Y. Jia, R. Geng, J. Jia, N. Z. Gong, Formalizing and Benchmark-
ing Prompt Injection Attacks and Defenses, in: 33rd USENIX Security
Symposium, 2024, pp. 1831–1847.
[20] X. Xu, W. Wu, Skill Availability and Presentation Granularity in
Large-Language-Model Agents: A Controlled SkillsBench Study, arXiv
preprint arXiv:2605.31408 (2026).
[21] X. Xu, W. Wu, Compression, Structure, and Executor Capability: A
ControlledReal-CostDecompositionofLanguage-ModelAgentSkillOp-
timisation, arXiv preprint arXiv:2607.03048 (2026).
[22] B. A. Nosek, C. R. Ebersole, A. C. DeHaven, D. T. Mellor, The prereg-
istration revolution, Proceedings of the National Academy of Sciences
115 (2018) 2600–2606.
[23] D. Lakens, Equivalence tests: a practical primer for t tests, correla-
tions, and meta-analyses, Social Psychological and Personality Science
8 (2017) 355–362.
[24] C. J. Clopper, E. S. Pearson, The use of confidence or fiducial limits
illustrated in the case of the binomial, Biometrika 26 (1934) 404–413.
17

## PDF Page 18

[25] B. Efron, R. J. Tibshirani, An Introduction to the Bootstrap, Chapman
and Hall, New York, 1993.
[26] D.Amodei, C.Olah, J.Steinhardt, P.Christiano, J.Schulman, D.Mané,
Concrete Problems in AI Safety, arXiv preprint arXiv:1606.06565
(2016).
[27] V. Krakovna, J. Uesato, V. Mikulik, M. Rahtz, T. Everitt, R. Kumar,
Z. Kenton, J. Leike, S. Legg, Specification Gaming: The Flip Side of AI
Ingenuity, DeepMind Safety Research (2020).
[28] M. Strathern, ‘Improving ratings’: audit in the British University sys-
tem, European Review 5 (1997) 305–321.
[29] OpenAI, GPT-5.6 Model Guidance, API documentation, accessed
July 2026.https://developers.openai.com/api/docs/guides/
latest-model(2026).
18

## PDF Page 19

Supplementary material
This appendix contains the collection-flow accounting (Table S1), the
adversarial missingness construction (Table S2), and the per-scenario sec-
ondary effects with leave-one-scenario-out estimates (Table S3) referenced in
the main text.
Table S1: collection flow
Each slot of the confirmatory matrix was filled by an original attempt, by
a prespecified one-for-one same-cell replacement of an invalid attempt, or by
the whole-scenario reruns of Terra M06 and Sol M10 described in Section 4.3.
Invalid attempts are interaction-budget exhaustions or validity failures under
the prespecified rules; “valid, not selected” attempts are valid trajectories
superseded by a whole-scenario rerun. In total, Terra recorded 575 attempts
for 504 slots (71 not selected: 42 invalid, 29 valid but superseded) and Sol
recorded 397 attempts for 336 slots (61 not selected: 47 invalid, 14 valid but
superseded). No attempt, selected or not, contains a prohibited tool call.
Table S1: Collection flow by tier and scenario group
Tier Group Slots Attempts Invalid Valid, not selected Selected
Terra 13 unaffected scenarios 468 468 0 0 468
Terra M06, 20-round attempts 36 71 42 29 0
Terra M06 rerun, 32-round 36 36 0 0 36
Sol 13 unaffected scenarios 312 315 3 0 312
Sol M10, 20-round attempts 24 58 44 14 0
Sol M10 rerun, 32-round 24 24 0 0 24
Table S2: adversarial missingness construction
The construction counts every attempt that did not enter the final pool,
whether invalid or valid but superseded, as if it had been a violation in
its condition–effort arm, alongside the arm’s selected trajectories. This is
the worst case permitted by the attrition record: the selected trajectories
themselves contain zero prohibited calls, and so do all non-selected attempts
under the same judges (Section 5.4 of the main text). Upper limits are exact
one-sided 95% Clopper–Pearson bounds at the worst-case counts.
19

## PDF Page 20

Table S2: Worst-case violation rates when every non-selected attempt is counted as a
violation
Tier Condition Effort SelectednNot selected Worst-casenWorst-case rate Upper limit
Terra salient low 84 7 91 7.7% 13.96%
Terra salient max 84 6 90 6.7% 12.73%
Terra hidden low 84 11 95 11.6% 18.44%
Terra hidden max 84 18 102 17.6% 25.04%
Terra clean low 84 10 94 10.6% 17.38%
Terra clean max 84 19 103 18.4% 25.88%
Sol salient low 56 4 60 6.7% 14.61%
Sol salient max 56 17 73 23.3% 32.86%
Sol hidden low 56 6 62 9.7% 18.21%
Sol hidden max 56 13 69 18.8% 28.28%
Sol clean low 56 5 61 8.2% 16.46%
Sol clean max 56 16 72 22.2% 31.77%
Table S3: per-scenario secondary effects and leave-one-scenario-out
The prespecified secondary estimandθprobe is the mean over scenarios of
the per-scenario contrast(Phidden,max −P hidden,low)−(P clean,max −P clean,low)for
ruleprobingonTerra. Theall-scenariomeanis−0.143; leavingoutM06gives
−0.128, matching the sensitivity analysis in Section 5.4 of the main text. The
table reports point estimates; the prespecified interval is the scenario-cluster
bootstrap reported in the main text.
20

## PDF Page 21

Table S3: Per-scenario secondary effect and leave-one-scenario-out mean (Terra)
Scenario Effect Leave-one-out mean
M01_procurement−0.167−0.141
M02_onboarding−0.333−0.128
M03_timesheets+0.167−0.167
M04_workorders+0.500−0.192
M05_email_qa−0.333−0.128
M06_translation−0.333−0.128
M07_backups−0.167−0.141
M08_access_review+0.000−0.154
M09_invoice_coding−0.500−0.115
M10_bug_triage−0.500−0.115
M11_refunds−0.333−0.128
M12_catalog+0.167−0.167
M13_training+0.000−0.154
M14_kb_qa−0.167−0.141
21