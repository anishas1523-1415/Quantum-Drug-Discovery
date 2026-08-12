"""Offline training pipeline for the real drug-effectiveness model.

Trains on GDSC2 (Genomics of Drug Sensitivity in Cancer) IC50 data,
cross-referenced with DepMap's damaging-mutation calls and cell-line
disease annotations, and PortalCompounds' compound structures/targets.
Every training example is a real (cell line, real screened compound)
measurement — nothing here is synthetic.

Run from the backend/ directory with the venv active:

    python -m ml.train_effectiveness_model --data-dir "C:\\Users\\ANISH\\Downloads"

Produces backend/trained_models/effectiveness_model.pkl and
effectiveness_model_meta.json. Source CSVs are NOT bundled into the
repo (large, no license to redistribute) — this script is meant to be
re-run whenever a contributor has their own copy of the GDSC2/DepMap
data, and the resulting compact artifact is what actually ships.

Modeling choices, stated plainly:
- Label: per-compound relative sensitivity. A cell line is labeled
  "sensitive" to a compound if its log2(IC50) is at or below that
  compound's own median log2(IC50) across all tested cell lines. GDSC
  compounds span wildly different potency scales (nanomolar to
  micromolar), so a single global IC50 cutoff would mostly just
  encode "which compound is this" rather than genuine differential
  sensitivity. A per-compound relative threshold is the standard
  framing for this kind of pharmacogenomic screen.
- Split: grouped by ModelID (cell line), never by row. The same cell
  line appears against dozens of compounds; letting rows from the same
  cell line land in both train and test would leak information and
  inflate reported performance.
- Model selection: several real, different algorithms are
  cross-validated (grouped, so no leakage there either) and compared
  on ROC-AUC; the best one is kept. This is not decided in advance.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import FEATURE_COLUMNS, build_feature_row  # noqa: E402
from ml.gene_panel import DRIVER_GENE_PANEL  # noqa: E402
from services.molecular_descriptors import compute_descriptors  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_effectiveness_model")

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")
RANDOM_STATE = 42


def _load_model_metadata(data_dir):
    path = os.path.join(data_dir, "Model.csv")
    df = pd.read_csv(path, usecols=["ModelID", "OncotreePrimaryDisease"])
    return dict(zip(df["ModelID"], df["OncotreePrimaryDisease"]))


def _load_compound_reference(data_dir, gdsc_compound_ids):
    path = os.path.join(data_dir, "PortalCompounds.csv")
    df = pd.read_csv(path, usecols=["CompoundID", "CompoundName", "SMILES", "GeneSymbolOfTargets"])
    df = df[df["CompoundID"].isin(gdsc_compound_ids)]

    descriptors_by_compound = {}
    targets_by_compound = {}
    names_by_compound = {}

    for _, row in df.iterrows():
        smiles = row["SMILES"]
        if pd.isna(smiles):
            continue

        descriptors = compute_descriptors(smiles)
        if descriptors is None:
            continue

        cid = row["CompoundID"]
        descriptors_by_compound[cid] = descriptors
        names_by_compound[cid] = row["CompoundName"]

        targets = set()
        if pd.notna(row["GeneSymbolOfTargets"]):
            targets = {g.strip().upper() for g in str(row["GeneSymbolOfTargets"]).split(";") if g.strip()}
        targets_by_compound[cid] = targets

    logger.info(
        "Compound reference: %d/%d GDSC2 compounds have a usable real structure (RDKit-parseable SMILES)",
        len(descriptors_by_compound), len(gdsc_compound_ids),
    )
    return descriptors_by_compound, targets_by_compound, names_by_compound


def _resolve_mutation_columns(data_dir, gene_symbols):
    path = os.path.join(data_dir, "OmicsSomaticMutationsMatrixDamaging.csv")
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")

    symbol_to_column = {}
    wanted = {g.upper() for g in gene_symbols}
    for col in header:
        base = col.split(" (")[0].strip().upper()
        if base in wanted:
            symbol_to_column[base] = col

    missing = wanted - set(symbol_to_column)
    if missing:
        logger.warning("%d gene(s) not found in mutation matrix header: %s", len(missing), sorted(missing))

    return symbol_to_column


def _load_mutations(data_dir, symbol_to_column):
    path = os.path.join(data_dir, "OmicsSomaticMutationsMatrixDamaging.csv")
    usecols = ["ModelID", "IsDefaultEntryForModel"] + list(symbol_to_column.values())
    df = pd.read_csv(path, usecols=usecols)
    df = df[df["IsDefaultEntryForModel"] == "Yes"]

    mutated_genes_by_model = {}
    column_to_symbol = {v: k for k, v in symbol_to_column.items()}

    for _, row in df.iterrows():
        mutated = {
            column_to_symbol[col]
            for col in symbol_to_column.values()
            if pd.notna(row[col]) and row[col] > 0
        }
        mutated_genes_by_model[row["ModelID"]] = mutated

    return mutated_genes_by_model


def build_training_table(data_dir):
    gdsc_path = os.path.join(data_dir, "GDSC2Log2IC50Matrix.csv")
    gdsc = pd.read_csv(gdsc_path, index_col=0)
    logger.info("GDSC2 matrix: %d cell lines x %d compounds", *gdsc.shape)

    disease_by_model = _load_model_metadata(data_dir)
    descriptors_by_compound, targets_by_compound, names_by_compound = _load_compound_reference(
        data_dir, set(gdsc.columns)
    )

    usable_compounds = set(descriptors_by_compound)
    gdsc = gdsc[[c for c in gdsc.columns if c in usable_compounds]]

    all_target_genes = set()
    for genes in targets_by_compound.values():
        all_target_genes |= genes

    gene_universe = set(DRIVER_GENE_PANEL) | all_target_genes
    symbol_to_column = _resolve_mutation_columns(data_dir, gene_universe)
    mutated_genes_by_model = _load_mutations(data_dir, symbol_to_column)

    long_df = gdsc.reset_index().melt(id_vars=gdsc.index.name or "index", var_name="CompoundID", value_name="Log2IC50")
    long_df.columns = ["ModelID", "CompoundID", "Log2IC50"]
    long_df = long_df.dropna(subset=["Log2IC50"])
    long_df = long_df[long_df["ModelID"].isin(disease_by_model)]
    long_df = long_df[long_df["ModelID"].isin(mutated_genes_by_model)]

    logger.info("Joined training rows before labeling: %d", len(long_df))

    # Per-compound relative sensitivity threshold (see module docstring).
    medians = long_df.groupby("CompoundID")["Log2IC50"].transform("median")
    long_df["label"] = (long_df["Log2IC50"] <= medians).astype(int)

    rows = []
    groups = []
    labels = []

    for record in long_df.itertuples(index=False):
        model_id, compound_id = record.ModelID, record.CompoundID
        row = build_feature_row(
            cancer_type_text=disease_by_model.get(model_id),
            mutated_genes=mutated_genes_by_model.get(model_id, set()),
            target_genes=targets_by_compound.get(compound_id, set()),
            descriptors=descriptors_by_compound.get(compound_id),
        )
        rows.append(row)
        groups.append(model_id)
        labels.append(record.label)

    X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    y = np.array(labels)
    groups = np.array(groups)

    return X, y, groups, {
        "n_samples": len(X),
        "n_cell_lines": len(set(groups)),
        "n_compounds": len(usable_compounds),
        "compounds_used": sorted(names_by_compound.values()),
        "label_positive_rate": float(y.mean()),
    }


def _candidate_models():
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "hist_gradient_boosting": HistGradientBoostingClassifier(random_state=RANDOM_STATE),
    }


def cross_validate_models(X_train, y_train, groups_train):
    cv = GroupKFold(n_splits=5)
    results = {}

    for name, model in _candidate_models().items():
        fold_aucs = []
        for train_idx, val_idx in cv.split(X_train, y_train, groups_train):
            fold_model = _candidate_models()[name]
            fold_model.fit(X_train.iloc[train_idx], y_train[train_idx])
            proba = fold_model.predict_proba(X_train.iloc[val_idx])[:, 1]
            fold_aucs.append(roc_auc_score(y_train[val_idx], proba))

        results[name] = {"mean_auc": float(np.mean(fold_aucs)), "std_auc": float(np.std(fold_aucs)), "fold_aucs": fold_aucs}
        logger.info("%-24s grouped 5-fold ROC-AUC = %.4f +/- %.4f", name, results[name]["mean_auc"], results[name]["std_auc"])

    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Directory containing the 4 GDSC/DepMap CSVs")
    args = parser.parse_args()

    logger.info("Building training table from %s", args.data_dir)
    X, y, groups, summary = build_training_table(args.data_dir)
    logger.info(
        "Training table: %d rows, %d cell lines, %d compounds, positive rate %.3f",
        summary["n_samples"], summary["n_cell_lines"], summary["n_compounds"], summary["label_positive_rate"],
    )

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    groups_train = groups[train_idx]

    logger.info("Train: %d rows (%d cell lines) / Test: %d rows (%d cell lines)",
                len(X_train), len(set(groups_train)), len(X_test), len(set(groups[test_idx])))

    cv_results = cross_validate_models(X_train, y_train, groups_train)
    best_name = max(cv_results, key=lambda k: cv_results[k]["mean_auc"])
    logger.info("Best model by cross-validated ROC-AUC: %s", best_name)

    best_model = _candidate_models()[best_name]
    best_model.fit(X_train, y_train)

    test_proba = best_model.predict_proba(X_test)[:, 1]
    test_pred = (test_proba >= 0.5).astype(int)
    test_auc = roc_auc_score(y_test, test_proba)
    test_acc = accuracy_score(y_test, test_pred)
    report = classification_report(y_test, test_pred, output_dict=True)

    logger.info("Held-out test ROC-AUC = %.4f, accuracy = %.4f", test_auc, test_acc)
    print(classification_report(y_test, test_pred))

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    model_path = os.path.join(ARTIFACT_DIR, "effectiveness_model.pkl")
    joblib.dump(best_model, model_path)

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_name": best_name,
        "feature_columns": FEATURE_COLUMNS,
        "training_data_summary": summary,
        "cv_results": cv_results,
        "held_out_test": {
            "n_samples": int(len(X_test)),
            "roc_auc": float(test_auc),
            "accuracy": float(test_acc),
            "classification_report": report,
        },
        "label_definition": (
            "1 (sensitive) if a cell line's log2(IC50) for a compound is at or "
            "below that compound's own median log2(IC50) across all tested cell "
            "lines in this dataset; 0 (resistant) otherwise."
        ),
        "data_sources": [
            "GDSC2Log2IC50Matrix.csv (Genomics of Drug Sensitivity in Cancer)",
            "OmicsSomaticMutationsMatrixDamaging.csv (DepMap)",
            "Model.csv (DepMap cell line annotations)",
            "PortalCompounds.csv (DepMap compound reference / structures)",
        ],
    }
    meta_path = os.path.join(ARTIFACT_DIR, "effectiveness_model_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("Saved model -> %s", model_path)
    logger.info("Saved metadata -> %s", meta_path)


if __name__ == "__main__":
    main()
