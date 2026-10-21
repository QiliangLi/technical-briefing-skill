/* zcode-workflow
description: 编排一期技术 briefing 的完整流水线：采集/续跑 → 逐个执行 Agent 任务卡（每任务全新子代理上下文）→
  渲染与发布前校验，终止于 READY_TO_SEND 并发布邮件预览与校验报告。运行中提供任务看板。不发送、不归档；发送确认保留在主会话。
whenToUse: 在 ZCode 宿主运行或续跑一期 briefing 时使用；替代 SKILL.md 手动任务循环，避免主会话上下文膨胀。
args:
  mode:
    type: string
    description: run = 采集并开启新一期；resume = 续跑最近一期（默认）
    required: false
    default: resume
  concurrency:
    type: number
    description: 每波并行执行的任务数上限（1–6，默认 6；1 即串行回退）
    required: false
    default: 6
*/
// briefing-run —— ZCode workflow 编排每日 briefing（止于 READY_TO_SEND）
// 发送确认（send --confirm-send 两步令牌）保留在主会话人工环节，本 workflow 不发送、不归档。

interface PendingRow {
  task_id: string;
  task_type: string;
  output_path: string;
}

interface TaskOutcome {
  /** 执行卡上的全部任务 ID */
  task_ids: string[];
  /** 是否已把输出写入执行卡指定的输出路径 */
  outputs_written: boolean;
  /** 一行补充说明（中文） */
  notes?: string;
}

interface AdvanceResult {
  synced: number;
  applied: number;
  invalid: number;
  pending: number;
  stage: string;
}

interface BoardItem {
  /** 波次在看板上的稳定标识（wave-N） */
  key: string;
  /** 卡片所在列：执行中 / 修复中 / 完成 / 修复后完成 */
  status: string;
  /** 卡片标题，如“第 3 波·4 个任务” */
  title: string;
  /** 波内各任务的功能·对象标签串 */
  tasks_text: string;
  /** 一行补充说明；无则整个字段省略（undefined 只允许出现在可选属性上） */
  note?: string;
}

interface InvalidRow {
  task_id: string;
  task_type: string;
  output_path: string;
}

interface Finding {
  where: string;
  what: string;
  evidence: string;
  status: "verified" | "unconfirmed";
  severity: "low" | "medium" | "high";
}

interface WorkflowReport {
  conclusion: string;
  findings: Finding[];
  verified: string[];
  notCovered: string[];
}

// 解析 `tasks list --status PENDING` 行："{status:9} {task_type:20} {id} -> {output_path}"，
// 该列表排序（priority DESC, created_at）与 tasks next 完全一致，前 K 行即串行队列接下来要派发的 K 个任务。
function parsePendingRows(stdout: string): PendingRow[] {
  const rows: PendingRow[] = [];
  for (const line of stdout.split("\n")) {
    const m = /^PENDING\s+(\S+)\s+(\S+)\s+->\s+(\S+)\s*$/.exec(line);
    if (m && m[1] && m[2] && m[3]) {
      rows.push({ task_type: m[1], task_id: m[2], output_path: m[3] });
    }
  }
  return rows;
}

