# ASTE PlagChecker

ASTE PlagChecker is a locally hosted document review system for plagiarism/reference matching and experimental AI-writing indicators. It provides document upload, reference comparison, review certificates, and administration tools.

The AI-writing score is a model estimate, not proof of authorship. It can be wrong and should not be used by itself to make academic or disciplinary decisions. Reference matches describe similarity to the configured reference collection; they are not AI-authorship evidence.

Project guide: Sqn Ldr Soham Sinha

Team lead: Fg Offr Krunal Nitin Badgujar

Deputy team lead: Fg Offr Gaurav Chauhan
Members -
Fg Offr Abha Ghildiyal
Fg Offr Prabhaditya Singh
Fg Offr Anjali Dabral
Fg Offr Farheen Khanam
Fg Offr Aman Joshi
Fg Offr Yugraj
Fg Offr Vansh Kadian
Fg Offr Pradyumn Kumar Yadav

## What you need

-Generate and Replace Secret Key into .env Using command in CMD or terminal
python -c "import secrets; print(secrets.token_hex(32))".

- Git and Git LFS (the model weights are large LFS files).
- Python 3.12 recommended. The local AI classifier was packaged with Python 3.12.
- Node.js 20 LTS and npm.
- PostgreSQL 16 with the pgvector server extension installed.
- Enough disk space for the Python environment, database, uploads, and local model weights. PyTorch and model files are large.

The application can run its inference locally without calling a hosted model service. Installing dependencies and obtaining this repository's Git LFS model files may require a network connection. For a fully disconnected deployment, prepare the Python wheels, npm package cache, Git LFS files, and NLTK tokenizer data on a compatible connected machine first.

## 1. Get the project and model files

Clone the repository and fetch its large model files:

```sh
git lfs install
git clone --branch Final-KNB https://github.com/KNB311/ASTE-PlagChecker.git
cd ASTE-PlagChecker
git lfs pull
```

If you already have the repository, run `git lfs pull` from its root. Verify that model weights are actual files rather than small Git LFS pointer text files. Required local model directories are:

```text
models/Qwen3-0.6B-Base/
models/ai-text-detector-modernbert/
```

The repository also includes BGE embedding models used by model-comparison tools. Keep these directories in place when using those tools.

## 2. Install and prepare PostgreSQL

Install PostgreSQL and the pgvector extension for your PostgreSQL version using your operating system's package instructions. The extension's server package must be installed before running the SQL below.

Connect as a PostgreSQL administrator, then create the application database, user, and vector extension:

```sql
CREATE USER aste_app WITH PASSWORD 'replace-with-a-strong-local-password';
CREATE DATABASE aste_plagchecker OWNER aste_app;
\connect aste_plagchecker
CREATE EXTENSION IF NOT EXISTS vector;
```

If you use an existing database or user, adjust the connection details in the next step. The migration history creates the application tables; it does not install PostgreSQL or pgvector itself.

## 3. Configure the backend

Open a terminal at the repository root and create the Python environment:

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Create `backend/.env` (do not commit it) with your database connection and fresh secrets:

```dotenv
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+psycopg://aste_app:replace-with-a-strong-local-password@127.0.0.1:5432/aste_plagchecker

UPLOAD_DIR=../uploads
MODEL_DIR=../models
EMBEDDING_MODEL_PATH=../models/Qwen3-0.6B-Base
EMBEDDING_DIMENSION=1024

SECRET_KEY=replace-with-a-long-random-secret
RESPONSE_ENCRYPTION_KEY=replace-with-a-url-safe-base64-key
ACCESS_TOKEN_EXPIRE_MINUTES=60

AI_SOURCE_TYPE=DUMMY_LLAMA
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:4b
```

Generate secret values locally; do not reuse the example values:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Use the first output for `SECRET_KEY` and the second for `RESPONSE_ENCRYPTION_KEY`. The encryption key must decode to exactly 32 bytes. Keep `.env` private and back up the encryption key securely; data encrypted with it cannot be decrypted if it is lost.

The settings file is read relative to the backend working directory. Run backend commands from `backend/` as shown below. The defaults point to the model folders in the repository root and uploads in `uploads/`.

## 4. Prepare local-only text processing and model registration

Sentence splitting uses NLTK's `punkt_tab` data. Prepare it once while connected:

```sh
python -c "import nltk; nltk.download('punkt_tab')"
```

In an offline deployment, copy the resulting NLTK data directory to that machine and set `NLTK_DATA` to its path before starting the API.

Run the database migrations:

