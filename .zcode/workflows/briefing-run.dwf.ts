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
*/
// briefing-run —— ZCode workflow 编排每日 briefing（止于 READY_TO_SEND）
// 发送确认（send --confirm-send 两步令牌）保留在主会话人工环节，本 workflow 不发送、不归档。

interface TaskCard {
  kind: "single" | "fact_session_group" | "unparsed";
  task_ids: string[];
  task_type: string;
  instructions: string;
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
  /** 执行卡在看板上的稳定标识（task_ids 拼接） */
  key: string;
  /** 卡片所在列：执行中 / 修复中 / 完成 / 修复后完成 */
  status: string;
  /** 卡片标题，如“第 3 轮 fact_extraction” */
  title: string;
  task_type: string;
  ids_text: string;
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

function parseCard(stdout: string): TaskCard | null {
  const text = stdout.trim();
  if (!text || text === "No pending tasks") {
    return null;
  }
  const groupIds: string[] = [];
  const firstLine: string[] = [];
  for (const line of text.split("\n")) {
    const g = /^ {3}Task \d+: (\S+) \(/.exec(line);
    if (g && g[1]) groupIds.push(g[1]);
    if (firstLine.length === 0 && line.trim().length > 0) firstLine.push(line);
  }
  if (groupIds.length > 0) {
    return { kind: "fact_session_group", task_ids: groupIds, task_type: "fact_extraction", instructions: text };
  }
  const head = firstLine[0] ?? "";
  const s = /^Task (\S+) \((\S+)\)$/.exec(head);
  if (s && s[1] && s[2]) {
    return { kind: "single", task_ids: [s[1]], task_type: s[2], instructions: text };
  }
  return { kind: "unparsed", task_ids: [], task_type: "unknown", instructions: text };
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

function taskAsk(card: TaskCard): string {
  return [
    "你是 briefing 流水线的任务执行子代理，独立完成下面这张执行卡的全部工作。",
    "",
    card.instructions,
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

function repairAsk(rows: InvalidRow[]): string {
  return [
    "以下 briefing 任务输出未通过校验（INVALID）。逐个读取其输入 JSON 与现有输出文件，按对应 schema_path 自检，做最小定向修复后覆盖写回原输出路径。",
    "常见原因：缺 _task 绑定、必填字段缺失（如 technology_value）、字段超限、数字超上限、evidence_gaps 未逐字回显。",
    "不得扩大证据读取范围，不得运行 briefing.py 子命令；确实无法修复的在 notes 说明并保留原文件。",
    "",
    ...rows.map((r) => `- ${r.task_id} (${r.task_type}) -> ${r.output_path}`),
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

const MAX_ROUNDS = 80;
const MAX_INVALID_RETRIES = 2;
const MAX_VALIDATE_RETRIES = 3;
const RENDER_STAGES = ["READY_FOR_RENDER", "RENDERED", "READY_TO_SEND"];
const mode: string = typeof args.mode === "string" && args.mode === "run" ? "run" : "resume";

// 任务看板：每张执行卡一张卡片，随 report(item, "tasks") 在列间实时移动
artifact.board("tasks", {
  title: "Agent 任务看板",
  key: "key",
  status: "status",
  columns: ["执行中", "修复中", "完成", "修复后完成"],
  cardTitle: "title",
  detail: [
    { field: "task_type", label: "类型" },
    { field: "ids_text", label: "任务" },
    { field: "note", label: "备注" },
  ],
});

phase("初始化 briefing 运行");
log(mode === "run" ? "采集并开启新一期 briefing" : "续跑最近一期 briefing");
const init = mode === "run"
  ? await world.run(".venv/bin/python3", ["briefing.py", "run"], { timeoutMs: 900000 })
  : await world.run(".venv/bin/python3", ["briefing.py", "resume", "--run", "latest"], { timeoutMs: 300000 });
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
let rounds = 0;
let queueEmpty = false;

phase("逐个执行 Agent 任务");
while (rounds < MAX_ROUNDS) {
  const next = await world.run(".venv/bin/python3", ["briefing.py", "tasks", "next", "--run", "latest"]);
  const card = parseCard(next.stdout);
  if (!card) {
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
  rounds += 1;
  const cardKey = card.task_ids.length > 0 ? card.task_ids.join("+").slice(0, 64) : `round-${rounds}`;
  const cardTitle = `第 ${rounds} 轮 ${card.task_type}`;
  const idsText = card.task_ids.join(", ");
  log(`第 ${rounds} 轮：${card.task_type}${idsText ? " " + idsText : ""}`);
  report({ key: cardKey, status: "执行中", title: cardTitle, task_type: card.task_type, ids_text: idsText }, "tasks");
  const outcome = await agent().ask<TaskOutcome>(taskAsk(card));
  const advRun = await world.run(".venv/bin/python3", ["briefing.py", "advance", "--run", "latest"]);
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
      verified: [`前 ${rounds - 1} 轮任务已 advance`],
      notCovered: ["剩余任务", "渲染与校验"],
    };
    return failReport;
  }
  stage = adv.stage || stage;
  if (adv.invalid === 0) {
    const done: BoardItem = { key: cardKey, status: "完成", title: cardTitle, task_type: card.task_type, ids_text: idsText };
    if (outcome.notes !== undefined) done.note = outcome.notes;
    report(done, "tasks");
  }
  if (adv.invalid > 0) {
    const listRun = await world.run(".venv/bin/python3", ["briefing.py", "tasks", "list", "--status", "INVALID", "--run", "latest"]);
    const rows = parseInvalidList(listRun.stdout);
    const over: string[] = [];
    for (const row of rows) {
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
        verified: [`前 ${rounds} 轮任务执行`],
        notCovered: ["剩余任务", "渲染与校验"],
      };
      return stopReport;
    }
    log(`修复 ${rows.length} 个 INVALID 任务后重同步`);
    await agent().ask<TaskOutcome>(repairAsk(rows));
    await world.run(".venv/bin/python3", ["briefing.py", "tasks", "reopen-invalid", "--run", "latest"]);
    const reRun = await world.run(".venv/bin/python3", ["briefing.py", "advance", "--run", "latest"]);
    const re = parseTrailingJson(reRun.stdout);
    if (re) stage = re.stage || stage;
    report({ key: cardKey, status: re && re.invalid === 0 ? "修复后完成" : "修复中", title: cardTitle, task_type: card.task_type, ids_text: idsText }, "tasks");
    notes.push({
      where: "INVALID 修复",
      what: `第 ${rounds} 轮后修复 ${rows.length} 个任务并重同步`,
      evidence: rows.map((r) => r.task_id).join(", "),
      status: "verified",
      severity: "low",
    });
  }
}
if (!queueEmpty) {
  const capReport: WorkflowReport = {
    conclusion: `任务轮次达到上限 ${MAX_ROUNDS}，停止等待人工介入；已完成任务均已落盘，可续跑。`,
    findings: notes,
    verified: [`${rounds} 轮任务执行并 advance`],
    notCovered: ["剩余任务", "渲染与校验"],
  };
  return capReport;
}

phase("渲染并做发布前校验");
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
    verified: [`Agent 任务循环完成（${rounds} 轮）`],
    notCovered: ["校验"],
  };
  return failReport;
}
const emailMatch = /"(workspace\/runs\/[^"]+\/email\.html)"/.exec(renderRun.stdout);
const emailPath = emailMatch && emailMatch[1] ? emailMatch[1] : "";
let validated = false;
let lastValidate = "";
for (let attempt = 1; attempt <= MAX_VALIDATE_RETRIES; attempt++) {
  const v = await world.run(".venv/bin/python3", ["briefing.py", "validate", "--run", "latest"], { timeoutMs: 300000 });
  lastValidate = v.stdout;
  if (v.exitCode === 0) {
    validated = true;
    break;
  }
  log(`发布校验未通过（第 ${attempt} 次），派发最小修复后重渲染`);
  await agent().ask<TaskOutcome>(validateFixAsk(v.stdout));
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
    verified: [`Agent 任务循环完成（${rounds} 轮）`, "render --execute 已执行"],
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
  const validationPath = emailPath.replace(/email\.html$/, "validation.json");
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
  conclusion: `briefing 已达 READY_TO_SEND（${rounds} 轮 Agent 任务，发布校验通过）。请人工阅读 email.html 与 validation.json，确认后在主会话执行 send --confirm-send 完成两步发送确认。`,
  findings: notes,
  verified: [`Agent 任务循环 ${rounds} 轮全部 advance`, "render --execute", "validate 退出码 0"],
  notCovered: ["send --confirm-send（主会话人工确认）", "发送后的归档与推送"],
};
return finalReport;