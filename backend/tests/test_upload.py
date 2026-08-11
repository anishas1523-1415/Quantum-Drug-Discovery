import io
import os

VALID_CSV = (
    "PatientID,Age,Gender,CancerType,TumorSize,Stage,GeneticMutation,DrugResponse\n"
    "P001,45,Female,Breast,2.5,II,BRCA1,Positive\n"
    "P002,62,Male,Lung,4.8,III,EGFR,Negative\n"
)

MISSING_COLUMNS_CSV = (
    "PatientID,Age,Gender,BMI,CancerType,Drug\n"
    "P001,45,Female,26,Lung,Cisplatin\n"
)


def _upload(client, headers, content=VALID_CSV, filename="patient.csv"):
    return client.post(
        "/api/upload",
        headers=headers,
        data={"file": (io.BytesIO(content.encode()), filename)},
        content_type="multipart/form-data",
    )


def test_upload_requires_auth(client):
    response = _upload(client, headers={})

    assert response.status_code == 401


def test_upload_requires_file(client, auth_headers):
    response = client.post("/api/upload", headers=auth_headers)

    assert response.status_code == 400


def test_upload_rejects_non_csv(client, auth_headers):
    response = _upload(client, auth_headers, content="not a csv", filename="notes.txt")

    assert response.status_code == 400


def test_upload_rejects_schema_mismatch(client, auth_headers):
    response = _upload(client, auth_headers, content=MISSING_COLUMNS_CSV)

    assert response.status_code == 422
    assert "missing" in response.get_json()["message"].lower()


def test_upload_success_returns_predictions_and_quantum_scores(client, auth_headers):
    response = _upload(client, auth_headers)
    data = response.get_json()

    assert response.status_code == 200
    assert len(data["prediction"]) == 2
    assert len(data["quantum_result"]) == 2
    assert data["prediction"][0]["PatientID"] == "P001"
    assert data["prediction"][0]["Prediction"] in ("Effective", "Not Effective")
    assert 0 <= data["quantum_result"][0]["QuantumScore"] <= 1


def test_upload_does_not_retain_files_on_disk(client, auth_headers):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "uploads")
    processed_dir = os.path.join(base_dir, "processed")

    before_uploads = set(os.listdir(uploads_dir))
    before_processed = set(os.listdir(processed_dir))

    _upload(client, auth_headers)

    after_uploads = set(os.listdir(uploads_dir))
    after_processed = set(os.listdir(processed_dir))

    assert after_uploads == before_uploads
    assert after_processed == before_processed
