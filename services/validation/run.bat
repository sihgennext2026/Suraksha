@echo off
REM Document Validation Service — backend API only
cd /d "%~dp0"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt -q

echo.
echo Starting Document Validation Service (API only) on http://0.0.0.0:8000
echo API docs: http://localhost:8000/docs
echo CLI:      python evaluate.py --document-type driving_license
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
