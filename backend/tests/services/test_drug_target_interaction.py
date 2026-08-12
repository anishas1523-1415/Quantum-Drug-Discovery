from unittest.mock import Mock, patch

import pytest
import requests

from services.drug_target_interaction import DTIError, get_bioactivity

FAKE_ACTIVITY_RESPONSE = {
    "activities": [
        {
            "target_pref_name": "Epidermal growth factor receptor",
            "assay_type": "B",
            "standard_type": "IC50",
            "standard_value": "515.0",
            "standard_units": "nM",
            "pchembl_value": "6.29",
        },
        {
            "target_pref_name": "Epidermal growth factor receptor",
            "assay_type": "B",
            "standard_type": "IC50",
            "standard_value": "12.0",
            "standard_units": "nM",
            "pchembl_value": "7.92",
        },
        {
            # No pchembl_value -> must be excluded, not crash
            "target_pref_name": "Some other target",
            "assay_type": "F",
            "standard_type": "Inhibition",
            "standard_value": None,
            "standard_units": None,
            "pchembl_value": None,
        },
    ]
}


def _mock_response(json_data, status_code=200):
    mock = Mock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = Mock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")
    return mock


@patch("services.drug_target_interaction.requests.get")
def test_get_bioactivity_picks_most_potent_record(mock_get):
    mock_get.return_value = _mock_response(FAKE_ACTIVITY_RESPONSE)

    result = get_bioactivity("CHEMBL939")

    assert result["has_data"] is True
    assert result["record_count"] == 2  # the null-pchembl record is excluded
    assert result["best"]["pchembl_value"] == 7.92
    assert result["best"]["potency_band"] == "High potency (sub-100nM)"


@patch("services.drug_target_interaction.requests.get")
def test_get_bioactivity_honest_empty_result_for_no_data(mock_get):
    mock_get.return_value = _mock_response({"activities": []})

    result = get_bioactivity("CHEMBL_NO_DATA")

    assert result["has_data"] is False
    assert result["record_count"] == 0
    assert result["best"] is None


@patch("services.drug_target_interaction.requests.get")
def test_get_bioactivity_raises_on_network_failure(mock_get):
    mock_get.side_effect = requests.ConnectionError("no route to host")

    with pytest.raises(DTIError):
        get_bioactivity("CHEMBL939")


@patch("services.drug_target_interaction.requests.get")
def test_get_bioactivity_raises_on_server_error(mock_get):
    mock_get.return_value = _mock_response({}, status_code=500)

    with pytest.raises(DTIError):
        get_bioactivity("CHEMBL939")


@patch("services.drug_target_interaction.requests.get")
def test_get_bioactivity_raises_on_non_json_response(mock_get):
    mock = Mock()
    mock.raise_for_status = Mock()
    mock.json.side_effect = ValueError("not json")
    mock_get.return_value = mock

    with pytest.raises(DTIError):
        get_bioactivity("CHEMBL939")


@pytest.mark.parametrize(
    "pchembl,expected_band",
    [
        (9.5, "Very high potency (sub-nM)"),
        (7.5, "High potency (sub-100nM)"),
        (6.5, "Moderate potency (sub-1uM)"),
        (5.0, "Weak potency"),
        (2.0, "Very weak / below typical drug-like range"),
    ],
)
@patch("services.drug_target_interaction.requests.get")
def test_potency_band_thresholds(mock_get, pchembl, expected_band):
    mock_get.return_value = _mock_response({
        "activities": [{"target_pref_name": "T", "assay_type": "B", "standard_type": "IC50",
                         "standard_value": "1", "standard_units": "nM", "pchembl_value": str(pchembl)}]
    })

    result = get_bioactivity("CHEMBLX")

    assert result["best"]["potency_band"] == expected_band
