"""Multi-factor candidate scoring: combines every real signal gathered by
the other services into one transparent, weighted, explained score.

No component is fabricated. A signal that doesn't apply to a given
candidate (most commonly: a biologic like an antibody has no small
-molecule structure, so no drug-likeness/ADMET score) is excluded from
the weighted average and reflected honestly in the confidence figure —
never defaulted to zero, which would unfairly penalize legitimate,
real, approved biologic drugs, and never faked to fill the gap.

Weights are a documented, explicit design choice, not hidden constants:
clinical trial/approval evidence is weighted highest because it's the
strongest real-world signal available; potency, drug-likeness, and
ADMET risk are supporting signals from earlier and less certain stages
of the same evidence chain.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from services.drug_target_interaction import DTIError, get_bioactivity
from services.molecular_properties import MolecularPropertiesError, get_molecular_properties
from services.target_identification import STAGE_RANK
from services.toxicity_admet import assess_admet_risk

logger = logging.getLogger("qdd.scoring_engine")

MAX_STAGE_RANK = 6.0  # APPROVAL, see target_identification.STAGE_RANK

WEIGHTS = {
    "clinical_evidence": 0.40,
    "dti_potency": 0.25,
    "drug_likeness": 0.15,
    "admet_safety": 0.20,
}

RISK_BAND_SAFETY_SCORE = {
    "Low": 1.0,
    "Moderate": 0.6,
    "Higher": 0.3,
}


def _potency_score(pchembl_value):
    """Normalize pChEMBL (roughly 4-10 in practice) to 0-1."""
    return max(0.0, min(1.0, (pchembl_value - 4.0) / 6.0))


def _build_explanation(candidate, components, admet_result, dti_result, mol_result):
    parts = []

    if "clinical_evidence" in components:
        stage = candidate.get("stage", "unknown stage")
        disease = candidate.get("matched_disease", "this cancer type")
        parts.append(f"{stage} clinical evidence in {disease}")

    if dti_result and dti_result.get("has_data"):
        best = dti_result["best"]
        parts.append(f"{best['potency_band'].lower()} against {best['target_name']} (pChEMBL {best['pchembl_value']})")

    if mol_result and mol_result.get("has_structure"):
        parts.append(f"QED drug-likeness {mol_result['qed']}")

    if admet_result:
        if admet_result["risk_band"] == "N/A":
            parts.append("biologic — small-molecule ADMET screening not applicable")
        else:
            parts.append(f"{admet_result['risk_band'].lower()} structural risk band")

    return "; ".join(parts) if parts else "Limited real-world data available for this candidate."


def score_candidate(candidate):
    """candidate: one entry from target_identification.recommend_drugs()'s
    matched_candidates list (drug_name, chembl_id, drug_type, stage,
    matched_disease, description)."""

    components = {}
    evidence = {}

    stage_rank = STAGE_RANK.get((candidate.get("stage") or "").upper(), 0)
    components["clinical_evidence"] = stage_rank / MAX_STAGE_RANK
    evidence["clinical_evidence"] = {
        "stage": candidate.get("stage"),
        "matched_disease": candidate.get("matched_disease"),
    }

    dti_result = None
    try:
        dti_result = get_bioactivity(candidate["chembl_id"])
    except DTIError as exc:
        logger.warning("DTI lookup failed for %s: %s", candidate.get("chembl_id"), exc)
        evidence["dti_error"] = str(exc)

    if dti_result and dti_result["has_data"]:
        components["dti_potency"] = _potency_score(dti_result["best"]["pchembl_value"])
        evidence["dti_potency"] = dti_result["best"]

    mol_result = None
    try:
        mol_result = get_molecular_properties(candidate["chembl_id"])
    except MolecularPropertiesError as exc:
        logger.warning("Molecular properties lookup failed for %s: %s", candidate.get("chembl_id"), exc)
        evidence["molecular_properties_error"] = str(exc)

    admet_result = None
    if mol_result is not None:
        admet_result = assess_admet_risk(mol_result)

        if mol_result["has_structure"]:
            components["drug_likeness"] = mol_result["qed"]
            evidence["molecular_properties"] = mol_result["properties"]

            safety_score = RISK_BAND_SAFETY_SCORE.get(admet_result["risk_band"])
            if safety_score is not None:
                components["admet_safety"] = safety_score

        evidence["admet"] = admet_result

    available_weight = sum(WEIGHTS[k] for k in components)

    if available_weight > 0:
        composite = sum(WEIGHTS[k] * components[k] for k in components) / available_weight
    else:
        composite = 0.0

    return {
        "drug_name": candidate["drug_name"],
        "chembl_id": candidate.get("chembl_id"),
        "drug_type": candidate.get("drug_type"),
        "description": candidate.get("description"),
        "composite_score": round(composite * 100, 1),
        # Confidence = fraction of the designed evidence weight actually
        # backed by real data for this candidate — not a model certainty,
        # a data-completeness measure.
        "confidence": round(available_weight, 2),
        "component_scores": {k: round(v, 3) for k, v in components.items()},
        "admet_risk_band": admet_result["risk_band"] if admet_result else "Unknown",
        "evidence": evidence,
        "explanation": _build_explanation(candidate, components, admet_result, dti_result, mol_result),
    }


def score_candidates(candidates, max_workers=4):
    """Score every candidate and return them ranked by composite score
    (highest first). Each candidate is scored independently — a failure
    enriching one candidate (e.g. a transient ChEMBL error) degrades
    only that candidate's confidence, it doesn't fail the whole batch.

    Enrichment is dominated by network round-trips to ChEMBL (2 calls per
    candidate), so candidates are scored concurrently rather than one at
    a time — this is the difference between ~2s and ~15s for a 6
    -candidate batch, with no change in what's actually computed."""

    if not candidates:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        scored = list(executor.map(score_candidate, candidates))

    scored.sort(key=lambda c: c["composite_score"], reverse=True)
    return scored
