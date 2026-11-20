"""验收：形式检查与语义验证的分工。"""

from __future__ import annotations

from single_loop import BlocklistVerifier, CheckResult, DefaultFormalVerifier, Verdict


def test_empty_answer_fails() -> None:
    assert DefaultFormalVerifier().check("", {}).verdict is Verdict.FAIL
    assert DefaultFormalVerifier().check("   ", {}).verdict is Verdict.FAIL


def test_unclosed_code_block_fails() -> None:
    result = DefaultFormalVerifier().check("看代码：\n```python\nprint(1)\n", {})
    assert result.verdict is Verdict.FAIL
    assert "代码块" in result.detail


def test_normal_answer_passes() -> None:
    result = DefaultFormalVerifier().check("答案：订单已改地址。", {})
    assert result.verdict is Verdict.PASS


def test_blocklist_catches_forbidden_literal() -> None:
    verifier = BlocklistVerifier(["999.99"])
    hit = verifier.check("股价是 999.99 元", {})
    assert hit.verdict is Verdict.FAIL
    assert "999.99" in hit.detail

    clean = verifier.check("股价数据源不可用", {})
    assert clean.verdict is Verdict.PASS


def test_check_result_passed_property() -> None:
    assert CheckResult(Verdict.PASS).passed is True
    assert CheckResult(Verdict.FAIL, "缺参数").passed is False
