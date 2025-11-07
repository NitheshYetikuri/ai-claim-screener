import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import time

# --- Page Configuration ---
# This must be the first Streamlit command
st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# --- Custom CSS (Combined from all files) ---
st.markdown("""
<style>
    /* --- NEW NAVIGATION BAR STYLES --- */
    
    /* Hide the default radio button's dot */
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
        display: none;
    }

    /* Style the container for each nav item */
    [data-testid="stSidebar"] [data-baseweb="radio"] {
        display: flex;
        flex-direction: column;
        width: 100%;
        margin-bottom: 5px; /* Spacing between buttons */
    }

    /* Style the label (the text) as a button */
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:last-child {
        width: 100%;
        border-radius: 8px;
        padding: 10px 15px;
        font-weight: 600;
        transition: background-color 0.2s ease, color 0.2s ease;
        background-color: #f0f2f6; /* Light grey background for unselected */
        color: #333; /* Dark text for unselected */
    }

    /* Style the label on hover */
    [data-testid="stSidebar"] [data-baseweb="radio"]:hover > div:last-child {
        background-color: #e0e4e8;
        color: #000;
    }

    /* This targets the selected item's label. This class is specific and may
       need updating if Streamlit's internal classes change, but it works now. */
    [data-testid="stSidebar"] .st-emotion-cache-1y4d8pa {
        width: 100%;
        border-radius: 8px;
        padding: 10px 15px;
        font-weight: 600;
        transition: background-color 0.2s ease, color 0.2s ease;
        
        /* The gradient background for the SELECTED item */
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; /* White text for selected */
    }

    /* --- END NAVIGATION BAR STYLES --- */


    /* Main container styling */
    .main {
        padding-top: 1rem;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
        font-size: 1.2rem;
        opacity: 0.9;
        margin: 0;
    }
    
    /* Metric cards styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 4px solid;
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
    }
    
    .metric-jobs { border-left-color: #2196F3; }
    .metric-human { border-left-color: #f44336; }
    .metric-pending { border-left-color: #FF9800; }
    .metric-processed { border-left-color: #4CAF50; }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        color: #333;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-icon {
        font-size: 2rem;
        float: right;
        opacity: 0.7;
    }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 2rem 0 1rem 0;
        border-left: 4px solid #667eea;
    }
    
    .section-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #333;
        margin: 0;
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    
    .error-box {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #f44336;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #FF9800;
        margin: 1rem 0;
    }

    /* Service status styling */
    .service-status {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .service-name {
        font-weight: 600;
        color: #333;
    }
    
    .service-port {
        font-size: 0.9rem;
        color: #666;
    }
    
    /* NEW STYLE FOR LOG BOX */
    .log-box {
        background-color: #000000;
        color: #00FF00; /* Green text */
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.85rem;
        padding: 1rem;
        border-radius: 8px;
        height: 600px;
        overflow-y: scroll;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: visible;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# --- Caching and Database ---

@st.cache_resource
def get_db_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('mysql_host'),
            port=int(os.getenv('mysql_port', 3306)),
            user=os.getenv('mysql_user'),
            password=os.getenv('mysql_password'),
            database=os.getenv('mysql_db')
        )
        if connection.is_connected():
            return connection
        else:
            st.error("Database connection failed.")
            return None
    except Error as e:
        st.error(f"Database connection failed: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

# --- Global Helper Functions ---

@st.cache_data(ttl=10) # Cache for 10 seconds
def get_kpi_metrics(_connection):
    """Get key performance indicators from all tables"""
    metrics = {
        'total_jobs_in_pipe': 0,
        'pending_review': 0,
        'pending_processing': 0,
        'processed_success': 0
    }
    if not _connection:
        return metrics
        
    try:
        with _connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM mail_jobs")
            metrics['total_jobs_in_pipe'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM human_fulfillment WHERE status = 'NEEDS_REVIEW'")
            metrics['pending_review'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM mail_jobs WHERE status = 'PENDING'")
            metrics['pending_processing'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM mail_jobs WHERE status = 'PROCESSED_SUCCESS'")
            metrics['processed_success'] = cursor.fetchone()['count']
            
        return metrics
    except Exception as e:
        st.error(f"Error getting KPI metrics: {e}")
        return metrics

@st.cache_data(ttl=5) # Cache for 5 seconds
def fetch_human_jobs(_connection, status_filter):
    if not _connection or not _connection.is_connected():
        _connection = get_db_connection()
        if not _connection:
            return pd.DataFrame()
            
    try:
        with _connection.cursor(dictionary=True) as cursor:
            query = "SELECT * FROM human_fulfillment WHERE status = %s ORDER BY created_at DESC LIMIT 100"
            cursor.execute(query, (status_filter,))
            results = cursor.fetchall()
            return pd.DataFrame(results) if results else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching human fulfillment jobs: {e}")
        return pd.DataFrame()

def mark_job_resolved(_connection, job_id):
    try:
        with _connection.cursor() as cursor:
            query = "UPDATE human_fulfillment SET status = 'RESOLVED' WHERE id = %s"
            cursor.execute(query, (job_id,))
            _connection.commit()
        st.cache_data.clear() # Clear cache to refresh
        return True
    except Exception as e:
        st.error(f"Failed to resolve job: {e}")
        _connection.rollback()
        return False

@st.cache_data(ttl=30) # Cache for 30 seconds
def fetch_fulfillments(_connection, status_filter):
    if not _connection or not _connection.is_connected():
        _connection = get_db_connection()
        if not _connection:
            return pd.DataFrame()

    try:
        with _connection.cursor(dictionary=True) as cursor:
            if status_filter == "All":
                query = "SELECT * FROM fulfillment ORDER BY created_at DESC LIMIT 100"
                cursor.execute(query)
            else:
                query = "SELECT * FROM fulfillment WHERE fulfillment_status = %s ORDER BY created_at DESC LIMIT 100"
                cursor.execute(query, (status_filter,))
            
            results = cursor.fetchall()
            return pd.DataFrame(results) if results else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching fulfillments: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=10) # Cache for 10 seconds
def fetch_users(_connection):
    if not _connection or not _connection.is_connected():
        _connection = get_db_connection()
        if not _connection:
            return pd.DataFrame()

    try:
        with _connection.cursor(dictionary=True) as cursor:
            query = "SELECT mail_id, policy_type, policy_issued_date FROM user_details ORDER BY id DESC LIMIT 100"
            cursor.execute(query)
            results = cursor.fetchall()
            return pd.DataFrame(results) if results else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching users: {str(e)}")
        return pd.DataFrame()

def add_user_to_database(email, policy_type, policy_date):
    """Add new user to database via API"""
    try:
        user_validator_url = os.getenv('FASTAPI_BASE_URL', 'http://localhost:8000')
        
        user_data = {
            "mail_id": email,
            "policy_type": policy_type,
            "policy_issued_date": policy_date.strftime('%Y-%m-%d')
        }
        
        response = requests.post(f"{user_validator_url}/user", json=user_data, timeout=10)
        
        if response.status_code == 201:
            # st.cache_data.clear() # REMOVED - will be handled by the main page
            return True, "User added successfully!"
        elif response.status_code == 400:
            error_data = response.json()
            return False, error_data.get('detail', 'User already exists or invalid data')
        else:
            return False, f"Failed to add user. Status code: {response.status_code}, {response.text}"
            
    except requests.exceptions.RequestException as e:
        return False, f"API connection error: {str(e)}"
    except Exception as e:
        return False, f"Error adding user: {str(e)}"

@st.cache_data(ttl=10)
def check_api_health(url):
    """Check if API is online"""
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            return "Online", response.json().get('status', 'OK')
        return "Offline", f"Status Code {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "Offline", "ConnectionError"
    except Exception as e:
        return "Offline", str(e)

@st.cache_data(ttl=10)
def check_db_health():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('mysql_host'),
            port=int(os.getenv('mysql_port', 3306)),
            user=os.getenv('mysql_user'),
            password=os.getenv('mysql_password'),
            database=os.getenv('mysql_db'),
            connection_timeout=3
        )
        if connection.is_connected():
            connection.close()
            return "Online", "Connection Successful"
        return "Offline", "Connection Failed"
    except Exception as e:
        return "Offline", str(e)

@st.cache_data(ttl=10)
def fetch_worker_status(_connection):
    """Fetch last process time of mail jobs"""
    try:
        with _connection.cursor(dictionary=True) as cursor:
            query = "SELECT last_processed_at FROM mail_jobs ORDER BY last_processed_at DESC LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            if result and result['last_processed_at']:
                return "Active", result['last_processed_at'].strftime('%Y-%m-%d %H:%M:%S')
            return "Idle", "No jobs processed yet"
    except Exception as e:
        return "Unknown", str(e)

@st.cache_data(ttl=10)
def fetch_monitor_status(_connection):
    """Fetch last mail check status"""
    try:
        with _connection.cursor(dictionary=True) as cursor:
            query = "SELECT last_connection_time FROM last_mail_details ORDER BY id DESC LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            if result and result['last_connection_time']:
                return "Active", result['last_connection_time'].strftime('%Y-%m-%d %H:%M:%S')
            return "Unknown", "No mail checks logged"
    except Exception as e:
        return "Unknown", str(e)

# --- Page Navigation ---

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "Overview", 
        "AI Job Monitor (Live Log)", 
        "Human Fulfillment (Failures)", 
        "Processed Claims (Archive)", 
        "User Management", 
        "System Status"
    ]
)

# Get database connection once
connection = get_db_connection()

if not connection:
    st.markdown("""
    <div class="error-box">
        <h4>❌ Database Connection Failed</h4>
        <p>Unable to connect to the database. Please check your connection settings and try again.</p>
        <p>Ensure your <code>.env</code> file has the correct <code>mysql_host</code>, <code>mysql_port</code>, <code>mysql_user</code>, <code>mysql_password</code>, and <code>mysql_db</code>.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# --- Render Selected Page ---

if page == "Overview":
    # --- Main Page Layout ---
    st.markdown("""
    <div class="header-container">
        <h1 class="header-title">🏥 Insurance Claim Automation</h1>
        <p class="header-subtitle">Admin Dashboard & Monitoring</p>
    </div>
    """, unsafe_allow_html=True)

    # --- KPI Metrics Display ---
    kpis = get_kpi_metrics(connection)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card metric-jobs">
            <div class="metric-icon">📦</div>
            <h2 class="metric-value">{kpis['total_jobs_in_pipe']:,}</h2>
            <p class="metric-label">Total Jobs Received</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card metric-human">
            <div class="metric-icon">⚠️</div>
            <h2 class="metric-value">{kpis['pending_review']:,}</h2>
            <p class="metric-label">Pending Human Review</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card metric-pending">
            <div class="metric-icon">⏳</div>
            <h2 class="metric-value">{kpis['pending_processing']:,}</h2>
            <p class="metric-label">Pending AI Processing</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card metric-processed">
            <div class="metric-icon">✅</div>
            <h2 class="metric-value">{kpis['processed_success']:,}</h2>
            <p class="metric-label">Processed by AI</p>
        </div>
        """, unsafe_allow_html=True)

    # --- Instructions ---
    st.markdown("""
    <div class="section-header">
        <h2 class="section-title">🚀 Welcome to Mission Control</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div classs="info-box">
        <h4>👋 Welcome, Admin!</h4>
        <p>This dashboard is your central hub for monitoring and managing the entire insurance claim automation pipeline.
        Use the navigation menu on the left to access different modules.</p>
        <ul>
            <li><strong>AI Job Monitor:</strong> A live-updating view of the processing queue (your "live log").</li>
            <li><strong>Human Fulfillment:</strong> Review and manage claims that failed AI processing.</li>
            <li><strong>Processed Claims:</strong> View the final, archived claims that were saved by the AI.</li>
            <li><strong>User Management:</strong> Add new policyholders to the system.</li>
            <li><strong>System Status:</strong> Check the health of your background services.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Refresh Stats"):
        st.rerun()

elif page == "AI Job Monitor (Live Log)":
    st.title("🤖 AI Job Monitor (Live Log)")
    st.markdown("This page streams the combined terminal output from all backend services (`app.log`).")
    
    log_file_path = "app.log"
    
    # We will store the log lines in session state to append them
    if 'log_content' not in st.session_state:
        st.session_state.log_content = []
    
    log_placeholder = st.empty()

    try:
        # Open the file and read historical data
        with open(log_file_path, "r", encoding="utf-8") as f:
            # Read the whole file on first load to show history
            if not st.session_state.log_content:
                st.session_state.log_content = f.readlines()
                if len(st.session_state.log_content) > 200:
                    st.session_state.log_content = st.session_state.log_content[-200:]
            else:
                f.seek(0, 2) # Go to end if we already have content
            
            # Display initial content
            log_placeholder.code("".join(st.session_state.log_content), language="log")

            # This is the "tail" loop
            while True:
                line = f.readline()
                if not line:
                    # No new line, wait a bit
                    time.sleep(0.5) 
                else:
                    # New line found, append it and update the display
                    st.session_state.log_content.append(line)
                    # Keep trimming to the last 200 lines
                    if len(st.session_state.log_content) > 200:
                        st.session_state.log_content = st.session_state.log_content[1:] # Remove from start
                    
                    # Update the placeholder with the new content
                    log_placeholder.code("".join(st.session_state.log_content), language="log")

    except FileNotFoundError:
        st.error(f"Log file not found at: {log_file_path}")
        st.info("Please ensure 'main_runner.py' is running to generate the 'app.log' file.")
    except Exception as e:
        st.error(f"Error reading log file: {e}")
    except KeyboardInterrupt:
        pass # Allow stopping the app

elif page == "Human Fulfillment (Failures)":
    st.title("⚠️ Human Fulfillment Queue")
    st.markdown("Review and manage claims that failed AI processing and require manual intervention.")
    
    status_filter = st.radio(
        "Filter by Status",
        ["NEEDS_REVIEW", "RESOLVED"],
        horizontal=True
    )

    st.markdown("---")

    jobs_df = fetch_human_jobs(connection, status_filter)

    if jobs_df.empty:
        st.info(f"No jobs found with status: {status_filter}")
    else:
        st.subheader(f"Found {len(jobs_df)} jobs requiring review")
        
        for index, row in jobs_df.iterrows():
            with st.expander(f"**Claim ID:** `{row['claim_id']}`  |  **Sender:** `{row['sender_email']}`  |  **Failed:** `{row['created_at']}`"):
                st.markdown(f"#### Failure Reason (Job ID: {row['failed_job_id']})")
                st.error(f"`{row['error_message']}`")
                
                st.markdown("#### Full Job Data")
                try:
                    st.json(json.loads(row['full_job_data']))
                except:
                    st.code(row['full_job_data'], language='json')

                if row['status'] == 'NEEDS_REVIEW':
                    if st.button(f"Mark as Resolved (ID: {row['id']})"):
                        if mark_job_resolved(connection, row['id']):
                            st.success(f"Job {row['id']} marked as resolved.")
                            st.rerun()

elif page == "Processed Claims (Archive)":
    st.title("📋 Processed Claims Archive")
    st.markdown("View all claims that have been successfully processed by the AI and saved to the final `fulfillment` table.")
    
    # --- Filters ---
    status_filter = st.selectbox(
        "Filter by Status",
        ["All", "completed", "pending"],
        help="Select a status to filter claims"
    )

    st.markdown("---")

    df = fetch_fulfillments(connection, status_filter)

    if df.empty:
        st.info(f"No processed claims found with status: {status_filter}")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "fulfillment_id": st.column_config.TextColumn("Fulfillment ID", width="small"),
                "claim_id": st.column_config.TextColumn("Claim ID", width="medium"),
                "user_mail": st.column_config.TextColumn("Sender", width="medium"),
                "fulfillment_status": st.column_config.TextColumn("Status", width="small"),
                "attachment_count": st.column_config.NumberColumn("Attachments", width="small"),
                "created_at": st.column_config.DatetimeColumn("Processed At", format="YYYY-MM-DD HH:mm:ss"),
                "mail_content_s3_url": st.column_config.LinkColumn("Content URL", width="small"),
                "attachment_s3_urls": st.column_config.TextColumn("Attachment URLs", width="medium"),
                "missing_items": st.column_config.TextColumn("Missing Items", width="medium"),
            }
        )

