# main.py
import streamlit as st
from auth_app import login_page, signup_page, student_signup, supervisor_signup
from app import main as student_main
from supervisor_dashboard import supervisor_dashboard
from database import verify_database

def initialize_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    if 'user_type' not in st.session_state:
        st.session_state.user_type = None
    if 'user' not in st.session_state:
        st.session_state.user = None

def main():
    st.set_page_config(page_title="Research Supervisor Matcher", layout="wide")
    
    initialize_session_state()
    
    # If not authenticated, show auth pages
    if not st.session_state.authenticated:
        if st.session_state.page == 'login':
            login_page()
        elif st.session_state.page == 'signup':
            signup_page()
        elif st.session_state.page == 'student_signup':
            student_signup()
        elif st.session_state.page == 'supervisor_signup':
            supervisor_signup()
    else:
        # Show appropriate page based on user type
        if st.session_state.user_type == 'student':
            student_main()
        elif st.session_state.user_type == 'supervisor':
            supervisor_dashboard()
        else:
            st.error("Invalid user type")

if __name__ == "__main__":
    verify_database()
    main()