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


def test_index_names_entries_but_not_bodies() -> None:
    text = Disclosure(make_registry()).index_text()
    assert "tool" in text and "skill" in text and "knowledge" in text
    # 条目名要出现：模型搜不到自己不知道存在的东西
    assert "update_address" in text
    assert "refund-sop" in text
    # 正文不能出现
    assert "超过 3000 元" not in text
    assert "2 小时内" not in text


def test_index_falls_back_to_counts_when_too_many() -> None:
    reg = Registry()
    for i in range(Disclosure.MAX_INLINE + 5):
        reg.add(AssetSpec(id=f"t{i:03d}", kind=AssetKind.TOOL, index=f"动作{i}"))
    text = Disclosure(reg).index_text()
    assert "条目较多" in text
    assert "t000" not in text


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