```sh
alembic upgrade head
```

Register the included local embedding model and AI-writing classifier in the database:

```sh
python -m app.scripts.register_embedding_model
python -m app.scripts.register_local_ai_classifier
```

These scripts use the model paths inside this checkout. They do not download model weights.

The database migration creates the role table but does not insert the initial roles. Add them once, using `psql` connected to `aste_plagchecker`:

```sql
INSERT INTO roles (role_name, description)
VALUES
  ('ADMIN', 'System administrator'),
  ('INSTRUCTOR', 'Instructor'),
  ('STUDENT_OFFICER', 'Student officer')
ON CONFLICT (role_name) DO NOTHING;
```

Create the first administrator interactively (the password is entered without echoing):

```sh
python -m app.scripts.create_admin
```

## 5. Start the backend and frontend

Keep the backend virtual environment activated. From `backend/`, start the API:

```sh
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root, install the locked frontend dependencies and start Vite:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The API is available at <http://127.0.0.1:8000>, and interactive API documentation is at <http://127.0.0.1:8000/docs>. Vite proxies API requests to port 8000. If you change the API port, set `VITE_BACKEND_URL` for the frontend or update `frontend/vite.config.ts`.

Sign in with the administrator account created above. Add other accounts and roles through the administration screens.

## Managing reference documents

Administrators can upload reference files and re-index them from **Manage Database → Manage Documents**. Use **Delete** to remove a reference from future matching. Deletion is a soft removal: the document's file and version history are retained for audit purposes, while it is excluded from active reference searches. Previously completed scan reports are not rewritten.

Administrators can change the plagiarism comparison model from **Plagiarism Model**. Compatible sentence-embedding models in the configured `models` directory are discovered automatically. Changing models generates embeddings for the reference sentences before activating the new selection.

## Offline installation

The application loads its embedding and classifier models from local directories, and model inference uses local-only loading. A connected machine is needed only to obtain dependencies, model files, and NLTK data unless your organization provides them through an internal mirror.

To prepare Python packages for an offline machine, download wheels on a machine matching its operating system, CPU architecture, and Python version:

```sh
python -m pip download --dest wheelhouse -r backend/requirements.txt
```

Transfer `wheelhouse/` to the offline machine and install from it:

```sh
python -m pip install --no-index --find-links=wheelhouse -r backend/requirements.txt
```

Also transfer this repository's Git LFS model files and prepared NLTK data. For the frontend, run `npm ci` while connected or prepare and transfer an npm cache/package mirror before disconnecting.

Ollama is not needed for the local embedding model or classifier. Features that call the configured local Ollama service require Ollama to be installed separately, the configured model to be available locally, and the service to be running at `OLLAMA_BASE_URL`.

## Useful checks

Run these commands from their respective directories:

```sh
# backend (with the backend virtual environment activated)
cd backend
python -m unittest test_ai_detector_result_service
```

```sh
# frontend
cd frontend
npm run build
```

Health checks:

- `GET /health` — API process.
- `GET /health/database` — PostgreSQL connection.
- `GET /health/vector` — pgvector extension.
- `GET /health/schema` — migrated tables.

## Troubleshooting

- **`pgvector`/`vector` errors:** Install the PostgreSQL pgvector server extension, enable it in the application database, then rerun `alembic upgrade head`.
- **Model not found:** Confirm `git lfs pull` completed and the local directories listed above contain real weight files. Re-run the relevant model registration script after correcting the path.
- **Database connection refused:** Check that PostgreSQL is running, the database exists, and the credentials in `backend/.env` match.
- **Login or role setup fails:** Insert the initial roles before running `python -m app.scripts.create_admin`.
- **NLTK `punkt_tab` error while offline:** Prepare the corpus while connected or transfer the NLTK data directory and set `NLTK_DATA`.
- **Frontend API requests fail:** Start the backend on port 8000, or configure `VITE_BACKEND_URL` to match its address.

## Project layout

```text
backend/
  app/
    api/                 FastAPI endpoints
    core/                Settings, security, encryption
    db/                  SQLAlchemy database setup
    models/              Database models
    scripts/             Setup and maintenance commands
    services/            Scanning, matching, models, certificates
  migrations/            Alembic database migrations
  requirements.txt       Python dependencies
frontend/
  src/                   React and TypeScript application
  package.json           Frontend dependencies and scripts
  package-lock.json      Reproducible npm dependency lock
models/                  Local embedding and classifier weights
uploads/                 Local uploaded documents (created at runtime)
```
