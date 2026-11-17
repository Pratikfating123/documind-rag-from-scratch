# Backend (FastAPI)

See the [root README](../README.md) for full setup. Quick start (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit GROQ_API_KEY
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs · Tests: `pytest -v`
