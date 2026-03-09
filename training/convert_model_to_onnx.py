"""
Convert XGBoost model to ONNX format for deployment without XGBoost dependency.
ONNX is a lightweight runtime that doesn't require the original training library.
"""

import joblib
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

# Load the trained XGBoost model
model = joblib.load("admission_model.pkl")

# Define input shape (8 features)
initial_type = [('float_input', FloatTensorType([None, 8]))]

# Convert to ONNX
onnx_model = convert_sklearn(
    model,
    initial_types=initial_type,
    target_opset=12
)

# Save ONNX model
with open("admission_model.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())

print("✅ Model converted to ONNX format!")
print("📦 File: admission_model.onnx")
print("💡 This can be used without XGBoost dependency")
