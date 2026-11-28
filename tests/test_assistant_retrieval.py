import json

from briefing_skill import cli
from briefing_skill.assistant import install_assistant
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.eval import evaluate
from briefing_skill.assistant.replies import compose_answer, within_limit
from briefing_skill.assistant.retrieval import (
    LexicalIndex,
    assess,
    ensure_index,
    is_stale,
    snapshot_dir,
    tokenize,
)
from assistant_support import SITE, repository
from briefing_skill.paths import discover_root
from briefing_skill.utils import read_json, write_json

CREATED = "2026-11-28T00:00:00+00:00"


def _config() -> AssistantConfig:
    return AssistantConfig(site_base_url=SITE)


def _doc(doc_id: str, title: str, summary: str = "") -> dict:
    return {
        "id": doc_id,
        "kind": "item",
        "title": title,
        "search": title,
        "summary": summary,
        "issue_date": "2026-10-01",
        "url": f"{SITE}#archive?date=2026-10-01&item={doc_id}",
        "topic_id": "",
        "direction_id": "",
    }


def test_tokenize_splits_english_words_and_chinese_bigrams():
    assert tokenize("KV cache 分层卸载") == ["kv", "cache", "分层", "层卸", "卸载"]
    # Stopwords are removed as whole words before bigrams are cut, so a pure
    # question phrase leaves no stray fragments behind.
    assert tokenize("请问有没有关于 X 的论文") == []
    assert tokenize("测试时扩展到底有没有用") == ["测试", "试时", "时扩", "扩展"]


def test_idx_01_only_published_content_is_indexed(tmp_path):
    index, rebuilt = ensure_index(repository(tmp_path), _config(), created_at=CREATED)
    assert rebuilt
    assert {doc["id"]: doc["kind"] for doc in index.docs} == {
        "item:" + "a" * 24: "item",
        "item:" + "b" * 24: "item",
        "radar:radar-1": "radar",
        "idea:idea_c": "idea",
        "roadmap:storage": "roadmap",
    }
    assert "DECOY" not in json.dumps(index.to_dict(), ensure_ascii=False)


def test_idx_02_building_twice_is_byte_equivalent(tmp_path):
    root = repository(tmp_path / "repo")
    first = ensure_index(root, _config(), tmp_path / "one", created_at=CREATED)[0]
    second = ensure_index(root, _config(), tmp_path / "two", created_at="2026-11-29T00:00:00+00:00")[0]
    assert first.input_digest == second.input_digest
    left, right = first.to_dict(), second.to_dict()
    left.pop("created_at"), right.pop("created_at")
    assert json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)

    snapshot = snapshot_dir(tmp_path / "one", root) / f"{first.input_digest}.json"
    before = snapshot.read_bytes()
    ensure_index(root, _config(), tmp_path / "one", created_at="2026-12-01T00:00:00+00:00")
    assert snapshot.read_bytes() == before


def test_idx_03_changed_input_changes_digest_and_retires_old_snapshot(tmp_path):
    root = repository(tmp_path / "repo")
    state = tmp_path / "state"
    first = ensure_index(root, _config(), state, created_at=CREATED)[0]
    old = snapshot_dir(state, root) / f"{first.input_digest}.json"
    assert old.exists() and not is_stale(root, _config(), state)

    issue_path = root / "archive" / "issues" / "2026-10-01" / "issue.json"
    issue = read_json(issue_path)
    issue["items"][0]["core_conclusion"] = "改过的结论。"
    write_json(issue_path, issue)

    assert is_stale(root, _config(), state)
    second, rebuilt = ensure_index(root, _config(), state, created_at=CREATED)
    assert rebuilt and second.input_digest != first.input_digest
    assert not old.exists()
    assert (snapshot_dir(state, root) / f"{second.input_digest}.json").exists()


def test_idx_04_colloquial_questions_reach_the_published_corpus(tmp_path):
    root = discover_root()
    index, _ = ensure_index(root, AssistantConfig.load(root), tmp_path / "state", created_at=CREATED)
    report = evaluate(index, read_json(root / "eval" / "assistant-questions.json"))
    assert report["pass"], report


def test_idx_05_confident_and_uncertain_are_distinguished():
    index = LexicalIndex.build(
        [
            _doc("item:1", "KV cache 分层卸载到内存与 SSD", "把冷 KV 卸载到内存后吞吐提升。"),
            _doc("item:2", "多智能体流水线的分工自动化", "多个智能体分工完成数据工作。"),
        ],
        "digest",
    )
    assert assess(index, "KV cache 放不下显存，能不能分层卸载到内存")["state"] == "confident"
    assert assess(index, "多智能体流水线里上下文超长，有什么压缩办法")["state"] == "uncertain"
    assert assess(index, "今天午饭吃什么")["state"] == "none"


def test_idx_06_ask_only_prints_a_draft(tmp_path, capsys):
    root = repository(tmp_path / "repo")
    state = tmp_path / "state"
    install_assistant()
    assert cli.main(["--root", str(root), "assistant", "--state-dir", str(state), "ask", "KV cache 分层卸载"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "confident"
    assert payload["draft"].startswith("日报库里相关的：")
    assert [path.relative_to(state).parts[0] for path in state.rglob("*.json") if path.is_file()] == ["index"]


def test_idx_07_links_are_generated_from_the_index(tmp_path):
    index, _ = ensure_index(repository(tmp_path), _config(), tmp_path / "state", created_at=CREATED)
    for doc in index.docs:
        assert doc["url"].startswith(SITE)
    assert index.get("item:" + "a" * 24)["url"] == SITE + "#archive?date=2026-10-01&item=" + "a" * 24
    assert index.get("radar:radar-1")["url"] == SITE + "#archive?date=2026-10-01"
    assert index.get("idea:idea_c")["url"] == SITE + "#ideas?idea=idea_c"
    assert index.get("roadmap:storage")["url"] == SITE + "#roadmaps?topic=storage"

    draft = compose_answer(index.search("KV cache 分层卸载", 5))
    assert draft and within_limit(draft)
    assert "https://example.test/site/" in draft
