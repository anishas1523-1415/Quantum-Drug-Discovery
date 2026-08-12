"""Real quantum optimization (QAOA) for diverse top-candidate panel selection.

Honesty note, read before touching this file: on a classical simulator,
QAOA offers no speed or quality advantage over the exact classical brute
-force search for problems this small (<=8 candidates). It's included
because "quantum optimization of the ranking step" is a named part of
this platform's architecture, and it's a genuine, correctly-formulated
QAOA application — not because it's the fastest way to solve this size
of problem. That distinction matters and should stay visible wherever
this module's output is shown.

THE PROBLEM: given N ranked candidates, select a panel of K that
maximizes total score while penalizing picking multiple candidates of
the same drug_type (redundant mechanism coverage) — a real, small
combinatorial optimization (not just "take the top K by score").

THE METHOD: formulate as a QUBO, convert to an Ising Hamiltonian via the
standard x_i = (1-z_i)/2 substitution, build a QAOA ansatz for that
Hamiltonian with Qiskit, and tune it with a classical optimizer
(COBYLA). The QUBO<->Ising conversion is the highest-risk-of-subtle-bugs
part of this file, so it's validated exhaustively (not just spot
-checked) in tests/services/test_quantum_ranking.py by comparing every
one of the 2^N Ising-Hamiltonian eigenvalues against the same objective
evaluated directly as a plain Python function.
"""

import logging

import numpy as np
from qiskit.circuit.library import qaoa_ansatz
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit.quantum_info import SparsePauliOp
from scipy.optimize import minimize

logger = logging.getLogger("qdd.quantum_ranking")

MAX_CANDIDATES = 8  # qubit count = candidate count; keeps simulation fast
QAOA_REPS = 2
QAOA_RESTARTS = 15  # random re-initializations; single-start COBYLA gets
                     # stuck in bad local optima on this landscape (verified
                     # empirically against brute-force ground truth — 8
                     # restarts was reliable up to n=5, needed 20 at n=7;
                     # 15 is a tested middle ground). This makes a single
                     # call slow (~20-30s at n=7-8) — callers should cache
                     # results per unique input rather than call inline
                     # per request, same pattern as target_identification.
QAOA_MAX_ITER = 300
DIVERSITY_PENALTY = 0.35
COUNT_PENALTY = 0.5


class QuantumRankingError(Exception):
    pass


def _objective(x, scores, same_type_pairs, target_k):
    """The actual thing being optimized, in plain terms — this is the
    ground truth used both for QAOA's target and for the brute-force
    correctness check in tests. If this function is right, everything
    downstream (Ising conversion, QAOA) is judged against it."""

    score_term = sum(scores[i] * x[i] for i in range(len(x)))
    diversity_term = -DIVERSITY_PENALTY * sum(x[i] * x[j] for i, j in same_type_pairs)
    count = sum(x)
    count_term = -COUNT_PENALTY * (count - target_k) ** 2
    return score_term + diversity_term + count_term


def _qubo_to_ising(n, linear, quadratic, constant=0.0):
    """Convert a QUBO objective (to MAXIMIZE) — linear coefficients a_i,
    quadratic coefficients b_ij (i<j), and a fixed constant term — into an
    Ising Hamiltonian (to MINIMIZE) via x_i = (1 - z_i) / 2.

    Returns (h, J, ising_constant) for -objective, i.e. minimizing this
    Hamiltonian (including its constant/identity term) maximizes the
    original objective.
    """

    h = [0.0] * n
    J = {}
    c = constant  # accumulate the constant term picked up by each substitution

    for i, a_i in linear.items():
        h[i] += -a_i / 2
        c += a_i / 2

    for (i, j), b_ij in quadratic.items():
        h[i] += -b_ij / 4
        h[j] += -b_ij / 4
        J[(i, j)] = J.get((i, j), 0.0) + b_ij / 4
        c += b_ij / 4

    # Negate everything: we derived coefficients for maximizing the
    # objective, but QAOA minimizes its cost Hamiltonian.
    h = [-hi for hi in h]
    J = {pair: -val for pair, val in J.items()}
    c = -c

    return h, J, c


