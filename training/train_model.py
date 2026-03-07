import pandas as pd
from xgboost import XGBClassifier
import joblib

data = pd.read_csv("admission_training_data.csv")
X = data.drop("enrolled", axis=1)
y = data["enrolled"]

model = XGBClassifier()
model.fit(X, y)

joblib.dump(model, "admission_model.pkl")
print("Model trained and saved")