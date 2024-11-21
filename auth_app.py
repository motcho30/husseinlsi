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






def get_custom_css():
    return """
    <style>
        /* Global Styles */
        .stApp {
            background: white;
        }
        
        /* Container Styles */
        .auth-container {
            max-width: 450px;
            margin: 2rem auto;
            padding: 2.5rem;
            background: white;
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        
        /* Header Styles */
        .form-header {
            text-align: center;
            margin-bottom: 2rem;
            color: #1a237e;
            font-size: 2rem;
            font-weight: 700;
        }
        
        .logo-container {
            text-align: center;
            margin-bottom: 1.5rem;
        }
        
        .logo-container img {
            width: 120px;
            height: auto;
            margin: 0 auto;
        }
        
        /* Form Field Styles */

        

        
        /* Button Styles */
        .stButton > button {
            width: 100%;
            background: linear-gradient(45deg, #4051b5, #536dfe);
            color: white;
            border-radius: 12px;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            border: none;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 1.5rem;
        }
        
        .stButton > button:hover {
            background: linear-gradient(45deg, #3949ab, #4051b5);
            box-shadow: 0 4px 15px rgba(64, 81, 181, 0.2);
            transform: translateY(-2px);
        }
        
        /* Link Styles */
        .link-button {
            background: none;
            border: none;
            color: #4051b5;
            text-decoration: none;
            cursor: pointer;
            font-weight: 500;
            transition: color 0.3s ease;
        }
        
        .link-button:hover {
            color: #3949ab;
            text-decoration: underline;
        }
        
        /* Role Selection Cards */
        .role-card {
            background: white;
            border-radius: 15px;
            padding: 1.5rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid #e9ecef;
            height: 100%;
        }
        
        .role-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
            border-color: #4051b5;
        }
        
        /* Error Messages */
        .stAlert {
            background: #fff3f3;
            color: #d32f2f;
            border-radius: 12px;
            border-left: 4px solid #d32f2f;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        /* Success Messages */
        .success-message {
            background: #f0f9f4;
            color: #2e7d32;
            border-radius: 12px;
            border-left: 4px solid #2e7d32;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        /* Divider */
        .divider {
            display: flex;
            align-items: center;
            text-align: center;
            margin: 1.5rem 0;
            color: #6c757d;
        }
        
        .divider::before,
        .divider::after {
            content: "";
            flex: 1;
            border-bottom: 1px solid #e9ecef;
        }
        
        .divider span {
            padding: 0 1rem;
        }
    </style>
    """
