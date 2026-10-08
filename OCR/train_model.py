import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import joblib

# 1 = Real Student Comment
# 0 = Administrative Noise / Boilerplate
data = [
    # ==========================================
    # NOISE (0) : SPECIFIC PDF SURVEY QUESTIONS
    # ==========================================
    ("instructor's organization and effective use of class time (or online environment) to facilitate your learning:", 0),
    ("Assess the clarity and helpfulness of your instructor's feedback/comments on assignments:", 0),
    ("Assess the timeliness of your instruc- tor's feedback on assignments:", 0),
    ("instructor's effectiveness in encouraging respect for different per- spectives and backgrounds:", 0),
    ("instructor's overall effec- tiveness in facilitating your learning:", 0),
    ("Assess how this course expanded your knowledge, understanding, and/or skills:", 0),
    ("For the number of credits, the workload in this class was:", 0),
    ("How many hours per week did you spend on this class outside of scheduled class/lab meeting time?", 0),
    ("Please describe specific examples in each of the following categories that were particularly effective in helping you fulfill the course learning outcomes and increase your understanding, knowledge, and/or skills.", 0),
    ("Why were they effective?", 0),
    ("If appropriate, please also describe examples that were less effective in helping you learn, and explain how they could be improved.", 0),
    ("You may describe strengths or suggest ways your instructor could improve the learning experience: -", 0),
    ("- Class assignments:", 0),
    ("Classroom activities (e.g. discussions, group activities, lectures, presentations):", 0),
    ("Class materials (e.g., textbooks, handouts, readings, videos, web resources):", 0),
    
    # ==========================================
    # NOISE (0) : EXCEL/CSV COLUMN HEADERS & DATA
    # ==========================================
    ("Course organization and structure", 0),
    ("Pace and workload", 0),
    ("Course materials / clarity", 0),
    ("Teaching effectiveness / instructor skill", 0),
    ("Global Aspects Aspect Score", 0),
    ("Questions focused on Instructor", 0),
    ("To What Extent Do You Feel That:", 0),
    ("Subject interest before course", 0),
    ("Difficulty (relative to other courses)", 0),
    ("Report Comments", 0),
    ("Please find your Instructor Summary Report below.", 0),
    ("Invited Count 308", 0),
    ("Response Count 226", 0),
    ("Response Ratio 73.38%", 0),
    ("CST 311 (02): Intro to Computer Networks", 0),
    ("26-Spring | Cao Thang Bui", 0),
    
    # ==========================================
    # NOISE (0) : MULTIPLE CHOICE SCALES & REPEATING HEADER ARTIFACTS
    # ==========================================
    ("About right", 0),
    ("Too much", 0),
    ("Too little", 0),
    ("More than", 0),
    ("Less than", 0),
    ("Needs improve- ment", 0),
    ("Needs improvement", 0),
    ("Unsatisfacto ry", 0),
    ("Unsatisfactory", 0),
    ("Outstandi ng", 0),
    ("Outstanding", 0),
    ("Satisfactor y", 0),
    ("Satisfactory", 0),
    ("Very Good", 0),
    ("Improvem ent", 0),
    ("Learning outcomes", 0),
    ("Due dates", 0),
    ("Grading", 0),
    ("1 - Too Slow, 2 - About Right, 3 - Too Much", 0),
    ("1 - Very Low or Never, 3 - Low or Infrequently, 5 - Average, 7 - High or Frequently, 9 - Very High or Always", 0),
    ("0% (0)", 0),
    ("50% ()", 0),
    (".56% ()", 0),
    ("23 |", 0),
    ("18 |", 0),
    ("to", 0),
    ("or", 0),
    ("-", 0),
    # NEW: OCR Rubric Header Mashups
    ("High High High High Too Much Excellent Excellent Excellent Excellent Excellent", 0),
    ("Good Good Good Fair Fair Fair Poor Poor", 0),
    ("Outstanding Outstanding Satisfactory Satisfactory", 0),
    ("Strongly Agree Agree Neutral Disagree Strongly Disagree", 0),

    # ==========================================
    # COMMENTS (1) : HIGHLY SPECIFIC CS/CHEM FEEDBACK
    # ==========================================
    ("Only thing I would change is if the professor Bui would stop reading directly off of the slides, and make the class a bit more engaging", 1),
    ("He always make sure that all confusion is gone before completing any interaction with a student", 1),
    ("Doesn't give feedback on programming assignments.", 1),
    ("I enjoy the wireshark scavenger hunts, and the hands-on learning experiences with the programming assignments that create a server and client.", 1),
    ("I think that the classes would be more interactive if it wasn't just a slide based class, but still very easy to follow along with Dr.", 1),
    ("Favorite CS teacher I've had so far", 1),
    ("Great slides and resources", 1),
    ("Usually ahead of scheudle", 1),
    ("Eric Wu is a HUGE step up from the last professor who taught chemistry.", 1),
    ("I felt like Ramachandran really cared about the students doing well and provided all of us ample opportunity to supplement when we were struggling.", 1),
    ("The programming assignments were helpful, especially the first one to help better understand DNS.", 1),
    ("Lecture slides proved very useful for reviewing and studying before exams.", 1),
    ("Labs were engaging and provided a different perspective on material than home- work or lectures that made course content really understandable.", 1),
    ("I have learned so many intricate details about networks.", 1),
    
    # ==========================================
    # COMMENTS (1) : SHORT & FRAGMENTED FEEDBACK
    # ==========================================
    ("Labs", 1),
    ("Extra credits", 1),
    ("not even needed", 1),
    ("Doing practice problems", 1),
    ("Class lecture follow along", 1),
    ("Programming assignments", 1),
    ("very effective", 1),
    ("Network handout", 1),
    ("lectures, videos, web resources", 1),
    ("Lecture slides", 1),
    ("Handouts, and videos", 1),
    ("Lectures and quizzes", 1),
    ("Lectures", 1),
    ("Solving slides together", 1),
    ("Group activities were helpful", 1),
    ("lectures, disscussions", 1)
]

df = pd.DataFrame(data, columns=['text', 'label'])

# Vectorize using TF-IDF - The AI learns the specific mathematical weight of words
vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
X = vectorizer.fit_transform(df['text'])
y = df['label']

# Train the Classifier
model = LinearSVC()
model.fit(X, y)

joblib.dump(model, 'comment_classifier.pkl')
joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')

print("✅ Model trained! Deeply integrated with CSU/UCLA specific evaluation terminology.")