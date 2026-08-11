import logging

import pandas as pd
import numpy as np

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

logger = logging.getLogger("qdd.quantum")


class QuantumProcessingError(Exception):
    pass


def quantum_process(file_path):

    # Read the newly processed patient file
    df = pd.read_csv(file_path)

    # Features used for quantum processing
    quantum_features = [
        "Age",
        "Gender",
        "TumorSize",
        "Stage"
    ]

    missing = [col for col in quantum_features if col not in df.columns]

    if missing:
        raise QuantumProcessingError(
            "Dataset is missing required column(s) for quantum analysis: "
            + ", ".join(missing)
        )

    if "PatientID" not in df.columns:
        raise QuantumProcessingError(
            "Dataset is missing the required 'PatientID' column"
        )

    data = df[quantum_features].copy()

    # Normalize each feature between 0 and 1
    for column in data.columns:

        minimum = data[column].min()
        maximum = data[column].max()

        if maximum != minimum:
            data[column] = (
                data[column] - minimum
            ) / (
                maximum - minimum
            )
        else:
            data[column] = 0

    # Convert to quantum angles
    data = data * np.pi

    quantum_results = []

    # Process every patient
    for index, row in data.iterrows():

        features = row.values

        circuit = QuantumCircuit(4)

        # Encode patient features
        for i in range(4):
            circuit.ry(float(features[i]), i)

        # Simulate circuit
        state = Statevector.from_instruction(circuit)

        probabilities = state.probabilities()

        # Store quantum result
        quantum_results.append(
            float(np.max(probabilities))
        )

    # Add quantum result to dataframe
    df["QuantumScore"] = quantum_results

    logger.debug("Quantum processing complete for %d patients", len(df))

    return df