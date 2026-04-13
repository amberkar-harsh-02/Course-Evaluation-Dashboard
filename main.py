from fastapi import FastAPI, HTTPException, UploadFile, File

import docx
import pdfplumber
import io
import re

app = FastAPI(title="Course Evaluation OCR")

def sanitize_text(text):
    text = re.sub(r'\n+', '\n', text)

    text = re.sub(r' +', ' ', text)

    text = text.replace('\x00', '')
    return text.strip()

@app.get("/")
async def roo():
    return {"message": "OCR api is running. Send a POST req to /api/extract-text"}

@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    if file.filename.endswith('.docx'):
        try:
            content = await file.read()
            doc = docx.Document(io.BytesIO(content))
            full_text = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            raw_text = "\n".join(full_text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading DOCX: {str(e)}")
        
    elif file.filename.endswith('.pdf'):
        try:
            content = await file.read()
            full_text = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text.strip():
                        full_text.append(text.strip())
            raw_text = "\n".join(full_text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported!")
    clean_text = sanitize_text(raw_text)

    return {
        "filename": file.filename,
        "extracted_text": clean_text
    }