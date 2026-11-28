"""Deterministic lexical retrieval over the published corpus.

English is tokenized by word and Chinese by character bigram, so mixed queries
such as ``KV cache 卸载`` match without a segmentation dependency. Scoring is
BM25 over a derived snapshot: the same inputs always rebuild the same content
under the same input digest.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from ..utils import write_json_atomic
from .config import AssistantConfig, default_state_dir
from .corpus import input_digest, load_corpus

WORD = re.compile(r"[a-z0-9]+")
CJK_RUN = re.compile(r"[\u3400-\u9fff]+")

# Removed as whole words before Chinese runs are cut into bigrams, so that
# ``请问有没有`` does not leave stray fragments such as ``问有`` behind. Only
# function and question words belong here; content words stay indexable.
CJK_WORD_STOPWORDS = (
    "请问 有没有 是不是 能不能 可不可以 什么 为什么 怎么 怎样 到底 有用 我们 大家 一个 这个 那个 这些 那些 "
    "时候 的时候 如果 但是 因为 所以 然后 之前 之后 以后 哪些 哪里 如何 有人 做过 没有 谢谢 求助 靠谱 "
    "非常 比较 觉得 认为 应该 可能 需要 还是 或者 其实 当然 不过 而且 因此 可是 然而 就是 也是 都是 "
    "这样 那样 只是 帮忙 大佬 各位 同学 老师 一下 一些 很多 看看 讲讲 说说 聊聊 知道 听说 见过 请教 "
    "想问 参考一下 相关的 类似的 差不多 靠不靠谱 好不好 有没有用 值不值得 关于 论文 文章 报道 "
).split()

STOPWORDS = frozenset(
    """
    a an the of to in on for and or nor is are was were be been being with by at from as
    that this these those it its we you they he she i me my our your their them there here
    how what why when which who whom whose can could should would shall will may might must
    do does did done have has had any some no not about into via vs use using used new paper
    papers arxiv
    我们 你们 他们 大家 一个 这个 那个 这些 那些 什么 怎么 怎样 为什 可以 不是
    能不 不能 有没 请问 一下 一些 很多 非常 比较 觉得 认为 应该 可能 需要 还是 或者
    如果 但是 因为 所以 然后 现在 之前 之后 以后 时候 关于 相关 有关 论文 文章 报道
    东西 问题 情况 方面 进行 如何 哪些 哪里 到底 有人 做过 看看 知道 想问 求助 各位
    同学 老师 大佬 谢谢 帮忙 推荐 介绍 讲了 讲讲 说说 聊聊 提到 提过 见过 听说 靠谱
    有用 好用 适合 值得 看过 找到 找过 类似 差不 这样 那样 一般 目前 最近 已经 还有
    只是 就是 也是 都是 其实 确实 当然 不过 而且 并且 因此 于是 可是 然而
    的事 的话 来的 去的 的是 的时
    """.split()
)

# Calibrated against eval/assistant-questions.json. Strength is the share of the
# question's total term weight that a document matches, so it does not depend on
# corpus size the way a raw BM25 score does.
MIN_STRENGTH = 0.1
CONFIDENT_STRENGTH = 0.5
CONFIDENT_COVERAGE = 0.45
CONFIDENT_UNITS = 2

K1 = 1.5
B = 0.75
# A non-capturing group: re.split would otherwise return the stopwords as pieces.
_WORD_BOUNDARY = re.compile("(?:" + "|".join(map(re.escape, sorted(CJK_WORD_STOPWORDS, key=len, reverse=True))) + ")")


def _pieces(run: str) -> list[str]:
    return [piece for piece in _WORD_BOUNDARY.split(run) if len(piece) >= 2]


def _units(text: str) -> list[tuple[str, int, int]]:
    units = [(match.group(), match.start(), match.end()) for match in WORD.finditer(text.lower())]
    for run in CJK_RUN.finditer(text):
        for piece in _pieces(run.group()):
            start = run.start() + run.group().index(piece)
            for offset in range(len(piece) - 1):
                units.append((piece[offset : offset + 2], start + offset, start + offset + 2))
    return units


def tokenize(text: str) -> list[str]:
    return [token for token, _, _ in _units(text) if len(token) > 1 and token not in STOPWORDS]


def coverage(query: str, doc_tokens: set[str]) -> tuple[float, int]:
    """How much of the question's content one document accounts for.

    Returns the covered fraction and the number of distinct content units that
    matched. Each English word is one unit; a Chinese piece counts by the
    characters its matched bigrams touch. Stopwords count neither way.
    """

    total = covered = 0.0
    units = 0
    for match in WORD.finditer(query.lower()):
        if len(match.group()) > 1 and match.group() not in STOPWORDS:
            total += 1.0
            if match.group() in doc_tokens:
                covered += 1.0
                units += 1
    for run in CJK_RUN.finditer(query):
        for piece in _pieces(run.group()):
            matched = [False] * len(piece)
            for offset in range(len(piece) - 1):
                token = piece[offset : offset + 2]
                if token not in STOPWORDS and token in doc_tokens:
                    matched[offset] = matched[offset + 1] = True
                    units += 1
            total += len(piece) / 2
            covered += sum(matched) / 2
    return (covered / total if total else 0.0), units


class LexicalIndex:
    def __init__(
        self,
        docs: list[dict[str, Any]],
        postings: dict[str, list[list[int]]],
        lengths: list[int],
        input_digest: str,
        created_at: str | None = None,
    ) -> None:
        self.docs = docs
        self.by_id = {doc["id"]: index for index, doc in enumerate(docs)}
        self.postings = postings
        self.lengths = lengths
        self.n = len(docs)
        self.avgdl = (sum(lengths) / len(lengths)) if lengths else 0.0
        self.input_digest = input_digest
        self.created_at = created_at
        self._token_cache: dict[int, set[str]] = {}

    @classmethod
    def build(cls, docs: list[dict[str, Any]], digest: str, created_at: str | None = None) -> "LexicalIndex":
        counts: list[dict[str, int]] = []
        postings: dict[str, list[list[int]]] = {}
        lengths: list[int] = []
        for index, doc in enumerate(docs):
            counter: dict[str, int] = {}
            for token in tokenize(doc["search"]):
                counter[token] = counter.get(token, 0) + 1
            counts.append(counter)
            lengths.append(sum(counter.values()))
        for index, counter in enumerate(counts):
            for token in sorted(counter):
                postings.setdefault(token, []).append([index, counter[token]])
        return cls(docs, postings, lengths, digest, created_at)

    def idf(self, token: str) -> float:
        return math.log(1 + (self.n - len(self.postings[token]) + 0.5) / (len(self.postings[token]) + 0.5))

    def tokens_of(self, doc_index: int) -> set[str]:
        tokens = self._token_cache.get(doc_index)
        if tokens is None:
            tokens = set(tokenize(self.docs[doc_index]["search"]))
            self._token_cache[doc_index] = tokens
        return tokens

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        tokens = sorted(set(tokenize(query)))
        scores: dict[int, float] = {}
        for token in tokens:
            entries = self.postings.get(token)
            if not entries:
                continue
            idf = self.idf(token)
            for index, frequency in entries:
                norm = K1 * (1 - B + B * self.lengths[index] / self.avgdl) if self.avgdl else K1
                scores[index] = scores.get(index, 0.0) + idf * frequency * (K1 + 1) / (frequency + norm)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return [
            {"doc": self.docs[index], "doc_index": index, "score": score, "strength": self._strength(tokens, index)}
            for index, score in ranked
        ]

    def _strength(self, tokens: list[str], doc_index: int) -> float:
        """Share of the question's known term weight that this document matches."""

        known = [token for token in tokens if token in self.postings]
        total = sum(self.idf(token) for token in known)
        if not total:
            return 0.0
        matched = 0.0
        for token in known:
            frequency = next((entry[1] for entry in self.postings[token] if entry[0] == doc_index), 0)
            if frequency:
                matched += self.idf(token) * frequency * (K1 + 1) / (frequency + K1)
        return matched / total

    def get(self, doc_id: str) -> dict[str, Any] | None:
        index = self.by_id.get(doc_id)
        return self.docs[index] if index is not None else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "input_digest": self.input_digest,
            "created_at": self.created_at,
            "docs": self.docs,
            "postings": {token: self.postings[token] for token in sorted(self.postings)},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LexicalIndex":
        postings = {token: [list(entry) for entry in entries] for token, entries in data["postings"].items()}
        lengths = [0] * len(data["docs"])
        for entries in postings.values():
            for index, frequency in entries:
                lengths[index] += frequency
        return cls(data["docs"], postings, lengths, data["input_digest"], data.get("created_at"))


