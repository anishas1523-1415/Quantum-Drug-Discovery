"""Full pipeline orchestration: target identification -> multi-factor
scoring -> quantum-optimized diverse panel selection.

This is the "hospital-grade report" endpoint — it chains every service
module together and returns one coherent, explainable result. Results
are cached per (gene, cancer_type) because the quantum ranking step
alone takes 20-30+ seconds; a doctor re-checking the same patient, or a
second patient sharing a gene, should get an instant cached response
rather than re-paying that cost every time.
"""

import json
import logging

from flask import Blueprint, Response, jsonify, request

from extensions import db, limiter
from models import GenomicsCache, utcnow
from services.quantum_ranking import QuantumRankingError, select_diverse_panel
from services.report_generator import generate_pdf_report
from services.scoring_engine import score_candidates
from services.target_identification import GenomicsError, recommend_drugs
from utils import error_response, token_required

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api")
logger = logging.getLogger("qdd.analyze")

CACHE_TTL_HOURS = 24
# Bump alongside changes to _run_pipeline()'s return shape — see the same
# pattern (and the bug it prevents) in services/target_identification.py.
CACHE_SCHEMA_VERSION = 2
# Capped for live API-call volume (2 ChEMBL calls per candidate) and to
# stay comfortably inside quantum_ranking's fast-converging range.
CANDIDATE_POOL_SIZE = 6
DIVERSE_PANEL_SIZE = 3


def _run_pipeline(gene, cancer_type):
    base = recommend_drugs(gene, cancer_type)
    top_candidates = base["matched_candidates"][:CANDIDATE_POOL_SIZE]

    if not top_candidates:
        return {
            "gene": base["gene"],
            "target_id": base["target_id"],
            "target_name": base["target_name"],
            "cancer_type": cancer_type,
            "total_direct_candidates": base["total_direct_candidates"],
            "candidates": [],
            "diverse_panel": [],
            "quantum_optimization": None,
            "message": (
                f"No drugs directly targeting {base['target_name'] or gene} have "
                f"documented evidence in {cancer_type} right now."
            ),
        }

    scored = score_candidates(top_candidates, gene=gene, cancer_type=cancer_type)

    quantum_input = [
        {"score": c["composite_score"] / 100.0, "drug_type": c["drug_type"]}
        for c in scored
    ]

    quantum_result = None
    try:
        quantum_result = select_diverse_panel(quantum_input, target_k=min(DIVERSE_PANEL_SIZE, len(scored)))
    except QuantumRankingError as exc:
        logger.warning("Quantum ranking failed, falling back to top-N by score: %s", exc)

    if quantum_result:
        diverse_panel = [scored[i] for i in quantum_result["selected_indices"]]
    else:
        diverse_panel = scored[:DIVERSE_PANEL_SIZE]

    return {
        "gene": base["gene"],
        "target_id": base["target_id"],
        "target_name": base["target_name"],
        "cancer_type": cancer_type,
        "total_direct_candidates": base["total_direct_candidates"],
        "candidates": scored,
        "diverse_panel": diverse_panel,
        "quantum_optimization": quantum_result,
        "source": "Open Targets + ChEMBL (live), RDKit (computed locally)",
    }


def _get_or_compute(gene, cancer_type):
    """Cache-first pipeline result, shared by the JSON and PDF endpoints
    so exporting a report never re-runs the (slow) live pipeline if a
    fresh cached result already exists."""

    cache_key = f"analyze:v{CACHE_SCHEMA_VERSION}:{gene.upper()}:{cancer_type.lower()}"
    cached = GenomicsCache.query.filter_by(cache_key=cache_key).first()

    if cached and cached.is_fresh(CACHE_TTL_HOURS):
        return json.loads(cached.payload)

    result = _run_pipeline(gene, cancer_type)
    payload_json = json.dumps(result)

    if cached:
        cached.payload = payload_json
        cached.fetched_at = utcnow()
    else:
        cached = GenomicsCache(cache_key=cache_key, payload=payload_json)
        db.session.add(cached)

    db.session.commit()

    return result


def _parse_gene_and_cancer_type():
    gene = (request.args.get("gene") or "").strip()
    cancer_type = (request.args.get("cancer_type") or "").strip()

    if not gene:
        return None, None, error_response("A 'gene' query parameter is required")

    if not cancer_type:
        return None, None, error_response("A 'cancer_type' query parameter is required")

    return gene, cancer_type, None


@analyze_bp.route("/analyze", methods=["GET"])
@token_required
@limiter.limit("20 per hour")
def analyze():
    gene, cancer_type, error = _parse_gene_and_cancer_type()
    if error:
        return error

    try:
        result = _get_or_compute(gene, cancer_type)
    except GenomicsError as exc:
        logger.warning("Pipeline failed for gene=%s: %s", gene, exc)
        return error_response(str(exc), 502)

    return jsonify(result)


@analyze_bp.route("/analyze/report", methods=["GET"])
@token_required
@limiter.limit("15 per hour")
def analyze_report():
    gene, cancer_type, error = _parse_gene_and_cancer_type()
    if error:
        return error

    try:
        result = _get_or_compute(gene, cancer_type)
    except GenomicsError as exc:
        logger.warning("Pipeline failed for gene=%s: %s", gene, exc)
        return error_response(str(exc), 502)

    pdf_bytes = generate_pdf_report(result, requested_by=request.user)

    filename = f"qdd-report-{gene.upper()}-{cancer_type.lower()}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
