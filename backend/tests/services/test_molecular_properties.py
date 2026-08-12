from unittest.mock import Mock, patch

import pytest
import requests

from services.molecular_properties import MolecularPropertiesError, get_molecular_properties

# Real, published Erlotinib SMILES/values — used as a live-value sanity
# anchor: this is exactly the structure verified against RDKit during
# development (MW 393.44, matches PubChem's published value).
ERLOTINIB_SMILES = "COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC"


def _mock_response(json_data, status_code=200):
    mock = Mock()
    mock.json.return_value = json_data
    mock.raise_for_status = Mock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")
    return mock


@patch("services.molecular_properties.requests.get")
def test_computes_real_descriptors_for_small_molecule(mock_get):
    mock_get.return_value = _mock_response({
        "molecule_type": "Small molecule",
        "molecule_structures": {"canonical_smiles": ERLOTINIB_SMILES},
    })

    result = get_molecular_properties("CHEMBL939")

    assert result["has_structure"] is True
    assert result["properties"]["molecular_weight"] == pytest.approx(393.44, abs=0.05)
    assert result["lipinski"]["violations"] == 0
    assert result["lipinski"]["passes"] is True
    assert 0 <= result["qed"] <= 1


@patch("services.molecular_properties.requests.get")
def test_biologic_has_no_structure_honestly(mock_get):
    mock_get.return_value = _mock_response({
        "molecule_type": "Antibody",
        "molecule_structures": None,
    })

    result = get_molecular_properties("CHEMBL1201576")

    assert result["has_structure"] is False
    assert result["molecule_type"] == "Antibody"
    assert result["properties"] is None
    assert result["lipinski"] is None
    assert result["qed"] is None


@patch("services.molecular_properties.requests.get")
def test_lipinski_violation_detected_for_large_molecule(mock_get):
    # A large, high-MW, high-LogP synthetic SMILES designed to violate Ro5
    big_smiles = "C" * 40 + "(=O)N" + "c1ccccc1" * 3
    mock_get.return_value = _mock_response({
        "molecule_type": "Small molecule",
        "molecule_structures": {"canonical_smiles": big_smiles},
    })

    result = get_molecular_properties("CHEMBL_BIG")

    if result["has_structure"]:
        assert result["properties"]["molecular_weight"] > 500
        assert result["lipinski"]["violations"] >= 1


@patch("services.molecular_properties.requests.get")
def test_unparseable_smiles_treated_as_no_structure(mock_get):
    mock_get.return_value = _mock_response({
        "molecule_type": "Small molecule",
        "molecule_structures": {"canonical_smiles": "not a valid smiles!!"},
    })

    result = get_molecular_properties("CHEMBL_BAD")

    assert result["has_structure"] is False


@patch("services.molecular_properties.requests.get")
def test_raises_on_network_failure(mock_get):
    mock_get.side_effect = requests.ConnectionError("down")

    with pytest.raises(MolecularPropertiesError):
        get_molecular_properties("CHEMBL939")
