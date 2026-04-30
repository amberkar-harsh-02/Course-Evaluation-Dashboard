from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import docx
import pdfplumber
import io
import re
import pandas as pd
import joblib
import wordninja

app = FastAPI(title="Course Evaluation OCR")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# We load this once when the server starts so it's blazing fast for every file
try:
    classifier = joblib.load('comment_classifier.pkl')
    vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("✅ ML Gatekeeper loaded successfully.")
except Exception as e:
    print(f"⚠️ WARNING: ML Models not found. Run train_model.py first. Error: {e}")

def sanitize_text(text):
    text = re.sub(r' +', ' ', text)
    text = text.replace('\x00', '')
    return text.strip()

def filter_meaningful_comments(text_list: list) -> str:
    # 1. Filter out stray rating numbers BEFORE gluing the PDF lines together
    valid_lines = []
    for t in text_list:
        clean_t = str(t).strip()
        
        # Skip empty lines or 'nan'
        if not clean_t or clean_t.lower() == 'nan':
            continue
            
        if re.match(r'^\d(\.\d+)?$', clean_t):
            continue
            
        valid_lines.append(clean_t)

    # Now glue the cleaned lines together
    raw_blob = " ".join(valid_lines)
    
    # 2. Split the massive blob into distinct sentences using punctuation 
    potential_segments = re.split(r'(?<=[.!?])\s+', raw_blob)
    
    final_results = []
    
    def unfuse_words(match):
        # wordninja.split takes "Theinstructortakes" and returns ["The", "instructor", "takes"]
        return " ".join(wordninja.split(match.group(0)))
    
    for segment in potential_segments:
        clean_segment = segment.strip()
        
        # Clean up any "Subreport" headers
        clean_segment = re.sub(r'^\d?\s*Subreport.*?Comment Rating\s*', '', clean_segment)
        
        # Pluck out isolated single digits
        clean_segment = re.sub(r'\b[1-9]\b', '', clean_segment)
        clean_segment = re.sub(r'\s+', ' ', clean_segment).strip()
        
        clean_segment = re.sub(r'[A-Za-z]{18,}', unfuse_words, clean_segment)
        
        if len(clean_segment.split()) < 4:
            continue
            
        try:
            vec_text = vectorizer.transform([clean_segment])
            prediction = classifier.predict(vec_text)[0]
            
            if prediction == 1:
                final_results.append(f"Comment: {clean_segment}")
        except:
            final_results.append(f"Comment (Unfiltered): {clean_segment}")

    return "\n\n".join(final_results)

def extract_from_tabular(contents: bytes, filename: str) -> list:
    if filename.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))
        
    best_col = None
    max_score = 0
    
    # Smart Detection: Look for columns with long, unique sentences
    for col in df.columns:
        col_data = df[col].dropna().astype(str)
        if col_data.empty: 
            continue
        
        avg_len = col_data.apply(len).mean()
        # Calculate how unique the data is (boilerplate repeats, comments are 100% unique)
        unique_ratio = len(col_data.unique()) / len(col_data)
        
        score = avg_len * unique_ratio
        
        if score > max_score:
            max_score = score
            best_col = col
                
    if not best_col:
        raise ValueError("Could not detect a comments column in this spreadsheet.")
        
    return df[best_col].dropna().astype(str).tolist()

@app.get("/")
async def roo():
    return {"message": "OCR api is running. Send a POST req to /api/extract-text"}

@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    raw_list = []
    filename = file.filename.lower()

    try:
        if filename.endswith('.docx'):
            content = await file.read()
            doc = docx.Document(io.BytesIO(content))
            raw_list = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            
        elif filename.endswith('.pdf'):
            content = await file.read()
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        # Split PDF text by newlines initially to feed the text_list
                        lines = text.split('\n')
                        raw_list.extend([line.strip() for line in lines if line.strip()])
                        
        elif filename.endswith('.xlsx') or filename.endswith('.csv'):
            content = await file.read()
            raw_list = extract_from_tabular(content, filename)
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        # Send the raw data through the AI Gatekeeper
        processed_text = filter_meaningful_comments(raw_list)
        clean_final_text = sanitize_text(processed_text)

        return {
            "filename": file.filename,
            "extracted_text": clean_final_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))