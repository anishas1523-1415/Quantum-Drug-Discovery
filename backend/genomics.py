import json
import logging

import requests

from extensions import db
from models import GenomicsCache, utcnow

logger = logging.getLogger("qdd.genomics")

OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"
REQUEST_TIMEOUT = 10
CACHE_TTL_HOURS = 24

# Open Targets reports clinical stage as free-text strings, not an enum.
# Verified against live responses: approved drugs come back as "APPROVAL"
# (not "APPROVED"), and combined-phase trials show up as e.g. "PHASE_2_3".
# Unrecognized values rank lowest rather than erroring.
STAGE_RANK = {
    "APPROVAL": 6,
    "APPROVED": 6,
    "PHASE_4": 6,
    "PHASE_3": 5,
    "PHASE_2_3": 4.5,
    "PHASE_2": 4,
    "PHASE_1_2": 3.5,
    "PHASE_1": 3,
    "PHASE_0": 2,
    "PRECLINICAL": 1,
}

SEARCH_QUERY = """
query($q: String!) {
  search(queryString: $q, entityNames: ["target"]) {
    hits { id name entity }
  }
}
"""

CANDIDATES_QUERY = """
query($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    drugAndClinicalCandidates {
      count
      rows {
        maxClinicalStage
        drug {
          id
          name
          drugType
          description
        }
        diseases {
          diseaseFromSource
          disease { id name }
        }
      }
    }
  }
}
"""


class GenomicsError(Exception):
    pass


def _graphql(query, variables=None):
    try:
        response = requests.post(
            OPEN_TARGETS_URL,
            json={"query": query, "variables": variables or {}},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GenomicsError(f"Could not reach Open Targets: {exc}") from exc

    payload = response.json()

    if payload.get("errors"):
        raise GenomicsError(f"Open Targets query failed: {payload['errors']}")

    return payload["data"]


def resolve_target(gene_symbol):
    """Resolve a gene symbol to its Open Targets (Ensembl) target ID.

    Prefers an exact symbol match; falls back to the top search hit
    since gene search commonly returns related/readthrough genes first.
    """
    data = _graphql(SEARCH_QUERY, {"q": gene_symbol})
    hits = data["search"]["hits"]

    if not hits:
        return None

    exact = next((h for h in hits if h["name"].upper() == gene_symbol.strip().upper()), None)
    return exact or hits[0]


def _fetch_candidates_live(gene_symbol):
    target = resolve_target(gene_symbol)

    if target is None:
        return {"gene": gene_symbol, "target_id": None, "target_name": None, "candidates": []}

    data = _graphql(CANDIDATES_QUERY, {"id": target["id"]})
    target_data = data["target"]

    candidates = []
    for row in target_data["drugAndClinicalCandidates"]["rows"]:
        diseases = [
            (d["disease"]["name"] if d["disease"] else d["diseaseFromSource"])
            for d in row["diseases"]
        ]

        candidates.append({
            "drug_name": row["drug"]["name"],
            "drug_type": row["drug"]["drugType"],
            "description": row["drug"]["description"],
            "stage": row["maxClinicalStage"],
            "diseases": diseases,
        })

    return {
        "gene": gene_symbol,
        "target_id": target["id"],
        "target_name": target_data["approvedSymbol"],
        "candidates": candidates,
    }


def get_candidates_for_gene(gene_symbol):
    """Cache-first lookup of every drug directly targeting this gene."""

    gene_key = gene_symbol.strip().upper()
    cache_key = f"target:{gene_key}"

    cached = GenomicsCache.query.filter_by(cache_key=cache_key).first()

    if cached and cached.is_fresh(CACHE_TTL_HOURS):
        return json.loads(cached.payload)

    result = _fetch_candidates_live(gene_key)
    payload_json = json.dumps(result)

    if cached:
        cached.payload = payload_json
        cached.fetched_at = utcnow()
    else:
        cached = GenomicsCache(cache_key=cache_key, payload=payload_json)
        db.session.add(cached)

    db.session.commit()

    return result


def _stage_rank(stage):
    return STAGE_RANK.get((stage or "").upper(), 0)


def recommend_drugs(gene_symbol, cancer_type):
    """Rank real drug candidates that directly target `gene_symbol` and
    have documented evidence (clinical or approved) against `cancer_type`.

    Returns candidates with zero fabricated data: every entry traces back
    to a live Open Targets record. An empty match list is a real, honest
    outcome for genes (like BRCA1/BRCA2) that don't have direct small
    -molecule targets — see README for why that happens.
    """

    result = get_candidates_for_gene(gene_symbol)
    cancer_term = (cancer_type or "").strip().lower()

    matched = []
    for candidate in result["candidates"]:
        hit = next((d for d in candidate["diseases"] if cancer_term and cancer_term in d.lower()), None)
        if hit:
            matched.append({**candidate, "matched_disease": hit})

    matched.sort(key=lambda c: _stage_rank(c["stage"]), reverse=True)

    return {
        "gene": result["gene"],
        "target_id": result["target_id"],
        "target_name": result["target_name"],
        "cancer_type": cancer_type,
        "total_direct_candidates": len(result["candidates"]),
        "matched_candidates": matched,
        "source": "Open Targets Platform (live)",
    }
