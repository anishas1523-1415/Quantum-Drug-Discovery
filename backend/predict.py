import os

import joblib
import pandas as pd

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "trained_models",
    "drug_model.pkl",
)


class PredictionError(Exception):
    pass


_model = None


def get_model():
    global _model

    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise PredictionError("Trained model file was not found on the server")
        _model = joblib.load(MODEL_PATH)

    return _model


def predict_drug(processed_file):

    df = pd.read_csv(processed_file)

    if "PatientID" not in df.columns:
        raise PredictionError("Dataset is missing the required 'PatientID' column")

    X = df.drop(
        columns=["PatientID", "DrugResponse"],
        errors="ignore"
    )

    model = get_model()

    expected_features = getattr(model, "feature_names_in_", None)

    if expected_features is not None:
        missing = [col for col in expected_features if col not in X.columns]

        if missing:
            raise PredictionError(
                "Dataset is missing column(s) required by the model: "
                + ", ".join(missing)
            )

        X = X[list(expected_features)]

    predictions = model.predict(X)

    result = []

    for value in predictions:

        if value == 1:
            result.append("Effective")

        else:
            result.append("Not Effective")

    df["Prediction"] = result

    return df