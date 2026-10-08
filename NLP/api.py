from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import time
import os
import json
import requests
import zipfile
from io import BytesIO
from datetime import datetime
from pathlib import Path

# Import your pipeline
from main import analysis_pipeline

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Define local directory paths
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "saved_inputs"
RESULT_DIR = BASE_DIR / "saved_results"
HISTORY_FILE = BASE_DIR / "history.json"

# Ensure directories exist
INPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# Helper to read/write batch history
def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(history_data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2)

@app.post("/api/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    model_choice: str = Form("local")
):
    start_time = time.time()
    filename = file.filename
    course_id = Path(filename).stem
    current_date = datetime.now().strftime("%m-%d-%Y")
    
    # 1. Save raw file permanently to local storage
    saved_file_path = INPUT_DIR / filename
    try:
        with open(saved_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        # Log failure in history
        history = load_history()
        history.append({
            "filename": filename,
            "course_id": course_id,
            "date": current_date,
            "runtime_seconds": 0.0,
            "status": f"Save Failed: {str(e)}"
        })
        save_history(history)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # 2. Extract text by calling your local OCR server
    extracted_text = ""
    try:
        # Re-open the saved file to send it to the OCR endpoint
        with open(saved_file_path, "rb") as f:
            ocr_response = requests.post(
                "http://127.0.0.1:8000/api/extract-text",
                files={"file": (filename, f)}
            )
        ocr_response.raise_for_status()
        ocr_data = ocr_response.json()
        extracted_text = ocr_data.get("extracted_text", "")
    except Exception as e:
        # Log failure in history
        history = load_history()
        history.append({
            "filename": filename,
            "course_id": course_id,
            "date": current_date,
            "runtime_seconds": round(time.time() - start_time, 2),
            "status": f"OCR Failed: {str(e)}"
        })
        save_history(history)
        raise HTTPException(status_code=502, detail=f"OCR Server communication failed: {str(e)}")

    # 3. Clean up the extracted text into comments
    raw_comments = [line.strip() for line in extracted_text.split('\n') if len(line.strip()) > 10]
    
    # 4. Run the pipeline and save the results permanently
    try:
        analysis_data = analysis_pipeline(
            course_id=course_id,
            raw_comments=raw_comments,
            output_dir=RESULT_DIR,
            write_files=True,  # Save the file permanently in results
            model_choice=model_choice
        )
        
        runtime = round(time.time() - start_time, 2)
        
        # Log successful run in history
        history = load_history()
        history.append({
            "filename": filename,
            "course_id": course_id,
            "date": current_date,
            "runtime_seconds": runtime,
            "status": "Success"
        })
        save_history(history)
        
        return {
            "status": "success",
            "time_taken": runtime,
            "data": analysis_data
        }
        
    except Exception as e:
        # Log pipeline failure
        runtime = round(time.time() - start_time, 2)
        history = load_history()
        history.append({
            "filename": filename,
            "course_id": course_id,
            "date": current_date,
            "runtime_seconds": runtime,
            "status": f"Pipeline Failed: {str(e)}"
        })
        save_history(history)
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {str(e)}")

# 5. Endpoint to get processing history
@app.get("/api/history")
async def get_history():
    return load_history()

# 6. Endpoint to export selected evaluations as a ZIP file
class ZipDownloadRequest(BaseModel):
    course_ids: list[str]

@app.post("/api/download-zip")
async def download_zip(req: ZipDownloadRequest):
    if not req.course_ids:
        raise HTTPException(status_code=400, detail="No course IDs selected")
        
    # Create an in-memory ZIP file
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        files_added = 0
        for cid in req.course_ids:
            # Locate the permanently saved JSON results file
            # Based on how main.py saves: {course_id}_COMBINED_REPORT.json
            json_file = RESULT_DIR / f"{cid}_COMBINED_REPORT.json"
            if json_file.exists():
                zip_file.write(json_file, arcname=f"{cid}_Evaluation_Data.json")
                files_added += 1
                
        if files_added == 0:
            raise HTTPException(status_code=404, detail="No matching result files found to package")
            
    # Position buffer at the beginning for reading
    zip_buffer.seek(0)
    
    # Save the temporary ZIP locally so we can stream it back
    temp_zip_path = BASE_DIR / "temp_export.zip"
    with open(temp_zip_path, "wb") as f:
        f.write(zip_buffer.getvalue())
        
    return FileResponse(
        path=temp_zip_path,
        media_type="application/x-zip-compressed",
        filename="course_evaluations_export.zip"
    )
@app.get("/api/download/{course_id}")
async def download_single(course_id: str):
    json_file = RESULT_DIR / f"{course_id}_COMBINED_REPORT.json"
    if not json_file.exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(
        path=json_file,
        media_type="application/json",
        filename=f"{course_id}_Evaluation_Data.json"
    )

# 8. Endpoint to clear history
@app.delete("/api/history")
async def clear_history():
    save_history([])
    return {"status": "success", "message": "History cleared"}


if __name__ == "__main__":
    print("Starting Backend Bridge on http://localhost:8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)