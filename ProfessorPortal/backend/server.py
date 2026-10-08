from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uvicorn
import json
from datetime import datetime, timedelta
import bcrypt
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Import your database setup from models.py
from models import SessionLocal, Professor, CourseEvaluation

# Load environment variables
load_dotenv()

# --- Security Configuration ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is missing!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

security = HTTPBearer()

# --- Authentication Utilities ---
def verify_password(plain_password: str, hashed_password: str):
    # Bcrypt requires bytes, so we encode the strings to utf-8 first
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str):
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8') # Decode back to string for database storage

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_logged_in_prof(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        # Try to decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        prof_id_str = payload.get("sub")
        
        if prof_id_str is None:
            raise HTTPException(status_code=401, detail="Auth Error: Token payload is missing the user ID.")
            
        prof_id = int(prof_id_str) # Convert the string back to an integer for the database!
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Auth Error: Your session expired. Please log in again.")
        
    except Exception as e:
        # 🟢 If it fails for ANY other reason, send the exact Python error to the frontend!
        print(f"❌ JWT DECODE ERROR: {type(e).__name__} - {str(e)}")
        raise HTTPException(status_code=401, detail=f"Auth Error: {str(e)}")
    
    professor = db.query(Professor).filter(Professor.id == prof_id).first()
    if professor is None:
        raise HTTPException(status_code=401, detail="Auth Error: User account no longer exists in the database.")
        
    return professor

# --- Startup Event (Modern Lifespan approach) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs when the server starts up
    db = SessionLocal()
    prof = db.query(Professor).filter(Professor.email == "professor@csumb.edu").first()
    if not prof:
        dummy_prof = Professor(
            email="professor@csumb.edu",
            hashed_password=get_password_hash("password123"),
            name="Dr. Ramachandran"
        )
        db.add(dummy_prof)
        db.commit()
        print("🟢 Created test account: professor@csumb.edu / password123")
    db.close()
    yield
    # Anything after yield runs when the server shuts down

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

# --- API Routes ---
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    prof = db.query(Professor).filter(Professor.email == req.email).first()
    if not prof or not verify_password(req.password, prof.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": str(prof.id)})
    return {"access_token": access_token, "name": prof.name}

@app.post("/api/upload-report")
async def upload_report(file: UploadFile = File(...), prof: Professor = Depends(get_logged_in_prof), db: Session = Depends(get_db)):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are accepted")
    
    contents = await file.read()
    try:
        report_data = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file format")

    course_id = report_data.get("course_id", "Unknown Course")
    overall_score = report_data.get("overall_score", 0.0)

    parts = course_id.split('_')
    if len(parts) >= 3:
        course_name = f"{parts[0]} {parts[1]}"
        term = parts[2]
    else:
        course_name = course_id
        term = "Imported"

    new_eval = CourseEvaluation(
        professor_id=prof.id,
        course_name=course_name,
        term=term,
        overall_score=overall_score,
        report_data=report_data
    )
    db.add(new_eval)
    db.commit()
    db.refresh(new_eval)

    return {"message": "Report saved successfully to database", "evaluation_id": new_eval.id}

@app.get("/api/history")
def get_history(prof: Professor = Depends(get_logged_in_prof), db: Session = Depends(get_db)):
    evals = db.query(CourseEvaluation).filter(CourseEvaluation.professor_id == prof.id).all()
    history = []
    for e in evals:
        history.append({
            "id": e.id,
            "course": e.course_name,
            "term": e.term,
            "date": "Recently Uploaded", 
            "score": e.overall_score,
            "status": "Complete",
            "institution": "California State University, Monterey Bay (CSUMB)"
        })
    return history

@app.get("/api/report/{eval_id}")
def get_report(eval_id: int, prof: Professor = Depends(get_logged_in_prof), db: Session = Depends(get_db)):
    evaluation = db.query(CourseEvaluation).filter(CourseEvaluation.id == eval_id, CourseEvaluation.professor_id == prof.id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"data": evaluation.report_data}

if __name__ == "__main__":
    print("Starting Professor Portal Backend on http://localhost:8080...")
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)