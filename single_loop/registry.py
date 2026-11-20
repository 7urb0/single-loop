"""资产注册表。

只存元数据，不存可执行函数。可执行函数归运行时管，
因为技能和知识没有函数，混在一起会让类型变脏。
"""

from __future__ import annotations

from .spec import AssetKind, AssetSpec, InvariantError


class Registry:
    def __init__(self) -> None:
        self._items: dict[str, AssetSpec] = {}

    def add(self, spec: AssetSpec) -> None:
        if spec.id in self._items:
            raise InvariantError(f"资产 id 重复：{spec.id}")
        self._items[spec.id] = spec

    def get(self, asset_id: str) -> AssetSpec | None:
        return self._items.get(asset_id)

    def all(self, kind: AssetKind | None = None) -> list[AssetSpec]:
        items = list(self._items.values())
        if kind is not None:
            items = [s for s in items if s.kind is kind]
        return items

    def kinds(self) -> dict[AssetKind, int]:
        counts = {k: 0 for k in AssetKind}
        for spec in self._items.values():
            counts[spec.kind] += 1
        return counts

    def __len__(self) -> int:
        return len(self._items)
