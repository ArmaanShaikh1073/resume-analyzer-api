import os
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any
import uvicorn

from app.config import settings
from app.services.extractor import extract_text_from_resume
from app.services.analyzer import analyze_resume
from app.services.jd_matcher import compare_resume_jd

app = FastAPI(
    title="Resume Analyzer API",
    description="API for analyzing resumes using Gemini AI",
    version="0.1.0"
)

# Configure CORS to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Resume Analyzer API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/analyze-resume")
async def analyze_resume_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a resume and get AI analysis feedback
    """
    # Validate file type
    allowed_extensions = [".pdf", ".docx", ".doc", ".txt"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Create unique filename
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Save the uploaded file temporarily
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Extract text from resume
        resume_text = extract_text_from_resume(file_path)
        
        # Analyze resume using Gemini
        analysis_result = analyze_resume(resume_text)
        
        # Schedule file cleanup
        background_tasks.add_task(os.remove, file_path)
        
        return JSONResponse(content=analysis_result)
        
    except Exception as e:
        # Clean up file in case of error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/compare-resume-job")
async def compare_resume_job_endpoint(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(...),
    job_description: UploadFile = File(...),
):
    """
    Upload a resume and job description to get match analysis
    """
    # Validate file types
    allowed_extensions = [".pdf", ".docx", ".doc", ".txt"]
    resume_ext = os.path.splitext(resume.filename)[1].lower()
    jd_ext = os.path.splitext(job_description.filename)[1].lower()
    
    if resume_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Resume file type not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
        
    if jd_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Job description file type not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Create unique filenames
        resume_filename = f"resume_{uuid.uuid4()}{resume_ext}"
        jd_filename = f"jd_{uuid.uuid4()}{jd_ext}"
        
        resume_path = os.path.join(settings.UPLOAD_DIR, resume_filename)
        jd_path = os.path.join(settings.UPLOAD_DIR, jd_filename)
        
        # Save the uploaded files temporarily
        resume_contents = await resume.read()
        with open(resume_path, "wb") as f:
            f.write(resume_contents)
            
        jd_contents = await job_description.read()
        with open(jd_path, "wb") as f:
            f.write(jd_contents)
        
        # Extract text from both files
        resume_text = extract_text_from_resume(resume_path)
        jd_text = extract_text_from_resume(jd_path)
        
        # Compare resume with job description using Gemini
        comparison_result = compare_resume_jd(resume_text, jd_text)
        
        # Schedule file cleanup
        background_tasks.add_task(os.remove, resume_path)
        background_tasks.add_task(os.remove, jd_path)
        
        return JSONResponse(content=comparison_result)
        
    except Exception as e:
        # Clean up files in case of error
        if 'resume_path' in locals() and os.path.exists(resume_path):
            os.remove(resume_path)
        if 'jd_path' in locals() and os.path.exists(jd_path):
            os.remove(jd_path)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)