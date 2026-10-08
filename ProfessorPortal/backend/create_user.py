import bcrypt
from models import SessionLocal, Professor

def get_password_hash(password: str):
    # Generates a secure salt and hashes the password using bcrypt
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')

def create_user():
    print("\n=== CourseEval Account Generator ===")
    name = input("Enter Professor's Full Name (e.g., Dr. Cao Thang Bui): ")
    email = input("Enter Institutional Email: ")
    password = input("Enter Temporary Password: ")

    db = SessionLocal()
    
    try:
        # Check if the email is already in the database
        existing_prof = db.query(Professor).filter(Professor.email == email).first()
        if existing_prof:
            print(f"\n❌ Error: An account with {email} already exists.")
            return

        # Hash the password and create the user
        hashed_pw = get_password_hash(password)
        new_prof = Professor(name=name, email=email, hashed_password=hashed_pw)
        
        db.add(new_prof)
        db.commit()
        
        print(f"\n✅ SUCCESS: Account created for {name}!")
        print(f"📧 Email: {email}")
        print("🔐 Password securely hashed and stored in PostgreSQL.")
        
    except Exception as e:
        print(f"\n❌ Database Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_user()