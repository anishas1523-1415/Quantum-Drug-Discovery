from ml.features import FEATURE_COLUMNS, build_feature_row, match_cancer_type_bucket
from ml.gene_panel import DRIVER_GENE_PANEL


def test_match_cancer_type_bucket_recognizes_common_terms():
    assert match_cancer_type_bucket("Non-Small Cell Lung Cancer") == "Non-Small Cell Lung Cancer"
    assert match_cancer_type_bucket("breast cancer") == "Invasive Breast Carcinoma"
    assert match_cancer_type_bucket("metastatic melanoma") == "Melanoma"


def test_match_cancer_type_bucket_falls_back_to_other():
    assert match_cancer_type_bucket("some rare unlisted cancer") == "Other"
    assert match_cancer_type_bucket(None) == "Other"
    assert match_cancer_type_bucket("") == "Other"


def test_build_feature_row_has_exactly_the_declared_columns():
    row = build_feature_row(
        cancer_type_text="breast cancer",
        mutated_genes={"BRCA1"},
        target_genes={"BRCA1"},
        descriptors={"molecular_weight": 300, "logp": 2, "tpsa": 60, "h_bond_donors": 2, "h_bond_acceptors": 4,
                     "rotatable_bonds": 3, "qed": 0.7},
    )
    assert set(row.keys()) == set(FEATURE_COLUMNS)


def test_build_feature_row_sets_correct_cancer_type_bucket():
    row = build_feature_row("breast cancer", {"BRCA1"}, {"BRCA1"}, {})
    assert row["cancer_type__Invasive Breast Carcinoma"] == 1.0
    assert row["cancer_type__Melanoma"] == 0.0
    assert row["cancer_type__Other"] == 0.0


def test_build_feature_row_marks_only_mutated_genes():
    row = build_feature_row("breast cancer", {"BRCA1"}, {"BRCA1"}, {})
    assert row["gene__BRCA1"] == 1.0
    other_genes = [g for g in DRIVER_GENE_PANEL if g != "BRCA1"]
    assert all(row[f"gene__{g}"] == 0.0 for g in other_genes)


def test_build_feature_row_target_gene_mutated_requires_overlap():
    overlapping = build_feature_row("breast cancer", {"EGFR"}, {"EGFR"}, {})
    assert overlapping["target_gene_mutated"] == 1.0

    non_overlapping = build_feature_row("breast cancer", {"EGFR"}, {"BRAF"}, {})
    assert non_overlapping["target_gene_mutated"] == 0.0

    unknown_target = build_feature_row("breast cancer", {"EGFR"}, set(), {})
    assert unknown_target["target_gene_mutated"] == 0.0
