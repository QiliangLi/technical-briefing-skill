# Task: Synthesize This Issue

Read only the final selected briefing items and compact `project_contexts` supplied with this task. Produce a restrained issue-level synthesis for company leaders and technical colleagues. The hotspot radar is selected and published by deterministic code; this task does not read or write radar content.

## 本期判断：必须有，但不要强造共同趋势

Return **1-3 judgements; usually 2-3**. The briefing has already selected useful evidence, so readers should get a small number of conclusions before reading the detailed cards.

Each judgement should make **one** concrete technical point that is worth remembering. It may be supported by:

- one strong item that challenges an assumption or gives a counter-intuitive result;
- multiple independent works that genuinely converge on the same mechanism;
- a previously vague engineering question that now has a measurable boundary;
- evidence that supports, challenges or narrows a technical assumption;
- a new direction that is concrete enough to test next.

A judgement does **not** need to combine multiple items. Do not add a second paper merely to make a statement look like a trend. Conversely, when several works really do converge, explain the shared mechanism rather than just listing systems.

A judgement also does **not** need to contain all of “what changed -> why it matters -> project implication”. State the part that carries the information gain. Do not force every judgement back to a configured project question.

Avoid:

- `System A...; System B...; 两者共同表明...` when the works only share a broad topic;
- slogans such as “X正在成为新的验收项”;
- compressed catchphrases such as “从体感受到数字”“从进程到资产”;
- abstract titles that require the body to decode what the title meant;
- repeating all benchmark numbers already visible in detailed cards.

## 写法参照：像转述证据的工程师，不像摘要模板

判断的读者是技术同事。写之前先假想一个场景：你读完这几篇材料，走到同事工位边讲给他听。你会先说结论，再讲你看到的具体证据，中间自然带上数字和条件——不会先说“三项独立工作在同一方向上给出证据”，也不会用“共同机制是”“这指向同一个工程判断”这类话来组织段落。这些元叙述是摘要工具的口吻，不是人的口吻。

按这个场景校准：

- 标题直接是可复述的断言（“H100上多挂加载反而掉带宽，选对数据通路比堆深度值钱”），不是需要正文解码的抽象短语；
- 正文从具体工作、具体实验或具体数字讲起，让证据自己承载结论；
- 一条判断里提到的工作数量由证据决定，写“同一期的rl-triton也遇到同样问题”就够了，不需要宣告“三项工作”；
- 结尾落在读者能带走的东西上：一个判断、一个下次写代码时该改的习惯、或一个值得安排的验证。不要用口号收尾，也不要在最后一段重新概括全文。

对照示例（同一证据的两种写法）：

不要这样写（AI 腔）：三项独立工作在同一方向上给出证据。系统A在X上实现了突破；系统B在Y上取得进展；系统C验证了Z。这三件事指向同一个工程判断，共同机制是给数据通路配上更高效的约束，堆并发深度本身不再可靠。

要这样写（人话）：CoreOptX在三颗H100上做了组受控微基准：普通全局加载的带宽在每线程深度约2处到顶，继续加深反而掉约三分之一。同一期的rl-triton把七种RL递推改成片上结合扫描拿到数倍加速，却在寄存器溢出处退回0.6倍。写访存内核的顺序应该反过来：先选数据通路和片上驻留，再谈并发深度。

后一种没有一个字在谈论“本期有哪些工作”，每个字都在谈论证据本身。照这个标准写。

Keep the title understandable on first read. The body may use ordinary technical prose instead of being compressed into a fixed sentence count. `evidence_item_ids` provides traceability, so include only the evidence that actually supports the judgement.

## No generated issue headline

Do **not** generate a `headline`. The publication layer owns the fixed briefing title and date. Your job starts with `judgements`.

## Project insights: internal traceability, not reader copy

Produce `project_insights` only when selected **core** evidence materially changes a configured project question.

- Use an exact question from the matching `project_contexts[].current_questions`.
- `effect` is one of `supports`, `challenges`, `narrows`, `opens`.
- `insight` is explicitly our inference from evidence, not a source claim.
- `next_action` is a concrete experiment, measurement, implementation check or decision step.
- Cite 1-4 exact `brief_item_id` values; at least one must come from the same topic.
- Preserve conditions and limitations.
- Return an empty array instead of filler.
- A project insight does not have to become a reader-facing judgement. Only surface it there when it is independently useful to readers.
- Discovery-only/Radar material cannot support `judgements` or `project_insights`.

## Hotspot Radar is not part of this task

The hotspot radar (`radar_signals`) is produced by a deterministic publication stage that copies frozen upstream summaries directly. Do not read radar material, do not write `radar_signals`, and do not use discovery-only items for `judgements` or `project_insights`.

## Output

Return JSON only:

- `judgements`: 1-3 concrete objects with `title`, `body`, `evidence_item_ids`; normally 2-3.
- `topic_names`: unique topic display names.
- `watch_next`: 1-3 concrete things to monitor before the next issue.
- `project_insights`: 0-4 trace objects with exact `topic_id`, `topic_name`, configured `project_question`, `effect`, `confidence`, `insight`, `next_action`, `evidence_item_ids`.

The detailed machine items have already passed the deterministic Evidence Gate (and selective semantic verification when triggered). Reader-facing item prose is generated separately. Do not call any writing Skill here. Return JSON only.
