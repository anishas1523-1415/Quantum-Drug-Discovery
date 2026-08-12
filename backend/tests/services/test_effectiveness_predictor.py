import services.effectiveness_predictor as ep

MOL_WITH_STRUCTURE = {
    "has_structure": True,
    "properties": {
        "molecular_weight": 393.4, "logp": 2.7, "tpsa": 71.0,
        "h_bond_donors": 1, "h_bond_acceptors": 6, "rotatable_bonds": 8,
    },
    "qed": 0.55,
}

MOL_NO_STRUCTURE = {"has_structure": False, "properties": None, "qed": None}


def test_not_applicable_when_no_structure():
    result = ep.predict_effectiveness("EGFR", "Non-Small Cell Lung Cancer", MOL_NO_STRUCTURE)
    assert result["applicable"] is False
    assert "reason" in result


def test_not_applicable_when_mol_result_is_none():
    result = ep.predict_effectiveness("EGFR", "Non-Small Cell Lung Cancer", None)
    assert result["applicable"] is False


def test_not_applicable_without_a_loaded_model(monkeypatch):
    monkeypatch.setattr(ep, "_model", None)
    monkeypatch.setattr(ep, "_load_attempted", True)  # skip real disk load for this test
    result = ep.predict_effectiveness("EGFR", "Non-Small Cell Lung Cancer", MOL_WITH_STRUCTURE)
    assert result["applicable"] is False
    assert "No trained effectiveness model" in result["reason"]


def test_real_model_predicts_a_valid_probability():
    """Integration test against the actual trained artifact — verifies
    the real model loads and produces a sane, bounded prediction, not a
    mock."""
    if not ep.model_available():
        import pytest
        pytest.skip("trained_models/effectiveness_model.pkl not present in this environment")

    result = ep.predict_effectiveness("EGFR", "Non-Small Cell Lung Cancer", MOL_WITH_STRUCTURE)

    assert result["applicable"] is True
    assert 0.0 <= result["probability_sensitive"] <= 1.0
    assert result["predicted_label"] in {"Likely Sensitive", "Likely Resistant"}
    assert result["model_name"]
    assert 0.0 <= result["model_cv_roc_auc"] <= 1.0
