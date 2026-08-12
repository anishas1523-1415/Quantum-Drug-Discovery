"""Live inference for the real, GDSC2-trained drug-effectiveness model.

The model (backend/trained_models/effectiveness_model.pkl) was trained
offline on real cell-line drug-sensitivity measurements — see
ml/train_effectiveness_model.py for the full methodology and
backend/trained_models/effectiveness_model_meta.json for its
cross-validated performance. This module only does inference: it builds
the exact same feature vector the model was trained on
(ml/features.py) from a live analysis request, and reports the model's
own cross-validated accuracy as this prediction's confidence — never a
fabricated certainty.

Honest scope limits, by design:
- Only applies to small molecules with a resolvable structure. The
  training data (GDSC2) is a small-molecule cell-viability screen; a
  model trained on that has no basis for predicting antibody/biologic
  response, so this is skipped for those rather than guessed.
- The training data has no patient age/tumor-stage fields (GDSC2 is
  cell-line data), and /api/analyze doesn't collect those either, so
  this signal is driven by cancer type, the analyzed driver gene, and
  the candidate drug's real molecular structure — not fabricated
  patient demographics.
"""

import json
import logging
import os

import joblib
import pandas as pd

from ml.features import FEATURE_COLUMNS, build_feature_row

logger = logging.getLogger("qdd.effectiveness_predictor")

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "effectiveness_model.pkl")
META_PATH = os.path.join(ARTIFACT_DIR, "effectiveness_model_meta.json")

_model = None
_meta = None
_load_attempted = False


class EffectivenessModelError(Exception):
    pass


def _load():
    global _model, _meta, _load_attempted

    if _load_attempted:
        return

    _load_attempted = True

    if not os.path.exists(MODEL_PATH) or not os.path.exists(META_PATH):
        logger.warning("Effectiveness model artifact not found at %s — ML scoring will be skipped", MODEL_PATH)
        return

    _model = joblib.load(MODEL_PATH)
    with open(META_PATH, encoding="utf-8") as f:
        _meta = json.load(f)

    logger.info(
        "Loaded effectiveness model '%s' (held-out test ROC-AUC=%.3f, trained %s)",
        _meta["model_name"], _meta["held_out_test"]["roc_auc"], _meta["trained_at"],
    )


def model_available():
    _load()
    return _model is not None


def model_metadata():
    _load()
    return _meta


def predict_effectiveness(gene, cancer_type, mol_result):
    """Predict effectiveness for one candidate against the analyzed gene
    and cancer type, given the candidate's already-fetched molecular
    properties (from services.molecular_properties.get_molecular_properties
    — reused here rather than re-fetched, since scoring_engine already
    computes it for the drug-likeness/ADMET components).

    Returns {"applicable": False, "reason": ...} when the model has no
    honest basis for a prediction (no trained model, or no real
    small-molecule structure for this candidate).
    """
    _load()

    if _model is None:
        return {"applicable": False, "reason": "No trained effectiveness model is available on this server"}

    if not mol_result or not mol_result.get("has_structure"):
        return {
            "applicable": False,
            "reason": "This model was trained on small-molecule structures only; this candidate has none "
                       "(e.g. a biologic/antibody), so no honest prediction can be made",
        }

    descriptors = dict(mol_result["properties"])
    descriptors["qed"] = mol_result["qed"]

    gene_upper = (gene or "").strip().upper()
    row = build_feature_row(
        cancer_type_text=cancer_type,
        mutated_genes={gene_upper} if gene_upper else set(),
        target_genes={gene_upper} if gene_upper else set(),
        descriptors=descriptors,
    )

    X = pd.DataFrame([row], columns=FEATURE_COLUMNS)
    probability_sensitive = float(_model.predict_proba(X)[0, 1])

    return {
        "applicable": True,
        "probability_sensitive": round(probability_sensitive, 3),
        "predicted_label": "Likely Sensitive" if probability_sensitive >= 0.5 else "Likely Resistant",
        "model_name": _meta["model_name"],
        "model_cv_roc_auc": round(_meta["held_out_test"]["roc_auc"], 3),
        "trained_on": (
            f"{_meta['training_data_summary']['n_samples']} real cell-line/compound measurements "
            f"across {_meta['training_data_summary']['n_cell_lines']} cell lines "
            f"and {_meta['training_data_summary']['n_compounds']} compounds (GDSC2/DepMap)"
        ),
    }
