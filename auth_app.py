import streamlit as st
from pathlib import Path
import base64
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'dbname': os.getenv('POSTGRES_DATABASE'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'host': os.getenv('POSTGRES_HOST'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'sslmode': 'require'  # Required for Neon
}

def init_db():
    """Initialize database tables if they don't exist"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Drop existing tables if needed for clean reset
        cur.execute("""
            DROP TABLE IF EXISTS matching_history CASCADE;
            DROP TABLE IF EXISTS supervisor_profiles CASCADE;
            DROP TABLE IF EXISTS student_profiles CASCADE;
            DROP TABLE IF EXISTS users CASCADE;
        """)
        
        # Create users table with TEXT password_hash
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                user_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create supervisor_profiles table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS supervisor_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                research_interests TEXT,
                department VARCHAR(255),
                expertise TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create student_profiles table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                course VARCHAR(255),
                year_of_study INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create matching_history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS matching_history (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES users(id),
                supervisor_name VARCHAR(255) NOT NULL,
                final_score FLOAT NOT NULL,
                research_alignment FLOAT NOT NULL,
                methodology_match FLOAT NOT NULL,
                technical_skills FLOAT NOT NULL,
                domain_knowledge FLOAT NOT NULL,
                matching_skills JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Add this to the init_db() function
        cur.execute("""
    CREATE TABLE IF NOT EXISTS supervisor_requests (
        id SERIAL PRIMARY KEY,
        student_id INTEGER REFERENCES users(id),
        supervisor_id INTEGER REFERENCES users(id),
        project_title VARCHAR(255),
        project_description TEXT,
        status VARCHAR(50) DEFAULT 'pending',  -- pending, accepted, rejected
        matching_score FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, supervisor_id)
    );
""")
                    # Add to init_db() function
        cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        message TEXT NOT NULL,
        type VARCHAR(50) NOT NULL,
        read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
        conn.commit()
        print("Database initialized successfully!")
        
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
        if conn:
            conn.rollback()
        raise e
        
    finally:
        if conn:
            cur.close()
            conn.close()

def get_svg_content():
    """Get the logo SVG content"""
    try:
        with open("assets/logo.svg", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"Error reading SVG: {e}")
        return ""

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).hex()  # Convert to hex string

def verify_password(password, hashed_password):
    """Verify password against hash"""
    try:
        # Convert hex string back to bytes
        hashed_bytes = bytes.fromhex(hashed_password)
        return bcrypt.checkpw(password.encode('utf-8'), hashed_bytes)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def authenticate_user(email, password):
    """Authenticate user and return user data if successful"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Get user data
        cur.execute("""
            SELECT id, email, password_hash::text, user_type, full_name 
            FROM users 
            WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        
        if user and verify_password(password, user[2]):
            return {
                'id': user[0],
                'email': user[1],
                'user_type': user[3],
                'full_name': user[4]
            }
        return None
        
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None
        
    finally:
        if conn:
            cur.close()
            conn.close()

def create_user(email, password, full_name, user_type, additional_data=None):
    """Create a new user and associated profile"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Check if email exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return False, "Email already registered"
        
        # Create user with hexadecimal password hash
        password_hash = hash_password(password)
        cur.execute("""
            INSERT INTO users (email, password_hash, full_name, user_type)
            VALUES (%s, %s::text, %s, %s)
            RETURNING id
        """, (email, password_hash, full_name, user_type))
        
        user_id = cur.fetchone()[0]
        
        # Create profile based on user type
        if user_type == 'supervisor' and additional_data:
            cur.execute("""
                INSERT INTO supervisor_profiles 
                (user_id, research_interests, department, expertise)
                VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                additional_data.get('research_interests'),
                additional_data.get('department'),
                additional_data.get('expertise', [])
            ))
        
        elif user_type == 'student' and additional_data:
            cur.execute("""
                INSERT INTO student_profiles 
                (user_id, course, year_of_study)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                additional_data.get('course'),
                additional_data.get('year_of_study')
            ))
        
        conn.commit()
        return True, "User created successfully"
        
    except Exception as e:
        conn.rollback()
        return False, f"Registration error: {e}"
        
    finally:
        if conn:
            cur.close()
            conn.close()