def _build_qubo(scores, same_type_pairs, target_k):
    n = len(scores)
    linear = {i: scores[i] for i in range(n)}
    quadratic = {}
    constant = 0.0

    for i, j in same_type_pairs:
        quadratic[(i, j)] = quadratic.get((i, j), 0.0) - DIVERSITY_PENALTY

    # -mu*(count - K)^2 expanded over binary x (x_i^2 = x_i):
    #   -mu*count^2 + 2*mu*K*count - mu*K^2
    #   count^2 = sum_i x_i + 2*sum_{i<j} x_i*x_j
    # so: linear += (-mu + 2*mu*K) ; quadratic(i<j) += -2*mu ; constant += -mu*K^2
    for i in range(n):
        linear[i] = linear.get(i, 0.0) + (-COUNT_PENALTY + 2 * COUNT_PENALTY * target_k)
    for i in range(n):
        for j in range(i + 1, n):
            quadratic[(i, j)] = quadratic.get((i, j), 0.0) + (-2 * COUNT_PENALTY)
    constant += -COUNT_PENALTY * (target_k ** 2)

    return linear, quadratic, constant


def _hamiltonian_from_ising(n, h, J, constant=0.0):
    terms = ["I" * n]
    coeffs = [constant]

    for i, hi in enumerate(h):
        if hi == 0:
            continue
        pauli = ["I"] * n
        pauli[i] = "Z"
        terms.append("".join(reversed(pauli)))
        coeffs.append(hi)

    for (i, j), jij in J.items():
        if jij == 0:
            continue
        pauli = ["I"] * n
        pauli[i] = "Z"
        pauli[j] = "Z"
        terms.append("".join(reversed(pauli)))
        coeffs.append(jij)

    return SparsePauliOp(terms, coeffs)


def _run_qaoa(hamiltonian, n_qubits):
    ansatz = qaoa_ansatz(hamiltonian, reps=QAOA_REPS)
    estimator = StatevectorEstimator()

    def cost_fn(params):
        bound = ansatz.assign_parameters(params)
        result = estimator.run([(bound, hamiltonian)]).result()
        return float(result[0].data.evs)

    # Single-start COBYLA reliably lands in bad local optima on this cost
    # landscape (verified empirically against brute-force ground truth).
    # Multiple random restarts, keeping the best, is the standard fix for
    # variational optimizers and is what actually converges here.
    best_value = float("inf")
    best_params = None

    for restart in range(QAOA_RESTARTS):
        rng = np.random.default_rng(restart)
        initial_params = rng.uniform(0, 2 * np.pi, ansatz.num_parameters)
        result = minimize(cost_fn, initial_params, method="COBYLA", options={"maxiter": QAOA_MAX_ITER})

        if result.fun < best_value:
            best_value = result.fun
            best_params = result.x

    sampler = StatevectorSampler()
    final_circuit = ansatz.assign_parameters(best_params)
    final_circuit.measure_all()
    sample_result = sampler.run([final_circuit], shots=512).result()
    counts = sample_result[0].data.meas.get_counts()

    best_bitstring = max(counts, key=counts.get)
    # Qiskit bit order is little-endian (qubit 0 = rightmost char)
    x = [int(bit) for bit in reversed(best_bitstring)]

    return x, best_value


def _local_search_polish(x, scores, same_type_pairs, target_k):
    """Classical bit-flip hill-climbing from the QAOA solution.

    QAOA is a heuristic — it reliably lands near the optimum but isn't
    guaranteed to hit it exactly (this is expected, documented behavior
    of variational algorithms, not a bug). Polishing the sampled result
    with a cheap classical local search is standard practice in hybrid
    quantum-classical algorithms, and guarantees the final answer is at
    least a local optimum rather than "whatever QAOA happened to sample."
    """

    x = list(x)
    current = _objective(x, scores, same_type_pairs, target_k)
    improved = True

    while improved:
        improved = False
        for i in range(len(x)):
            x[i] = 1 - x[i]
            candidate_value = _objective(x, scores, same_type_pairs, target_k)
            if candidate_value > current:
                current = candidate_value
                improved = True
            else:
                x[i] = 1 - x[i]  # revert

    return x, current


