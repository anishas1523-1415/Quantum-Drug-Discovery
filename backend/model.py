import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os

# Read processed dataset
df = pd.read_csv("processed/processed_patient.csv")

# Input Features
X = df.drop(columns=["PatientID", "DrugResponse"])

# Output
y = df["DrugResponse"]

# Split Dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# Create Model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

# Train Model
model.fit(X_train, y_train)

# Accuracy
accuracy = model.score(X_test, y_test)

print("\n========== MODEL TRAINED ==========")
print("Accuracy :", accuracy)

# Save Model
os.makedirs("trained_models", exist_ok=True)

joblib.dump(
    model,
    "trained_models/drug_model.pkl"
)

print("Model Saved Successfully")