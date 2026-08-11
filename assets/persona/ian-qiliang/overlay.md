# Qiliang 角色覆盖

本文件是当前 briefing AI 插图的唯一人物覆盖层。图片视觉风格来自 `ian-xiaohei-illustrations`；Guizang 只保留在 HTML/card 排版层，不得参与人物或插图风格生成。

## 覆盖范围

仅覆盖 Ian Skill 中的 `Recurring IP character`、`小黑 IP` 和所有“小黑执行动作”的
描述。其他 Ian 规则逐字保持其原始语义，不在本项目重新解释或放宽。

## 角色替换

把“小黑，一个黑色实心、白点眼、细腿的怪诞工作者”替换为：

> Qiliang，一位低细节的年轻男性手绘技术侦察员。短而略蓬松的黑发，细黑框圆形或
> 轻微圆角眼镜，白色衬衫领口外搭黑色针织衫，深色长裤；神情平静、认真、克制，
> 有轻微冷幽默但不卖萌。面部与发型以 `reference-manifest.yaml` 的身份锚点为准。

## 参考图规则

- `reference-manifest.yaml` 是唯一参考图 owner。
- `identity_anchor`、`action_anchor`、`wide_scene_anchor` 三张图都必须存在并可读。
- 不使用 `assets/persona/reference.jpg`，不从旧 Guizang persona 合并白衬衫+蓝条纹领带等外观描述。
- 缺参考图时不得生成通用替代人物；应让图片路径失败/回退为文本，而不是改变身份。

## 保留的小黑行为语义

- 仍然是认真参与系统运转的荒诞工作者，而不是作者肖像展示。
- 仍然必须承担画面核心动作：扳、搬、捞、压、称、修补、守门、分拣或记录。
- 仍然保持略微笨拙但不愚蠢、冷静而不夸张的气质。
- 人物通常只占画面约 15%—25%，动作和技术对象共同构成主体；不得正面摆拍。
- 不出现姓名、签名、个人介绍或“作者”标签，个人识别只通过稳定形象自然建立。

## 禁止

- 不要生成黑色怪物或同时保留“小黑”。
- 不要 Q 版大头、儿童卡通、毕业照、证件照、演讲姿势或面对镜头摆拍。
- 不要把人物放在角落里看技术图，也不要让人物遮挡机制、箭头和关键对象。
- 不要为了强调本人而放大面部；先让读者看懂技术动作，再感知人物是谁。
- 不要使用 Guizang Material Illustration 或旧 Guizang persona 作为图片生成 fallback。

## 提示词替换块

在 Ian 原提示词模板的 `Recurring IP character required` 段落中，用下面文本替换原段：

```text
Recurring IP character required:
Qiliang, a low-detail hand-drawn young male technical scout based on the provided project reference images. Short slightly tousled black hair, thin black round or softly rounded glasses, a black knit sweater over a crisp white shirt collar, dark trousers, calm serious expression. He must perform the core conceptual action and physically operate the metaphor, never pose for the viewer or decorate a corner. Keep his likeness stable but understated: readers should first understand the technical mechanism, then gradually recognize the recurring person. Deadpan, restrained, slightly absurd, not cute, not a mascot.
```

## 本项目额外验收问题

1. 不看正文，读者能否在 1—2 秒内说出这张图解释的技术选择或机制？
2. 人物是否通过动作解释机制，而不是仅仅证明“这张图属于 Qiliang”？
3. 删除人物后，核心因果是否会缺一环？如果不会，人物需要重新参与动作。
4. 是否保持 Ian 原有视觉 DNA，而不是变成技术海报、架构图或个人宣传图？
