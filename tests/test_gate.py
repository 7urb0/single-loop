"""门控：三条上限各管一件事。"""

from __future__ import annotations

from single_loop import Budget, Gate, StopReason


def test_turns_limit() -> None:
    gate = Gate(Budget(max_turns=2))
    assert gate.before_turn() is StopReason.NONE
    gate.enter_turn()
    assert gate.before_turn() is StopReason.NONE
    gate.enter_turn()
    assert gate.before_turn() is StopReason.TURNS


def test_budget_limit() -> None:
    gate = Gate(Budget(max_tokens=100))
    gate.charge(60)
    assert gate.before_turn() is StopReason.NONE
    gate.charge(60)
    assert gate.before_turn() is StopReason.BUDGET


def test_repeat_denial_stops_earlier_than_turns() -> None:
    gate = Gate(Budget(max_turns=100, max_repeat_denials=2))
    gate.note_denial("update_address:{'a':1}")
    assert gate.before_turn() is StopReason.NONE
    gate.note_denial("update_address:{'a':1}")
    assert gate.before_turn() is StopReason.REPEAT_DENIAL
    assert gate.denial_counts["update_address:{'a':1}"] == 2


def test_success_clears_denial() -> None:
    gate = Gate(Budget(max_turns=100, max_repeat_denials=2))
    gate.note_denial("sig")
    gate.note_denial("sig")
    gate.clear_denial("sig")
    assert gate.before_turn() is StopReason.NONE


def test_budget_validates_input() -> None:
    import pytest

    with pytest.raises(ValueError, match="max_turns"):
        Budget(max_turns=0)
    with pytest.raises(ValueError, match="max_tokens"):
        Budget(max_tokens=0)
