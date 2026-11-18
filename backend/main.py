
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import os

load_dotenv()

app = FastAPI(
    title="Intelligent Bug Diagnosis Platform",
    description="Bug Submission API - Milestone 1",
    version="1.0.0"
)

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL")

collection = None

if MONGODB_URL:
    try:
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client["bug_diagnosis_db"]
        collection = db["bug_reports"]
        print("MongoDB connected successfully!")
    except Exception as error:
        print("MongoDB connection failed:", error)

# Local fallback for testing when MongoDB is not configured
local_bug_reports = []

# Folder for uploaded files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def home():
    return FileResponse(
        Path(__file__).parent / "static" / "index.html"
    )


@app.get("/health")
def health():
    return {
        "message": "Backend is running",
        "status": "Running"
    }

@app.post("/bugs")
async def submit_bug(
    title: str = Form(...),
    description: str = Form(...),
    severity: str = Form("Medium"),
    error_log: str = Form(""),
    stack_trace: str = Form(""),
    file: UploadFile | None = File(None)
):
    # Validate required fields
    if not title.strip() or not description.strip():
        raise HTTPException(
            status_code=400,
            detail="Title and description are required."
        )

    # Validate severity
    allowed_severities = ["Low", "Medium", "High", "Critical"]

    if severity not in allowed_severities:
        raise HTTPException(
            status_code=400,
            detail="Invalid severity level."
        )

    file_path = None

    # Handle optional file upload
    if file and file.filename:
        allowed_extensions = {".txt", ".log", ".py", ".json", ".pdf"}

        extension = Path(file.filename).suffix.lower()

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type."
            )

        content = await file.read()

        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File size must not exceed 5 MB."
            )

        safe_filename = f"{uuid4().hex}{extension}"
        saved_path = UPLOAD_DIR / safe_filename
        saved_path.write_bytes(content)
        file_path = str(saved_path)

    # Create bug report
    bug_report = {
        "bug_id": str(uuid4()),
        "title": title.strip(),
        "description": description.strip(),
        "severity": severity,
        "error_log": error_log,
        "stack_trace": stack_trace,
        "file_path": file_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "Submitted"
    }

    # Store in MongoDB or temporary local memory
    try:
        if collection is not None:
            collection.insert_one(bug_report.copy())
        else:
            local_bug_reports.append(bug_report.copy())
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not store the bug report."
        )

    return {
        "message": "Bug report submitted successfully!",
        "bug_report": bug_report
    }

@app.get("/bugs")
def get_bug_reports():
    if collection is not None:
        reports = list(collection.find({}, {"_id": 0}))
        return {"total": len(reports), "bug_reports": reports}

    return {
        "total": len(local_bug_reports),
        "bug_reports": local_bug_reports
    }

