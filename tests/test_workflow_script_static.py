"""briefing-run workflow 脚本的静态守卫。

镜像宿主（glm/zcode.cjs）泳道名静态投影契约：agent() 首参模板的 head（首个 ${ 之前的
字面文本）与 tail（最后一个 ${ 之后）须 trim 后含字母/数字，否则运行图泳道头回退
「未命名子代理」。契约与修复设计见
docs/history/designs/2026-11-04-workflow-lane-affix-names.md。
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".zcode" / "workflows" / "briefing-run.dwf.ts"

# 近似宿主 meaningfulAffix 的 /[\p{L}\p{N}]/u：Unicode 字母或数字（不含下划线）
_HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]", re.UNICODE)

_AGENT_TEMPLATE = re.compile(r"agent\((`[^`]*`|\"[^\"]*\"|'[^']*')")
_CASE_LABEL = re.compile(r"^\s*case \"([^\"]+)\":", re.MULTILINE)
_ROLE_VALUE = re.compile(r"^\s*\w+: \"([^\"]+)\",", re.MULTILINE)
_ROLE_TABLE_START = "const ROLE: Record<string, string> = {"


def _meaningful_affix(text: str) -> bool:
    trimmed = text.strip()
    return bool(trimmed) and bool(_HAS_LETTER_OR_DIGIT.search(trimmed))


def test_every_agent_call_has_literal_name_source() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    calls = _AGENT_TEMPLATE.findall(source)
    assert calls, "脚本里应存在 agent() 调用"
    for arg in calls:
        assert arg[0] in "`\"'", f"agent() 首参必须是字面量（模板或字符串），否则泳道头匿名：{arg!r}"


def test_every_agent_template_head_or_tail_is_meaningful() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    templates = [arg for arg in _AGENT_TEMPLATE.findall(source) if arg.startswith("`")]
    assert templates, "脚本里应存在模板字面量命名的 agent() 调用"
    for tpl in templates:
        body = tpl[1:-1]
        head, _, rest = body.partition("${")
        tail = rest.rpartition("${")[2] if "${" in rest else ""
        # 无插值的模板是精确名；有插值的须 head 或 tail 含字母/数字（宿主 templateAffixes 契约）
        if "${" in body:
            assert _meaningful_affix(head) or _meaningful_affix(tail), (
                f"agent() 模板首尾均无有效字面文本，泳道头将回退「未命名子代理」：{tpl!r}"
            )


def test_wave_dispatch_switch_covers_role_table() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    table = source.partition(_ROLE_TABLE_START)[2].partition("};")[0]
    role_values = set(_ROLE_VALUE.findall(table))
    assert role_values, "ROLE 表解析失败"
    cases = set(_CASE_LABEL.findall(source))
    assert cases == role_values, (
        f"派发 switch 分支标签 {sorted(cases)} 应等于 ROLE 表全部去重值 {sorted(role_values)}"
    )
    assert "default:" in source, "派发 switch 须保留 default 兜底分支（执行编辑）"


def test_wave_names_still_route_through_uniquename() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "uniqueName(base)" in source, "子代理名必须经 uniqueName() 去重（重名会终止运行）"
    # 名字拼法锚定：switch 每个分支的模板 = 字面标签·${mid}第${waves}波${suffix}
    for label in set(_CASE_LABEL.findall(source)):
        expected = f"`{label}·${{waveTags[i].mid}}第${{waves}}波${{waveTags[i].suffix}}`"
        assert expected in source, f"缺少与分支 {label} 对应的命名模板 {expected}"
