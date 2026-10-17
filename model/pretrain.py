"""Curated grammar trajectories for syntax and feasibility pretraining."""

from __future__ import annotations

from core.grammar import ACTION_BY_NAME, PRODUCTIONS, SearchState

from .training import ReplaySample


CURATED_PROGRAMS = (
    # Shell recurrence: floor(n / 2), floor(h / 2)
    (
        "template_recursive",
        "floor", "div", "var_n", "const_2",
        "floor", "div", "var_h", "const_2",
    ),
    # Pratt set: 2^a * 3^b, with bounded enumeration.
    (
        "template_enumerative", "bound_8", "bound_8",
        "mul", "pow", "const_2", "var_a", "pow", "const_3", "var_b",
        "lt", "var_g", "var_n",
    ),
)


def curated_samples(max_nodes: int = 20) -> list[ReplaySample]:
    samples: list[ReplaySample] = []
    for names in CURATED_PROGRAMS:
        state = SearchState(max_nodes=max_nodes)
        for name in names:
            action = ACTION_BY_NAME[name]
            policy = [0.0] * len(PRODUCTIONS)
            policy[action] = 1.0
            samples.append(ReplaySample.from_state(state, policy, value=0.0, feasibility=1.0))
            state = state.apply(action)
        if not state.terminal:
            raise AssertionError("curated program is incomplete")
    return samples
