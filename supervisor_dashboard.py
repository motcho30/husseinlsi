import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from auth_app import DB_CONFIG

def get_supervisor_requests(supervisor_id):
    """Fetch all requests for a supervisor"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                sr.id as request_id,
                sr.project_title,
                sr.project_description,
                sr.status,
                sr.matching_score,
                sr.created_at,
                sr.student_id,
                u.full_name as student_name,
                u.email as student_email,
                sp.course,
                sp.year_of_study
            FROM supervisor_requests sr
            JOIN users u ON sr.student_id = u.id
            JOIN student_profiles sp ON u.id = sp.user_id
            WHERE sr.supervisor_id = %s
            ORDER BY CASE 
                WHEN sr.status = 'pending' THEN 1
                WHEN sr.status = 'accepted' THEN 2
                ELSE 3
            END, sr.created_at DESC
        """, (supervisor_id,))
        
        requests = cur.fetchall()
        return requests
        
    except Exception as e:
        st.error(f"Error fetching requests: {e}")
        return []
        
    finally:
        if conn:
            cur.close()
            conn.close()

def update_request_status(request_id, new_status):
    """Update the status of a request"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE supervisor_requests
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING student_id
        """, (new_status, request_id))
        
        student_id = cur.fetchone()[0]
        
        # Add notification for the student
        cur.execute("""
            INSERT INTO notifications (user_id, message, type)
            VALUES (%s, %s, 'request_update')
        """, (
            student_id,
            f"Your supervision request has been {new_status}"
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Error updating request: {e}")
        return False
        
    finally:
        if conn:
            cur.close()
            conn.close()

def get_request_statistics(supervisor_id):
    """Get statistics about supervisor requests"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get status counts
        cur.execute("""
            SELECT status, COUNT(*) as count
            FROM supervisor_requests
            WHERE supervisor_id = %s
            GROUP BY status
        """, (supervisor_id,))
        status_counts = cur.fetchall()
        
        # Get weekly request counts
        cur.execute("""
            SELECT DATE_TRUNC('week', created_at) as week, COUNT(*) as count
            FROM supervisor_requests
            WHERE supervisor_id = %s
            AND created_at > NOW() - INTERVAL '6 months'
            GROUP BY week
            ORDER BY week
        """, (supervisor_id,))
        weekly_counts = cur.fetchall()
        
        return {
            'status_counts': status_counts,
            'weekly_counts': weekly_counts
        }
        
    except Exception as e:
        st.error(f"Error fetching statistics: {e}")
        return None
        
    finally:
        if conn:
            cur.close()
            conn.close()

def create_statistics_charts(stats):
    """Create statistics visualizations"""
    if not stats or not stats['status_counts']:
        return None
        
    # Create subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Request Status Distribution", "Weekly Requests"),
        specs=[[{"type": "pie"}, {"type": "scatter"}]]
    )
    
    # Status distribution pie chart
    labels = [item['status'] for item in stats['status_counts']]
    values = [item['count'] for item in stats['status_counts']]
    fig.add_trace(
        go.Pie(labels=labels, values=values, 
               textinfo='label+percent',
               marker=dict(colors=['#FFA500', '#4CAF50', '#F44336'])),
        row=1, col=1
    )
    
    # Weekly requests line chart
    if stats['weekly_counts']:
        weeks = [item['week'].strftime('%Y-%m-%d') for item in stats['weekly_counts']]
        counts = [item['count'] for item in stats['weekly_counts']]
        fig.add_trace(
            go.Scatter(x=weeks, y=counts, mode='lines+markers',
                      name='Weekly Requests',
                      line=dict(color='#2196F3')),
            row=1, col=2
        )
    
    fig.update_layout(
        height=400,
        showlegend=True,
        template='plotly_white'
    )
    return fig

def supervisor_dashboard():
    """Main supervisor dashboard page"""
    if not st.session_state.get('authenticated') or st.session_state.user_type != 'supervisor':
        st.error("Please login as a supervisor to access this page")
        return
    
    st.title("Supervisor Dashboard")
    
    # Get supervisor ID from session
    supervisor_id = st.session_state.user['id']
    
    # Create tabs
    tabs = ["Overview", "Requests", "Profile"]
    selected_tab = st.tabs(tabs)
    
    # Overview Tab
    with selected_tab[0]:
        st.subheader("Overview")
        
        # Get and display statistics
        stats = get_request_statistics(supervisor_id)
        if stats:
            fig = create_statistics_charts(stats)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Summary metrics
            total_requests = sum(item['count'] for item in stats['status_counts'])
            pending_requests = next(
                (item['count'] for item in stats['status_counts'] 
                 if item['status'] == 'pending'), 0
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Requests", total_requests)
            with col2:
                st.metric("Pending Requests", pending_requests)
            with col3:
                acceptance_rate = next(
                    (item['count'] for item in stats['status_counts'] 
                     if item['status'] == 'accepted'), 0
                ) / total_requests * 100 if total_requests > 0 else 0
                st.metric("Acceptance Rate", f"{acceptance_rate:.1f}%")
    
    # Requests Tab
    with selected_tab[1]:
        st.subheader("Student Requests")
        
        # Filter controls
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All", "Pending", "Accepted", "Rejected"],
                key="status_filter"
            )
        
        # Get requests
        requests = get_supervisor_requests(supervisor_id)
        
        # Apply filters
        if status_filter != "All":
            requests = [r for r in requests if r['status'].lower() == status_filter.lower()]
        
        # Display requests
        if not requests:
            st.info("No requests found.")
        else:
            for request in requests:
                with st.expander(
                    f"{request['project_title']} - {request['student_name']}",
                    expanded=(request['status'] == 'pending')
                ):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write("**Student Details:**")
                        st.write(f"Name: {request['student_name']}")
                        st.write(f"Email: {request['student_email']}")
                        st.write(f"Course: {request['course']} (Year {request['year_of_study']})")
                        
                        st.write("\n**Project Details:**")
                        st.write(request['project_description'])
                        
                    with col2:
                        st.write("**Status:**")
                        status_colors = {
                            'pending': 'orange',
                            'accepted': 'green',
                            'rejected': 'red'
                        }
                        st.markdown(
                            f":{status_colors[request['status']]}[{request['status'].upper()}]"
                        )
                        
                        st.write("**Match Score:**")
                        st.write(f"{request['matching_score']:.2f}")
                        
                        st.write("**Submitted:**")
                        st.write(request['created_at'].strftime("%Y-%m-%d"))
                        
                        if request['status'] == 'pending':
                            if st.button("Accept", key=f"accept_{request['request_id']}"):
                                if update_request_status(request['request_id'], 'accepted'):
                                    st.success("Request accepted!")
                                    st.rerun()
                            
                            if st.button("Reject", key=f"reject_{request['request_id']}"):
                                if update_request_status(request['request_id'], 'rejected'):
                                    st.success("Request rejected!")
                                    st.rerun()
    
    # Profile Tab
    with selected_tab[2]:
        st.subheader("Supervisor Profile")
        st.info("Profile settings and management coming soon!")
    
    # Sidebar
    with st.sidebar:
        st.write(f"Welcome, {st.session_state.user['full_name']}")
        if st.button("Logout", key="supervisor_logout"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    supervisor_dashboard()