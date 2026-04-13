from fastapi import FastAPI, HTTPException, UploadFile, File

import docx
import io

app = FastAPI(title="Course Evaluation OCR")

@app.get("/")
async def roo():
    return {"message": "OCR api is running. Send a POST req to /api/extract-text"}

@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):

    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code =400, detail="Only .docx files are supported!")
    
    try:
        content = await file.read()
        doc = docx.Document(io.BytesIO(content))

        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())

        final_text = "\n".join(full_text)

        return {"filename": file.filename, "extracted_text": final_text}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")