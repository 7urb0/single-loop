"""渐进披露：索引常驻、正文按需。

实现了一条容易被忽略的约束：索引本身也占窗口。
所以索引分两级，一级只放类别和数量，二级才是条目。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import Registry
from .spec import AssetKind, AssetSpec


def tokenize(text: str) -> set[str]:
    """粗粒度分词：英文按词，中文按二元组，够用于本地检索。"""
    lowered = text.lower()
    words = set(re.findall(r"[a-z0-9_]+", lowered))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(chunk) == 1:
            words.add(chunk)
        else:
            words.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return words


@dataclass(frozen=True)
class Hit:
    spec: AssetSpec
    score: int


class Disclosure:
    """把「装不下」换成「什么时候装」。"""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self._loaded: set[str] = set()

    def index_text(self) -> str:
        """一级索引：常驻上下文的那一段，只放类别和数量。"""
        counts = self.registry.kinds()
        lines = ["可用资产（先检索再用，正文不会自动进入上下文）："]
        for kind in AssetKind:
            n = counts.get(kind, 0)
            if n:
                lines.append(f"- {kind.value}：{n} 项")
        return "\n".join(lines)

    def catalog_text(self, kind: AssetKind | None = None) -> str:
        """二级索引：条目的 id 加一句话。按需调用，不常驻。"""
        return "\n".join(f"{s.id}：{s.index}" for s in self.registry.all(kind))

    def search(
        self, query: str, kind: AssetKind | None = None, limit: int = 5
    ) -> list[Hit]:
        wanted = tokenize(query)
        if not wanted:
            return []
        hits: list[Hit] = []
        for spec in self.registry.all(kind):
            target = tokenize(spec.index + " " + " ".join(spec.tags) + " " + spec.id)
            score = len(wanted & target)
            if score:
                hits.append(Hit(spec, score))
        hits.sort(key=lambda h: (-h.score, h.spec.id))
        return hits[:limit]

    def load(self, asset_id: str) -> AssetSpec:
        spec = self.registry.get(asset_id)
        if spec is None:
            raise KeyError(f"没有这个资产：{asset_id}")
        self._loaded.add(asset_id)
        return spec

    @property
    def loaded(self) -> set[str]:
        return set(self._loaded)