def login_page():
    """Render the login page"""
    svg_content = get_svg_content()
    
    # Add custom CSS
    st.markdown("""
        <style>
        .stApp {
            background-color: #f5f5f5;
        }
        .auth-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .form-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .stButton>button {
            width: 100%;
            background-color: #0066ff;
            color: white;
            border-radius: 25px;
            padding: 0.5rem 1rem;
            margin-top: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        
        # Logo and title
        if svg_content:
            st.image(f"data:image/svg+xml;base64,{svg_content}", width=100)
        st.markdown('<h1 class="form-header">Login</h1>', unsafe_allow_html=True)
        
        # Login form
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if not email or not password:
                    st.error("Please fill in all fields")
                elif not is_valid_email(email):
                    st.error("Please enter a valid email address")
                else:
                    user = authenticate_user(email, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.user_type = user['user_type']
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
        
        # Sign up link
        st.markdown('<div style="text-align: center; margin-top: 1rem;">', unsafe_allow_html=True)
        if st.button("Create an Account"):
            st.session_state.page = 'signup'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def signup_page():
    """Render the signup role selection page"""
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    
    st.markdown('<h1 class="form-header">Create Account</h1>', unsafe_allow_html=True)
    st.subheader("Choose your role")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("I'm a Student", use_container_width=True):
            st.session_state.page = 'student_signup'
            st.rerun()
    
    with col2:
        if st.button("I'm a Supervisor", use_container_width=True):
            st.session_state.page = 'supervisor_signup'
            st.rerun()
    
    if st.button("← Back to Login"):
        st.session_state.page = 'login'
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def student_signup():
    """Render the student signup page"""
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    
    st.markdown('<h1 class="form-header">Student Sign Up</h1>', unsafe_allow_html=True)
    
    with st.form("student_signup_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        course = st.text_input("Course")
        year = st.selectbox("Year of Study", [1, 2, 3, 4, 5])
        
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            if not all([full_name, email, password, confirm_password, course]):
                st.error("Please fill in all fields")
            elif not is_valid_email(email):
                st.error("Please enter a valid email address")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters long")
            else:
                additional_data = {
                    'course': course,
                    'year_of_study': year
                }
                success, message = create_user(email, password, full_name, 'student', additional_data)
                if success:
                    st.success(message)
                    st.session_state.page = 'login'
                    st.rerun()
                else:
                    st.error(message)
    
    if st.button("← Back"):
        st.session_state.page = 'signup'
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def supervisor_signup():
    """Render the supervisor signup page"""
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    
    st.markdown('<h1 class="form-header">Supervisor Sign Up</h1>', unsafe_allow_html=True)
    
    with st.form("supervisor_signup_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        department = st.text_input("Department")
        research_interests = st.text_area("Research Interests")
        expertise = st.multiselect(
            "Areas of Expertise",
            [
                "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
                "Data Science", "Cybersecurity", "Software Engineering",
                "Artificial Intelligence", "Robotics", "Cloud Computing"
            ]
        )
        
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            if not all([full_name, email, password, confirm_password, department, research_interests]):
                st.error("Please fill in all fields")
            elif not is_valid_email(email):
                st.error("Please enter a valid email address")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters long")
            else:
                additional_data = {
                    'department': department,
                    'research_interests': research_interests,
                    'expertise': expertise
                }
                success, message = create_user(email, password, full_name, 'supervisor', additional_data)
                if success:
                    st.success(message)
                    st.session_state.page = 'login'
                    st.rerun()
                else:
                    st.error(message)
    
    if st.button("← Back"):
        st.session_state.page = 'signup'
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Initialize the database when the app starts
init_db()