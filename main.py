# main.py
import streamlit as st
import requests
import re
import homepage  # dashboard logic
import chatbot 
import os

FLASK_URL = os.environ.get("FLASK_URL", "http://127.0.0.1:10000")

# ---------------------
# CONFIGURATION
# ---------------------
st.set_page_config(page_title="CanViz | Medical Auth", layout="wide", page_icon="🏥")

# ---------------------
# 🎨 CUSTOM STYLING (YOUR EXACT ORIGINAL DESIGN)
# ---------------------
def load_css():
    st.markdown("""
        <style>
        /* Main Background - Soft Medical Gradient */
        .stApp { background: linear-gradient(to bottom right, #f0f8ff, #e6f7ff); }
        
        /* Remove top padding */
        .block-container { padding-top: 3rem; padding-bottom: 3rem; }

        /* Center Form Container */
        [data-testid="stForm"] {
            background-color: white; padding: 2.5rem; 
            border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border-top: 5px solid #009688;
        }

        /* Input Fields */
        .stTextInput > div > div > input { border-radius: 8px; border: 1px solid #dfe6e9; padding: 10px; }

        /* 🌟 Make Input Labels Bigger and Bolder */
        .stTextInput label p {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            color: #334155 !important;
            margin-bottom: 4px !important;
        }

        /* Primary Button */
        div.stButton > button[kind="primary"] {
            background-color: #009688; border: none; color: white;
            padding: 0.6rem 1rem; border-radius: 25px; transition: all 0.3s;
            width: 100%; font-weight: bold; font-size: 16px;
        }
        div.stButton > button[kind="primary"]:hover { background-color: #00796b; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }

        /* Secondary Button */
        div.stButton > button[kind="secondary"] {
            border: 1px solid #009688; color: #009688; border-radius: 25px; width: 100%;
        }
        div.stButton > button[kind="secondary"]:hover { background-color: #e0f2f1; border-color: #00796b; color: #00796b; }
        
        /* Headers */
        h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #2d3436; }
        </style>
    """, unsafe_allow_html=True)

load_css()

# ---------------------
# SESSION STATE INIT
# ---------------------
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "name" not in st.session_state: st.session_state.name = ""    
if "email" not in st.session_state: st.session_state.email = ""
if "role" not in st.session_state: st.session_state.role = "user" 
if "page" not in st.session_state: st.session_state.page = "Login"
if "auth_msg" not in st.session_state: st.session_state.auth_msg = ""
if "msg_type" not in st.session_state: st.session_state.msg_type = "error"

# --- RESTORE SESSION FROM URL ---
if not st.session_state.logged_in and "user" in st.query_params:
    st.session_state.logged_in = True
    saved_user = st.query_params["user"]
    st.session_state.username = saved_user
    
    try:
        users_response = requests.get(f"{FLASK_URL}/users")
        if users_response.status_code == 200:
            for u in users_response.json():
                if u["username"] == saved_user:
                    st.session_state.name = u["name"]
                    st.session_state.email = u["email"]
                    st.session_state.role = u.get("role", "user") 
                    break
    except:
        pass

# ---------------------
# HELPER: EMAIL VALIDATION
# ---------------------
def is_valid_email(email):
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email) is not None

def set_message(msg, type="error"):
    st.session_state.auth_msg = msg
    st.session_state.msg_type = type

def switch_page(page_name):
    st.session_state.page = page_name
    st.session_state.auth_msg = "" 

# ---------------------
# LOGIC: UNIFIED LOGIN
# ---------------------
def handle_login(email, password):
    if not email or not password:
        set_message("Please enter both email and password")
        st.rerun() # 🌟 Instantly updates the UI with the error!

    if not is_valid_email(email):
        set_message("⚠️ Invalid email format", "error")
        st.rerun()

    # Master Admin Hardcoded Override
    if email == "admin@gmail.com" and password == "123456":
        st.session_state.auth_msg = ""
        st.session_state.logged_in = True
        st.session_state.username = "master_admin"
        st.session_state.name = "System Administrator"
        st.session_state.email = "admin@gmail.com"
        st.session_state.role = "admin"
        st.session_state.page = "admin"
        st.query_params.clear() # Clears logout bugs
        st.rerun()

    # Standard Database Login for Doctors and Patients
    try:
        response = requests.post(f"{FLASK_URL}/login", json={"email": email, "password": password})

        if response.status_code == 200:
            data = response.json()
            db_role = data.get("role", "user")
            
            st.session_state.auth_msg = ""
            st.session_state.logged_in = True
            st.session_state.username = data.get("username", "")
            st.session_state.name = data.get("name", "") 
            st.session_state.email = data.get("email", email) 
            st.session_state.role = db_role 
            
            # Multi-Role Routing
            if db_role == "admin":
                st.session_state.page = "admin"
            elif db_role == "doctor":
                st.session_state.page = "doctor_dashboard" 
            else:
                st.session_state.page = "home" 
            
            st.query_params.clear()
            st.rerun()
            
        elif response.status_code == 404:
            set_message("Email not found")
            st.rerun()
        elif response.status_code == 401:
            set_message("Wrong password")
            st.rerun()
        else:
            set_message("Login failed")
            st.rerun()
    except requests.exceptions.ConnectionError:
        set_message("❌ Cannot connect to backend. Is flask_app.py running?")
        st.rerun()

