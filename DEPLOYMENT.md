# FinPilot AI — Cloud & GitHub Deployment Guide

This guide details how FinPilot AI is packaged, tested, and deployed directly from GitHub.

---

## 1. Automated GitHub Actions CI/CD Pipeline

Every push or pull request to the `main` branch triggers the automated GitHub Actions workflow (`.github/workflows/ci-cd.yml`):
* **MySQL 8.0 Service Container:** Automatically boots an isolated MySQL database in the GitHub runner.
* **System OCR Installation:** Installs `tesseract-ocr`, `poppler-utils`, and `libmagic1`.
* **Database Migrations:** Executes `flask db upgrade` against the live test database.
* **Full Test Execution:** Runs all 103 automated tests with Pytest.
* **Docker Build Verification:** Builds the production container image to guarantee zero build failures.

---

## 2. Option A: 1-Click Cloud Deployment via Render

FinPilot AI includes a `render.yaml` specification for zero-configuration deployment:
1. Log in to [Render.com](https://render.com) using your GitHub account (`AnshX100`).
2. Click **New +** $\rightarrow$ **Blueprint**.
3. Select the repository **`Documind-AI`**.
4. Render will automatically detect `render.yaml`, provision a managed database (`documind_db`), build the Docker container, and deploy your live public URL (e.g. `https://finpilot-ai.onrender.com`).

---

## 3. Option B: 1-Click Cloud Deployment via Railway

1. Log in to [Railway.app](https://railway.app) with GitHub.
2. Click **New Project** $\rightarrow$ **Deploy from GitHub repo** $\rightarrow$ Select `Documind-AI`.
3. Click **Add Service** $\rightarrow$ **Database** $\rightarrow$ **MySQL**.
4. Connect the database to the web service by setting `DATABASE_URL: ${{MySQL.DATABASE_URL}}`.
5. Railway detects the `Dockerfile` and deploys the production web server with SSL enabled.

---

## 4. Option C: Local / On-Premise Production Deployment via Docker Compose

To run the full production stack (Web Application + MySQL 8.0 database) locally or on a VPS:

```bash
# 1. Clone repository
git clone https://github.com/AnshX100/Documind-AI.git
cd Documind-AI

# 2. Build and run containers
docker-compose up --build -d

# 3. View live logs
docker-compose logs -f web

# 4. Access application
# Open browser to: http://localhost:5000
```

---

## 5. Required Environment Variables Reference

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `FLASK_APP` | Application entrypoint | `run.py` |
| `FLASK_ENV` | Runtime environment | `production` |
| `SECRET_KEY` | Cryptographic session key | Random 64-char string |
| `DATABASE_URL` | MySQL connection string | `mysql+pymysql://USER:PASS@HOST:3306/DB` |
| `UPLOAD_FOLDER` | Document storage directory | `uploads` |
| `MAX_CONTENT_LENGTH` | Max file upload size in bytes | `16777216` (16 MB) |
| `TESSERACT_CMD` | Custom Tesseract binary path | Empty (auto-detected on PATH) |
| `OCR_LANGUAGE` | OCR recognition dictionary | `eng` |
| `GOOGLE_CLIENT_ID` | Optional Google OAuth 2.0 ID | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Optional Google OAuth 2.0 Secret| From Google Cloud Console |
