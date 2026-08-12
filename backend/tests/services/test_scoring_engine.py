from unittest.mock import patch

from services.drug_target_interaction import DTIError
from services.molecular_properties import MolecularPropertiesError
from services.scoring_engine import score_candidate, score_candidates

BASE_CANDIDATE = {
    "drug_name": "TEST-DRUG",
    "chembl_id": "CHEMBL1",
    "drug_type": "Small molecule",
    "stage": "APPROVAL",
    "matched_disease": "test cancer",
    "description": "a test drug",
}

FULL_DTI = {
    "chembl_id": "CHEMBL1",
    "has_data": True,
    "record_count": 3,
    "best": {"target_name": "T", "pchembl_value": 8.0, "potency_band": "High potency (sub-100nM)",
             "assay_type": "B", "standard_type": "IC50", "standard_value": "10", "standard_units": "nM"},
}

FULL_MOL = {
    "chembl_id": "CHEMBL1",
    "has_structure": True,
    "molecule_type": "Small molecule",
    "smiles": "CCO",
    "properties": {"molecular_weight": 300, "logp": 2, "tpsa": 60, "h_bond_donors": 2, "h_bond_acceptors": 4, "rotatable_bonds": 3},
    "lipinski": {"violations": 0, "passes": True},
    "qed": 0.75,
}

BIOLOGIC_MOL = {
    "chembl_id": "CHEMBL2",
    "has_structure": False,
    "molecule_type": "Antibody",
    "properties": None,
    "lipinski": None,
    "qed": None,
}

FULL_ML = {
    "applicable": True,
    "probability_sensitive": 0.7,
    "predicted_label": "Likely Sensitive",
    "model_name": "random_forest",
    "model_cv_roc_auc": 0.65,
    "trained_on": "17667 real cell-line/compound measurements across 936 cell lines and 68 compounds (GDSC2/DepMap)",
}

NOT_APPLICABLE_ML = {"applicable": False, "reason": "no structure"}


@patch("services.scoring_engine.predict_effectiveness")
@patch("services.scoring_engine.get_molecular_properties")
@patch("services.scoring_engine.get_bioactivity")
def test_full_data_candidate_gets_full_confidence(mock_dti, mock_mol, mock_ml):
    mock_dti.return_value = FULL_DTI
    mock_mol.return_value = FULL_MOL
    mock_ml.return_value = FULL_ML

    result = score_candidate(BASE_CANDIDATE)

    assert result["confidence"] == 1.0  # all five weighted components present
    assert set(result["component_scores"].keys()) == {
        "clinical_evidence", "dti_potency", "drug_likeness", "admet_safety", "ml_effectiveness",
    }
    assert result["composite_score"] > 0


@patch("services.scoring_engine.predict_effectiveness")
@patch("services.scoring_engine.get_molecular_properties")
@patch("services.scoring_engine.get_bioactivity")
def test_biologic_scored_fairly_without_molecular_data(mock_dti, mock_mol, mock_ml):
    """A biologic has no small-molecule structure — this must not be
    treated as a defect (score of 0 for those components) since real,
    approved biologic drugs legitimately have no SMILES structure."""

    mock_dti.return_value = {"chembl_id": "CHEMBL2", "has_data": False, "record_count": 0, "best": None}
    mock_mol.return_value = BIOLOGIC_MOL
    mock_ml.return_value = NOT_APPLICABLE_ML

    candidate = {**BASE_CANDIDATE, "chembl_id": "CHEMBL2", "drug_type": "Antibody"}
    result = score_candidate(candidate)

    # Only clinical_evidence (weight 0.35) was available -> confidence
    # equals exactly that weight, not zero and not silently 1.0
    assert result["confidence"] == 0.35
    assert result["component_scores"] == {"clinical_evidence": 1.0}  # APPROVAL = max rank
    assert result["admet_risk_band"] == "N/A"
    # A biologic with strong clinical evidence should still score well —
    # missing molecular data must not tank it.
    assert result["composite_score"] == 100.0


@patch("services.scoring_engine.predict_effectiveness")
@patch("services.scoring_engine.get_molecular_properties")
@patch("services.scoring_engine.get_bioactivity")
def test_upstream_failures_degrade_confidence_not_crash(mock_dti, mock_mol, mock_ml):
    mock_dti.side_effect = DTIError("chembl down")
    mock_mol.side_effect = MolecularPropertiesError("chembl down")
    mock_ml.return_value = NOT_APPLICABLE_ML

    result = score_candidate(BASE_CANDIDATE)

    assert result["confidence"] == 0.35  # only clinical_evidence survived
    assert "dti_error" in result["evidence"]
    assert "molecular_properties_error" in result["evidence"]


@patch("services.scoring_engine.predict_effectiveness")
@patch("services.scoring_engine.get_molecular_properties")
@patch("services.scoring_engine.get_bioactivity")
def test_score_candidates_ranks_highest_first(mock_dti, mock_mol, mock_ml):
    mock_dti.return_value = {"chembl_id": "X", "has_data": False, "record_count": 0, "best": None}
    mock_mol.return_value = BIOLOGIC_MOL
    mock_ml.return_value = NOT_APPLICABLE_ML

    weak = {**BASE_CANDIDATE, "drug_name": "WEAK", "stage": "PHASE_1"}
    strong = {**BASE_CANDIDATE, "drug_name": "STRONG", "stage": "APPROVAL"}

    results = score_candidates([weak, strong])

    assert [r["drug_name"] for r in results] == ["STRONG", "WEAK"]


@patch("services.scoring_engine.predict_effectiveness")
@patch("services.scoring_engine.get_molecular_properties")
@patch("services.scoring_engine.get_bioactivity")
def test_explanation_only_mentions_available_signals(mock_dti, mock_mol, mock_ml):
    mock_dti.return_value = {"chembl_id": "X", "has_data": False, "record_count": 0, "best": None}
    mock_mol.return_value = BIOLOGIC_MOL
    mock_ml.return_value = NOT_APPLICABLE_ML

    result = score_candidate(BASE_CANDIDATE)

    assert "clinical evidence" in result["explanation"]
    assert "QED" not in result["explanation"]
    assert "pChEMBL" not in result["explanation"]


def test_score_candidates_handles_empty_list():
    assert score_candidates([]) == []