# ---------------------
# LOGIC: PATIENT REGISTRATION
# ---------------------
def handle_register(name, email, username, password, confirm):
    if not name or not email or not username or not password:
        set_message("Please fill all fields")
        st.rerun()
    
    if len(password) < 6:
        set_message("⚠️ Password must be at least 6 characters long")
        st.rerun()
        
    if password != confirm:
        set_message("Passwords do not match")
        st.rerun()
        
    if not is_valid_email(email):
        set_message("⚠️ Invalid email format")
        st.rerun()

    try:
        payload = {
            "username": username, 
            "password": password, 
            "name": name, 
            "email": email,
            "role": "user" 
        }
        response = requests.post(f"{FLASK_URL}/register", json=payload)

        if response.status_code == 201:
            st.session_state.page = "Login"
            set_message("Patient Registration successful! Please log in.", "success")
            st.rerun()
        elif response.status_code == 409:
            set_message("Username or Email already exists")
            st.rerun()
        else:
            set_message("Registration failed")
            st.rerun()
    except requests.exceptions.ConnectionError:
        set_message("❌ Cannot connect to backend")
        st.rerun()

# ---------------------
# UI PAGES
# ---------------------
def render_message():
    if st.session_state.auth_msg:
        if st.session_state.msg_type == "success":
            st.success(st.session_state.auth_msg, icon="✅")
        else:
            st.error(st.session_state.auth_msg, icon="⚠️")

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #009688; margin-bottom: 0;">CanViz</h1>
                <p style="color: gray; font-size: 0.9em;">Multi Cancer Detection System</p>
                <h3 style="margin-top: 20px;">Secure Login Portal</h3>
            </div>
        """, unsafe_allow_html=True)
        
        render_message()

        # 🌟 THE FIX: Kept your beautiful st.form but removed the buggy callback!
        with st.form("login_form"):
            login_email = st.text_input("Email Address", placeholder="name@example.com") 
            login_password = st.text_input("Password", type="password", placeholder="Enter your secure password")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Login", type="primary")

        # The logic runs synchronously AFTER the form submits
        if submitted:
            st.session_state.auth_msg = ""
            handle_login(login_email.strip(), login_password)

        st.markdown("""
            <div style="text-align: center; margin-top: 20px; color: gray;">
                Are you a new patient?
            </div>
        """, unsafe_allow_html=True)
        st.button("Register Patient Account", on_click=switch_page, args=("Register",), type="secondary")

def register_page():
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #009688; margin-bottom: 0;">CanViz</h1>
                <p style="color: gray; font-size: 0.9em;">Medical Intelligence System</p>
                <h3 style="margin-top: 20px;">Patient Registration</h3>
            </div>
        """, unsafe_allow_html=True)
        
        render_message()

        with st.form("register_form"):
            c1, c2 = st.columns(2)
            with c1: reg_name = st.text_input("Full Name", placeholder="Adam Smith")
            with c2: reg_user = st.text_input("Username", placeholder="adamsmith99")
                
            reg_email = st.text_input("Email Address", placeholder="adam@gmail.com")
            
            p1, p2 = st.columns(2)
            with p1: reg_pass = st.text_input("Password", type="password")
            with p2: reg_confirm = st.text_input("Confirm Password", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Complete Registration", type="primary")

        if submitted:
            st.session_state.auth_msg = ""
            handle_register(reg_name.strip(), reg_email.strip(), reg_user.strip(), reg_pass, reg_confirm)

        st.markdown("""
            <div style="text-align: center; margin-top: 20px; color: gray;">
                Already have access?
            </div>
        """, unsafe_allow_html=True)
        st.button("Return to Login", on_click=switch_page, args=("Login",), type="secondary")
        

# ---------------------
# MASTER CONTROLLER
# ---------------------
if st.session_state.logged_in:
    chatbot.show_floating_interface()
    
    if st.session_state.role == "admin":
        import admin
        admin.show_admin_page()
    elif st.session_state.role == "doctor":
        import doctor
        doctor.show_doctor_page()
    else:
        homepage.show_homepage()
else:
    if st.session_state.page == "Register":
        register_page()
    else:
        login_page()