# briefing-run 泳道名首尾字面契约与波始进度卡

- Status: implemented
- Created: 2026-11-04
- Last updated: 2026-11-04
- Supersedes: `2026-10-31-workflow-run-legibility.md` 中「内联模板字面量即可解析泳道名」的假设（该设计其余部分仍有效）

## Problem and evidence

2026-10-31 期运行（`dwfrun-eaabb261`，14:06 发起）已使用 dbbf8eb 的「内联模板字面量」脚本，用户仍反馈两点：运行图里还是有「未命名子代理」；看运行时不知道进度。事实核对：

- 运行期命名无恙：`GetWorkflowRun` 子代理列表全部具名（`筛选候选·…·第2波` 等），阶段看板与进度总览两个 board 产物都在。
- 「未命名」来自运行图的**泳道标签静态投影**。本轮反混淆宿主 `glm/zcode.cjs` 中的分析器，拿到确切契约：

  - `actorName`：`agent()` 首参为**字符串字面量**才有精确泳道名；
  - 否则 `actorNamePattern` → `templateAffixes`：只取模板字面量的 **head**（首个 `${` 之前的字面文本）与 **tail**（最后一个 `${` 之后的字面文本），**中间字面片段一律不读**；head/tail 各自须 trim 后非空且含至少一个字母或数字（`/[\p{L}\p{N}]/u`；纯标点如 `·` 不算），有一个即成 namePattern；
  - head 与 tail 皆无效 → 无 namePattern → 泳道头回退 UI 常量「未命名子代理」。

- 对照脚本四处调用点：波次任务两处 `` agent(`${waveTags[i].role}·${waveTags[i].subject}·第${waves}波${waveTags[i].suffix}`) `` 以 `${` 开头、以 `${…}` 结尾，head/tail 双双为空 → 匿名（这恰是占绝大多数的子代理，~150/160）；修复输出处 head=`修复输出·`、终审修复处 head=`终审修复·第` tail=`次`，本就不匿名。与用户观察完全吻合：10-31 修复方向对了一半（内联模板），但首尾没留字面文本，中间片段对分析器不可见。

进度侧：进度总览卡只在每波 advance 之后更新，首波执行期间（可能 30 分钟以上）没有任何「当前在哪」的卡；波始日志行「已完成 90」无总数分母，读不出比例。

## Fix

全部在 `.zcode/workflows/briefing-run.dwf.ts`，运行期子代理名**逐字节不变**（AmendWorkflow 缓存与已文档化命名体系不受影响）：

1. **波次任务调用点改为按角色分支的字面 head 模板**。`waveTags` 预计算 `mid`（`subject ? subject + "·" : ""`），map 回调内 switch（10 个分支 = ROLE 表全部功能标签 + 执行编辑兜底），每个分支的模板以字面功能标签开头：

   ```ts
   case "筛选候选":
     return agent(`筛选候选·${waveTags[i].mid}第${waves}波${waveTags[i].suffix}`).ask<TaskOutcome>(taskAsk(t.instructions));
   ```

   head=`筛选候选·`（含字母）→ namePattern 成立，泳道头不再匿名；且每个流水线角色一条泳道，运行图静态呈现 开放搜索→筛选候选→…→生成插画 的管线形状。修复输出、终审修复两处维持原状（本就有有效 head/tail）。

2. **波始进度卡**。`reportProgress(stage, running)` 增加执行中标记，在派发子代理**之前**上卡：`当前：筛选候选·第 3 批（执行中）｜完成 90/154｜待办 64`。首波起进度卡即存在并随波推进，advance 后与修复后再各更新一次（不带执行中标记）。

3. **波始日志行加总数分母**：`已完成 ${appliedTotal}/${appliedTotal + rows.length}`（总数 = 完成 + 当前全部待办，与进度卡口径一致）。

不做每任务看板：10-31 决策日志已否决（百余张卡加重过载），「谁在做什么」仍由运行流中的命名子代理卡承担；本次只补「到哪了」的顶线。

## Compatibility and migration

- 存量运行不受影响；改动只影响下次新起/续跑的展示与日志。
- 运行期名字逐字节不变（switch 分支重组的是模板，不重组字符串），对进行中旧运行 AmendWorkflow 缓存命中不受影响。
- 静态图从 2 条匿名泳道变为 10 条角色泳道（32 泳道上限内）；确认对话框与运行图共用同一投影，均受益。

## Verification

- strict tsc 全脚本编译干净（门面 stub + `tsc --strict --noEmit`）。
- 新增 `tests/test_workflow_script_static.py` 静态守卫：脚本内每个 `agent(` 调用点的模板 head 须 trim 后含字母/数字（镜像 `meaningfulAffix` 规则）；switch 分支标签集合 = ROLE 表值集合 + 执行编辑。
- 下次例行运行目检：确认对话框泳道头逐角色非匿名；首波期间进度总览卡已出现且带（执行中）；波始日志行带 X/Y 分母。

## Decision log

- 2026-11-04：从 `zcode.cjs` 反混淆拿到泳道名确切契约（actorName / templateAffixes / meaningfulAffix），10-31 的「内联模板即可」假设被证伪：**只有首尾字面片段参与，且须含字母数字**。中间片段（`·`、`第`、`波`）不可见。
- 2026-11-04：否决「单一调用点加通用字面前缀（如 `Agent任务·`）」——运行期名字会变形（破坏缓存命中与 `功能·对象·第N波` 文档契约），且泳道信息量低；采用按角色分支 switch，字面角色作 head，名字逐字节不变。
- 2026-11-04：否决每任务看板（维持 10-31 决策）；进度可读性由「波始进度卡 + 日志分母」补齐。