def assess(index: LexicalIndex, query: str, limit: int = 20) -> dict[str, Any]:
    """Search and judge whether the best hit is confident enough to answer directly."""

    hits = index.search(query, limit)
    best = hits[0] if hits else None
    strength = best["strength"] if best else 0.0
    explained, units = coverage(query, index.tokens_of(best["doc_index"])) if best else (0.0, 0)
    confident = strength >= CONFIDENT_STRENGTH and explained >= CONFIDENT_COVERAGE and units >= CONFIDENT_UNITS
    if strength < MIN_STRENGTH:
        state = "none"
    elif confident:
        state = "confident"
    else:
        state = "uncertain"
    return {"hits": hits, "state": state, "top_strength": strength, "top_score": best["score"] if best else 0.0, "top_coverage": explained, "top_units": units}


# A discussion is answered best by a concrete published item or idea. A
# judgement is long and general, a radar entry is a bare title, and both match
# many a message on common words; they are kept but rank below.
DISCUSSION_KIND_WEIGHTS = {"item": 1.0, "idea": 1.0, "roadmap": 0.8, "radar": 0.7, "judgement": 0.5}


def search_discussion(index: LexicalIndex, messages: list[str], limit: int) -> list[dict[str, Any]]:
    """Search for a discussion: each message on its own, then fuse the rankings.

    A discussion read as one block buries the words that matter under the rest
    of its sentences. Each message is searched alone and the rankings are fused
    by reciprocal rank, so one message carrying the right words is enough.
    """

    scores: dict[int, float] = {}
    found_by: dict[int, int] = {}
    texts = messages[-6:]
    for text in texts:
        for rank, hit in enumerate(index.search(text, limit * 2), start=1):
            scores[hit["doc_index"]] = scores.get(hit["doc_index"], 0.0) + 1.0 / (60 + rank)
            found_by[hit["doc_index"]] = found_by.get(hit["doc_index"], 0) + 1
    weighted = [
        (doc_index, score * DISCUSSION_KIND_WEIGHTS.get(index.docs[doc_index]["kind"], 1.0))
        for doc_index, score in scores.items()
    ]
    ranked = sorted(weighted, key=lambda item: (-item[1], item[0]))[:limit]
    return [
        {"doc": index.docs[doc_index], "doc_index": doc_index, "score": round(score, 4), "strength": found_by[doc_index] / len(texts)}
        for doc_index, score in ranked
    ]


