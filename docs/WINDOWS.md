# Windows Setup and Troubleshooting

These instructions assume the project is at `C:\red-thread`.

## Prerequisites

- Windows 10/11.
- Python 3.12+ from <https://www.python.org/downloads/windows/>. Enable **Add Python to PATH**.
- Node.js 20+ from <https://nodejs.org/>.
- Optional: Tesseract OCR from <https://github.com/UB-Mannheim/tesseract/wiki>.
- Optional: Git for Windows.

Verify in PowerShell:

```powershell
py --version
node --version
npm --version
tesseract --version
```

## Backend setup

```powershell
cd C:\red-thread\backend
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-ocr.txt
Copy-Item .env.example .env
notepad .env
python -m uvicorn app.main:app --reload --port 8000
```

If you do not want to activate the environment, call the executables directly:

```powershell
C:\red-thread\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## Frontend setup

Open a second PowerShell window:

```powershell
cd C:\red-thread\frontend
npm install --include=dev
npm run dev
```

Open <http://localhost:5173>.

## Demo data and seed

Open a third PowerShell window:

```powershell
cd C:\red-thread
.\backend\.venv\Scripts\python.exe sample_data\generate_sample_data.py
.\backend\.venv\Scripts\python.exe scripts\seed_demo.py --include-benign
```

## Tests

```powershell
cd C:\red-thread\backend
.\.venv\Scripts\pytest.exe -q

cd C:\red-thread\frontend
npm run build
```

## Troubleshooting

### `Activate.ps1 cannot be loaded`

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This changes the policy only for the current PowerShell process.

### `python` opens the Microsoft Store

Use the Python launcher:

```powershell
py -3.12 -m venv .venv
```

Or disable **App Execution Aliases → python.exe/python3.exe** in Windows Settings.

### `tesseract` is not recognized

Install Tesseract, then set the full path in `backend\.env`:

```dotenv
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Restart the backend. Verify:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

### OCR returns no text

- Verify the language data (for example `eng.traineddata`).
- Use a high-contrast image.
- Check the `/api/health` response for `ocr_available`.
- Inspect the evidence metadata for `ocr_available` and the warning list.
- OCR is not ground truth; inspect the original image.

### `npm` is not recognized

Reinstall Node.js with the npm component, reopen PowerShell, and verify `node --version` and
`npm --version`.

### Port 8000 is already in use

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

Then update the Vite proxy target in `frontend/vite.config.ts` or set
`VITE_API_BASE_URL=http://127.0.0.1:8001/api`.

### CORS error

Add the frontend origin to `RED_THREAD_CORS_ORIGINS`:

```dotenv
RED_THREAD_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Restart the backend.

### SQLite database or evidence path issues

Use absolute paths in `backend\.env` if relative paths are confusing:

```dotenv
RED_THREAD_DATA_DIR=C:\red-thread\data
RED_THREAD_REPORTS_DIR=C:\red-thread\reports
```

### PDF parsing fails

Confirm `pdfplumber` is installed in the active environment:

```powershell
python -c "import pdfplumber; print(pdfplumber.__version__)"
```

### `esbuild` install script blocked

If npm reports that an install script was blocked:

```powershell
npm install-scripts approve esbuild
npm install --include=dev
```

### Long path errors

Place the project at `C:\red-thread` or enable long path support in Windows.

### The frontend shows an AI-disabled state

That is expected without `COMMANDCODE_API_KEY` or `TOKENHARBOR_API_KEY`. The deterministic
pipeline still works. Add a key to `backend\.env`, restart the backend, and reload the page.

### The AI provider returns 401 or 403

- Confirm the key is in `backend\.env`, not a frontend file.
- CommandCode API access requires a plan other than Go.
- Confirm the model ID matches the configured provider.
- Never commit the key.

### The AI provider rate-limits or times out

Red Thread retries transient failures and reports a clear error. No fabricated answer is generated.
Try again later or continue with the deterministic workflow.