# --- MODIFIED PAGE: User Management ---
elif page == "User Management":
    st.title("👥 User Management")
    st.markdown("Add new policyholders to the `user_details` table so they can be recognized by the system.")
    
    # --- Add User Form ---
    st.markdown("""
    <div class="section-header">
        <h2 class="section-title">➕ Add New User</h2>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        with st.form("add_user_form"):
            st.markdown("#### User Details")
            
            email = st.text_input(
                "Email Address *",
                placeholder="user@example.com",
                help="Enter a valid email address"
            )
            
            policy_type = st.selectbox(
                "Policy Type *",
                ["Health Insurance", "Life Insurance", "Auto Insurance", "Home Insurance", "Travel Insurance"],
                help="Select the type of insurance policy"
            )
            
            policy_date = st.date_input(
                "Policy Issued Date *",
                value=datetime.now().date(),
                help="Select when the policy was issued"
            )
            
            submitted = st.form_submit_button("🔒 Add User", use_container_width=True, type="primary")
            
            if submitted:
                if not email or "@" not in email:
                    st.error("❌ Please enter a valid email address")
                else:
                    with st.spinner("Adding user..."):
                        success, message = add_user_to_database(email, policy_type, policy_date)
                        if success:
                            # MODIFIED: Set a flag in session state instead of rerunning
                            st.session_state.user_added_success = message
                        else:
                            # Show error directly
                            st.error(f"❌ {message}")

    # --- NEW BLOCK ---
    # Check for the success flag *outside* the form
    if 'user_added_success' in st.session_state and st.session_state.user_added_success:
        st.success(f"✅ {st.session_state.user_added_success}")
        del st.session_state.user_added_success # Clear the flag
        st.cache_data.clear() # NOW we can clear the cache
        st.rerun() # And NOW it's safe to rerun
    # --- END NEW BLOCK ---

    with col2:
        st.markdown("""
        <div class="info-box">
            <h4>ℹ️ Instructions</h4>
            <p>This form calls the <strong>User Validator API</strong> to add a new policyholder to the <code>user_details</code> table.</p>
            <p>All fields marked with * are required.</p>
        </div>
        """, unsafe_allow_html=True)

    # --- Registered Users Table ---
    st.markdown("""
    <div class="section-header">
        <h2 class_name="section-title">👥 Registered Users</h2>
    </div>
    """, unsafe_allow_html=True)

    users_df = fetch_users(connection)

    if users_df.empty:
        st.markdown("""
        <div class="warning-box">
            <h4>👥 No Users Found</h4>
            <p>No registered users found in the system. Add your first user above!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.dataframe(
            users_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "mail_id": st.column_config.TextColumn("Email Address", width="large"),
                "policy_type": st.column_config.TextColumn("Policy Type", width="medium"),
                "policy_issued_date": st.column_config.DateColumn("Policy Date", format="YYYY-MM-DD", width="medium")
            }
        )
