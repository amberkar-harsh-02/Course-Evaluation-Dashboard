from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import docx
import io
import re
import fitz
import pandas as pd
import joblib
import wordninja

app = FastAPI(title="Course Evaluation OCR")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

try:
    classifier = joblib.load('comment_classifier.pkl')
    vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("✅ ML Gatekeeper loaded successfully.")
except Exception as e:
    print(f"⚠️ WARNING: ML Models not found. Run train_model.py first. Error: {e}")

# ==========================================
# THE HARD GATEKEEPER BLACKLISTS
# ==========================================
SQUISHED_BLACKLIST = {
    "needsimprovement", "excellent", "good", "fair", "poor",
    "stronglyagree", "agree", "neutral", "disagree", "stronglydisagree",
    "notapplicable", "na", "yes", "no", "quantitative", "qualitative", 
    "outstanding", "satisfactory", "unsatisfactory", "dna", "sd", "m", "n", 
    "reportcomments", "none", "verygood", "learningoutcomes", "assignments", 
    "duedates", "grading", "aboutright", "toomuch", "toolittle",
    "morethan", "lessthan", "to", "or", "-", "notevenneeded"
}

SUBSTRING_BLACKLIST = [
    "assess the clarity and helpfulness",
    "assess the timeliness",
    "for the number of credits",
    "how many hours per week",
    "please describe specific examples",
    "why were they effective",
    "if appropriate, please also describe",
    "instructor's organization",
    "instructor's effectiveness",
    "assess how this course expanded",
    "describe strengths or suggest ways",
    "students enrolled",
    "students responded",
    "response rate",
    "course evaluations"
]

REGEX_BLACKLIST = [
    r"^page\s+\d+\s+of\s+\d+",           
    r"^\d{2}-(spring|fall|winter)",      
    r"^(cst|chem)\s*\d+",                
    r"^\d+\s*\|",                        
    r"^\.?\d+\.?\d*%\s*\(?",             # Kills percentages like ".56% ()" or "78.26% |"
    r"^\d+$",
    # NEW: The Rubric Mashup Killer (Kills lines composed ENTIRELY of scale words)
    r"^(high|low|excellent|very good|good|fair|poor|outstanding|satisfactory|unsatisfactory|too much|too little|about right|neutral|strongly agree|agree|disagree|strongly disagree|n/a|na|\s)+$"
]

def sanitize_text(text):
    text = re.sub(r' +', ' ', text)
    text = text.replace('\x00', '')
    return text.strip()

def filter_meaningful_comments(text_list: list) -> str:
    final_results = []
    
    def unfuse_words(match):
        return " ".join(wordninja.split(match.group(0)))

    for t in text_list:
        clean_t = str(t).strip()
        if not clean_t or clean_t.lower() == 'nan': continue
        if re.match(r'^\d(\.\d+)?$', clean_t): continue
        
        # Disarm abbreviations so the sentence splitter doesn't chop them!
        clean_t = clean_t.replace("e.g.", "eg").replace("Dr.", "Dr").replace("Prof.", "Prof").replace("Mr.", "Mr").replace("Mrs.", "Mrs")
        
        # Strip survey prefixes
        clean_t = re.sub(r'^(Please provide.*?|Comments:? -?|Classroom activities.*?:|Class materials.*?:|Class assignments.*?:|Assess your.*?)\s*', '', clean_t, flags=re.IGNORECASE)
        
        potential_segments = re.split(r'(?<=[.!?])\s+|•\s*', clean_t)
        
        for segment in potential_segments:
            clean_segment = segment.strip()
            clean_segment = re.sub(r'^\d?\s*Subreport.*?Comment Rating\s*', '', clean_segment)
            clean_segment = re.sub(r'\b[1-9]\b', '', clean_segment)
            clean_segment = re.sub(r'\s+', ' ', clean_segment).strip()
            clean_segment = re.sub(r'[A-Za-z]{18,}', unfuse_words, clean_segment)
            
            # ==========================================
            # LAYER 2: NOISE DESTRUCTION
            # ==========================================
            text_lower = clean_segment.lower()
            squished_text = re.sub(r'[\s\-‐_\|]', '', text_lower)
            
            if not text_lower: continue
            if squished_text in SQUISHED_BLACKLIST: continue
            if any(bad in text_lower for bad in SUBSTRING_BLACKLIST): continue
            if any(re.match(pattern, text_lower) for pattern in REGEX_BLACKLIST): continue
            
            # THE EXECUTIONER: Kill any fragment under 4 words
            words = text_lower.split()
            if len(words) < 4:
                continue
            
            # ==========================================
            # LAYER 3: ML GATEKEEPER
            # ==========================================
            try:
                vec_text = vectorizer.transform([clean_segment])
                confidence = classifier.decision_function(vec_text)[0]
                
                if confidence > -0.8 or vec_text.nnz == 0:
                    clean_segment = re.sub(r'^Class assignments:\s*', '', clean_segment, flags=re.IGNORECASE)
                    final_results.append(clean_segment)  # No more "Comment: " prefix!
                    
            except Exception as e:
                print(f"Bypassing ML Gatekeeper due to error: {e}")
                final_results.append(clean_segment)

    # Remove duplicates while preserving list order
    seen = set()
    deduped_results = []
    for res in final_results:
        if res not in seen:
            deduped_results.append(res)
            seen.add(res)

    return "\n\n".join(deduped_results)

def extract_from_tabular(contents: bytes, filename: str) -> list:
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents), dtype=str, on_bad_lines='skip')
        else:
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
    except Exception as e:
        print(f"Error parsing tabular data: {e}")
        return []

    raw_texts = []
    for value in df.values.flatten():
        val_str = str(value).strip()
        if len(val_str) > 5 and not re.match(r'^[\d\W]+$', val_str) and val_str.lower() != 'nan':
            raw_texts.append(val_str)
            
    return raw_texts

@app.get("/")
async def roo():
    return {"message": "OCR api is running. Send a POST req to /api/extract-text"}

@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    raw_list = []
    filename = file.filename.lower()
    print(f"Processing: {filename}...")

    try:
        if filename.endswith('.docx'):
            content = await file.read()
            doc = docx.Document(io.BytesIO(content))
            raw_list = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            
        elif filename.endswith('.pdf'):
            content = await file.read()
            
            with fitz.open(stream=content, filetype="pdf") as pdf:
                for page in pdf:
                    text = page.get_text("text")
                    if text:
                        lines = text.split('\n')
                        current_sentence = ""
                        
                        for line in lines:
                            line = line.strip()
                            if not line: continue
                            
                            if current_sentence:
                                if not current_sentence[-1] in '.!?:' and line[0].islower():
                                    current_sentence += " " + line
                                else:
                                    raw_list.append(current_sentence)
                                    current_sentence = line
                            else:
                                current_sentence = line
                        
                        if current_sentence:
                            raw_list.append(current_sentence)
                        
        elif filename.endswith('.xlsx') or filename.endswith('.csv'):
            content = await file.read()
            raw_list = extract_from_tabular(content, filename)
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        processed_text = filter_meaningful_comments(raw_list)
        clean_final_text = sanitize_text(processed_text)

        print(f"✅ Success: {file.filename}")
        
        return {
            "filename": file.filename,
            "extracted_text": clean_final_text
        }

    except Exception as e:
        print(f"❌ Error processing {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)