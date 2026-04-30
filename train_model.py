import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import joblib

# 1 = Real Student Comment
# 0 = Administrative Noise / Boilerplate
data = [
    # --- NOISE (0) ---
    ("Report Comments", 0),
    ("Please find your Instructor Summary Report below. Please visit the Student Experiences of Teaching website for additional information.", 0),
    ("Statistics Value", 0),
    ("Invited Count 308", 0),
    ("Response Count 226", 0),
    ("Response Ratio 73.38%", 0),
    ("5 - Average", 0),
    ("Overall - Your overall rating of the instructor.", 0),
    ("1 - Very Low or Never, 3 - Low or Infrequently, 5 - Average, 7 - High or Frequently, 9 - Very High or Always", 0),
    ("Questions focused on Instructor", 0),
    ("To What Extent Do You Feel That:", 0),
    ("Instructor Concern - The instructor was concerned about student learning.", 0),
    ("Organization - Class presentations were well prepared and organized.", 0),
    ("1 - Low", 0),
    ("2 - Medium", 0),
    ("3 - High", 0),
    ("Your View of Course Characteristics:", 0),
    ("Subject interest before course", 0),
    ("Difficulty (relative to other courses)", 0),
    ("1 - Too Slow, 2 - About Right, 3 - Too Much", 0),
    ("Global Aspects Aspect Score", 0),
    ("Course organization and structure 4.73", 0),
    ("Pace and workload 4.07", 0),
    ("Topic Scores Topic Score", 0),
    ("Course materials / clarity 3.5", 0),
    ("Teaching effectiveness / instructor skill 5.0", 0),
    ("Grading and exams 2.0", 0),
    ("However, grading and exams received a lower score of 2.0, indicating a need for improvement in assessment practices.", 0),
    ("While the pace and workload were generally well-received (3.5), there is room for enhancement in course materials and clarity (3.5).", 0),
    
    # --- COMMENTS (1) ---
    ("The material is taught with clarity too and her assignments and exams are fair game.", 1),
    ("Presentations and lectures were very clear.", 1),
    ("I felt like Ramachandran really cared about the students doing well and provided all of us ample opportunity to supplement when we were struggling.", 1),
    ("Professor Ramachandran is an engaging lecturer and very obviously cares about students understanding the material.", 1),
    ("I know that many of us struggle with such dense course but I believe that Professor Ramachandran has made is extremely doable.", 1),
    ("The strengths of this course is that we got through all the material so it was excellent on time management.", 1),
    ("I believe Dr.Ramachandran has a very organized course and truly cares about the success of her students.", 1),
    ("However, I believe that the course could be improved in terms of the course resources that are posted online on CCLE.", 1),
    ("Ramachandran genuinely cares for the well being of her students and is constantly trying to improve her teaching methods.", 1),
    ("The strengths that this professor has performed was teaching skills, knowledge of the material, communication, and concern of the students.", 1),
    ("Theinstructortakesthetimetogooveranyquestionthatisaskedduring lecture, does her best to make sure that students are understanding the material.", 1),
    ("I love her lectures, and I can always understand the concepts after her explanation.", 1),
    ("This was the first time I felt welcomed and interested in such material.", 1),
    ("I think her exams and grading system are fair but it would be very helpful if there could be a timer on the screen during exams instead of just a 3 minute warning.", 1),
    ("I also do not think partial credit was fair.", 1),
    ("The material on the exams was always fair, my only problem was the timeconstraintasitresultedinaverystressfulenvironment.", 1),
    ("I think weekly graded homeworks should be included for a small portion of the grade.", 1),
    ("I learned a lot and worked very hard but my grade doesn’t reflect it.", 1),
    ("Her grading scale is a bit harsh and she does not give too much partial credit.", 1),
    ("Overall, I really enjoyed Ramachandran as a professor and felt confident in a subject I did not think I would be.", 1),
    ("Tends to get ex- tremely anxious during exams (weakness).", 1),
    ("She is open and welcoming, and always responds super quickly to discussion posts and emails.", 1),
    ("Professor Ramachandran completely changed Chemistry for me and I am so thankful I came across this class.", 1),
    ("I would say however that the level of questions on the tests seem to exceed what is taught in class.", 1)
]

df = pd.DataFrame(data, columns=['text', 'label'])

# Vectorize using TF-IDF (Analyzes frequency and uniqueness of word combinations)
vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
X = vectorizer.fit_transform(df['text'])
y = df['label']

# Train the Classifier
model = LinearSVC()
model.fit(X, y)

# Save the offline model files
joblib.dump(model, 'comment_classifier.pkl')
joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')

print("✅ Model trained and saved successfully! No internet connection required.")