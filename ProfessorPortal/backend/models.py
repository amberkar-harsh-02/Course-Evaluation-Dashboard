from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is missing!")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Professor(Base):
    __tablename__ = "professors"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)

    # Sets up the relationship to the evaluations table
    evaluations = relationship("CourseEvaluation", back_populates="professor")

class CourseEvaluation(Base):
    __tablename__ = "course_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    professor_id = Column(Integer, ForeignKey("professors.id"), nullable=False)
    course_name = Column(String, nullable=False)
    term = Column(String, nullable=False)
    overall_score = Column(Float, nullable=True)
    
    report_data = Column(JSONB, nullable=False)

    professor = relationship("Professor", back_populates="evaluations")

# This creates the tables in PostgreSQL if they don't exist yet
Base.metadata.create_all(bind=engine)