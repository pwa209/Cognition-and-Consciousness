from __future__ import annotations

from factorcon.simulation import recover_architecture


def test_recovery_is_bitwise_deterministic_for_fixed_seed() -> None:
    first = recover_architecture("M4", seed=1776)
    second = recover_architecture("M4", seed=1776)
    assert first == second

