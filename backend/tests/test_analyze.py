from unittest.mock import patch

from .conftest import register_user

BASE_RECOMMEND_RESULT = {
    "gene": "EGFR",
    "target_id": "ENSG00000146648",
    "target_name": "EGFR",
    "cancer_type": "Lung",
    "total_direct_candidates": 2,
    "total_matches": 2,
    "matched_candidates": [
        {"chembl_id": "CHEMBL1", "drug_name": "DRUG-A", "drug_type": "Small molecule",
         "description": "d", "stage": "APPROVAL", "matched_disease": "lung cancer"},
        {"chembl_id": "CHEMBL2", "drug_name": "DRUG-B", "drug_type": "Antibody",
         "description": "d", "stage": "PHASE_2", "matched_disease": "lung cancer"},
    ],
    "truncated": False,
    "source": "Open Targets Platform (live)",
}

EMPTY_RECOMMEND_RESULT = {
    "gene": "BRCA1",
    "target_id": "ENSG00000012048",
    "target_name": "BRCA1",
    "cancer_type": "Breast",
    "total_direct_candidates": 0,
    "total_matches": 0,
    "matched_candidates": [],
    "truncated": False,
    "source": "Open Targets Platform (live)",
}


def auth_headers_for(client):
    token = register_user(client).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def fake_score_candidates(candidates):
    return [
        {
            "drug_name": c["drug_name"], "chembl_id": c["chembl_id"], "drug_type": c["drug_type"],
            "description": c["description"], "composite_score": 90.0 if c["drug_name"] == "DRUG-A" else 60.0,
            "confidence": 0.4, "component_scores": {"clinical_evidence": 1.0},
            "admet_risk_band": "Unknown", "evidence": {}, "explanation": "test",
        }
        for c in candidates
    ]


def test_analyze_requires_auth(client):
    response = client.get("/api/analyze?gene=EGFR&cancer_type=Lung")
    assert response.status_code == 401


def test_analyze_requires_gene_param(client):
    headers = auth_headers_for(client)
    response = client.get("/api/analyze?cancer_type=Lung", headers=headers)
    assert response.status_code == 400


def test_analyze_requires_cancer_type_param(client):
    headers = auth_headers_for(client)
    response = client.get("/api/analyze?gene=EGFR", headers=headers)
    assert response.status_code == 400


@patch("analyze_routes.select_diverse_panel")
@patch("analyze_routes.score_candidates", side_effect=fake_score_candidates)
@patch("analyze_routes.recommend_drugs", return_value=BASE_RECOMMEND_RESULT)
def test_analyze_returns_ranked_and_diverse_panel(mock_recommend, mock_score, mock_quantum, client):
    mock_quantum.return_value = {
        "selected_indices": [0, 1],
        "objective_score": 1.5,
        "qaoa_raw_score": 1.5,
        "qaoa_found_optimum": True,
        "method": "QAOA (test)",
        "caveat": "test",
    }

    headers = auth_headers_for(client)
    response = client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["gene"] == "EGFR"
    assert len(data["candidates"]) == 2
    # Highest composite_score should sort first
    assert data["candidates"][0]["drug_name"] == "DRUG-A"
    assert len(data["diverse_panel"]) == 2


@patch("analyze_routes.recommend_drugs", return_value=EMPTY_RECOMMEND_RESULT)
def test_analyze_handles_no_candidates_honestly(mock_recommend, client):
    headers = auth_headers_for(client)
    response = client.get("/api/analyze?gene=BRCA1&cancer_type=Breast", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["candidates"] == []
    assert data["diverse_panel"] == []
    assert "message" in data


@patch("analyze_routes.select_diverse_panel")
@patch("analyze_routes.score_candidates", side_effect=fake_score_candidates)
@patch("analyze_routes.recommend_drugs", return_value=BASE_RECOMMEND_RESULT)
def test_analyze_falls_back_to_top_n_when_quantum_ranking_fails(mock_recommend, mock_score, mock_quantum, client):
    from services.quantum_ranking import QuantumRankingError

    mock_quantum.side_effect = QuantumRankingError("simulation failed")

    headers = auth_headers_for(client)
    response = client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["quantum_optimization"] is None
    assert len(data["diverse_panel"]) > 0  # fell back to top-N by score, not empty


@patch("analyze_routes.select_diverse_panel")
@patch("analyze_routes.score_candidates", side_effect=fake_score_candidates)
@patch("analyze_routes.recommend_drugs", return_value=BASE_RECOMMEND_RESULT)
def test_analyze_result_is_cached(mock_recommend, mock_score, mock_quantum, client):
    mock_quantum.return_value = {
        "selected_indices": [0], "objective_score": 1.0, "qaoa_raw_score": 1.0,
        "qaoa_found_optimum": True, "method": "test", "caveat": "test",
    }

    headers = auth_headers_for(client)
    client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)
    client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)

    # Pipeline (specifically the expensive recommend_drugs call) should
    # only run once — the second request must be served from cache.
    assert mock_recommend.call_count == 1


@patch("analyze_routes.recommend_drugs")
def test_analyze_surfaces_upstream_failure_as_502(mock_recommend, client):
    from services.target_identification import GenomicsError

    mock_recommend.side_effect = GenomicsError("Open Targets is down")

    headers = auth_headers_for(client)
    response = client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 502


def test_analyze_report_requires_auth(client):
    response = client.get("/api/analyze/report?gene=EGFR&cancer_type=Lung")
    assert response.status_code == 401


def test_analyze_report_requires_params(client):
    headers = auth_headers_for(client)
    response = client.get("/api/analyze/report?gene=EGFR", headers=headers)
    assert response.status_code == 400


@patch("analyze_routes.select_diverse_panel")
@patch("analyze_routes.score_candidates", side_effect=fake_score_candidates)
@patch("analyze_routes.recommend_drugs", return_value=BASE_RECOMMEND_RESULT)
def test_analyze_report_returns_a_real_pdf(mock_recommend, mock_score, mock_quantum, client):
    mock_quantum.return_value = {
        "selected_indices": [0], "objective_score": 1.0, "qaoa_raw_score": 1.0,
        "qaoa_found_optimum": True, "method": "test", "caveat": "test",
    }

    headers = auth_headers_for(client)
    response = client.get("/api/analyze/report?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")  # a real PDF, not a stub
    assert "attachment" in response.headers.get("Content-Disposition", "")


@patch("analyze_routes.select_diverse_panel")
@patch("analyze_routes.score_candidates", side_effect=fake_score_candidates)
@patch("analyze_routes.recommend_drugs", return_value=BASE_RECOMMEND_RESULT)
def test_analyze_report_reuses_cache_from_json_endpoint(mock_recommend, mock_score, mock_quantum, client):
    """Exporting a report right after viewing the JSON result shouldn't
    re-run the (slow) live pipeline a second time."""

    mock_quantum.return_value = {
        "selected_indices": [0], "objective_score": 1.0, "qaoa_raw_score": 1.0,
        "qaoa_found_optimum": True, "method": "test", "caveat": "test",
    }

    headers = auth_headers_for(client)
    client.get("/api/analyze?gene=EGFR&cancer_type=Lung", headers=headers)
    response = client.get("/api/analyze/report?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    assert mock_recommend.call_count == 1


@patch("analyze_routes.recommend_drugs")
def test_analyze_report_handles_no_candidates(mock_recommend, client):
    mock_recommend.return_value = EMPTY_RECOMMEND_RESULT

    headers = auth_headers_for(client)
    response = client.get("/api/analyze/report?gene=BRCA1&cancer_type=Breast", headers=headers)

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
