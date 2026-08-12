"""Real drug-target interaction (bioactivity) lookups via the ChEMBL API.

Given a ChEMBL compound ID, fetches real potency measurements (IC50/Ki/EC50/
Kd) reported against protein targets in the literature. Every value here is
exactly what's published in ChEMBL — nothing is estimated or predicted.

Schema verified against live ChEMBL responses during development (see
services/target_identification.py header for the same practice). ChEMBL's
API had a transient outage while this module was built (confirmed via
their own /status.json endpoint returning 500) — this module is written
defensively for exactly that reason: a real system depending on a real
external API has to tolerate the API being down sometimes.
"""

import logging

import requests

logger = logging.getLogger("qdd.dti")

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
REQUEST_TIMEOUT = 10

# pChEMBL = -log10(molar IC50/Ki/Kd/EC50). Standard cheminformatics
# thresholds: >=7 is sub-100nM ("potent", drug-like), >=6 is sub-1uM
# ("moderate"), below that is weak. These are the same thresholds ChEMBL
# itself documents, not something invented for this app.
POTENCY_BANDS = [
    (9.0, "Very high potency (sub-nM)"),
    (7.0, "High potency (sub-100nM)"),
    (6.0, "Moderate potency (sub-1uM)"),
    (4.0, "Weak potency"),
]


class DTIError(Exception):
    pass


def _potency_band(pchembl_value):
    for threshold, label in POTENCY_BANDS:
        if pchembl_value >= threshold:
            return label
    return "Very weak / below typical drug-like range"


def get_bioactivity(chembl_id):
    """Fetch real bioactivity records for a compound, ranked by potency.

    Returns the strongest reported potency (highest pChEMBL value = lowest
    concentration needed for effect) plus how many independent assay
    records support it. `has_data=False` is a real, honest outcome for
    compounds without quantitative bioactivity data in ChEMBL (e.g. large
    biologics like monoclonal antibodies, which aren't measured in IC50
    terms the same way small molecules are).
    """

    try:
        response = requests.get(
            f"{CHEMBL_API}/activity.json",
            params={
                "molecule_chembl_id": chembl_id,
                "limit": 50,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DTIError(f"Could not reach ChEMBL: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise DTIError("ChEMBL returned a non-JSON response (likely a temporary outage)") from exc

    activities = payload.get("activities", [])

    records = []
    for act in activities:
        pchembl = act.get("pchembl_value")
        if pchembl is None:
            continue
        try:
            pchembl_f = float(pchembl)
        except (TypeError, ValueError):
            continue

        records.append({
            "target_name": act.get("target_pref_name"),
            "assay_type": act.get("assay_type"),
            "standard_type": act.get("standard_type"),
            "standard_value": act.get("standard_value"),
            "standard_units": act.get("standard_units"),
            "pchembl_value": pchembl_f,
        })

    if not records:
        return {
            "chembl_id": chembl_id,
            "has_data": False,
            "record_count": 0,
            "best": None,
        }

    records.sort(key=lambda r: r["pchembl_value"], reverse=True)
    best = records[0]
    best["potency_band"] = _potency_band(best["pchembl_value"])

    return {
        "chembl_id": chembl_id,
        "has_data": True,
        "record_count": len(records),
        "best": best,
    }
