import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from auth_app import DB_CONFIG
from datetime import datetime

def admin_dashboard():
    if not st.session_state.get('authenticated') or st.session_state.user_type != 'admin':
        st.error("Please login as an admin to access this page")
        return

    st.title("Module Lead Dashboard")

    tabs = st.tabs(["Matches Overview", "Manage Supervisors and Students", "Student Allocations"])

    with tabs[0]:
        show_matches_overview()
    with tabs[1]:
        manage_supervisors_students()
    with tabs[2]:
        show_student_allocations()

def show_matches_overview():
    st.header("Matches Overview")
    matches = get_all_matches()

    if matches.empty:
        st.info("No matches found.")
    else:
        st.dataframe(
            matches.style.format({
                'final_score': '{:.2f}',
                'created_at': lambda x: x.strftime('%Y-%m-%d %H:%M')
            })
        )

def show_student_allocations():
    st.header("Student Allocations")
    
    students = get_all_students_with_allocation()
    if students.empty:
        st.info("No students found.")
        return
        
    # Add filters
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Allocated", "Unallocated"]
        )
    with col2:
        search_term = st.text_input("Search by Name or Course")
    
    # Apply filters
    filtered_students = students
    if status_filter != "All":
        filtered_students = filtered_students[filtered_students['allocation_status'] == status_filter.lower()]
    if search_term:
        mask = (
            filtered_students['full_name'].str.contains(search_term, case=False, na=False) |
            filtered_students['course'].str.contains(search_term, case=False, na=False)
        )
        filtered_students = filtered_students[mask]
    
    # Display statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        total = len(students)
        st.metric("Total Students", total)
    with col2:
        allocated = len(students[students['allocation_status'] == 'allocated'])
        st.metric("Allocated Students", allocated)
    with col3:
        unallocated = len(students[students['allocation_status'] == 'unallocated'])
        st.metric("Unallocated Students", unallocated)
    
    # Display student list
    st.dataframe(
        filtered_students[[
            'full_name', 'email', 'course', 'year_of_study', 
            'allocation_status', 'supervisor_name'
        ]].style.apply(color_status, axis=1)
    )

def color_status(row):
    """Apply colors to allocation status"""
    color = 'background-color: '
    if row['allocation_status'] == 'allocated':
        return [color + '#d4edda'] * len(row)
    else:
        return [color + '#f8d7da'] * len(row)

def get_all_students_with_allocation():
    """Fetch all students with their allocation status"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            WITH latest_matches AS (
                SELECT DISTINCT ON (student_id) 
                    student_id,
                    supervisor_id,
                    'allocated' as allocation_status
                FROM matching_history
                ORDER BY student_id, created_at DESC
            )
            SELECT 
                u.id,
                u.full_name,
                u.email,
                sp.course,
                sp.year_of_study,
                COALESCE(lm.allocation_status, 'unallocated') as allocation_status,
                sup.full_name as supervisor_name
            FROM users u
            JOIN student_profiles sp ON u.id = sp.user_id
            LEFT JOIN latest_matches lm ON u.id = lm.student_id
            LEFT JOIN users sup ON lm.supervisor_id = sup.id
            WHERE u.user_type = 'student'
            ORDER BY u.full_name
        """)
        
        students = cur.fetchall()
        return pd.DataFrame(students)
    except Exception as e:
        st.error(f"Error fetching students: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            cur.close()
            conn.close()

def manage_supervisors_students():
    st.header("Manage Supervisors and Students")
    
    supervisors = get_supervisors()
    if supervisors.empty:
        st.info("No supervisors found.")
        return

    selected_supervisor = st.selectbox(
        "Select Supervisor", 
        supervisors['full_name'].tolist(),
        key="supervisor_select"
    )

    if selected_supervisor:
        supervisor_id = int(supervisors.loc[supervisors['full_name'] == selected_supervisor, 'id'].iloc[0])
        show_supervisor_details(supervisor_id, selected_supervisor)

def show_supervisor_details(supervisor_id, supervisor_name):
    students = get_students_under_supervisor(supervisor_id)
    
    st.subheader(f"Students under {supervisor_name}")
    
    if students.empty:
        st.info("No students assigned to this supervisor.")
        return
        
    # Display student list with management options
    for _, student in students.iterrows():
        with st.expander(f"📚 {student['full_name']} - {student['course']}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Email:** {student['email']}")
                st.write(f"**Year of Study:** {student['year_of_study']}")
                st.write(f"**Course:** {student['course']}")
            
            with col2:
                if st.button("Remove", key=f"remove_{student['id']}"):
                    if remove_student_from_supervisor(int(student['id']), supervisor_id):
                        st.success(f"Removed {student['full_name']} from {supervisor_name}")
                        st.rerun()
                
                other_supervisors = get_supervisors()
                other_supervisors = other_supervisors[other_supervisors['id'] != supervisor_id]
                
                new_supervisor = st.selectbox(
                    "Move to",
                    other_supervisors['full_name'].tolist(),
                    key=f"move_{student['id']}"
                )
                
                if new_supervisor and st.button("Move", key=f"move_btn_{student['id']}"):
                    new_supervisor_id = int(other_supervisors.loc[
                        other_supervisors['full_name'] == new_supervisor, 'id'
                    ].iloc[0])
                    
                    if move_student_to_supervisor(int(student['id']), new_supervisor_id, supervisor_id):
                        st.success(f"Moved {student['full_name']} to {new_supervisor}")
                        st.rerun()

def get_students_under_supervisor(supervisor_id):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT DISTINCT 
                u.id, 
                u.full_name, 
                u.email, 
                sp.course, 
                sp.year_of_study
            FROM matching_history mh
            JOIN users u ON mh.student_id = u.id
            JOIN student_profiles sp ON u.id = sp.user_id
            WHERE mh.supervisor_id = %s
            ORDER BY u.full_name
        """, (supervisor_id,))
        
        students = cur.fetchall()
        return pd.DataFrame(students)
    except Exception as e:
        st.error(f"Error fetching students: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            cur.close()
            conn.close()

def get_supervisors():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT u.id, u.full_name, u.email
            FROM users u
            WHERE u.user_type = 'supervisor'
            ORDER BY u.full_name
        """)
        
        supervisors = cur.fetchall()
        return pd.DataFrame(supervisors)
    except Exception as e:
        st.error(f"Error fetching supervisors: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            cur.close()
            conn.close()

def get_all_matches():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT 
                mh.id,
                su.full_name AS student_name,
                sp.full_name AS supervisor_name,
                mh.final_score,
                mh.created_at
            FROM matching_history mh
            JOIN users su ON mh.student_id = su.id
            JOIN users sp ON mh.supervisor_id = sp.id
            ORDER BY mh.created_at DESC
        """)
        
        matches = cur.fetchall()
        return pd.DataFrame(matches)
    except Exception as e:
        st.error(f"Error fetching matches: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            cur.close()
            conn.close()

def remove_student_from_supervisor(student_id, supervisor_id):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM matching_history
            WHERE student_id = %s AND supervisor_id = %s
        """, (student_id, supervisor_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error removing student: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

def move_student_to_supervisor(student_id, new_supervisor_id, old_supervisor_id):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            UPDATE matching_history
            SET supervisor_id = %s
            WHERE student_id = %s AND supervisor_id = %s
        """, (new_supervisor_id, student_id, old_supervisor_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error moving student: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()