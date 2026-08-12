from unittest.mock import patch

import genomics
from genomics import GenomicsError, get_candidates_for_gene, recommend_drugs

from .conftest import register_user

FAKE_SEARCH_RESPONSE = {
    "search": {"hits": [{"id": "ENSG00000146648", "name": "EGFR", "entity": "target"}]}
}

FAKE_CANDIDATES_RESPONSE = {
    "target": {
        "approvedSymbol": "EGFR",
        "drugAndClinicalCandidates": {
            "count": 2,
            "rows": [
                {
                    "maxClinicalStage": "PHASE_4",
                    "drug": {
                        "id": "CHEMBL939",
                        "name": "ERLOTINIB",
                        "drugType": "Small molecule",
                        "description": "EGFR inhibitor",
                    },
                    "diseases": [
                        {"diseaseFromSource": "non-small cell lung cancer", "disease": {"id": "MONDO_1", "name": "non-small cell lung carcinoma"}},
                    ],
                },
                {
                    "maxClinicalStage": "PHASE_2",
                    "drug": {
                        "id": "CHEMBL999",
                        "name": "EXPERIMENTAL-EGFRI",
                        "drugType": "Small molecule",
                        "description": "Investigational EGFR inhibitor",
                    },
                    "diseases": [
                        {"diseaseFromSource": "non-small cell lung cancer", "disease": {"id": "MONDO_1", "name": "non-small cell lung carcinoma"}},
                        {"diseaseFromSource": "breast cancer", "disease": {"id": "MONDO_2", "name": "breast carcinoma"}},
                    ],
                },
            ],
        },
    }
}

FAKE_EMPTY_SEARCH_RESPONSE = {"search": {"hits": []}}


def fake_graphql_egfr(query, variables=None):
    if "search(" in query:
        return FAKE_SEARCH_RESPONSE
    return FAKE_CANDIDATES_RESPONSE


def auth_headers_for(client):
    token = register_user(client).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@patch("genomics._graphql", side_effect=fake_graphql_egfr)
def test_recommend_drugs_ranks_by_clinical_stage(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("EGFR", "Lung")

    assert result["gene"] == "EGFR"
    assert result["total_direct_candidates"] == 2
    assert len(result["matched_candidates"]) == 2
    # Phase 4 (approved-track) should outrank phase 2
    assert result["matched_candidates"][0]["drug_name"] == "ERLOTINIB"


@patch("genomics._graphql", side_effect=fake_graphql_egfr)
def test_recommend_drugs_filters_by_cancer_type(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("EGFR", "Breast")

    # Only EXPERIMENTAL-EGFRI lists breast cancer among its diseases
    assert len(result["matched_candidates"]) == 1
    assert result["matched_candidates"][0]["drug_name"] == "EXPERIMENTAL-EGFRI"


@patch("genomics._graphql", side_effect=lambda query, variables=None: FAKE_EMPTY_SEARCH_RESPONSE)
def test_recommend_drugs_gene_not_found_returns_empty_not_error(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("NOTAREALGENE", "Lung")

    assert result["target_id"] is None
    assert result["matched_candidates"] == []


@patch("genomics._graphql", side_effect=fake_graphql_egfr)
def test_get_candidates_for_gene_uses_cache_on_second_call(mock_graphql, app):
    with app.app_context():
        get_candidates_for_gene("EGFR")
        get_candidates_for_gene("EGFR")

    # Two live GraphQL calls (search + candidates) for the first lookup,
    # zero more for the second — the cache should short-circuit it.
    assert mock_graphql.call_count == 2


def test_recommend_endpoint_requires_auth(client):
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung")
    assert response.status_code == 401


def test_recommend_endpoint_requires_gene_param(client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?cancer_type=Lung", headers=headers)
    assert response.status_code == 400


def test_recommend_endpoint_requires_cancer_type_param(client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?gene=EGFR", headers=headers)
    assert response.status_code == 400


@patch("genomics._graphql", side_effect=fake_graphql_egfr)
def test_recommend_endpoint_returns_ranked_results(mock_graphql, client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["gene"] == "EGFR"
    assert len(data["matched_candidates"]) == 2


@patch("genomics._graphql", side_effect=genomics.GenomicsError("upstream is down"))
def test_recommend_endpoint_surfaces_upstream_failure_as_502(mock_graphql, client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 502