def snapshot_dir(state_dir: Path | None, root: Path) -> Path:
    return (state_dir or default_state_dir(root)) / "index"


def _load_inputs(root: Path, config: AssistantConfig) -> tuple[list[dict[str, Any]], str]:
    docs, inputs = load_corpus(root, config.site_base_url)
    return docs, input_digest(root, inputs, config.site_base_url)


def ensure_index(
    root: Path,
    config: AssistantConfig,
    state_dir: Path | None = None,
    created_at: str | None = None,
) -> tuple[LexicalIndex, bool]:
    """Load the snapshot for the current inputs, rebuilding only when it is stale."""

    docs, digest = _load_inputs(root, config)
    directory = snapshot_dir(state_dir, root)
    path = directory / f"{digest}.json"
    if path.exists():
        return LexicalIndex.from_dict(json.loads(path.read_text(encoding="utf-8"))), False
    index = LexicalIndex.build(docs, digest, created_at)
    write_json_atomic(path, index.to_dict())
    for old in directory.glob("*.json"):
        if old != path:
            old.unlink()
    return index, True


def is_stale(root: Path, config: AssistantConfig, state_dir: Path | None = None) -> bool:
    """True when the stored snapshot no longer matches the published inputs."""

    _, digest = _load_inputs(root, config)
    return not (snapshot_dir(state_dir, root) / f"{digest}.json").exists()
