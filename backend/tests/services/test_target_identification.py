from unittest.mock import patch

from services import target_identification
from services.target_identification import GenomicsError, get_candidates_for_gene, recommend_drugs

from ..conftest import register_user

FAKE_SEARCH_RESPONSE = {
    "search": {"hits": [{"id": "ENSG00000146648", "name": "EGFR", "entity": "target"}]}
}

FAKE_CANDIDATES_RESPONSE = {
    "target": {
        "approvedSymbol": "EGFR",
        "drugAndClinicalCandidates": {
            "count": 3,
            "rows": [
                {
                    "drug": {
                        "id": "CHEMBL939",
                        "name": "ERLOTINIB",
                        "drugType": "Small molecule",
                        "description": "EGFR inhibitor",
                        "indications": {
                            "rows": [
                                {"maxClinicalStage": "APPROVAL", "disease": {"id": "MONDO_1", "name": "non-small cell lung carcinoma"}},
                            ]
                        },
                    },
                },
                {
                    "drug": {
                        "id": "CHEMBL999",
                        "name": "EXPERIMENTAL-EGFRI",
                        "drugType": "Small molecule",
                        "description": "Investigational EGFR inhibitor",
                        "indications": {
                            "rows": [
                                {"maxClinicalStage": "PHASE_2", "disease": {"id": "MONDO_1", "name": "non-small cell lung carcinoma"}},
                                {"maxClinicalStage": "PHASE_2", "disease": {"id": "MONDO_2", "name": "breast carcinoma"}},
                            ]
                        },
                    },
                },
                {
                    # Regression case: approved for a DIFFERENT cancer, only
                    # early-phase for the one we're asking about. Ranking
                    # must use the lung-specific stage, not the drug's best
                    # stage anywhere.
                    "drug": {
                        "id": "CHEMBL111",
                        "name": "CROSS-APPROVED-DRUG",
                        "drugType": "Antibody",
                        "description": "Approved elsewhere, early-phase here",
                        "indications": {
                            "rows": [
                                {"maxClinicalStage": "APPROVAL", "disease": {"id": "MONDO_3", "name": "head and neck cancer"}},
                                {"maxClinicalStage": "PHASE_1", "disease": {"id": "MONDO_1", "name": "non-small cell lung carcinoma"}},
                            ]
                        },
                    },
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


@patch("services.target_identification._graphql", side_effect=fake_graphql_egfr)
def test_recommend_drugs_ranks_by_clinical_stage(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("EGFR", "Lung")

    assert result["gene"] == "EGFR"
    assert result["total_direct_candidates"] == 3
    assert len(result["matched_candidates"]) == 3
    names_in_order = [c["drug_name"] for c in result["matched_candidates"]]
    assert names_in_order == ["ERLOTINIB", "EXPERIMENTAL-EGFRI", "CROSS-APPROVED-DRUG"]


@patch("services.target_identification._graphql", side_effect=fake_graphql_egfr)
def test_recommend_drugs_filters_by_cancer_type(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("EGFR", "Breast")

    # Only EXPERIMENTAL-EGFRI lists breast cancer among its indications
    assert len(result["matched_candidates"]) == 1
    assert result["matched_candidates"][0]["drug_name"] == "EXPERIMENTAL-EGFRI"


@patch("services.target_identification._graphql", side_effect=fake_graphql_egfr)
def test_recommend_drugs_uses_disease_specific_stage_not_global_stage(mock_graphql, app):
    """Regression test: a drug approved for one cancer but only Phase 1
    for the requested one must rank/label by the Phase 1 status, not by
    its unrelated approval elsewhere."""
    with app.app_context():
        result = recommend_drugs("EGFR", "Lung")

    cross_approved = next(c for c in result["matched_candidates"] if c["drug_name"] == "CROSS-APPROVED-DRUG")
    assert cross_approved["stage"] == "PHASE_1"
    assert cross_approved["matched_disease"] == "non-small cell lung carcinoma"


@patch("services.target_identification._graphql", side_effect=lambda query, variables=None: FAKE_EMPTY_SEARCH_RESPONSE)
def test_recommend_drugs_gene_not_found_returns_empty_not_error(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("NOTAREALGENE", "Lung")

    assert result["target_id"] is None
    assert result["matched_candidates"] == []


@patch("services.target_identification._graphql", side_effect=fake_graphql_egfr)
def test_get_candidates_for_gene_uses_cache_on_second_call(mock_graphql, app):
    with app.app_context():
        get_candidates_for_gene("EGFR")
        get_candidates_for_gene("EGFR")

    # Two live GraphQL calls (search + candidates) for the first lookup,
    # zero more for the second — the cache should short-circuit it.
    assert mock_graphql.call_count == 2


def fake_graphql_many_matches(query, variables=None):
    if "search(" in query:
        return FAKE_SEARCH_RESPONSE

    rows = [
        {
            "drug": {
                "id": f"CHEMBL{i}",
                "name": f"DRUG-{i}",
                "drugType": "Small molecule",
                "description": "d",
                "indications": {
                    "rows": [{"maxClinicalStage": "PHASE_2", "disease": {"id": "MONDO_1", "name": "lung cancer"}}]
                },
            },
        }
        for i in range(15)
    ]
    return {"target": {"approvedSymbol": "EGFR", "drugAndClinicalCandidates": {"count": 15, "rows": rows}}}


@patch("services.target_identification._graphql", side_effect=fake_graphql_many_matches)
def test_recommend_drugs_caps_results_at_limit(mock_graphql, app):
    with app.app_context():
        result = recommend_drugs("EGFR", "Lung")

    assert result["total_matches"] == 15
    assert len(result["matched_candidates"]) == target_identification.RESULT_LIMIT
    assert result["truncated"] is True


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


@patch("services.target_identification._graphql", side_effect=fake_graphql_egfr)
def test_recommend_endpoint_returns_ranked_results(mock_graphql, client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["gene"] == "EGFR"
    assert len(data["matched_candidates"]) == 3


@patch("services.target_identification._graphql", side_effect=GenomicsError("upstream is down"))
def test_recommend_endpoint_surfaces_upstream_failure_as_502(mock_graphql, client):
    headers = auth_headers_for(client)
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 502
