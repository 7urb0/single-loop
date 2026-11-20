"""四条架构不变式。"""

from __future__ import annotations

import pytest

from single_loop import AssetKind, AssetSpec, InvariantError, Registry, assert_kinds_closed


def test_asset_requires_index() -> None:
    with pytest.raises(InvariantError, match="常驻索引"):
        AssetSpec(id="x", kind=AssetKind.TOOL, index="   ")


def test_asset_index_must_stay_short() -> None:
    with pytest.raises(InvariantError, match="挤占窗口"):
        AssetSpec(id="x", kind=AssetKind.TOOL, index="很长" * 100)


def test_code_asset_needs_body() -> None:
    with pytest.raises(InvariantError, match="必须有正文"):
        AssetSpec(id="x", kind=AssetKind.CODE, index="实体解析")


def test_registry_rejects_duplicate_id() -> None:
    reg = Registry()
    reg.add(AssetSpec(id="a", kind=AssetKind.SKILL, index="流程"))
    with pytest.raises(InvariantError, match="id 重复"):
        reg.add(AssetSpec(id="a", kind=AssetKind.SKILL, index="另一个"))


def test_kinds_are_closed() -> None:
    good = [AssetSpec(id="a", kind=AssetKind.TOOL, index="动作")]
    assert_kinds_closed(good)

    bad = AssetSpec(id="b", kind="tool", index="伪装成工具")  # type: ignore[arg-type]
    with pytest.raises(InvariantError, match="不在四类之内"):
        assert_kinds_closed([bad])


def test_registry_counts_by_kind() -> None:
    reg = Registry()
    reg.add(AssetSpec(id="t1", kind=AssetKind.TOOL, index="动作一"))
    reg.add(AssetSpec(id="t2", kind=AssetKind.TOOL, index="动作二"))
    reg.add(AssetSpec(id="s1", kind=AssetKind.SKILL, index="流程一"))
    counts = reg.kinds()
    assert counts[AssetKind.TOOL] == 2
    assert counts[AssetKind.SKILL] == 1
    assert counts[AssetKind.KNOWLEDGE] == 0
