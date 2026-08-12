import logging
import os
import uuid

import pandas as pd
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from extensions import db, limiter
from genomics import GenomicsError, recommend_drugs
from models import AuditLog
from predict import PredictionError, predict_drug
from preprocessing import preprocess_data
from quantum.quantum_model import QuantumProcessingError, quantum_process
from utils import allowed_file, error_response, token_required

data_bp = Blueprint("data", __name__, url_prefix="/api")
logger = logging.getLogger("qdd.upload")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)


def _cleanup(*paths):
    """Delete working files as soon as we're done with them.

    Patient data has no reason to live on disk longer than the request
    that produced it — the response already contains everything the
    client needs.
    """
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            logger.warning("Failed to remove temp file: %s", path)


def _log_audit(action, detail=None):
    try:
        user_id = getattr(request, "user", {}).get("id")
        db.session.add(AuditLog(user_id=user_id, action=action, detail=detail))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to write audit log for action=%s", action)


@data_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@data_bp.route("/upload", methods=["POST"])
@token_required
@limiter.limit("30 per hour")
def upload():

    if "file" not in request.files:
        return error_response("No file found in the request")

    file = request.files["file"]

    if file.filename == "":
        return error_response("Select a file to upload")

    if not allowed_file(file.filename):
        return error_response("Only .csv files are supported")

    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    output_path = os.path.join(PROCESSED_FOLDER, f"processed_{unique_name}")

    file.save(filepath)

    try:
        # CancerType/GeneticMutation get label-encoded to integers during
        # preprocessing for the ML model's benefit. The frontend needs the
        # original human-readable strings (to display them and to call
        # /api/recommend), so capture them here before that happens.
        raw_lookup = {}
        try:
            raw_df = pd.read_csv(filepath)
            if "PatientID" in raw_df.columns:
                for _, row in raw_df.iterrows():
                    raw_lookup[str(row["PatientID"])] = {
                        "CancerType": None if pd.isna(row.get("CancerType")) else row.get("CancerType"),
                        "GeneticMutation": None if pd.isna(row.get("GeneticMutation")) else row.get("GeneticMutation"),
                    }
        except Exception:
            logger.warning("Could not read raw CancerType/GeneticMutation values")
            raw_lookup = {}

        try:
            df = preprocess_data(filepath)
        except Exception as exc:
            _log_audit("upload_failed", "preprocessing_error")
            return error_response(f"Preprocessing failed: {exc}", 422)

        df.to_csv(output_path, index=False)

        try:
            quantum_df = quantum_process(output_path)
        except QuantumProcessingError as exc:
            _log_audit("upload_failed", "quantum_processing_error")
            return error_response(str(exc), 422)
        except Exception as exc:
            logger.exception("Quantum processing failed")
            _log_audit("upload_failed", "quantum_processing_error")
            return error_response(f"Quantum processing failed: {exc}", 500)

        quantum_preview = quantum_df[["PatientID", "QuantumScore"]].to_dict(orient="records")

        try:
            prediction_df = predict_drug(output_path)
        except PredictionError as exc:
            _log_audit("upload_failed", "prediction_error")
            return error_response(str(exc), 422)
        except Exception as exc:
            logger.exception("Prediction failed")
            _log_audit("upload_failed", "prediction_error")
            return error_response(f"Prediction failed: {exc}", 500)

        prediction_preview = prediction_df.to_dict(orient="records")

        for row in prediction_preview:
            raw = raw_lookup.get(str(row.get("PatientID")))
            if raw:
                if "CancerType" in row:
                    row["CancerType"] = raw["CancerType"]
                if "GeneticMutation" in row:
                    row["GeneticMutation"] = raw["GeneticMutation"]

        _log_audit("upload_success", f"{len(prediction_preview)} patients analyzed")

        return jsonify({
            "message": "Upload, preprocessing, quantum processing and prediction completed",
            "quantum_result": quantum_preview,
            "prediction": prediction_preview,
        })
    finally:
        _cleanup(filepath, output_path)


@data_bp.route("/recommend", methods=["GET"])
@token_required
@limiter.limit("60 per hour")
def recommend():
    gene = (request.args.get("gene") or "").strip()
    cancer_type = (request.args.get("cancer_type") or "").strip()

    if not gene:
        return error_response("A 'gene' query parameter is required")

    if not cancer_type:
        return error_response("A 'cancer_type' query parameter is required")

    try:
        result = recommend_drugs(gene, cancer_type)
    except GenomicsError as exc:
        logger.warning("Genomics lookup failed for gene=%s: %s", gene, exc)
        return error_response(str(exc), 502)

    _log_audit(
        "recommend",
        f"gene={gene} cancer_type={cancer_type} matches={len(result['matched_candidates'])}",
    )

    return jsonify(result)
