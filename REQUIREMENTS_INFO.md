# 📦 Requirements Files Guide

## Overview

This project has two requirements files to optimize deployment size.

---

## 📄 Files

### 1. requirements.txt (Production)
**Use for:** Deployment (Vercel, Railway, Render, etc.)

**Size:** ~50-100MB

**Includes:**
- ✅ FastAPI & Uvicorn (API framework)
- ✅ OpenAI SDK (Azure OpenAI)
- ✅ Joblib & NumPy (model loading)
- ✅ Pydantic (data validation)
- ✅ Python-dotenv (configuration)

**Excludes:**
- ❌ XGBoost (~400MB)
- ❌ Pandas (~100MB)
- ❌ Scikit-learn (~50MB)
- ❌ Matplotlib
- ❌ pyttsx3

**Why?** Model is already trained and saved as `.pkl` file. We only need to LOAD it, not TRAIN it.

---

### 2. requirements-dev.txt (Development)
**Use for:** Local development, model training

**Size:** ~500MB+

**Includes:**
- ✅ All production dependencies
- ✅ XGBoost (model training)
- ✅ Pandas (data processing)
- ✅ Scikit-learn (ML utilities)
- ✅ Matplotlib (visualization)
- ✅ NumPy (numerical computing)

**Why?** Needed for training new models or modifying existing ones.

---

### 3. requirements-production.txt (Backup)
**Use for:** Reference, same as requirements.txt

Kept as backup/reference for production dependencies.

---

## 🚀 Usage

### For Deployment
```bash
pip install -r requirements.txt
```

### For Development/Training
```bash
pip install -r requirements-dev.txt
```

### For Local Testing (Production Mode)
```bash
pip install -r requirements.txt
```

---

## 💡 Why This Matters

### Problem
Vercel and other serverless platforms have size limits:
- Vercel: 50MB (free), 250MB (pro)
- Railway: 500MB
- Render: 500MB

With all libraries: ~550MB ❌
With production only: ~50MB ✅

### Solution
1. Train model locally with full dependencies
2. Save model as `.pkl` file
3. Deploy with minimal dependencies
4. Load model at runtime with joblib

---

## 🔍 Dependency Breakdown

### Production (requirements.txt)
```
fastapi==0.109.0          # ~10MB - API framework
uvicorn[standard]==0.27.0 # ~5MB  - ASGI server
python-multipart==0.0.6   # ~1MB  - File upload
python-dotenv==1.0.0      # <1MB  - Environment variables
openai==1.10.0            # ~5MB  - Azure OpenAI SDK
pydantic==2.5.3           # ~3MB  - Data validation
joblib==1.3.2             # ~1MB  - Model loading
numpy==1.26.3             # ~15MB - Numerical computing
-----------------------------------
Total: ~50MB ✅
```

### Development (requirements-dev.txt)
```
All production dependencies  # ~50MB
xgboost==2.0.3              # ~400MB - Model training
pandas==2.1.4               # ~100MB - Data processing
scikit-learn==1.4.0         # ~50MB  - ML utilities
matplotlib==3.8.2           # ~50MB  - Visualization
pyttsx3==2.90               # ~10MB  - Text-to-speech
-----------------------------------
Total: ~660MB ❌ (Too large for deployment)
```

---

## 🎯 When to Use Each

### Use requirements.txt when:
- ✅ Deploying to Vercel
- ✅ Deploying to Railway
- ✅ Deploying to Render
- ✅ Deploying to any serverless platform
- ✅ Testing production build locally
- ✅ Running the API in production

### Use requirements-dev.txt when:
- ✅ Training a new model
- ✅ Modifying the existing model
- ✅ Running training scripts
- ✅ Generating new datasets
- ✅ Experimenting with ML algorithms
- ✅ Local development with full features

---

## 🔧 How It Works

### Model Training (Local - Dev Requirements)
```python
# training/train_model.py
import xgboost as xgb
import pandas as pd

# Train model
model = xgb.XGBClassifier()
model.fit(X_train, y_train)

# Save model
joblib.dump(model, 'admission_model.pkl')
```

### Model Loading (Production - Prod Requirements)
```python
# app/ml_model.py
import joblib
import numpy as np

# Load pre-trained model (no xgboost needed!)
model = joblib.load("training/admission_model.pkl")

# Use model
def predict_enrollment(features):
    values = np.array([features])
    prob = model.predict_proba(values)[0][1]
    return float(prob)
```

**Key Point:** Joblib serializes the model with all its logic. We don't need XGBoost to USE the model, only to TRAIN it!

---

## 📊 Size Comparison

### Scenario 1: Deploy with requirements-dev.txt
```
Deployment Size: 660MB
Vercel Free Tier: 50MB limit
Result: ❌ FAILED - Too large!
```

### Scenario 2: Deploy with requirements.txt
```
Deployment Size: 50MB
Vercel Free Tier: 50MB limit
Result: ✅ SUCCESS - Perfect fit!
```

---

## 🐛 Troubleshooting

### Error: "No module named 'xgboost'"
**Cause:** Using requirements.txt (production)
**Solution:** This is expected! XGBoost not needed in production.
**Fix:** Model already trained, just load with joblib.

### Error: "Deployment size exceeded"
**Cause:** Using requirements-dev.txt
**Solution:** Use requirements.txt instead
```bash
pip install -r requirements.txt
```

### Error: "Cannot train model"
**Cause:** Using requirements.txt (production)
**Solution:** Use requirements-dev.txt for training
```bash
pip install -r requirements-dev.txt
python training/train_model.py
```

---

## 🎓 Best Practices

### For Development
1. Use requirements-dev.txt
2. Train models locally
3. Test thoroughly
4. Save models as .pkl files
5. Commit .pkl files to git

### For Deployment
1. Use requirements.txt
2. Ensure .pkl files are included
3. Test with production requirements locally
4. Deploy to platform
5. Monitor size and performance

### For CI/CD
1. Use requirements.txt in deployment pipeline
2. Keep requirements-dev.txt for training pipeline
3. Separate training and deployment workflows
4. Cache dependencies for faster builds

---

## 📝 Summary

| File | Size | Use Case | Includes XGBoost? |
|------|------|----------|-------------------|
| requirements.txt | ~50MB | Production/Deployment | ❌ No |
| requirements-dev.txt | ~660MB | Development/Training | ✅ Yes |
| requirements-production.txt | ~50MB | Reference/Backup | ❌ No |

**Remember:** 
- Train with requirements-dev.txt
- Deploy with requirements.txt
- Model is already trained!

---

## 🎉 Benefits

### Cost Savings
- Smaller deployments = Lower costs
- Faster cold starts
- Less bandwidth usage

### Performance
- Faster deployment times
- Quicker startup
- Better response times

### Simplicity
- Fewer dependencies to manage
- Easier troubleshooting
- Cleaner production environment

---

<div align="center">

**Optimized for production! 🚀**

[Deployment Guide](../DEPLOYMENT_GUIDE.md) • [Main Docs](../README.md)

</div>
