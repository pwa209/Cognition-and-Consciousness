from __future__ import annotations

import numpy as np

from factorcon.tmseeg.transitions import state_transition_complexity


def test_state_transition_complexity_is_bounded() -> None:
    baseline = np.ones((4, 20)) * 0.1
    evoked = np.tile([0.0, 1.0] * 10, (4, 1))
    value = state_transition_complexity(evoked, baseline)
    assert 0 <= value <= 1
