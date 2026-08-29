# 个人肖像卡通化建议

**User:** Anonymous  
**Created:** 8/9/2026 11:07:41  
**Updated:** 8/9/2026 19:26:26  
**Exported:** 8/10/2026 1:03:54  
**Link:** [https://chatgpt.com/c/6a77eefb-1ffc-83ec-9e52-251b0cc9740c](https://chatgpt.com/c/6a77eefb-1ffc-83ec-9e52-251b0cc9740c)  

## Prompt:
2026/8/9 11:07:37

https://github.com/QiliangLi/technical-briefing-skill这个仓库中的pics文件夹中包含我个人肖像的图片，我想类似于仓库https://github.com/helloianneo/ian-xiaohei-illustrations一样创建符合我个人肖像的图片，并插入每日简报的email.html中，你有什么好的建议吗？

## Response:
2026/8/9 11:07:41

我会先对比两个仓库里三件事：你当前 `pics/` 的素材组织、`email.html` 的生成/插图方式，以及 `ian-xiaohei-illustrations` 是怎么把“固定人物 IP + 多场景插画”工程化的。然后我给你一个适合每日简报的方案，重点考虑**稳定复用、生成成本、人物一致性和邮件兼容性**。

我已经确认一个关键差异：`ian-xiaohei-illustrations` 真正可借鉴的不是“小黑人物长什么样”，而是它把视觉系统拆成了 **IP 定义 / 风格 DNA / 构图模式 / Prompt 模板 / QA 清单** 五层；你的仓库目前已经有 `pics/` 和 `assets/persona/`，很适合直接沿这个思路升级，而不是每天临时拿照片重新生图。

从你现有代码看，还有一个很重要的现实约束：当前 `expanded_v2` 路径是**明确按“邮件无图”设计的**，而现有视觉资产主要服务于社交卡片；`email.html` 本身也没有图片槽位。所以这不是简单“多写一个 prompt”，而是需要把**人物插画变成正式的邮件资产管线**。

> **检索并比较仓库中的邮件与每日简报HTML**
>
> 
>
> **正在搜索网页**
>
> [gallery/skills/README.md at main · google-ai-edge/gallery · GitHub](https://github.com/google-ai-edge/gallery/blob/main/skills/README.md)
> [GitHub Skills Content Model](https://skills.github.com/content-model)
>
> **已搜索 2 个网站**
>
> 
>
> **检索仓库 README、技能文件及 pics 路径引用**
>
> 
>
> **正在搜索网页**
>
> [GitHub - QiliangLi/technical-briefing-skill · GitHub](https://github.com/QiliangLi/technical-briefing-skill)
>
> **已搜索 1 个网站**
>
> 
>
> **克隆技术简报技能仓库**
>
>
> **克隆技术简报技能仓库**
>
> 
>
> **搜索 GitHub 文件中的 Guizang 内容**
>
> 
>
> **正在搜索网页**
>
>
> **正在搜索 2 个网站**
>
> 
>
> **获取并检查仓库资源、视觉规范及渲染文件**
>
> 
>
> **正在搜索网页**
>
>
> **正在搜索网页**
>
> 
>
> **规划视觉个性化**
>
> 我会把原始照片与最终参考图分开管理：先选出少量肖像，制作统一的卡通角色设定与表情、服饰、构图规范，再将其稳定应用到每日简报视觉中。
>
> **规划视觉个性化方案**
>
> 
>
> **完善投递方案**
>
> 我还需要确认邮件发送链路是否支持内嵌图片。相比直接引用本地路径，我更倾向于使用稳定的 HTTPS 图片或 MIME 内嵌资源，并同步检查转发环节是否保留相关附件。
>
> **完善了投递方案**
>
> 
>
> **获取并评估插画提示词、风格规范及邮件图表方案**
>
> 
>
> **正在搜索 @tencent-qqmail/agently-cli message send attachment inline image body-file GitHub**
>
> [keywords:qqmail - npm search](https://www.npmjs.com/search?q=keywords%3Aqqmail)
> [agently-mail Skill by tencent | Claude Skills Hub](https://claudeskills.info/skills/tencent/agentlymail/agently-mail/)
> [Agently Mail Skill for Claude Code & OpenClaw | Remote OpenClaw](https://www.remoteopenclaw.com/skills/tencent/agentlymail/agently-mail)
> [@tencent-qqmail/agently-cli CDN by jsDelivr - A CDN for npm and GitHub](https://www.jsdelivr.com/package/npm/%40tencent-qqmail/agently-cli)
> [Reply With: Proactive Recommendation of Email Attachments](https://arxiv.org/abs/1710.06061)
>
> **已搜索 5 个网站**
>
> 
>
> 思考了 2m 49s

我看完两个仓库后，我的建议是：**不要简单把 `ian-xiaohei-illustrations` 的“小黑”替换成你的真人卡通头像，而是把它的“视觉 IP 工程化方法”移植进 `technical-briefing-skill`。**

你现在其实已经走了一半。仓库里已经有 `assets/persona/persona-spec.yaml`，而且对“技术侦察员”的短发、细框眼镜、白衬衫、略松深蓝条纹领带、克制表情、人物占画面 10-25% 等都已经定义好了。 现有 `visual-routing.md` 甚至已经有 `persona_metaphor` 这个模式，而且明确要求人物只承担“为什么重要 / 应验证什么”这类认知动作，而不是替代技术证据。

### 我最推荐的最终效果

不是每天简报里出现很多张“你的卡通照片”，而是形成一个长期稳定的 **“Qiliang 技术侦察员”视觉 IP**。

比如一期简报里的主图讲：

> “这周大量 AI Infra 新闻看起来都很热，但真正值得关注的是存储、网络和推理运行时开始围绕 KV 状态重新分工。”

画面不是你站着指 PPT，而是：

**卡通化的你戴眼镜、穿白衬衫和蓝色领带，蹲在一台怪异的「技术信号分拣机」旁边。几十张论文、GitHub Release、芯片图标从左边进入，你把大部分扔进灰色箱子，只有 KVCache、DPU、CXL、光网络几块从右边蓝色出口出来。**

这样，“人物”不是装饰，而是在执行一个认知动作。

这正是 Ian 项目最值得学的地方：它要求“小黑必须承担核心动作”，而不是在角落里当 mascot。

---

## 但我不建议完全照 Ian 的视觉风格

Ian 的风格是：

纯白背景、黑色手绘线稿、大量留白、少量红橙蓝批注、怪诞隐喻，而且明确避免 PPT 信息图感。

你的简报是发给内部领导和技术同事看的，我会稍微收敛“怪诞感”，做成：

**白底手绘技术草图 + 轻度材质感 + 你的固定卡通 IP + 极少量藏蓝/橙色标注。**

也就是说，比 Ian 稍微专业一点，但比你现在的 Guizang Material Illustration **更有人味、更有个人识别度**。

可以把风格定义成：

> **Technical Scout Notebook**
>
> 白底、手绘、低细节、轻微不规则线稿；技术对象相对准确，人物略带漫画化；70% 技术解释 + 30% 隐喻；人物认真工作而不是面对镜头；整体像一个研究员在白板上画出来的技术观察。

这样跟你现在邮件里的藏蓝 `#002fa7` 也很搭。当前邮件本身就是白/灰底 + IKB 蓝的克制技术风格。

---

## 人物一致性是这里最重要的问题

我**不建议每天直接把 `pics/` 里的真人照片喂给模型，然后让模型自由生成**。

这样跑十期之后，非常容易出现：

今天脸圆一点，明天脸长一点；今天是动漫，明天是写实；眼镜、发型、领带不断漂移。

Ian 的项目能稳定，一个原因就是它不是一句“小黑长这样”，而是把它拆成 IP 定义、Style DNA、构图模式、Prompt 模板和 QA checklist。它甚至明确规定如何判断“小黑已经沦为装饰”。 

所以你的流程应该变成：

**真人照片 → 一次性生成并人工确认标准人物设定图 → 以后所有日报只参考标准人物设定图。**

例如第一次用 `pics/` 里 3-5 张清晰照片，生成一张固定的 Character Sheet：

正面头像、3/4 侧面、站立全身、低头检查资料、搬数据块、操作设备。

然后你自己挑一个“最像我”的版本。

从此之后每天生成插图时主要引用：

`character-sheet.png`

而不是重新理解原始照片。

这样会稳定很多。

顺便提醒一下，你目前这个 GitHub 仓库是 **Public**，而根目录目前确实公开展示了 `pics/`。([github.com](https://github.com/QiliangLi/technical-briefing-skill)) 如果这些是你不希望长期公开传播的真人原图，我建议原始照片不要继续放在公开仓库；仓库里保留经过你确认的低分辨率 character sheet / persona reference 就够了。

---

## 我会把你的 Persona 目录改成这样

```text
assets/persona/
├── README.md
├── persona-spec.yaml
│
├── reference/
│   ├── portrait-front.jpg
│   ├── portrait-3q.jpg
│   └── full-body.jpg
│
├── character-sheet.png
├── character-reference.png
│
└── references/
    ├── style-dna.md
    ├── character-ip.md
    ├── composition-patterns.md
    ├── prompt-template.md
    └── qa-checklist.md
```

这里基本就是吸收 Ian 的工程思想。他的项目也是把 `xiaohei-ip.md`、`style-dna.md`、`composition-patterns.md`、`prompt-template.md`、`qa-checklist.md` 分开的。

你现在的 `persona-spec.yaml` 不需要推翻，反而非常好，可以继续作为**机器可读配置**；新加的 Markdown 是给 Agent 理解视觉语言的。

---

## 邮件里我建议只放 1～2 张，而不是每条信息都放

这是我觉得最关键的产品设计判断。

你现在一个专题最多 Top 4 深读，又有 8 个深度专题，理论上最多能出现很多条核心内容。 如果每篇都配一个你的卡通形象：

**视觉会非常吵，而且生成成本也会重新起来。**

更重要的是，人物 IP 会从“识别度”变成“水印”。

我建议这样分：

| 位置 | 图片 | 作用 |
|---|---|---|
| 本期判断后 | **1 张主插画，固定生成** | 把本期最重要的判断视觉化 |
| 最重要专题中间 | **0-1 张专题插画** | 解释最值得关注的机制/变化 |
| 单条论文/Release | 默认不生成个人插画 | 优先原论文图、官方图、程序化图表 |
| 热点雷达 | 不生成 | 保持快速浏览 |

这其实和你现有的 `visual-routing` 哲学完全一致：技术证据优先 `source_figure / official_image / screenshot / chart_redraw`，人物隐喻排在后面。

我甚至会进一步改成：

**item-level visual routing 保留；另加一个 issue-level visual planning。**

也就是：

```text
issue synthesis
      ↓
issue visual planner
      ↓
选本期一个“认知锚点”
      ↓
生成 Qiliang 技术侦察员主插画
      ↓
email.html
```

这比现在“每个 brief item 决定要不要 persona_metaphor”更适合日报。

---

## 邮件中的最佳位置也很明确

你当前结构实际上是：

```text
HEADER
专题导航
本期判断
────────────
专题 1
专题 2
...
热点雷达
```

我会把人物主插图直接插在：

**「本期判断」之后、「第一个专题」之前。**

即：

```text
HEADER

专题导航

本期判断
01 ...
02 ...
03 ...

┌─────────────────────────────┐
│                             │
│      本期主题人物插画        │
│                             │
└─────────────────────────────┘

TPN / 状态感知网络
...
```

而不是塞进现在的双栏 item card。

你邮件只有 720px 宽，双栏以后单卡只有大约 320px 左右；在这么窄的空间放人物+技术机制图，信息密度会非常糟糕。当前模板确实采用两列 50% 卡片结构。

主插画建议：

**显示宽度约 664px，高度约 330-360px，约 1.9:1。**

这正好跟你现在 `illustration-brief.md` 要求的 1.9:1 横图一致。

---

## 你的底层邮件代码其实已经为这件事准备得差不多了

这里有个很有意思的发现。

`EmailService.build()` 已经会检查：

```python
item["illustration"]["generated_asset_path"]
```

和：

```python
item["visual_plan"]["asset_path"]
```

然后生成 `email_asset_path`。

更重要的是，SMTP 发送时已经实现：

```text
本地 <img src="/.../xxx.png">
        ↓
_prepare_inline_images()
        ↓
cid:xxxx
        ↓
MIME related inline image
```

也就是说，**SMTP 这条链路几乎不用重新设计。** 

真正缺的主要就是：

```html
{% if issue.hero_illustration %}
<img src="{{ issue.hero_illustration.email_asset_path }}">
{% endif %}
```

以及 issue-level illustration 数据。

不过这里有一个坑：你的默认发送 backend 是 `agently`，配置里也是这么设计的；而 `_agently_send()` 当前只是把 `email.html` 通过 `--body-file` 交给 CLI，并没有调用 `_prepare_inline_images()`。SMTP 路径才明确做了 CID related。

所以这个功能上线前一定要做一个真实端到端测试：

**本地 HTML 有图 → 外部邮箱收到有图 → 如果还需要转发 → 公司 Outlook 最终收到仍有图。**

不要只验证浏览器里的 `email.html`。

---

## 如果现在让我给这个仓库提一个 PR，我会控制范围

我不会一上来改整个视觉系统。

**第一个 PR 就做“Issue-level Personal Illustration for Email”。**

它包含这些改动：

1. 把 `pics/` 里的肖像整理成正式 Persona reference，人工先确定一张 `character-sheet.png`；
2. 参考 Ian 的结构补齐 `style-dna / character-ip / composition-patterns / prompt-template / qa-checklist`；
3. 新增 `issue-illustration-brief.md`，从本期 `synthesis.judgements` 中选择**一个最值得画的认知锚点**；
4. 每期默认只生成 **1 张**个人 IP 主插画；
5. 输出到类似  
   `workspace/runs/<run-id>/visuals/issue-hero.png`；
6. `issue.json` 增加：
   ```json
   {
     "hero_illustration": {
       "status": "generated",
       "visual_anchor": "...",
       "generated_asset_path": "..."
     }
   }
   ```
7. 修改 `email.html`，把图片插到“本期判断”之后；
8. 加邮件图片验证：本地路径存在、宽高比正确、实际 MIME/发送链路不丢图；
9. **不要改现在单条 item 的 source figure / chart / Guizang 路径。**

这样 PR 很干净，也不会把你刚刚优化好的 Top4、Evidence Pack、Token 成本等主流程重新搅乱。

### 一句话概括

**Ian 项目值得复制的是“固定 IP + 每期重新发明一个认知隐喻 + 严格风格约束”，而不是它的小黑画风本身。**

对你的简报，我会把它做成：

> **一个固定的“技术侦察员 Qiliang”角色，每期只出现 1～2 次，通过实际动作把“本期最重要的技术判断”画出来。**

这会比“给每篇论文配个卡通版的你”高级很多，也更适合长期形成你这份技术简报自己的辨识度。

## Prompt:
2026/8/9 19:24:42

现在代码仓有些更新，会不会影响你刚才计划修改的文件？

## Response:
2026/8/9 19:24:46

我先对比一下**你刚更新后的 `main`** 和我刚才计划涉及的文件，重点看 `assets/persona/`、视觉 prompts、`templates/email.html`、`emailer.py`、`rendering.py` 和 `settings.yaml` 有没有被最近提交改动。只要这些地方有冲突，我会直接调整方案，不按旧结构硬套。

> **核对提交影响**
>
> 我正在比较基线与当前提交：主要变化集中在邮件模板、配置和问题综合；现有渲染、邮件发送器与视觉提示看起来未被改动。
>
> **核对提交影响**
>
> 
>
> **检视提交变更并审阅最新模板配置**
>
> 
>
> 思考了 43s

会有影响，但**不影响整体方案，只需要调整 PR 的落点**。

我刚对比了我上次分析时的 `1c91f3` 和现在 `main` 的 `4572c8`：中间又进了 **9 个提交**。其中真正与“个人 IP 插画进入邮件”直接相关的变化主要有三类。最新提交已经把人工 review/approve gate 删除，改成“最终校验通过 → `READY_TO_SEND`，失败 → `VALIDATION_FAILED`”。

### 1. `templates/email.html` 确实已经被改过

这个是我们原计划**一定会修改**的文件，所以需要以最新版为基础做。

新版给邮件 DOM 增加了不少机器可校验标记，例如：

- `data-reader-role="judgement"`
- `data-reader-row="deep-row"`
- `data-reader-role="deep-card"`
- `data-reader-meta="1"`
- 单卡自动变成 100% 宽

同时已经去掉了之前暴露给读者的内部评分。

因此我现在不会简单在模板里随便插一个 `<img>`，而会明确加一个独立块，例如：

```html
<tr data-reader-role="hero-illustration">
  ...
  <img ...>
</tr>
```

位置依然是：

**本期判断 → 主插画 → 第一个专题**

所以视觉设计方案完全不变，只是实现时要尊重现在的 reader contract。

---

### 2. 最终 HTML 现在是“发布阻断级”校验对象

这是最大的变化。

PR #31 新增了 `final_reader_contract.py`，最终生成出来的 `email.html` 会重新检查：

- Deep / appendix / Radar 是否重复；
- 单卡是否正确占满一行；
- 是否暴露内部 score；
- 文案是否违反 reader contract；
- 最终 Deep 是否真的是合法 Top4。

只要失败，就会阻断发送。

而 #33 又进一步把这个 validation 变成了**正式 release gate**。现在流程是：

```text
生成 email
   ↓
RENDERED
   ↓
Final Validation
   ├─ PASS → READY_TO_SEND
   └─ FAIL → VALIDATION_FAILED
```

发送仍然必须显式 `--confirm-send`。

这对我们的 PR 其实是好事。

我会顺势把**人物插画本身也纳入最终校验**，例如至少检查：

```text
hero_illustration.status == generated
        ↓
文件实际存在
        ↓
是支持的 PNG/JPEG/WebP
        ↓
HTML 里只出现一次
        ↓
没有破坏 reader DOM
```

这样不会出现：

> Agent 说生成成功了，但邮件实际是一张裂图。

---

### 3. 我现在反而不建议修改 `issue-synthesis.md`

之前我的方案里有一点倾向于：

> issue synthesis → 顺手产生插图的“认知锚点”。

现在看完新代码，我会把这个拆得更彻底。

因为 `issue-synthesis.md` 现在有非常严格的 reader-writing contract：`judgements` 只能有 1-3 条，每条标题 ≤32 中文字符，正文 ≤180 字、≤3 句，而且有数字密度、证据 ID、项目 insight 等硬约束。

再加上新加入的 canonical execution envelope 体系，我认为**不要为了生图去污染 issue synthesis 的语义职责**。

新的流程应该是：

```text
issue synthesis
     │
     │  已经完成
     ▼
synthesis.judgements
core_items
project_insights
     │
     ▼
Issue Visual Planner   ← 新增
     │
     ├─ 选择一个视觉认知锚点
     ├─ 选择隐喻
     ├─ 选择人物动作
     └─ 形成 illustration brief
     │
     ▼
Image Generation
     │
     ▼
hero_illustration.json
hero.png
     │
     ▼
Email Build
     │
     ▼
Final Validation
```

这是我现在认为比上一版更干净的架构。

---

## 所以现在 PR 的修改范围，我会调整成这样

原本想碰的一些文件，现在可以少碰。

| 文件 | 现在建议 |
|---|---|
| `assets/persona/persona-spec.yaml` | **改/增强** |
| `assets/persona/reference.*` | **整理** |
| `assets/persona/references/*` | **新增** |
| `prompts/issue-illustration-brief.md` | **新增** |
| `schemas/issue-illustration.schema.json` | **新增** |
| `briefing_skill/issue_visual.py` | **新增** |
| `templates/email.html` | **修改最新版** |
| `briefing_skill/emailer.py` | **需要修改** |
| `briefing_skill/final_reader_contract.py` | **建议扩展校验** |
| `config/settings.yaml` | **小改** |
| `prompts/issue-synthesis.md` | **不改** |
| `prompts/visual-routing.md` | **原则上不改** |
| `prompts/illustration-brief.md` | **原则上不改** |
| item-level visual pipeline | **不动** |

尤其是 `settings.yaml`，最近其实只移除了 `require_human_approval`；原来的视觉配置仍然存在，包括 `persona_max_appearances_per_issue: 2`、`persona_reference` 等。

所以现有 Persona 设计可以继续利用。

---

## 有一个问题反而比刚才更值得单独解决

**Agently 邮件内嵌图片。**

这次 9 个提交里没有改 `emailer.py` 的这部分逻辑，所以我之前指出的问题依然存在：

SMTP 路径有：

```text
local image
→ _prepare_inline_images()
→ cid:
→ MIME related
```

但默认的 Agently 路径还是直接：

```text
email.html
→ agently-cli --body-file
```

因此对于这个 PR，我现在会把优先级调整为：

> **先保证图片真的能通过默认 agently backend 到达收件箱，再谈人物画风多漂亮。**

否则非常容易变成浏览器里 `email.html` 完美，真正发出去就是裂图。

---

### 结论

**代码更新不会推翻刚才的方案，但让我会把 PR 做得更“旁路化”。**

最重要的变化是：

> 不修改现在刚强化过的 `issue-synthesis`、Top4、Deep eligibility、Evidence 和 reader-writing 主链路；在 **Issue Synthesis 完成之后、Email Build 之前** 插入一个独立的 `Issue Visual Planner → Image Generation` 阶段。

这样与最近 #28～#33 的改动冲突最小，而且以后你继续改简报正文质量，也基本不会和个人 IP 插画互相干扰。



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)