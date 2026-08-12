"""Tests for the QAOA-based diverse panel selection.

The most important test here is test_ising_hamiltonian_matches_objective_exhaustively:
this caught two real bugs during development (a missing constant term in
the QUBO->Ising conversion, and an unreliable single-restart optimizer)
that a superficial "does it run without crashing" test would have
completely missed. Keep this test — it's the correctness guarantee for
the whole module.
"""

import itertools

import pytest

from services.quantum_ranking import (
    MAX_CANDIDATES,
    QuantumRankingError,
    _build_qubo,
    _hamiltonian_from_ising,
    _objective,
    _qubo_to_ising,
    select_diverse_panel,
)


@pytest.mark.parametrize(
    "scores,same_type_pairs,target_k",
    [
        ([0.9, 0.6, 0.8, 0.3, 0.7], [(0, 2), (1, 4)], 3),
        ([0.1, 0.9, 0.5, 0.2], [(0, 1), (2, 3)], 2),
        ([0.9, 0.9, 0.9, 0.9, 0.9, 0.9], [], 3),
        ([0.5], [], 1),
        ([0.3, 0.7], [(0, 1)], 1),
    ],
)
def test_ising_hamiltonian_matches_objective_exhaustively(scores, same_type_pairs, target_k):
    """For every possible bitstring, the Ising Hamiltonian's exact
    eigenvalue must equal -objective(x). This is checked exhaustively
    (all 2^n states), not sampled, because the earlier bug (missing
    constant term) produced a *uniform* offset error that a handful of
    spot-checks would not have revealed as clearly as an exhaustive scan."""

    from qiskit.quantum_info import Statevector

    n = len(scores)
    linear, quadratic, constant = _build_qubo(scores, same_type_pairs, target_k)
    h, J, ising_constant = _qubo_to_ising(n, linear, quadratic, constant)
    hamiltonian = _hamiltonian_from_ising(n, h, J, ising_constant)

    for bits in itertools.product([0, 1], repeat=n):
        x = list(bits)
        obj = _objective(x, scores, same_type_pairs, target_k)

        bitstring = "".join(str(b) for b in reversed(x))
        statevector = Statevector.from_label(bitstring)
        energy = statevector.expectation_value(hamiltonian).real

        assert energy == pytest.approx(-obj, abs=1e-9), f"mismatch at x={x}"


def test_rejects_more_than_max_candidates():
    candidates = [{"score": 0.5, "drug_type": "Small molecule"} for _ in range(MAX_CANDIDATES + 1)]

    with pytest.raises(QuantumRankingError):
        select_diverse_panel(candidates)


def test_handles_empty_candidate_list():
    result = select_diverse_panel([])

    assert result["selected_indices"] == []
    assert result["objective_score"] == 0.0


@pytest.mark.slow
def test_final_selection_is_always_at_least_as_good_as_exhaustive_search():
    """The end-to-end guarantee: regardless of whether QAOA itself finds
    the true optimum, the *final* selection returned to callers must
    match the true optimum, because exact verification is cheap at this
    scale and is used as a safety net (see select_diverse_panel)."""

    scores = [0.95, 0.2, 0.85, 0.3, 0.8, 0.15, 0.9]
    # 0, 2, 4, 6 are a fully-connected "same type" clique (every pair among
    # them appears); 1, 3, 5 are each their own distinct type.
    same_type_pairs = [(0, 2), (0, 4), (2, 4), (0, 6), (2, 6), (4, 6)]
    target_k = 3
    n = len(scores)
    clique = {0, 2, 4, 6}

    candidates = []
    for i, s in enumerate(scores):
        drug_type = "clique" if i in clique else f"solo_{i}"
        candidates.append({"score": s, "drug_type": drug_type})

    true_optimum = max(
        _objective(list(bits), scores, same_type_pairs, target_k)
        for bits in itertools.product([0, 1], repeat=n)
    )

    result = select_diverse_panel(candidates, target_k=target_k)

    assert result["objective_score"] == pytest.approx(true_optimum, abs=1e-6)
