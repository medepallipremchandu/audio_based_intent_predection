# RBAC + Feedback System Setup

## 1) Configure environment

1. Copy `.env.example` to `.env`.
2. Set:
   - `DATABASE_URL`
   - `JWT_SECRET`
   - Azure keys (for sentiment/intent analysis)

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

## 3) Run migrations + seed

```bash
python run_migrations.py
```

This applies all SQL files in `migrations/` once and seeds:
- default roles
- default permissions
- one superadmin user

Default seeded superadmin credentials:
- email: `superadmin@local.dev`
- password: `SuperAdmin@123`

## 4) Start backend

```bash
uvicorn main:app --reload
```

## 5) Start frontend

In `voxintentai`, set `VITE_API_URL=http://localhost:8000` and run:

```bash
npm install
npm run dev
```
