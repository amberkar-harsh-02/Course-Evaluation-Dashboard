import logging

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

import extractors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ocr")

app = FastAPI(title="Course Evaluation OCR")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "OCR api is running. Send a POST req to /api/extract-text"}


@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Extract whole student responses (with their survey question) and rating tables from an upload.

    `extracted_text` (responses joined by blank lines) is kept for older clients.
    """
    logger.info("Processing %s", file.filename)
    content = await file.read()
    try:
        result = extractors.extract(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Extraction failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Could not read {file.filename}: {exc}")

    logger.info(
        "%s: parser=%s responses=%d rating tables=%d warnings=%d",
        file.filename, result["parser"], len(result["responses"]), len(result["quantitative"]), len(result["warnings"]),
    )
    return {
        "filename": file.filename,
        "parser": result["parser"],
        "responses": result["responses"],
        "quantitative": result["quantitative"],
        "warnings": result["warnings"],
        "extracted_text": "\n\n".join(r["text"] for r in result["responses"]),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