# --- END MODIFIED PAGE ---

elif page == "System Status":
    st.title("⚙️ System Status")
    st.markdown("Health checks for all background services and database connections.")
    
    # --- API Services Status ---
    st.markdown("""
    <div class="section-header">
        <h2 class="section-title">🌐 API Services Status</h2>
    </div>
    """, unsafe_allow_html=True)

    services = [
        {"name": "User Validator API", "url": os.getenv('FASTAPI_BASE_URL', 'http://localhost:8000') + "/", "port": 8000, "icon": "👤"},
        {"name": "Mail Service API", "url": os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001') + "/", "port": 8001, "icon": "📧"},
        {"name": "Fulfillment API", "url": os.getenv('FULFILLMENT_API_URL', 'http://localhost:8002') + "/", "port": 8002, "icon": "📋"}
    ]

    for service in services:
        status, message = check_api_health(service['url'])
        status_color = "#d4edda" if status == "Online" else "#f8d7da"
        status_text = f"🟢 {status}" if status == "Online" else f"🔴 {status}"
        
        st.markdown(f"""
        <div class="service-status" style="background-color: {status_color};">
            <div>
                <span class="service-name">{service['icon']} {service['name']}</span>
                <br>
                <span class="service-port">URL: {service['url']}</span>
            </div>
            <div style="text-align: right;">
                <strong style="font-size: 1.1rem;">{status_text}</strong>
                <br>
                <small>Info: {message}</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- Background Worker Status ---
    st.markdown("""
    <div class="section-header">
        <h2 class="section-title">⚙️ Background Worker Status</h2>
    </div>
    """, unsafe_allow_html=True)

    # --- Database ---
    db_status, db_msg = check_db_health()
    db_color = "#d4edda" if db_status == "Online" else "#f8d7da"
    db_text = f"🟢 {db_status}" if db_status == "Online" else f"🔴 {db_status}"
    st.markdown(f"""
    <div class="service-status" style="background-color: {db_color};">
        <div><span class="service-name">🗃️ MySQL Database</span></div>
        <div style="text-align: right;">
            <strong style="font-size: 1.1rem;">{db_text}</strong>
            <br><small>Info: {db_msg}</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- Mail Monitor ---
    mon_status, mon_msg = fetch_monitor_status(connection)
    mon_color = "#d4edda" if mon_status == "Active" else "#fff8e1"
    mon_text = f"🟢 {mon_status}" if mon_status == "Active" else f"🟡 {mon_status}"
    st.markdown(f"""
    <div class="service-status" style="background-color: {mon_color};">
        <div><span class="service-name">📥 Mail Monitor (Producer)</span></div>
        <div style="text-align: right;">
            <strong style="font-size: 1.1rem;">{mon_text}</strong>
            <br><small>Last Mail Check: {mon_msg}</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- Mail Worker ---
    work_status, work_msg = fetch_worker_status(connection)
    work_color = "#d4edda" if work_status == "Active" else "#fff8e1"
    work_text = f"🟢 {work_status}" if work_status == "Active" else f"🟡 {work_status}"
    st.markdown(f"""
    <div classs="service-status" style="background-color: {work_color};">
        <div><span class="service-name">🤖 Mail Worker (Consumer)</span></div>
        <div style="text-align: right;">
            <strong style="font-size: 1.1rem;">{work_text}</strong>
            <br><small>Last Job Processed: {work_msg}</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
