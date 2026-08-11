import logging

import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger("qdd.preprocessing")


def preprocess_data(filepath):

    # Read CSV
    df = pd.read_csv(filepath)

    logger.debug("Loaded %d rows from %s", len(df), filepath)

    # Remove duplicates
    df = df.drop_duplicates()

    # Handle missing values
    for column in df.columns:

        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].fillna(
                df[column].mean()
            )
        else:
            df[column] = df[column].fillna(
                "Unknown"
            )

    # Encode text columns (skip PatientID so results stay identifiable)
    encoder = LabelEncoder()

    for column in df.columns:

        if column == "PatientID":
            continue

        if not pd.api.types.is_numeric_dtype(
            df[column]
        ):
            df[column] = encoder.fit_transform(
                df[column]
            )

    # Basic Feature Engineering
    if "Age" in df.columns and "BMI" in df.columns:
        df["RiskScore"] = (
            df["Age"] * 0.3
            + df["BMI"] * 0.2
        )

    logger.debug("Preprocessing complete: %d rows, %d columns", len(df), len(df.columns))

    return df