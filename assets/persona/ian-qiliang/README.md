# Ian 风格的 Qiliang 项目覆盖层

这个目录是当前 `technical-briefing-skill` **唯一的 AI 插图人物契约**：
`ian-xiaohei-illustrations` 提供视觉 DNA，本目录只把默认“小黑”替换为 Qiliang 的手绘形象。

它不是 Ian Skill 的分叉，也不复制或修改 Ian Skill。生成时仍以已安装 Skill 中的
`style-dna.md`、`composition-patterns.md`、`prompt-template.md` 和
`qa-checklist.md` 为准，然后叠加本目录的 `overlay.md`。

Guizang 只继续用于现有 HTML/card 排版层；不得把 Guizang Material Illustration、旧 Guizang persona、`assets/persona/reference.jpg` 或通用人物作为 AI 插图的替代路径。

## 使用顺序

1. 读取并遵守 `ian-xiaohei-illustrations`。
2. 读取 `overlay.md`，只替换角色定义。
3. 读取 `reference-manifest.yaml`，同时使用身份、动作和横版场景锚点。
4. 验证 `identity_anchor`、`action_anchor`、`wide_scene_anchor` 对应文件都真实存在；缺任意一张都不得静默换人物或换风格。
5. 每张图都要先证明技术解释价值，再允许人物出现。

## 不变量

- Ian 的纯白背景、黑色手绘线稿、克制的红橙蓝批注、大量留白和怪诞隐喻不变。
- 一张图只解释一个核心结构，不能做成 PPT 或商业信息图。
- 人物必须是动作主体，不能作为头像、签名、水印或角落里的装饰。
- 去掉人物后如果技术隐喻仍能完整成立，说明人物没有真正参与，需要重做。
- HTML/card 的 Guizang 排版规则与图片风格相互独立，本目录不修改邮件布局。
