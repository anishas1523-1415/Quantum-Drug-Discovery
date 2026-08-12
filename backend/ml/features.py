"""Shared feature engineering for the drug-effectiveness model.

The exact same functions build the feature vector at training time
(ml/train_effectiveness_model.py, from GDSC2/DepMap data) and at
inference time (services/effectiveness_predictor.py, from a live
/api/analyze request). That parity is the whole point of this module
existing separately — if training and inference ever computed features
differently, the model's predictions would be meaningless.
"""

from ml.gene_panel import DRIVER_GENE_PANEL

# Top real OncotreePrimaryDisease categories by cell-line count in the
# DepMap Model.csv reference data (see ml/train_effectiveness_model.py),
# excluding "Non-Cancerous" (not relevant to this tool). Anything that
# doesn't match one of these buckets falls into "Other" — a real, honest
# fallback rather than a forced/incorrect match.
CANCER_TYPE_BUCKETS = [
    "Non-Small Cell Lung Cancer",
    "Melanoma",
    "Mature B-Cell Neoplasms",
    "Colorectal Adenocarcinoma",
    "Adult-Type Diffuse Glioma",
    "Head and Neck Squamous Cell Carcinoma",
    "Lung Neuroendocrine Tumor",
    "Invasive Breast Carcinoma",
    "Esophagogastric Adenocarcinoma",
    "Ovarian Epithelial Tumor",
    "Acute Myeloid Leukemia",
    "Pancreatic Adenocarcinoma",
    "Renal Cell Carcinoma",
    "Neuroblastoma",
    "Ewing Sarcoma",
    "Endometrial Carcinoma",
    "Pleural Mesothelioma",
    "Bladder Urothelial Carcinoma",
    "Other",
]

# Free-text keyword -> bucket. Checked in order; first match wins. This is
# a simple, transparent heuristic for mapping a doctor's free-text cancer
# type (or an Open Targets matched_disease string) onto the coarse
# categories the model was actually trained on.
_KEYWORD_RULES = [
    (("non-small cell", "nsclc"), "Non-Small Cell Lung Cancer"),
    (("neuroendocrine",), "Lung Neuroendocrine Tumor"),
    (("lung",), "Non-Small Cell Lung Cancer"),
    (("melanoma",), "Melanoma"),
    (("lymphoma", "b-cell", "b cell"), "Mature B-Cell Neoplasms"),
    (("colorectal", "colon", "rectal"), "Colorectal Adenocarcinoma"),
    (("glioma", "glioblastoma", "brain"), "Adult-Type Diffuse Glioma"),
    (("head and neck",), "Head and Neck Squamous Cell Carcinoma"),
    (("esophag", "gastric", "stomach"), "Esophagogastric Adenocarcinoma"),
    (("ovarian", "ovary"), "Ovarian Epithelial Tumor"),
    (("myeloid leukemia", "aml"), "Acute Myeloid Leukemia"),
    (("breast",), "Invasive Breast Carcinoma"),
    (("pancreatic", "pancreas"), "Pancreatic Adenocarcinoma"),
    (("renal", "kidney"), "Renal Cell Carcinoma"),
    (("neuroblastoma",), "Neuroblastoma"),
    (("ewing",), "Ewing Sarcoma"),
    (("endometrial", "uterine"), "Endometrial Carcinoma"),
    (("mesothelioma",), "Pleural Mesothelioma"),
    (("bladder", "urothelial"), "Bladder Urothelial Carcinoma"),
]

DESCRIPTOR_FIELDS = [
    "molecular_weight",
    "logp",
    "tpsa",
    "h_bond_donors",
    "h_bond_acceptors",
    "rotatable_bonds",
    "qed",
]

# Deterministic, fixed column order — training and inference both build a
# row against this exact list so the model always sees the same schema.
FEATURE_COLUMNS = (
    [f"cancer_type__{b}" for b in CANCER_TYPE_BUCKETS]
    + [f"gene__{g}" for g in DRIVER_GENE_PANEL]
    + ["target_gene_mutated"]
    + DESCRIPTOR_FIELDS
)


def match_cancer_type_bucket(text):
    """Map free-text cancer type to one of CANCER_TYPE_BUCKETS, or 'Other'."""
    if not text:
        return "Other"

    lowered = text.strip().lower()

    for keywords, bucket in _KEYWORD_RULES:
        if any(kw in lowered for kw in keywords):
            return bucket

    return "Other"


def build_feature_row(cancer_type_text, mutated_genes, target_genes, descriptors):
    """Build one feature row (dict, keyed exactly by FEATURE_COLUMNS).

    cancer_type_text: free-text cancer type (matched to a bucket)
    mutated_genes: set/iterable of gene symbols known damaging-mutated
        for this patient/cell-line profile
    target_genes: set/iterable of gene symbols this compound is known to
        target (empty/None if unknown)
    descriptors: dict with the DESCRIPTOR_FIELDS keys (from
        services.molecular_descriptors.compute_descriptors)
    """
    mutated = {g.upper() for g in (mutated_genes or [])}
    targets = {g.upper() for g in (target_genes or [])}

    bucket = match_cancer_type_bucket(cancer_type_text)
    row = {f"cancer_type__{b}": 1.0 if b == bucket else 0.0 for b in CANCER_TYPE_BUCKETS}

    for gene in DRIVER_GENE_PANEL:
        row[f"gene__{gene}"] = 1.0 if gene in mutated else 0.0

    row["target_gene_mutated"] = 1.0 if (targets and (mutated & targets)) else 0.0

    for field in DESCRIPTOR_FIELDS:
        row[field] = float(descriptors.get(field, 0.0)) if descriptors else 0.0

    return row