def _brute_force_optimum(n, scores, same_type_pairs, target_k):
    """Exact optimum via exhaustive search — tractable and fast up to
    MAX_CANDIDATES (2^8 = 256 states), used as a correctness safety net.
    See module docstring: QAOA is included for a genuine quantum
    formulation of this step, not because it's needed at this scale."""

    import itertools

    best_x, best_value = None, float("-inf")

    for bits in itertools.product([0, 1], repeat=n):
        x = list(bits)
        value = _objective(x, scores, same_type_pairs, target_k)
        if value > best_value:
            best_value = value
            best_x = x

    return best_x, best_value


def select_diverse_panel(candidates, target_k=3):
    """Given ranked candidates (list of dicts with 'score' in [0,1] and
    'drug_type'), select a diverse top panel of size target_k using QAOA.

    Returns the selected candidates plus the real objective score of the
    selection, and is capped at MAX_CANDIDATES inputs to keep the
    simulation fast — callers should pre-rank and slice before calling.
    """

    if len(candidates) > MAX_CANDIDATES:
        raise QuantumRankingError(
            f"select_diverse_panel accepts at most {MAX_CANDIDATES} candidates "
            f"(got {len(candidates)}) — pre-rank and slice before calling."
        )

    n = len(candidates)

    if n == 0:
        return {"selected_indices": [], "objective_score": 0.0}

    scores = [c["score"] for c in candidates]
    types = [c.get("drug_type") for c in candidates]

    same_type_pairs = [
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if types[i] and types[i] == types[j]
    ]

    target_k = min(target_k, n)

    linear, quadratic, constant = _build_qubo(scores, same_type_pairs, target_k)
    h, J, ising_constant = _qubo_to_ising(n, linear, quadratic, constant)
    hamiltonian = _hamiltonian_from_ising(n, h, J, ising_constant)

    try:
        x_qaoa, _ = _run_qaoa(hamiltonian, n)
    except Exception as exc:
        raise QuantumRankingError(f"QAOA optimization failed: {exc}") from exc

    qaoa_score = _objective(x_qaoa, scores, same_type_pairs, target_k)
    x_polished, polished_score = _local_search_polish(x_qaoa, scores, same_type_pairs, target_k)

    # Exact verification (tractable at this scale — see module docstring).
    # QAOA is a heuristic and won't always land on the global optimum; the
    # final recommendation shown to a doctor should be the best available
    # answer, not "whatever the heuristic happened to find." QAOA's own
    # result is still reported in full for transparency.
    x_optimal, optimal_score = _brute_force_optimum(n, scores, same_type_pairs, target_k)

    x_final, final_score = (
        (x_polished, polished_score) if polished_score >= optimal_score else (x_optimal, optimal_score)
    )

    selected_indices = [i for i, bit in enumerate(x_final) if bit == 1]

    return {
        "selected_indices": selected_indices,
        "objective_score": round(final_score, 4),
        "qaoa_raw_score": round(qaoa_score, 4),
        "qaoa_found_optimum": round(qaoa_score, 6) == round(optimal_score, 6),
        "method": "QAOA (Qiskit statevector simulator), classically verified",
        "caveat": (
            "Quantum optimization at this candidate-list size offers no "
            "speed or quality advantage over exact classical search — "
            "included as a genuine QAOA formulation of the ranking-"
            "selection step, not as a performance claim. QAOA is a "
            "heuristic and doesn't always land on the exact optimum "
            "(reported via qaoa_found_optimum); because exact "
            "verification is cheap at this scale, the final selection "
            "is guaranteed optimal regardless."
        ),
    }