function num(v: unknown): number {
  return typeof v === "number" ? v : 0;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function parseTrailingJson(stdout: string): AdvanceResult | null {
  let idx = stdout.lastIndexOf("{");
  while (idx >= 0) {
    try {
      const raw: unknown = JSON.parse(stdout.slice(idx));
      if (typeof raw === "object" && raw !== null && "stage" in raw) {
        const rec = raw as Record<string, unknown>;
        return {
          synced: num(rec.synced),
          applied: num(rec.applied),
          invalid: num(rec.invalid),
          pending: num(rec.pending),
          stage: str(rec.stage),
        };
      }
    } catch {
      // 尝试更早的 '{'
    }
    idx = stdout.lastIndexOf("{", idx - 1);
  }
  return null;
}

function parseInvalidList(stdout: string): InvalidRow[] {
  const rows: InvalidRow[] = [];
  for (const line of stdout.split("\n")) {
    const m = /^INVALID\s+(\S+)\s+(\S+)\s+->\s+(\S+)\s*$/.exec(line);
    if (m && m[1] && m[2] && m[3]) {
      rows.push({ task_type: m[1], task_id: m[2], output_path: m[3] });
    }
  }
  return rows;
}

function taskAsk(instructions: string): string {
  return [
    "你是 briefing 流水线的任务执行子代理，独立完成下面这张执行卡的全部工作。",
    "",
    instructions,
    "",
    "编排边界（覆盖执行卡末尾的 advance 步骤）：",
    "- 不要运行 briefing.py 的任何子命令；advance 由编排器在你完成后执行。",
    "- 只读取执行卡明确引用的 Prompt、输入 JSON、判断卡与 Evidence；禁止打开未引用的原始全文。",
    "- 会话组卡：前序任务的证据不可采信，禁止合并输出或 batch 数组，逐任务复制 _task 绑定并写独立输出文件。",
    "- 输出必须符合卡内 Schema；宁可少写结论并记录缺失，不得猜测数字。",
    "- 若证据与要求矛盾或无法产出合规输出，直接升级提问（escalate），不要伪造。",
    "",
    "完成后只返回：task_ids（卡上全部任务 ID）、outputs_written（bool）、notes（一行，可省略）。",
  ].join("\n");
}

function repairAsk(row: InvalidRow): string {
  return [
    "以下 briefing 任务输出未通过校验（INVALID）。读取其输入 JSON 与现有输出文件，按对应 schema_path 自检，做最小定向修复后覆盖写回原输出路径。",
    "常见原因：缺 _task 绑定、必填字段缺失（如 technology_value）、字段超限、数字超上限、evidence_gaps 未逐字回显。",
    "不得扩大证据读取范围，不得运行 briefing.py 子命令；确实无法修复的在 notes 说明并保留原文件。",
    "",
    `- ${row.task_id} (${row.task_type}) -> ${row.output_path}`,
    "",
    "完成后返回 task_ids、outputs_written、notes。",
  ].join("\n");
}

function validateFixAsk(failures: string): string {
  return [
    "最终校验存在 FAIL。读取最近一期 run 的 validation.json 中 failures 列表，对相应任务输出文件做最小修复；",
    "不要直接改渲染产物，不要运行 briefing.py 子命令；无法修复的字段在 notes 中说明。",
    "校验输出节选：",
    failures.slice(0, 4000),
  ].join("\n");
}

const MAX_WAVES = 40;
const MAX_INVALID_RETRIES = 2;
const MAX_VALIDATE_RETRIES = 3;
const RENDER_STAGES = ["READY_FOR_RENDER", "RENDERED", "READY_TO_SEND"];
const mode: string = typeof args.mode === "string" && args.mode === "run" ? "run" : "resume";
// 每波并行上限：1–6（6 为账户速率限制实测安全值；1 即串行回退）。留在控制流里，不插值进 ask 文本。
const rawK = typeof args.concurrency === "number" ? args.concurrency : 6;
const K = Math.max(1, Math.min(6, Math.floor(rawK) || 6));

// 功能直述命名：任务类型 → 用户一眼能懂的功能标签。名字按"功能·对象·第N轮"组成，
// 对象取自任务 input.json 的人读字段；各功能读什么/产出什么的对照表见 docs/operations/zcode-workflow-run.md。
const ROLE: Record<string, string> = {
  agent_web_search: "开放搜索",
  relevance_batch: "筛选候选",
  relevance_review: "筛选候选",
  fact_extraction: "提取事实",
  fact_evidence_repair: "补齐证据",
  item_writing_batch: "撰写条目",
  item_writing: "撰写条目",
  fact_check_batch: "核查事实",
  fact_check: "核查事实",
  issue_synthesis: "汇总判断",
  reader_projection: "读者润稿",
  illustrated_publication: "生成插画",
};

function rec(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
}

function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function strField(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function cut(s: string): string {
  return s.length > 24 ? s.slice(0, 24) + "…" : s;
}

async function cardLabel(instructions: string, taskType: string): Promise<{ role: string; subject: string }> {
  const role = ROLE[taskType] || "执行编辑";
  const single = /^1\. Read the canonical envelope first: (\S+)$/m.exec(instructions);
  const envelope = single && single[1] ? single[1] : "";
  if (!envelope) {
    return { role, subject: "" };
  }
  try {
    const env = rec(JSON.parse(await files.read(envelope)));
    const input = rec(JSON.parse(await files.read(strField(env.input_path))));
    const topicName = strField(rec(input.topic).name);
    const docTitle = strField(rec(input.document).title);
    if (docTitle) {
      return { role, subject: cut(docTitle) };
    }
    const candidates = arr(input.candidates);
    if (candidates.length > 0) {
      return { role, subject: cut(topicName ? `${topicName}·${candidates.length}篇候选` : `${candidates.length}篇候选`) };
    }
    // 全期任务（读者润稿/汇总判断/生成插画）的 items 无嵌套 topic.name 或跨全部专题，取首条专题名反而误导；
    // 无专题前缀时标签只用数量，避免「读者润稿··26条」这类空段双点
    const items = arr(input.items);
    if (items.length > 0) {
      const firstTopic = strField(rec(rec(items[0]).topic).name);
      const prefix = firstTopic || topicName;
      return { role, subject: cut(prefix ? `${prefix}·${items.length}条` : `${items.length}条`) };
    }
    const checks = arr(input.checks);
    if (checks.length > 0) {
      return { role, subject: `${checks.length}项核查` };
    }
    const searches = arr(input.searches);
    if (searches.length > 0) {
      return { role, subject: `${searches.length}路搜索` };
    }
    const directionName = strField(rec(input.direction).name);
    if (directionName) {
      return { role, subject: cut(topicName ? `${topicName}·${directionName}` : directionName) };
    }
    return { role, subject: cut(topicName) };
  } catch {
    return { role, subject: "" };
  }
}

// 子代理名在同一运行内必须唯一（重名直接终止运行，且 AmendWorkflow 按名导入缓存）。同一波里同主题、
// 同候选数的两个任务组会得到相同标签，所以按名去重：首个占用保留原名以保持缓存命中，后续重复者追加"·之N"。
const usedNames = new Set<string>();

function uniqueName(base: string): string {
  let name = base;
  for (let n = 2; usedNames.has(name); n += 1) {
    name = `${base}·之${n}`;
  }
  usedNames.add(name);
  return name;
}

// 任务看板：每波一张卡片（受单次运行 256 条 report 上限约束，不按任务拆卡），
// 任务级"谁在做什么"由命名子代理在运行流中承担
artifact.board("tasks", {
  title: "任务波次看板",
  key: "key",
  status: "status",
  columns: ["执行中", "修复中", "完成", "修复后完成"],
  cardTitle: "title",
  detail: [
    { field: "tasks_text", label: "波内任务" },
    { field: "note", label: "备注" },
  ],
});

phase("初始化 briefing 运行");
log(mode === "run" ? "采集并开启新一期 briefing" : "续跑最近一期 briefing");
const init = mode === "run"
  ? await world.run(".venv/bin/python3", ["briefing.py", "run"], { timeoutMs: 900000 })
  : await world.run(".venv/bin/python3", ["briefing.py", "resume", "--run", "latest"], { timeoutMs: 900000 });
const initAdv = parseTrailingJson(init.stdout);
if (!initAdv) {
  const report: WorkflowReport = {
    conclusion: "初始化失败：briefing.py 未返回可解析的 advance JSON，等待人工处理。",
    findings: [{
      where: "briefing.py " + mode,
      what: "初始化命令失败或输出异常",
      evidence: (init.stderr || init.stdout).slice(0, 800),
      status: "unconfirmed",
      severity: "high",
    }],
    verified: [],
    notCovered: ["全部 Agent 任务", "渲染与校验"],
  };
  return report;
}
let stage = initAdv.stage;
const notes: Finding[] = [];
const invalidBudget = new Map<string, number>();
let waves = 0;
let queueEmpty = false;

phase("按波次并行执行任务");
while (waves < MAX_WAVES) {
  const listRun = await world.run(".venv/bin/python3", ["briefing.py", "tasks", "list", "--status", "PENDING", "--run", "latest"]);
  const rows = parsePendingRows(listRun.stdout);
  if (rows.length === 0) {
    queueEmpty = true;
    if (!RENDER_STAGES.includes(stage)) {
      notes.push({
        where: "任务队列",
        what: `队列已空但阶段为 ${stage}，未进入渲染`,
        evidence: `advance stage=${stage}`,
        status: "verified",
        severity: "medium",
      });
    }
    break;
  }
  waves += 1;
  // 波 = PENDING 前缀（与串行队列同序，不跳优先级）；逐任务取 canonical 执行卡，取卡失败者本波跳过、仍为 PENDING
  const waveRows = rows.slice(0, K);
  const cardRuns = await Promise.all(
    waveRows.map((row) =>
      world.run(".venv/bin/python3", ["briefing.py", "tasks", "card", "--task", row.task_id, "--run", "latest"]),
    ),
  );
  const wave: { row: PendingRow; instructions: string }[] = [];
  for (let i = 0; i < cardRuns.length; i += 1) {
    const cardRun = cardRuns[i];
    const row = waveRows[i];
    if (cardRun.exitCode === 0 && cardRun.stdout.trim().length > 0) {
      wave.push({ row, instructions: cardRun.stdout.trim() });
    } else {
      log(`第 ${waves} 波：任务 ${row.task_id} 取卡失败，本波跳过（仍为 PENDING）`);
    }
  }
  if (wave.length === 0) {
    notes.push({
      where: "tasks card",
      what: `第 ${waves} 波全部取卡失败，停止等待人工介入`,
      evidence: ((cardRuns[0] && cardRuns[0].stderr) || (cardRuns[0] && cardRuns[0].stdout) || "").slice(0, 400),
      status: "unconfirmed",
      severity: "high",
    });
    break;
  }
  const waveKey = `wave-${waves}`;
  const labels = await Promise.all(wave.map((t) => cardLabel(t.instructions, t.row.task_type)));
  const waveTitle = `第 ${waves} 波·${wave.length} 个任务`;
  const tasksText = wave
    .map((t, i) => `${labels[i].role}${labels[i].subject ? "·" + labels[i].subject : ""}`)
    .join("；");
  log(`第 ${waves} 波（并行 ${wave.length}/${rows.length} 待办）：${tasksText}`);
  const started: BoardItem = { key: waveKey, status: "执行中", title: waveTitle, tasks_text: tasksText };
  report(started, "tasks");
  const waveNames = labels.map((label) =>
    uniqueName(label.subject ? `${label.role}·${label.subject}·第${waves}波` : `${label.role}·第${waves}波`),
  );
  // 一波 K 个命名子代理并行；单个失败不拖垮兄弟（allSettled），未写输出的任务仍为 PENDING，下一波重发
  const outcomes = await Promise.allSettled(
    wave.map((t, i) => agent(waveNames[i]).ask<TaskOutcome>(taskAsk(t.instructions))),
  );
  const rejected = outcomes.filter((o) => o.status === "rejected").length;
  if (rejected > 0) {
    log(`第 ${waves} 波 ${rejected} 个任务执行失败（未写输出），下一波将重发`);
  }
  // 阶段切换（如 relevance 收尾触发 fact 重组）或 DB 锁竞争时 advance 可能超过默认 300s；放宽后重试一次
  let advRun;
  try {
    advRun = await world.run(".venv/bin/python3", ["briefing.py", "advance", "--run", "latest"]);
  } catch {
    advRun = await world.run(".venv/bin/python3", ["briefing.py", "advance", "--run", "latest"], { timeoutMs: 900000 });
  }
  const adv = parseTrailingJson(advRun.stdout);
  if (!adv) {
    const failReport: WorkflowReport = {
      conclusion: "advance 输出无法解析，停止等待人工介入。",
      findings: [...notes, {
        where: "advance",
        what: "输出不是可解析 JSON",
        evidence: advRun.stdout.slice(0, 800) + advRun.stderr.slice(0, 200),
        status: "unconfirmed",
        severity: "high",
      }],
      verified: [`前 ${Math.max(0, waves - 1)} 波已 advance，第 ${waves} 波 advance 状态未知`],
      notCovered: ["剩余任务", "渲染与校验"],
    };
    return failReport;
  }
  stage = adv.stage || stage;
  if (adv.invalid === 0) {
    const done: BoardItem = { key: waveKey, status: "完成", title: waveTitle, tasks_text: tasksText };
    if (rejected > 0) done.note = `${rejected} 个任务失败待重发`;
    report(done, "tasks");
  }
  if (adv.invalid > 0) {
    const listInvalid = await world.run(".venv/bin/python3", ["briefing.py", "tasks", "list", "--status", "INVALID", "--run", "latest"]);
    const invalidRows = parseInvalidList(listInvalid.stdout);
    const over: string[] = [];
    for (const row of invalidRows) {
      const used = invalidBudget.get(row.task_id) ?? 0;
      if (used + 1 > MAX_INVALID_RETRIES) over.push(row.task_id);
      else invalidBudget.set(row.task_id, used + 1);
    }
    if (over.length > 0) {
      const stopReport: WorkflowReport = {
        conclusion: `任务 ${over.join(", ")} 连续校验失败已达修复上限，停止等待人工介入（可用 tasks next-single 手动接手）。`,
        findings: [...notes, {
          where: "INVALID",
          what: "修复预算耗尽",
          evidence: over.join(", "),
          status: "verified",
          severity: "high",
        }],
        verified: [`前 ${waves} 波任务执行`],
        notCovered: ["剩余任务", "渲染与校验"],
      };
      return stopReport;
    }
    log(`第 ${waves} 波后修复 ${invalidRows.length} 个 INVALID 任务（逐任务并行）`);
    const repairNames = invalidRows.map((row) => uniqueName(`第${waves}波·修复输出·${row.task_id.slice(0, 8)}`));
    await Promise.allSettled(
      invalidRows.map((row, i) => agent(repairNames[i]).ask<TaskOutcome>(repairAsk(row))),
    );
    await world.run(".venv/bin/python3", ["briefing.py", "tasks", "reopen-invalid", "--run", "latest"]);
    const reRun = await world.run(".venv/bin/python3", ["briefing.py", "advance", "--run", "latest"], { timeoutMs: 900000 });
    const re = parseTrailingJson(reRun.stdout);
    if (re) stage = re.stage || stage;
    const repaired: BoardItem = {
      key: waveKey,
      status: re && re.invalid === 0 ? "修复后完成" : "修复中",
      title: waveTitle,
      tasks_text: tasksText,
    };
    report(repaired, "tasks");
    notes.push({
      where: "INVALID 修复",
      what: `第 ${waves} 波后修复 ${invalidRows.length} 个任务并重同步`,
      evidence: invalidRows.map((r) => r.task_id).join(", "),
      status: "verified",
      severity: "low",
    });
  }
}
if (!queueEmpty) {
  const capReport: WorkflowReport = {
    conclusion: `任务波次达到上限 ${MAX_WAVES}，停止等待人工介入；已完成任务均已落盘，可续跑。`,
    findings: notes,
    verified: [`${waves} 波任务执行并 advance`],
    notCovered: ["剩余任务", "渲染与校验"],
  };
  return capReport;
}

phase("排版与发布前校验");
const renderRun = await world.run(".venv/bin/python3", ["briefing.py", "render", "--execute", "--run", "latest"], { timeoutMs: 600000 });
if (renderRun.exitCode !== 0) {
  const failReport: WorkflowReport = {
    conclusion: "渲染失败（render --execute 非零退出），等待人工处理。",
    findings: [...notes, {
      where: "render",
      what: "渲染命令失败",
      evidence: renderRun.stderr.slice(0, 800),
      status: "unconfirmed",
      severity: "high",
    }],
    verified: [`Agent 任务波次完成（${waves} 波）`],
    notCovered: ["校验"],
  };
  return failReport;
}
// render --execute 的 stdout 是 JSON，"email" 键为绝对路径且可能指向 email-illustrated.html；取 workspace/ 起的相对路径。兼容旧的带引号相对 email.html 输出。
const emailJsonMatch = /"email":\s*"([^"]*workspace\/runs\/[^"]+\.html)"/.exec(renderRun.stdout);
const emailLegacyMatch = /"(workspace\/runs\/[^"]+\/email\.html)"/.exec(renderRun.stdout);
const emailRaw = emailJsonMatch && emailJsonMatch[1] ? emailJsonMatch[1] : (emailLegacyMatch && emailLegacyMatch[1] ? emailLegacyMatch[1] : "");
const emailPath = emailRaw ? emailRaw.slice(emailRaw.indexOf("workspace/")) : "";
let validated = false;
let lastValidate = "";
for (let attempt = 1; attempt <= MAX_VALIDATE_RETRIES; attempt++) {
  const v = await world.run(".venv/bin/python3", ["briefing.py", "validate", "--run", "latest"], { timeoutMs: 600000 });
  lastValidate = v.stdout;
  if (v.exitCode === 0) {
    validated = true;
    break;
  }
  log(`发布校验未通过（第 ${attempt} 次），派发最小修复后重渲染`);
  await agent(`终审修复·第${attempt}次`).ask<TaskOutcome>(validateFixAsk(v.stdout));
  await world.run(".venv/bin/python3", ["briefing.py", "render", "--execute", "--run", "latest"], { timeoutMs: 600000 });
}
if (!validated) {
  const failReport: WorkflowReport = {
    conclusion: `发布校验连续 ${MAX_VALIDATE_RETRIES} 次未通过，停止等待人工处理。`,
    findings: [...notes, {
      where: "validate",
      what: "校验 FAIL 未消除",
      evidence: lastValidate.slice(0, 2000),
      status: "verified",
      severity: "high",
    }],
    verified: [`Agent 任务波次完成（${waves} 波）`, "render --execute 已执行"],
    notCovered: ["READY_TO_SEND"],
  };
  return failReport;
}
if (emailPath) {
  try {
    await artifact.file("email", emailPath, {
      title: "本期 briefing 邮件（待人工确认发送）",
      description: "渲染完成的 email.html；发送仍需主会话执行 send --confirm-send 两步确认。",
      primary: true,
    });
  } catch {
    log(`email.html 发布失败：${emailPath}`);
  }
  const validationPath = emailPath.slice(0, emailPath.lastIndexOf("/") + 1) + "validation.json";
  try {
    await artifact.file("validation", validationPath, {
      title: "最终校验报告",
      description: "validate 通过的 validation.json。",
    });
  } catch {
    log(`validation.json 发布失败：${validationPath}`);
  }
} else {
  notes.push({
    where: "artifact",
    what: "未能从 render 输出解析出 email.html 路径，未发布预览",
    evidence: renderRun.stdout.slice(0, 300),
    status: "unconfirmed",
    severity: "low",
  });
}

const finalReport: WorkflowReport = {
  conclusion: `briefing 已达 READY_TO_SEND（${waves} 波 Agent 任务，发布校验通过）。请人工阅读 email.html 与 validation.json，确认后在主会话执行 send --confirm-send 完成两步发送确认。`,
  findings: notes,
  verified: [`Agent 任务波次 ${waves} 波全部 advance`, "render --execute", "validate 退出码 0"],
  notCovered: ["send --confirm-send（主会话人工确认）", "发送后的归档与推送"],
};
return finalReport;