def login_page():
    """Render the login page with improved styling"""
    svg_content = get_svg_content()
    
    # Add custom CSS with fixed input field styling
    st.markdown("""
        <style>
        /* Main container styling */
        .stApp {
            background: white;
        }
        
        .auth-container {
            max-width: 450px;
            margin: 2rem auto;
            padding: 2.5rem;
            background: white;
            border-radius: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }
        
        /* Form header styling */
        .form-header {
            color: #1e2a4a;
            font-size: 2.5rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 2rem;
        }
        
        /* Input field styling */
        .stTextInput input {
            background-color: #f8f9fe;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            font-size: 1rem;
            color: #1e2a4a !important;
            width: 100%;
            transition: border-color 0.2s ease;
        }
        
        .stTextInput input:focus {
            border-color: #4c63d9;
            box-shadow: 0 0 0 2px rgba(76, 99, 217, 0.1);
        }
        
        .stTextInput input::placeholder {
            color: #a0aec0;
        }
        
        /* Button styling */
        .stButton>button {
            width: 100%;
            background-color: #4c63d9;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }
        
        .stButton>button:hover {
            background-color: #3b4fa8;
        }
        
        /* Checkbox styling */
        .stCheckbox {
            color: #4a5568;
        }
        
        /* Link styling */
        a {
            color: #4c63d9;
            text-decoration: none;
            font-weight: 500;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        /* Divider styling */
        .divider {
            text-align: center;
            margin: 1.5rem 0;
            color: #a0aec0;
        }
        
        /* Sign up prompt styling */
        .signup-prompt {
            text-align: center;
            margin-top: 1.5rem;
            color: #4a5568;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        st.markdown("""
                    <img src="https://i.ibb.co/khnRGSD/1.png" style="width: 180px; height: 180px;"/>
                
            """, unsafe_allow_html=True)
        # Logo and title
        if svg_content:
            st.image(f"https://i.ibb.co/n8kvbRY/crested-wm-dubai-cmyk.jpg", width=80)
        st.markdown('<h1 class="form-header">Welcome Back</h1>', unsafe_allow_html=True)
        
        # Login form
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="Enter your email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.checkbox("Remember me", key="remember_me")
            with col2:
                st.markdown('<div style="text-align: right;"><a href="#">Forgot Password?</a></div>', 
                          unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Sign In")
            
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
        
        # Divider
        st.markdown('<div class="divider">OR</div>', unsafe_allow_html=True)
        
        # Sign up section
        st.markdown('<div class="signup-prompt">New to the platform?</div>', unsafe_allow_html=True)
        if st.button("Create an Account", use_container_width=True):
            st.session_state.page = 'signup'
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
def load_local_image(image_path):
    """Load a local image file and return it as base64"""
    try:
        image_path = Path(image_path)
        with open(image_path, "rb") as f:
            image_data = f.read()
            return base64.b64encode(image_data).decode()
    except Exception as e:
        print(f"Error loading image: {e}")
        return None
def signup_page():
    student_icon = load_local_image("assets/student_icon.svg")
    supervisor_icon = load_local_image("assets/supervisor_icon.svg")

    """Render the redesigned signup role selection page"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        
        st.markdown('<h1 class="form-header">Join Us</h1>', unsafe_allow_html=True)
        st.markdown('<p style="text-align: center; margin-bottom: 2rem; color: #666;">Choose your role to get started</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
                <div class="role-card" onclick="student_signup()">
                    <img src="https://i.ibb.co/bJdX1fV/1.png" style="width: 80px; height: 80px;"/>
                    <h3 style="margin: 1rem 0; color: #1a237e;">Student</h3>
                    <p style="color: #666; font-size: 0.9rem;">Looking for a supervisor</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("I'm a Student", key="student_btn", use_container_width=True):
                st.session_state.page = 'student_signup'
                st.rerun()
        
        with col2:
            st.markdown("""
                <div class="role-card" onclick="supervisor_signup()">
                    <img src="https://i.ibb.co/DKnCTQk/2.png" style="width: 80px; height: 80px;"/>
                    <h3 style="margin: 1rem 0; color: #1a237e;">Supervisor</h3>
                    <p style="color: #666; font-size: 0.9rem;">Guide and mentor students</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("I'm a Supervisor", key="supervisor_btn", use_container_width=True):
                st.session_state.page = 'supervisor_signup'
                st.rerun()
        
        st.markdown('<div style="text-align: center; margin-top: 2rem;">', unsafe_allow_html=True)
        st.markdown('Already have an account?', unsafe_allow_html=True)
        if st.button("← Back to Login", key="back_to_login"):
            st.session_state.page = 'login'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def student_signup():


    st.markdown("""
    <style>
    /* Fix for input text visibility */
    .stTextInput input, 
    .stNumberInput input,
    .stTextArea textarea,
    .stSelectbox select {
        color: #1e2a4a !important;
        background-color: white !important;
    }
    
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #6b7280 !important;
        opacity: 0.8;
    }
     </style>
""", unsafe_allow_html=True)
    """Render the redesigned student signup page"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        
        st.markdown('<h1 class="form-header">Student Registration</h1>', unsafe_allow_html=True)
        
        with st.form("student_signup_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                full_name = st.text_input("Full Name", placeholder="Enter your full name")
            with col2:
                email = st.text_input("Email", placeholder="Enter your email")
            
            col1, col2 = st.columns(2)
            with col1:
                password = st.text_input("Password", type="password", placeholder="Create password")
            with col2:
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
            
            col1, col2 = st.columns(2)
            with col1:
                course = st.text_input("Course", placeholder="Your course of study")
            with col2:
                year = st.selectbox("Year of Study", [1, 2, 3, 4, 5])
            
            submit = st.form_submit_button("Create Account")
            
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
        
        st.markdown('<div style="text-align: center; margin-top: 1rem;">', unsafe_allow_html=True)
        if st.button("← Back", key="back_to_roles"):
            st.session_state.page = 'signup'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def supervisor_signup():
    st.markdown("""
    <style>
    /* Fix for input text visibility */
    .stTextInput input, 
    .stNumberInput input,
    .stTextArea textarea,
    .stSelectbox select,
    .stMultiSelect select {
        color: #1e2a4a !important;
        background-color: white !important;
    }
    
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #6b7280 !important;
        opacity: 0.8;
    }
    </style>
    """, unsafe_allow_html=True)
    
    """Render the redesigned supervisor signup page"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        st.markdown('<h1 class="form-header">Supervisor Registration</h1>', unsafe_allow_html=True)
        
        with st.form("supervisor_signup_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                full_name = st.text_input("Full Name", placeholder="Enter your full name")
            with col2:
                email = st.text_input("Email", placeholder="Enter your email")
            
            col1, col2 = st.columns(2)
            with col1:
                password = st.text_input("Password", type="password", placeholder="Create password")
            with col2:
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
            
            col1, col2 = st.columns(2)
            with col1:
                department = st.text_input("Department", placeholder="Your department")
            with col2:
                expertise = st.multiselect(
                    "Areas of Expertise",
                    [
                        "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
                        "Data Science", "Cybersecurity", "Software Engineering",
                        "Artificial Intelligence", "Robotics", "Cloud Computing"
                    ],
                    placeholder="Select expertise"
                )
            
            research_interests = st.text_area("Research Interests", placeholder="Describe your research interests...")
            
            submit = st.form_submit_button("Create Account")
            
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
        
        st.markdown('<div style="text-align: center; margin-top: 1rem;">', unsafe_allow_html=True)
        if st.button("← Back", key="back_to_roles"):
            st.session_state.page = 'signup'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# Initialize the database when the app starts
init_db()