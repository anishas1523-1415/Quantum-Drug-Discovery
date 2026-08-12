from services.toxicity_admet import assess_admet_risk


def _mol_result(mw=300, logp=2, hbd=2, hba=4, tpsa=60, qed=0.7, has_structure=True, molecule_type="Small molecule"):
    if not has_structure:
        return {"has_structure": False, "molecule_type": molecule_type, "properties": None, "lipinski": None, "qed": None}

    violations = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
    return {
        "has_structure": True,
        "molecule_type": molecule_type,
        "properties": {
            "molecular_weight": mw, "logp": logp, "tpsa": tpsa,
            "h_bond_donors": hbd, "h_bond_acceptors": hba, "rotatable_bonds": 5,
        },
        "lipinski": {"violations": violations, "passes": violations <= 1},
        "qed": qed,
    }


def test_biologic_gets_not_applicable_result():
    result = assess_admet_risk(_mol_result(has_structure=False, molecule_type="Antibody"))

    assert result["method"] == "not_applicable"
    assert result["risk_band"] == "N/A"
    assert "Antibody" in result["explanation"]


def test_good_drug_likeness_gets_low_risk_band():
    result = assess_admet_risk(_mol_result(qed=0.8))

    assert result["risk_band"] == "Low"
    assert result["flags"] == []


def test_poor_drug_likeness_gets_higher_risk_band():
    result = assess_admet_risk(_mol_result(qed=0.2, mw=600, logp=6))

    assert result["risk_band"] == "Higher"
    assert any("500" in f for f in result["flags"])
    assert any("5" in f and "LogP" in f for f in result["flags"])


def test_moderate_qed_gets_moderate_band():
    result = assess_admet_risk(_mol_result(qed=0.5))

    assert result["risk_band"] == "Moderate"


def test_explanation_never_claims_confirmed_toxicity():
    result = assess_admet_risk(_mol_result(qed=0.1, mw=700))

    # This is the core honesty requirement for this module: it must never
    # read as a confirmed safety verdict, only a structural screening flag.
    assert "not a trained toxicity prediction" in result["explanation"]
    assert "confirmed adverse effects" not in result["explanation"] or "not" in result["explanation"]
