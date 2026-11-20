"""渐进披露：索引常驻、正文按需。"""

from __future__ import annotations

from single_loop import AssetKind, AssetSpec, Disclosure, Registry


def make_registry() -> Registry:
    reg = Registry()
    reg.add(
        AssetSpec(
            id="update_address",
            kind=AssetKind.TOOL,
            index="修改订单送货地址",
            body='{"name":"update_address"}',
        )
    )
    reg.add(
        AssetSpec(
            id="refund-sop",
            kind=AssetKind.SKILL,
            index="退款审批流程与判断标准",
            body="1. 核对订单 2. 判断金额是否超过阈值 3. 超阈值走财务审批",
        )
    )
    reg.add(
        AssetSpec(
            id="sla-policy",
            kind=AssetKind.KNOWLEDGE,
            index="客服首次回复时效要求",
            body="首次回复须在 2 小时内给出预计时效",
        )
    )
    return reg


def test_index_only_shows_kinds() -> None:
    text = Disclosure(make_registry()).index_text()
    assert "tool" in text and "skill" in text and "knowledge" in text
    # 索引不含正文，也不含条目 id
    assert "update_address" not in text
    assert "退款审批" not in text


def test_search_hits_skill_by_chinese_bigram() -> None:
    d = Disclosure(make_registry())
    hits = d.search("退款怎么审批")
    assert hits
    assert hits[0].spec.id == "refund-sop"


def test_search_can_filter_by_kind() -> None:
    d = Disclosure(make_registry())
    hits = d.search("时效", kind=AssetKind.KNOWLEDGE)
    assert [h.spec.id for h in hits] == ["sla-policy"]


def test_search_returns_empty_for_unknown() -> None:
    d = Disclosure(make_registry())
    assert d.search("量子计算") == []


def test_load_marks_loaded() -> None:
    d = Disclosure(make_registry())
    spec = d.load("update_address")
    assert spec.kind is AssetKind.TOOL
    assert d.loaded == {"update_address"}


def test_load_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError, match="没有这个资产"):
        Disclosure(make_registry()).load("nope")
