import streamlit as st
import pandas as pd
import requests
import time
import os 
import base64
import plotly.express as px  
from datetime import datetime, timedelta
import math
from fpdf import FPDF

# 🌟 NEW: Supabase Import
from supabase import create_client, Client

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FLASK_URL = "http://127.0.0.1:5000"

CANCER_ONLY_CLASSES = [
    "Blood Cancer - Stage 1", "Blood Cancer - Stage 2", "Blood Cancer - Stage 3",
    "Breast Cancer", "Colon Cancer", "Kidney Cancer",
    "Lung Cancer - Stage 1", "Lung Cancer - Stage 2"
]

# ---------------------
# HIGH-SPEED CACHING ENGINE
# ---------------------
@st.cache_data(ttl=30)
def fetch_global_users():
    try:
        res = requests.get(f"{FLASK_URL}/users", timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# ---------------------
# HELPER: LOAD IMAGE AS BASE64
# ---------------------
def get_base64_image(path):
    try:
        with open(path, "rb") as img:
            return base64.b64encode(img.read()).decode()
    except FileNotFoundError:
        return "" 

# ---------------------
# HELPER: GENERATE REFERRAL LETTER
# ---------------------
def generate_referral_letter(doctor_name, patient_name, scan_id, date, result, confidence, urgency, notes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "CLINICAL ONCOLOGY REFERRAL", ln=True, align="C")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True)
    pdf.cell(0, 6, f"Referring Physician: Dr. {doctor_name}", ln=True)
    pdf.cell(0, 6, "To: Oncology & Specialist Department", ln=True)
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 12)
    if urgency == "High (Immediate)": pdf.set_text_color(220, 38, 38)
    elif urgency == "Moderate": pdf.set_text_color(217, 119, 6)
    else: pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, f"SUBJECT: {urgency.upper()} REFERRAL FOR PATIENT {patient_name.upper()}", ln=True)
    pdf.set_text_color(15, 23, 42)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    body_text = (
        f"Dear Colleague,\n\n"
        f"I am formally referring my patient, {patient_name}, for specialist evaluation, further histopathological confirmation, and subsequent treatment management.\n\n"
        f"On {date}, a tissue biopsy sample (Scan ID: {scan_id}) was analyzed utilizing the CanViz AI Diagnostic System. The computational neural network flagged the morphology as abnormal, yielding the following results:\n\n"
        f"Primary AI Finding: {result}\n"
        f"AI Confidence Score: {confidence}\n\n"
        f"Clinical Notes & Reason for Referral:\n{notes}\n\n"
        f"Given the AI-assisted indications and the {urgency.lower()} priority of this case, I would greatly appreciate your expert consultation and intervention.\n\n"
        f"The patient's full AI Diagnostic Report, including Grad-CAM heatmaps and morphological overlays, has been attached to their electronic health record for your review.\n\n"
        f"Sincerely,\n\n"
        f"Dr. {doctor_name}\n"
        f"CanViz Medical Command Center"
    )
    pdf.multi_cell(0, 6, body_text)
    return bytes(pdf.output())

def show_admin_page():
    # --- SECURITY CHECK ---
    if st.session_state.get("role") != "admin":
        st.error("🛑 UNAUTHORIZED ACCESS. Administrators only.")
        st.stop()

    if "admin_del_hist_id" not in st.session_state: st.session_state.admin_del_hist_id = None
    if "admin_del_global_id" not in st.session_state: st.session_state.admin_del_global_id = None
    if "hist_page" not in st.session_state: st.session_state.hist_page = 1 
    if "ref_page" not in st.session_state: st.session_state.ref_page = 1

    admin_name = st.session_state.get("name", "Administrator")

    # --- CSS STYLING & PREMIUM NAVBAR TRICK ---
    st.markdown("""
    <style>
    /* 🌟 THE SECRET NAVBAR TRICK: High-Visibility Boxes 🌟 */
    [data-baseweb="tab-list"] {
        background-color: #000000 !important;
        padding: 15px 20px;
        border-radius: 16px;
        box-shadow: 0px 8px 16px rgba(0,0,0,0.6);
        margin-bottom: 25px;
        gap: 15px; 
    }
    
    [data-baseweb="tab"] {
        background-color: #1E293B !important; 
        border: 2px solid #475569 !important; 
        border-radius: 8px !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease;
    }
    
    /* NUCLEAR OPTION FOR PURE WHITE TEXT */
    [data-baseweb="tab"], 
    [data-baseweb="tab"] *, 
    [data-baseweb="tab"] span, 
    [data-baseweb="tab"] p {
        color: #FFFFFF !important; 
        font-weight: 800 !important;
        font-size: 14px !important;
        letter-spacing: 0.05em !important;
    }
    
    [data-baseweb="tab"]:hover {
        background-color: #334155 !important; 
        border-color: #94A3B8 !important; 
        transform: translateY(-2px);
    }
    
    /* 🌟 Admin Active Tab Highlight (Crimson Red) 🌟 */
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: #E11D48 !important; 
        border-color: #E11D48 !important;
        box-shadow: 0 4px 12px rgba(225, 29, 72, 0.6) !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"],
    [data-baseweb="tab"][aria-selected="true"] *,
    [data-baseweb="tab"][aria-selected="true"] span,
    [data-baseweb="tab"][aria-selected="true"] p {
        color: #FFFFFF !important;
    }
    
    [data-baseweb="tab-highlight"] { display: none !important; }

    /* Admin Shared Styles */
    .admin-header {
        font-size: 2.5rem; font-weight: 900;
        background: linear-gradient(135deg, #1E293B, #E11D48);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0px;
    }
    .admin-sub { color: #64748B; font-size: 1.05rem; margin-bottom: 30px; }
    
    .badge-soft {
        padding: 6px 12px; border-radius: 8px; font-weight: 700;
        font-size: 0.85rem; letter-spacing: 0.5px; text-transform: uppercase;
        display: inline-block;
    }
    .badge-safe { background-color: #DEF7EC; color: #03543F; } 
    .badge-alert { background-color: #FDE8E8; color: #9B1C1C; } 
    .badge-warn { background-color: #FEF08A; color: #723B13; }  
    
    .scan-id { font-size: 1.1rem; font-weight: 700; color: #0F172A; }
    .scan-date { font-size: 0.85rem; color: #64748B; margin-top: 4px; }
    .scan-file { font-size: 0.85rem; color: #0284c7; margin-top: 2px; font-weight: 500; } 
    
    div[data-testid="metric-container"] {
        background-color: white; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 15px 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); text-align: center;
    }
    
    /* Pagination Styling */
    .page-indicator {
        text-align: center; font-size: 1.1rem; font-weight: 700; color: #1E293B; padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- BRANDING HEADER & LOGOUT ---
    logo_base64 = get_base64_image("assets/logo_canviz.png")
    
    head_col1, head_col2, head_col3 = st.columns([3.5, 0.8, 1.2], vertical_alignment="center")
    
    with head_col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 15px;">
            <img src="data:image/png;base64,{logo_base64}" style="height: 45px; width: auto; object-fit: contain;">
            <span style="font-size: 1.8rem; font-weight: 900; background: linear-gradient(135deg, #1E293B, #E11D48); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">ADMIN CONTROL PANEL</span>
        </div>
        """, unsafe_allow_html=True)
        
    with head_col2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        
    with head_col3:
        st.markdown(f"""
        <div style="background: #000000; padding: 8px 18px; border-radius: 10px; color: white; font-family: monospace; font-weight: bold; text-align: center;">
            ⚙️ Admin: {admin_name}
        </div>
        """, unsafe_allow_html=True)
            
    st.markdown("<br>", unsafe_allow_html=True)

    # 🌟 NEW BLACK NAVBAR WITH PROTOCOLS
    tab_dash, tab_register, tab_manage, tab_protocols, tab_history, tab_appointments = st.tabs([
        "📈 DASHBOARD",
        "👨‍⚕️ REGISTRATION", 
        "👥 USERS", 
        "💉 PROTOCOLS",
        "📊 DATABASE", 
        "🗓️ APPOINTMENTS"
    ])

    # ==========================================
    # 🌟 TAB 0: INTERACTIVE EPIDEMIOLOGY DASHBOARD 🌟
    # ==========================================
    with tab_dash:
        st.subheader("Global Epidemiology & System Analytics")
        st.write("Live data aggregation from all CanViz clinical endpoints.")
        
        try:
            res = supabase.table('history').select('*').execute()
            df_dash = pd.DataFrame(res.data)
        except:
            df_dash = pd.DataFrame()

        if df_dash.empty:
            st.info("Insufficient data available to generate system analytics. Upload more scans to populate the dashboard.")
        else:
            df_dash['conf_float'] = pd.to_numeric(df_dash['confidence'].astype(str).str.replace('%', ''), errors='coerce')
            df_dash['date_obj'] = pd.to_datetime(df_dash['date'], errors='coerce')
            df_dash['date_only'] = df_dash['date_obj'].dt.date
            df_dash['month_year'] = df_dash['date_obj'].dt.to_period('M').astype(str)

            st.markdown("##### 📅 Filter Analytics Data")
            filt_col1, filt_col2 = st.columns(2)
            
            with filt_col1:
                filter_mode = st.selectbox(
                    "Select Date Range Mode:", 
                    ["All Time", "Specific Date", "Specific Month", "Last 5 Days", "Last 10 Days", "Last 30 Days"]
                )
            
            current_date = datetime.now().date()
            filtered_df = df_dash.copy()

            with filt_col2:
                if filter_mode == "Specific Date":
                    chosen_date = st.date_input("Select Exact Date:", current_date)
                    filtered_df = df_dash[df_dash['date_only'] == chosen_date]
                
                elif filter_mode == "Specific Month":
                    months_list = df_dash['month_year'].dropna().unique().tolist()
                    months_list.sort(reverse=True)
                    if months_list:
                        chosen_month = st.selectbox("Select Month:", months_list)
                        filtered_df = df_dash[df_dash['month_year'] == chosen_month]
                    else:
                        st.info("No valid month data available.")
                        filtered_df = pd.DataFrame()
                
                elif filter_mode == "Last 5 Days":
                    cutoff = current_date - timedelta(days=5)
                    filtered_df = df_dash[df_dash['date_only'] >= cutoff]
                    st.info(f"Showing records since {cutoff}")
                    
                elif filter_mode == "Last 10 Days":
                    cutoff = current_date - timedelta(days=10)
                    filtered_df = df_dash[df_dash['date_only'] >= cutoff]
                    st.info(f"Showing records since {cutoff}")
                    
                elif filter_mode == "Last 30 Days":
                    cutoff = current_date - timedelta(days=30)
                    filtered_df = df_dash[df_dash['date_only'] >= cutoff]
                    st.info(f"Showing records since {cutoff}")

            if filtered_df.empty:
                st.warning(f"No scans found for the selected filter: {filter_mode}")
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                
                with m1:
                    st.metric(label="Total Biopsies Analyzed", value=len(filtered_df), delta=filter_mode)
                with m2:
                    avg_conf = filtered_df['conf_float'].mean()
                    st.metric(label="Average AI Confidence", value=f"{avg_conf:.1f}%", delta="High Precision Matrix", delta_color="normal")
                with m3:
                    most_common = filtered_df['result'].mode()[0] if not filtered_df['result'].empty else "N/A"
                    st.metric(label="Most Frequent Detection", value=most_common, delta="Primary Target")

                st.markdown("<br>", unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                with c1:
                    with st.container(border=True):
                        st.markdown("**Cancer Type Distribution**")
                        fig_pie = px.pie(
                            filtered_df, 
                            names='result', 
                            hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
                with c2:
                    with st.container(border=True):
                        st.markdown("**System Traffic (Scans Over Time)**")
                        df_dates = filtered_df.groupby('date_only').size().reset_index(name='scans')
                        fig_line = px.line(
                            df_dates, 
                            x='date_only', 
                            y='scans', 
                            markers=True,
                            line_shape="spline"
                        )
                        fig_line.update_traces(line_color="#E11D48", marker=dict(size=8, color="#1E293B"))
                        fig_line.update_layout(margin=dict(t=10, b=10, l=10, r=10), xaxis_title="Date", yaxis_title="Number of Scans Processed")
                        st.plotly_chart(fig_line, use_container_width=True)

    # ==========================================
    # TAB 1: DOCTOR REGISTRATION
    # ==========================================
    with tab_register:
        with st.container(border=True):
            st.subheader("Onboard a New Doctor")
            st.write("Create official access credentials for certified medical professionals.")
            
            with st.form("doc_register_form"):
                c1, c2 = st.columns(2)
                with c1: doc_name = st.text_input("Doctor's Full Name", placeholder="Dr. Imran")
                with c2: doc_user = st.text_input("Username", placeholder="dr_imran")
                
                doc_email = st.text_input("Official Email Address", placeholder="imran.doc@gmail.com", help="Use standard format: name.doc@gmail.com")
                
                p1, p2 = st.columns(2)
                with p1: doc_pass = st.text_input("Assign Password", type="password")
                with p2: doc_confirm = st.text_input("Confirm Password", type="password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit_doc = st.form_submit_button("✅ Register Doctor Account", type="primary", use_container_width=True)
                
                if submit_doc:
                    if not doc_name or not doc_user or not doc_email or not doc_pass:
                        st.error("⚠️ All fields are required.")
                    elif doc_pass != doc_confirm:
                        st.error("⚠️ Passwords do not match.")
                    elif ".doc@" not in doc_email:
                        st.warning("⚠️ Please use the official format (e.g., name.doc@gmail.com)")
                    else:
                        payload = {
                            "username": doc_user,
                            "password": doc_pass,
                            "name": doc_name,
                            "email": doc_email
                        }
                        try:
                            with st.spinner("Registering doctor into the secure database..."):
                                res = requests.post(f"{FLASK_URL}/admin/register_doctor", json=payload)
                                
                            if res.status_code == 201:
                                st.success(f"Success! {doc_name} has been added to the system.")
                            elif res.status_code == 409:
                                st.error("❌ Username or Email already exists in the system.")
                            else:
                                st.error("Failed to register. Server error.")
                        except Exception as e:
                            st.error(f"Connection Error: {e}")

    # ==========================================
    # TAB 2: USER MANAGEMENT
    # ==========================================
    with tab_manage:
        st.subheader("Search & Manage Users")
        try:
            resp = requests.get(f"{FLASK_URL}/users")
            df_users = pd.DataFrame(resp.json() if resp.status_code == 200 else [])
        except:
            df_users = pd.DataFrame()

        if not df_users.empty:
            if 'role' in df_users.columns:
                df_normal_users = df_users[df_users['role'] != 'admin']
            else:
                df_normal_users = df_users
            
            search_user = st.text_input("🔍 Search Users (by Name, Username, or Email):", placeholder="Type here to filter the list...")
            
            if search_user:
                df_normal_users = df_normal_users[
                    df_normal_users['username'].str.contains(search_user, case=False, na=False) |
                    df_normal_users['name'].str.contains(search_user, case=False, na=False) |
                    df_normal_users['email'].str.contains(search_user, case=False, na=False)
                ]

            user_list = df_normal_users['username'].tolist()
            
            if user_list:
                selected_user = st.selectbox("Select a User to View/Modify:", user_list)
                user_info = df_normal_users[df_normal_users['username'] == selected_user].iloc[0]
                
                with st.container(border=True):
                    role_badge = "👨‍⚕️ DOCTOR" if user_info.get('role') == 'doctor' else "👤 PATIENT"
                    st.markdown(f"### 🛠️ Profile: {selected_user} <span style='font-size:14px; background:#E2E8F0; padding:4px 8px; border-radius:4px; color:#334155;'>{role_badge}</span>", unsafe_allow_html=True)
                    
                    with st.form("edit_user_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            new_u = st.text_input("Username", user_info['username'])
                            new_e = st.text_input("Email", user_info['email'])
                        with col2:
                            new_n = st.text_input("Full Name", user_info['name'])
                            new_p = st.text_input("Password", "********")
                            
                        if st.form_submit_button("💾 Save Profile Changes", type="primary"):
                            pass_to_send = new_p if new_p != "********" else user_info['password']
                            
                            payload = {"target_username": selected_user, "new_username": new_u, "new_name": new_n, "new_email": new_e, "new_password": pass_to_send}
                            res = requests.put(f"{FLASK_URL}/admin_update_user", json=payload)
                            if res.status_code == 200:
                                st.toast("User updated successfully!", icon="✅")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res.json().get("message", "Error updating user"))
                
                if st.button("🗑️ Delete Entire Account", type="secondary"):
                    res = requests.delete(f"{FLASK_URL}/delete_account", json={"username": selected_user})
                    if res.status_code == 200:
                        st.toast("User deleted permanently!", icon="🗑️")
                        time.sleep(1)
                        st.rerun()

    # ==========================================
    # 🌟 TAB 3: ADMIN PROTOCOLS & REFERRALS 🌟
    # ==========================================
    with tab_protocols:
        st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #E11D48;">Global Protocol & Referral Management</div><br>', unsafe_allow_html=True)
        st.write("Establish treatment plans and generate referral letters globally on behalf of any doctor.")
        
        all_users = fetch_global_users()
        all_patients = [u for u in all_users if u.get('role') == 'user']
        all_doctors = [u for u in all_users if u.get('role') == 'doctor']

        if not all_patients or not all_doctors:
            st.warning("⚠️ The system requires at least one registered patient and one registered doctor to establish protocols.")
        else:
            sub_admin_protocols, sub_admin_referrals = st.tabs(["💉 Treatment Protocols & Scheduling", "📄 Generate Referral Letters"])
            
            pat_map = {p['username']: p for p in all_patients}
            doc_names = [d['name'] for d in all_doctors]
            
            with sub_admin_protocols:
                sel_col1, sel_col2 = st.columns(2)
                with sel_col1: selected_treat_patient = st.selectbox("1️⃣ Select Target Patient:", list(pat_map.keys()))
                with sel_col2: selected_doctor_for_plan = st.selectbox("2️⃣ Assign to Attending Doctor:", doc_names)
                
                try:
                    all_pat_appts_res = supabase.table('appointments').select('*').eq('username', selected_treat_patient).eq('doctor', selected_doctor_for_plan).eq('doctor_deleted', 0).execute()
                    all_pat_appts = all_pat_appts_res.data if all_pat_appts_res.data else []
                    
                    st.markdown("---")
                    st.markdown(f"#### Active Protocols for @{selected_treat_patient} under Dr. {selected_doctor_for_plan}")
                    
                    plan_res = supabase.table('treatment_plans').select('*').eq('patient_username', selected_treat_patient).eq('doctor_name', selected_doctor_for_plan).execute()
                    if plan_res.data:
                        for plan in plan_res.data:
                            with st.expander(f"💉 {plan['treatment_type']} | Started: {plan['start_date']}", expanded=True):
                                st.markdown(f"**Target Duration:** {plan['duration_months']} Months | **Frequency:** {plan['frequency']}")
                                st.markdown(f"**Protocol Details:** {plan['notes']}")
                                
                                freq_map = {"Weekly": 4, "Bi-Weekly": 2, "Monthly": 1, "Quarterly": 0.33, "As Needed": 1}
                                sessions_per_month = freq_map.get(plan['frequency'], 1)
                                target_total_sessions = int(plan['duration_months'] * sessions_per_month)
                                if target_total_sessions < 1: target_total_sessions = 1
                                
                                completed_count = sum(1 for a in all_pat_appts if a.get('status') == 'Completed' and plan['treatment_type'] in str(a.get('notes', '')))
                                display_count = min(completed_count, target_total_sessions)
                                progress = min(display_count / target_total_sessions, 1.0)
                                percent_complete = int(progress * 100)
                                
                                st.progress(progress)
                                st.markdown(f"<div style='text-align:right; font-weight:bold; color:#E11D48; margin-bottom:10px;'>{display_count}/{target_total_sessions} Sessions Completed ({percent_complete}%)</div>", unsafe_allow_html=True)
                                
                                st.markdown("---")
                                pending_for_plan = [a for a in all_pat_appts if a.get('status') != 'Completed' and plan['treatment_type'] in str(a.get('notes', ''))]
                                
                                if pending_for_plan:
                                    next_appt = sorted(pending_for_plan, key=lambda x: x['date'])[0]
                                    st.success(f"📅 **Next Session Confirmed:** Patient is scheduled for **{next_appt['date']} at {next_appt['time']}**.")
                                else:
                                    st.warning("⚠️ **Action Required:** No upcoming session scheduled for this protocol.")
                                    st.markdown("##### Schedule Next Session:")
                                    
                                    b_col1, b_col2 = st.columns([1, 1.5])
                                    with b_col1: b_date = st.date_input("Date", min_value=datetime.now().date(), key=f"admin_book_date_{plan['id']}")
                                    with b_col2:
                                        available_times = []
                                        if b_date:
                                            try:
                                                res = requests.post(f"{FLASK_URL}/get_available_times", json={"doctor_name": selected_doctor_for_plan, "date": str(b_date)})
                                                if res.status_code == 200: available_times = res.json().get("available_times", [])
                                            except: pass
                                        
                                        if not available_times:
                                            st.error("No slots available for this date.")
                                            b_time = None
                                        else:
                                            b_time = st.selectbox("Time", available_times, key=f"admin_book_time_{plan['id']}")
                                            
                                    b_notes = st.text_input("Session Notes (Optional):", key=f"admin_b_notes_{plan['id']}")
                                            
                                    if b_time and st.button("✅ Book Session & Notify Patient", key=f"admin_btn_book_{plan['id']}", type="primary"):
                                        target_email = pat_map[selected_treat_patient].get('email', 'DISABLED')
                                        target_name = pat_map[selected_treat_patient].get('name', selected_treat_patient)
                                        
                                        protocol_stamp = f"Protocol Session: {plan['treatment_type']}"
                                        final_note = f"{protocol_stamp}. Note: {b_notes}" if b_notes else protocol_stamp
                                        
                                        payload = {
                                            "username": selected_treat_patient, "email": target_email, "name": target_name,
                                            "date": str(b_date), "time": b_time, "doctor": selected_doctor_for_plan,
                                            "notes": final_note, "attached_scan": "None" 
                                        }
                                        with st.spinner("Booking session and synchronizing globally..."):
                                            try:
                                                pre_check = supabase.table('appointments').select('id').eq('username', selected_treat_patient).execute()
                                                pre_count = len(pre_check.data) if pre_check.data else 0
                                                
                                                response = requests.post(f"{FLASK_URL}/book_appointment", json=payload)
                                                if response.status_code == 200:
                                                    for _ in range(15):
                                                        post_check = supabase.table('appointments').select('id').eq('username', selected_treat_patient).execute()
                                                        post_count = len(post_check.data) if post_check.data else 0
                                                        if post_count > pre_count:
                                                            supabase.table('appointments').update({"status": "Approved"}).eq('username', selected_treat_patient).eq('doctor', selected_doctor_for_plan).eq('status', 'Pending').execute()
                                                            break
                                                        time.sleep(0.3)
                                                        
                                                    st.toast("Session Scheduled & Auto-Approved!", icon="✅")
                                                    time.sleep(0.5)
                                                    st.rerun()
                                            except Exception as e: st.error(f"Error: {e}")

                                st.markdown("---")
                                st.button("🛑 Terminate Protocol", key=f"admin_term_btn_{plan['id']}", type="secondary")
                                if st.session_state.get(f"admin_term_btn_{plan['id']}"):
                                    try:
                                        supabase.table('treatment_plans').delete().eq('id', plan['id']).execute()
                                    except Exception: pass
                                    st.rerun()
                    else:
                        st.info("No active treatment plans established for this patient/doctor combination.")
                    st.markdown("---")
                    
                    st.markdown("#### Establish New Protocol & Anchor Session")
                    patient_hist = supabase.table('history').select('*').eq('username', selected_treat_patient).order('date', desc=True).execute()
                    scan_options = []
                    if patient_hist.data:
                        for r in patient_hist.data:
                            if "Healthy" not in r["result"] and "Inconclusive" not in r["result"]:
                                scan_options.append(f"{r['result']} | {r['confidence']} [Scan ID: {r['scan_id']}]")
                    if not scan_options: scan_options = ["No Malignant Scans Found - Manual Selection: " + c for c in CANCER_ONLY_CLASSES]

                    with st.container(border=True):
                        t_cancer_target = st.selectbox("🎯 Target Cancer Diagnosis (Linked to Scan)", scan_options, key="admin_canc_tgt")
                        t_col1, t_col2 = st.columns(2)
                        with t_col1:
                            t_type = st.selectbox("Primary Treatment Modality", ["Chemotherapy", "Radiation Therapy", "Targeted Therapy", "Surgery Follow-up", "Observation/Monitoring"], key="admin_t_type")
                            t_duration = st.number_input("Duration (in Months)", min_value=1, max_value=60, value=6, key="admin_t_dur")
                        with t_col2:
                            t_freq = st.selectbox("Session Frequency", ["Weekly", "Bi-Weekly", "Monthly", "Quarterly", "As Needed"], key="admin_t_freq")
                            
                        st.markdown("##### 📅 Book First Clinical Session (Anchor)")
                        b_col1, b_col2 = st.columns([1, 1.5])
                        with b_col1: t_start = st.date_input("Session Date", min_value=datetime.now().date(), key="admin_anchor_date")
                        with b_col2:
                            available_times = []
                            if t_start:
                                try:
                                    res = requests.post(f"{FLASK_URL}/get_available_times", json={"doctor_name": selected_doctor_for_plan, "date": str(t_start)})
                                    if res.status_code == 200: available_times = res.json().get("available_times", [])
                                except: pass
                            
                            if not available_times:
                                st.warning("No slots available for this date.")
                                b_time = None
                            else:
                                b_time = st.selectbox("Session Time", available_times, key="admin_anchor_time")
                                
                        t_notes = st.text_area("Clinical Notes & Protocol Details", placeholder="Specify dosage, machine targets, or secondary medications...", key="admin_t_notes")
                        
                        if b_time and st.button("💾 Establish Protocol & Notify Patient", type="primary"):
                            target_email = pat_map[selected_treat_patient].get('email', 'DISABLED')
                            target_name = pat_map[selected_treat_patient].get('name', selected_treat_patient)
                            combined_treatment = f"{t_type} for {t_cancer_target}"
                            
                            with st.spinner("Saving Protocol and synchronizing globally..."):
                                try:
                                    supabase.table('treatment_plans').insert({
                                        "doctor_name": selected_doctor_for_plan, "patient_username": selected_treat_patient,
                                        "treatment_type": combined_treatment, "duration_months": t_duration,
                                        "frequency": t_freq, "start_date": str(t_start), "notes": t_notes
                                    }).execute()
                                    
                                    pre_check = supabase.table('appointments').select('id').eq('username', selected_treat_patient).execute()
                                    pre_count = len(pre_check.data) if pre_check.data else 0
                                    
                                    payload = {
                                        "username": selected_treat_patient, "email": target_email, "name": target_name,
                                        "date": str(t_start), "time": b_time, "doctor": selected_doctor_for_plan,
                                        "notes": f"Protocol Session: {combined_treatment}. Doctor's Note: {t_notes}", "attached_scan": "None" 
                                    }
                                    response = requests.post(f"{FLASK_URL}/book_appointment", json=payload)
                                    
                                    if response.status_code == 200:
                                        for _ in range(15):
                                            post_check = supabase.table('appointments').select('id').eq('username', selected_treat_patient).execute()
                                            post_count = len(post_check.data) if post_check.data else 0
                                            if post_count > pre_count:
                                                supabase.table('appointments').update({"status": "Approved"}).eq('username', selected_treat_patient).eq('doctor', selected_doctor_for_plan).eq('status', 'Pending').execute()
                                                break
                                            time.sleep(0.3)
                                            
                                        st.success("Treatment protocol established and initial session booked successfully.")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else: st.error("Protocol saved, but failed to book the initial appointment.")
                                except Exception as e: st.error(f"Error: {e}")
                except Exception as e: st.warning(f"Database error. Details: {e}")

            with sub_admin_referrals:
                sel_r_col1, sel_r_col2 = st.columns(2)
                with sel_r_col1: r_patient_user = st.selectbox("Select Patient to Refer:", list(pat_map.keys()), key="admin_ref_patient")
                with sel_r_col2: r_doctor_name = st.selectbox("Referring Doctor:", doc_names, key="admin_ref_doctor")
                
                r_patient_name = pat_map[r_patient_user].get('name', r_patient_user)
                
                try:
                    ref_hist = supabase.table('history').select('*').eq('username', r_patient_user).order('date', desc=True).execute()
                    ref_scans = [r for r in ref_hist.data if "Healthy" not in r["result"]]
                    
                    if not ref_scans:
                        st.warning(f"@{r_patient_user} has no malignant AI scans on record to base a referral on.")
                    else:
                        scan_dict = {f"{s['result']} | Confidence: {s['confidence']} [{s['scan_id']}]": s for s in ref_scans}
                        selected_ref_scan_str = st.selectbox("Select Abnormal Scan to Attach:", list(scan_dict.keys()), key="admin_ref_scan_select")
                        ref_urgency = st.selectbox("Referral Urgency Level:", ["High (Immediate)", "Moderate", "Routine/Standard"], key="admin_ref_urgency")
                        ref_notes = st.text_area("Clinical Justification / Detailed Notes:", placeholder="Patient presents with severe localized pain. Requesting immediate biopsy review.", height=150, key="admin_ref_notes")
                        
                        if st.button("📄 Prepare Referral Letter", type="primary", use_container_width=True):
                            if not ref_notes: st.error("Please provide clinical justification notes.")
                            else:
                                target_scan = scan_dict[selected_ref_scan_str]
                                letter_bytes = generate_referral_letter(r_doctor_name, r_patient_name, target_scan['scan_id'], target_scan['date'], target_scan['result'], target_scan['confidence'], ref_urgency, ref_notes)
                                
                                # 🌟 SAVE ENGINE: Create a unique ID and save PDF to server disk
                                ref_scan_id = f"REF_{int(time.time())}"
                                os.makedirs("uploaded_scans", exist_ok=True)
                                with open(f"uploaded_scans/{ref_scan_id}.pdf", "wb") as f:
                                    f.write(letter_bytes)
                                
                                # 🌟 Insert into History database so it appears in History Tab
                                try:
                                    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    supabase.table('history').insert({
                                        "username": r_patient_user,
                                        "scan_id": ref_scan_id,
                                        "date": date_str,
                                        "result": "Clinical Referral",
                                        "confidence": ref_urgency,
                                        "status": "Completed",
                                        "filename": f"Referral_{r_patient_user}.pdf"
                                    }).execute()
                                    st.toast("Referral securely logged to Clinical History Archive!", icon="✅")
                                except Exception as e:
                                    st.error(f"Error saving referral to database: {e}")

                                st.session_state[f'admin_ref_letter_{r_patient_user}'] = letter_bytes
                                st.session_state[f'admin_ref_scan_{r_patient_user}'] = ref_scan_id
                        
                        if f'admin_ref_letter_{r_patient_user}' in st.session_state:
                            st.success("Referral Letter Prepared! Choose an action below:")
                            letter_bytes = st.session_state[f'admin_ref_letter_{r_patient_user}']
                            scan_id_ref = st.session_state[f'admin_ref_scan_{r_patient_user}']

                            d_col1, d_col2 = st.columns(2)
                            with d_col1:
                                st.download_button(label="⬇️ Download PDF", data=letter_bytes, file_name=f"Referral_{r_patient_user}_{scan_id_ref}.pdf", mime="application/pdf", use_container_width=True, key=f"admin_dl_{scan_id_ref}")
                            with d_col2:
                                target_p_email = pat_map[r_patient_user].get('email', '')
                                if st.button("📧 Email to Patient", use_container_width=True, key=f"admin_email_{scan_id_ref}"):
                                    with st.spinner("Sending..."):
                                        files = {'pdf_file': (f"Referral_{r_patient_user}_{scan_id_ref}.pdf", letter_bytes, 'application/pdf')}
                                        data = {'email': target_p_email, 'name': r_patient_name, 'scan_id': scan_id_ref}
                                        try:
                                            resp = requests.post(f"{FLASK_URL}/email_report", data=data, files=files)
                                            if resp.status_code == 200: st.success(f"Referral sent to {target_p_email}!")
                                            else: st.error("Server failed to send.")
                                        except Exception as e: st.error(f"Error: {e}")
                except Exception as e: st.error(f"Error fetching patient data: {e}")

    # ==========================================
    # 🌟 TAB 4: GLOBAL HISTORY MANAGEMENT (3-TAB SPLIT) 🌟
    # ==========================================
    with tab_history:
        st.subheader("Global AI Diagnostic Records")
        st.write("This tab shows every scan performed across the entire system by all users.")
        
        sub_scan_hist, sub_appt_hist, sub_ref_hist = st.tabs(["🔬 Clinical Scan History", "📅 Appointment History", "📄 Referral Letters"])
        
        try:
            res = supabase.table('history').select('*').order('date', desc=True).execute()
            df_global_hist = pd.DataFrame(res.data)
        except:
            df_global_hist = pd.DataFrame()

        # ------------------- TAB 1: CLINICAL AI SCANS -------------------
        with sub_scan_hist:
            # 🌟 Isolate ONLY Scans (Exclude Referrals)
            if not df_global_hist.empty:
                df_scans = df_global_hist[~df_global_hist['scan_id'].astype(str).str.startswith("REF_", na=False)].copy()
            else:
                df_scans = pd.DataFrame()

            if df_scans.empty:
                st.info("No biopsy scan records found in the database.")
            else:
                search_hist = st.text_input("🔍 Search Scans (by Username, Scan ID, Filename, or Result):", placeholder="Try searching a specific username or file...")
                
                st.markdown("##### 📅 Filter Database Records")
                db_col1, db_col2 = st.columns(2)
                
                with db_col1:
                    db_filter_mode = st.selectbox(
                        "Select Date Range Mode (Scans):", 
                        ["All Time", "Specific Date", "Specific Month", "Last 5 Days", "Last 10 Days", "Last 30 Days"]
                    )
                
                with db_col2:
                    current_date = datetime.now().date()
                    
                    df_scans['date_obj'] = pd.to_datetime(df_scans['date'], errors='coerce')
                    df_scans['date_only'] = df_scans['date_obj'].dt.date
                    df_scans['month_year'] = df_scans['date_obj'].dt.to_period('M').astype(str)
                    
                    if db_filter_mode == "Specific Date":
                        db_chosen_date = st.date_input("Select Exact Scan Date:", current_date)
                    elif db_filter_mode == "Specific Month":
                        db_months = df_scans['month_year'].dropna().unique().tolist()
                        db_months.sort(reverse=True)
                        if db_months:
                            db_chosen_month = st.selectbox("Select Scan Month:", db_months)
                        else:
                            st.info("No valid month data available.")

                filtered_hist_df = df_scans.copy()
                if search_hist:
                    if 'filename' not in filtered_hist_df.columns:
                        filtered_hist_df['filename'] = "Legacy Scan"
                        
                    filtered_hist_df = filtered_hist_df[
                        filtered_hist_df['username'].str.contains(search_hist, case=False, na=False) |
                        filtered_hist_df['scan_id'].str.contains(search_hist, case=False, na=False) |
                        filtered_hist_df['filename'].str.contains(search_hist, case=False, na=False) |
                        filtered_hist_df['result'].str.contains(search_hist, case=False, na=False)
                    ]

                if db_filter_mode == "Specific Date":
                    filtered_hist_df = filtered_hist_df[filtered_hist_df['date_only'] == db_chosen_date]
                elif db_filter_mode == "Specific Month":
                    filtered_hist_df = filtered_hist_df[filtered_hist_df['month_year'] == db_chosen_month]
                elif db_filter_mode == "Last 5 Days":
                    filtered_hist_df = filtered_hist_df[filtered_hist_df['date_only'] >= (current_date - timedelta(days=5))]
                elif db_filter_mode == "Last 10 Days":
                    filtered_hist_df = filtered_hist_df[filtered_hist_df['date_only'] >= (current_date - timedelta(days=10))]
                elif db_filter_mode == "Last 30 Days":
                    filtered_hist_df = filtered_hist_df[filtered_hist_df['date_only'] >= (current_date - timedelta(days=30))]

                if filtered_hist_df.empty:
                    st.warning("No scans match your search or date criteria.")
                else:
                    items_per_page = 10
                    total_items = len(filtered_hist_df)
                    total_pages = math.ceil(total_items / items_per_page)
                    
                    if total_pages == 0: total_pages = 1
                    if st.session_state.hist_page > total_pages: st.session_state.hist_page = 1

                    st.markdown("---")
                    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                    
                    with p_col1:
                        if st.button("⬅️ Previous Page", disabled=(st.session_state.hist_page == 1), use_container_width=True):
                            st.session_state.hist_page -= 1
                            st.rerun()
                    
                    with p_col2:
                        st.markdown(f"<div class='page-indicator'>Page {st.session_state.hist_page} of {total_pages} (Showing {total_items} Scans)</div>", unsafe_allow_html=True)
                    
                    with p_col3:
                        if st.button("Next Page ➡️", disabled=(st.session_state.hist_page == total_pages), use_container_width=True):
                            st.session_state.hist_page += 1
                            st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

                    start_idx = (st.session_state.hist_page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    paginated_df = filtered_hist_df.iloc[start_idx:end_idx]

                    for _, row in paginated_df.iterrows():
                        with st.container(border=True):
                            res = row["result"]
                            if res in ["Healthy Tissue", "Healthy Colon", "Healthy Lung", "Healthy Blood", "Healthy Kidney", "Healthy Breast"]:
                                b_class = "badge-safe"
                            elif res == "Inconclusive / Not Recognized":
                                b_class = "badge-warn"
                            else:
                                b_class = "badge-alert"

                            fname = row.get("filename")
                            if pd.isna(fname) or not fname:
                                fname = "Legacy Scan (No Name)"

                            cols = st.columns([2.5, 2.5, 2, 2, 2], vertical_alignment="center")
                            cols[0].markdown(f"👤 **{row['username']}**<br><span style='color:gray; font-size:0.85em;'>📅 {row['date']}</span>", unsafe_allow_html=True)
                            
                            cols[1].markdown(f"""
                                <div class='scan-id'>{row['scan_id']}</div>
                                <div class='scan-file'>📁 {fname}</div>
                            """, unsafe_allow_html=True)
                            
                            cols[2].markdown(f"<div class='badge-soft {b_class}'>{res}</div>", unsafe_allow_html=True)
                            cols[3].markdown(f"**Conf:** {row['confidence']}")
                            
                            if st.session_state.admin_del_global_id != row["scan_id"]:
                                if cols[4].button("Delete Scan", key=f"glob_del_{row['scan_id']}", use_container_width=True):
                                    st.session_state.admin_del_global_id = row["scan_id"]
                                    st.rerun()
                            else:
                                with cols[4]:
                                    c_yes, c_no = st.columns(2)
                                    if c_yes.button("✅", key=f"glob_yes_{row['scan_id']}"):
                                        base_path = f"uploaded_scans/{row['scan_id']}"
                                        for ext in [".jpg", "_heatmap.jpg", "_overlay.jpg"]:
                                            if os.path.exists(base_path + ext):
                                                try: os.remove(base_path + ext)
                                                except: pass 
                                
                                        supabase.table('history').delete().eq('scan_id', row["scan_id"]).execute()
                                        st.session_state.admin_del_global_id = None
                                        st.rerun()
                                    if c_no.button("❌", key=f"glob_no_{row['scan_id']}"):
                                        st.session_state.admin_del_global_id = None
                                        st.rerun()

                        with st.expander("🔬 View Clinical Scans & Heatmaps"):
                            img_path = f"uploaded_scans/{row['scan_id']}.jpg"
                            hm_path = f"uploaded_scans/{row['scan_id']}_heatmap.jpg"
                            ov_path = f"uploaded_scans/{row['scan_id']}_overlay.jpg"
                            
                            if os.path.exists(img_path):
                                if os.path.exists(hm_path) and os.path.exists(ov_path):
                                    v1, v2, v3 = st.columns(3, gap="medium")
                                    with v1:
                                        with st.container(border=True):
                                            st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>1. Standardized Scan</div>", unsafe_allow_html=True)
                                            st.image(img_path, use_container_width=True)
                                    with v2:
                                        with st.container(border=True):
                                            st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>2. Grad-CAM Heatmap</div>", unsafe_allow_html=True)
                                            st.image(hm_path, use_container_width=True)
                                    with v3:
                                        with st.container(border=True):
                                            st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>3. Detection Overlay</div>", unsafe_allow_html=True)
                                            st.image(ov_path, use_container_width=True)
                            else:
                                with st.container(border=True):
                                    st.markdown(f"<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>Patient: {row['username']} | Legacy Scan Only</div>", unsafe_allow_html=True)
                                    st.image(img_path, width=350)

        # ------------------- TAB 2: COMPLETED APPOINTMENTS -------------------
        with sub_appt_hist:
            st.write("Review past completed consultations and clinical notes.")
            try:
                res = supabase.table('appointments').select('*').eq('status', 'Completed').order('date', desc=True).execute()
                past_appts = res.data
                if not past_appts:
                    st.info("You do not have any completed appointments on record.")
                else:
                    for appt in past_appts:
                        appt_id = appt['id']
                        with st.container(border=True):
                            c1, c2 = st.columns([4, 1], vertical_alignment="center")
                            with c1:
                                st.markdown(f"**Patient:** @{appt['username']} | **Doctor:** {appt['doctor']} | **Date:** {appt['date']}")
                                advice = appt['doctor_advice'] if appt['doctor_advice'] else "No advice recorded."
                                st.markdown(f"<div style='background:#F8FAFC; padding:12px; border-radius:8px; border: 1px dashed #cbd5e1; color:#475569;'><b>Notes:</b><br>{advice}</div>", unsafe_allow_html=True)
                            with c2:
                                if st.button("🗑️ Delete", key=f"admin_del_doc_hist_{appt_id}", use_container_width=True):
                                    supabase.table('appointments').delete().eq('id', appt_id).execute()
                                    st.toast("Record permanently removed.", icon="✅")
                                    time.sleep(1)
                                    st.rerun()
            except Exception as e:
                st.error(f"Could not fetch history: {e}")

        # ------------------- TAB 3: REFERRAL LETTERS -------------------
        with sub_ref_hist:
            st.write("Archive of all generated Clinical Referral Letters.")
            
            # 🌟 Isolate ONLY Referrals
            if not df_global_hist.empty:
                df_refs = df_global_hist[df_global_hist['scan_id'].astype(str).str.startswith("REF_", na=False)].copy()
            else:
                df_refs = pd.DataFrame()

            if df_refs.empty:
                st.info("No referral letters found in the system.")
            else:
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1: search_query_ref = st.text_input("🔍 Search Record ID:", placeholder="e.g., REF_170...", key="admin_ref_search")
                with f_col2:
                    patient_list_ref = ["All Patients"] + sorted(df_refs['username'].dropna().unique().tolist())
                    selected_patient_filter_ref = st.selectbox("👤 Filter by Patient:", patient_list_ref, key="admin_ref_pat_filter")
                with f_col3: filter_date_ref = st.date_input("📅 Filter by Exact Date", value=None, key="admin_ref_date_filter")

                filtered_df_refs = df_refs.copy()
                if search_query_ref:
                    filtered_df_refs = filtered_df_refs[filtered_df_refs['scan_id'].str.contains(search_query_ref, case=False, na=False)]
                if selected_patient_filter_ref != "All Patients": filtered_df_refs = filtered_df_refs[filtered_df_refs['username'] == selected_patient_filter_ref]
                if filter_date_ref: filtered_df_refs = filtered_df_refs[filtered_df_refs['date'].str.startswith(str(filter_date_ref), na=False)]

                if filtered_df_refs.empty:
                    st.warning("No referrals match your criteria.")
                else:
                    items_per_page = 10
                    total_items = len(filtered_df_refs)
                    total_pages = math.ceil(total_items / items_per_page)
                    if total_pages == 0: total_pages = 1
                    if st.session_state.ref_page > total_pages: st.session_state.ref_page = 1

                    st.markdown("---")
                    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                    with p_col1:
                        if st.button("⬅️ Previous Page", disabled=(st.session_state.ref_page == 1), use_container_width=True, key="admin_ref_prev"):
                            st.session_state.ref_page -= 1
                            st.rerun()
                    with p_col2: st.markdown(f"<div class='page-indicator'>Page {st.session_state.ref_page} of {total_pages} (Showing {total_items} Total Referrals)</div>", unsafe_allow_html=True)
                    with p_col3:
                        if st.button("Next Page ➡️", disabled=(st.session_state.ref_page == total_pages), use_container_width=True, key="admin_ref_next"):
                            st.session_state.ref_page += 1
                            st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

                    start_idx = (st.session_state.ref_page - 1) * items_per_page
                    paginated_df_refs = filtered_df_refs.iloc[start_idx : start_idx + items_per_page]

                    for _, row in paginated_df_refs.iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="center")
                            c1.markdown(f"**Patient:** {row['username']} | **Record ID:** {row['scan_id']} | **Date:** {row['date']}")
                            c2.markdown(f"<span style='color:#0284c7; font-weight:bold;'>Clinical Referral ({row['confidence']})</span>", unsafe_allow_html=True)
                            
                            if st.session_state.admin_del_global_id != row["scan_id"]:
                                if c3.button("Delete Letter", key=f"glob_del_{row['scan_id']}", use_container_width=True):
                                    st.session_state.admin_del_global_id = row["scan_id"]
                                    st.rerun()
                            else:
                                with c3:
                                    c_yes, c_no = st.columns(2)
                                    if c_yes.button("✅", key=f"glob_yes_{row['scan_id']}"):
                                        pdf_path = f"uploaded_scans/{row['scan_id']}.pdf"
                                        if os.path.exists(pdf_path):
                                            try: os.remove(pdf_path)
                                            except: pass 
                            
                                        supabase.table('history').delete().eq('scan_id', row["scan_id"]).execute()
                                        st.session_state.admin_del_global_id = None
                                        st.rerun()
                                    if c_no.button("❌", key=f"glob_no_{row['scan_id']}"):
                                        st.session_state.admin_del_global_id = None
                                        st.rerun()
                            
                            with st.expander("📄 View Referral Document & Comments"):
                                pdf_path = f"uploaded_scans/{row['scan_id']}.pdf"
                                if os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as f: pdf_data = f.read()
                                    st.download_button(label="⬇️ Download Official Referral PDF", data=pdf_data, file_name=f"{row['scan_id']}.pdf", mime="application/pdf", type="primary", use_container_width=True, key=f"dl_ref_hist_{row['scan_id']}")
                                else:
                                    st.warning("Referral document missing from server.")
                                    
                                st.markdown("---")
                                st.markdown("##### 💬 Clinical Comments")
                                try:
                                    comments_res = supabase.table('scan_comments').select('*').eq('scan_id', row['scan_id']).order('created_at').execute()
                                    if not comments_res.data: st.info("No comments on this referral yet.")
                                    else:
                                        for c in comments_res.data:
                                            st.markdown(f"<div class='comment-box'><span class='comment-author'>Dr. {c['doctor_name']}</span><span class='comment-date'>{c['created_at'][:16]}</span><br>{c['comment']}</div>", unsafe_allow_html=True)
                                except: pass
                                    
                                with st.form(key=f"comment_form_{row['scan_id']}"):
                                    new_comment = st.text_input("Add a note to this referral:", placeholder="E.g., Physical copy handed to patient.")
                                    if st.form_submit_button("Post Comment"):
                                        if new_comment:
                                            supabase.table('scan_comments').insert({"scan_id": row['scan_id'], "doctor_name": "Admin", "comment": new_comment}).execute()
                                            st.rerun()

    # ==========================================
    # TAB 5: GLOBAL APPOINTMENTS 
    # ==========================================
    with tab_appointments:
        st.subheader("Global Clinical Appointments")
        st.write("Oversee, modify, or cancel any appointment across the entire clinic system.")
        
        try:
            res = supabase.table('appointments').select('*').order('date', desc=True).order('time', desc=True).execute()
            all_appts = res.data
            
            if not all_appts:
                st.info("There are no appointments scheduled in the database.")
            else:
                search_appt = st.text_input("🔍 Search Appointments (by Patient, Doctor, or Status):", placeholder="e.g., Pending, Dr. Smith, adam99")
                
                st.markdown("##### 📅 Filter Appointment Schedule")
                appt_col1, appt_col2 = st.columns(2)
                
                with appt_col1:
                    appt_filter_mode = st.selectbox(
                        "Select Date Range Mode (Appts):", 
                        ["All Time", "Specific Date", "Specific Month", "Last 5 Days", "Last 10 Days", "Last 30 Days"]
                    )
                
                with appt_col2:
                    current_date = datetime.now().date()
                    
                    df_appts_filter = pd.DataFrame(all_appts)
                    df_appts_filter['date_obj'] = pd.to_datetime(df_appts_filter['date'], errors='coerce')
                    df_appts_filter['date_only'] = df_appts_filter['date_obj'].dt.date
                    df_appts_filter['month_year'] = df_appts_filter['date_obj'].dt.to_period('M').astype(str)
                    
                    if appt_filter_mode == "Specific Date":
                        appt_chosen_date = st.date_input("Select Exact Appt Date:", current_date)
                    
                    elif appt_filter_mode == "Specific Month":
                        appt_months = df_appts_filter['month_year'].dropna().unique().tolist()
                        appt_months.sort(reverse=True)
                        if appt_months:
                            appt_chosen_month = st.selectbox("Select Appt Month:", appt_months)
                        else:
                            st.info("No valid month data available.")

                appts_list = all_appts
                
                if search_appt:
                    appts_list = [
                        a for a in appts_list 
                        if search_appt.lower() in a['username'].lower() 
                        or search_appt.lower() in a['doctor'].lower()
                        or search_appt.lower() in a.get('status', 'Pending').lower()
                    ]
                
                filtered_appt_list = []
                for a in appts_list:
                    try:
                        d_obj = pd.to_datetime(a['date']).date()
                        
                        if appt_filter_mode == "All Time":
                            filtered_appt_list.append(a)
                        elif appt_filter_mode == "Specific Date" and d_obj == appt_chosen_date:
                            filtered_appt_list.append(a)
                        elif appt_filter_mode == "Specific Month" and pd.to_datetime(a['date']).strftime("%Y-%m") == appt_chosen_month:
                            filtered_appt_list.append(a)
                        elif appt_filter_mode == "Last 5 Days" and d_obj >= (current_date - timedelta(days=5)):
                            filtered_appt_list.append(a)
                        elif appt_filter_mode == "Last 10 Days" and d_obj >= (current_date - timedelta(days=10)):
                            filtered_appt_list.append(a)
                        elif appt_filter_mode == "Last 30 Days" and d_obj >= (current_date - timedelta(days=30)):
                            filtered_appt_list.append(a)
                    except:
                        if appt_filter_mode == "All Time": 
                            filtered_appt_list.append(a)

                appts_list = filtered_appt_list

                if not appts_list:
                    st.warning("No appointments match your search/filter criteria.")
                else:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for appt in appts_list:
                        appt_id = appt['id']
                        p_user = appt['username']
                        doc_name = appt['doctor']
                        status = appt.get('status', 'Pending')
                        
                        status_color = "red" if status == "Pending" else ("orange" if status == "Approved" else "green")
                        
                        with st.expander(f"📅 {appt['date']} at {appt['time']} | Patient: @{p_user} | Dr. {doc_name} | Status: {status}"):
                            
                            st.markdown(f"**Patient Notes:** {appt.get('notes', 'None provided')}")
                            if appt.get('attached_scan') and appt['attached_scan'] != 'None':
                                st.markdown(f"📎 **Attached AI Scan:** `{appt['attached_scan']}`")
                            if appt.get('doctor_advice'):
                                st.markdown(f"📋 **Doctor's Final Advice:** {appt['doctor_advice']}")

                            st.markdown("---")
                            st.markdown("##### ✏️ Edit Appointment Details")
                            
                            with st.form(key=f"admin_edit_appt_{appt_id}"):
                                c1, c2, c3 = st.columns(3)
                                with c1: edit_doc = st.text_input("Assigned Doctor", doc_name)
                                with c2: edit_date = st.text_input("Date (YYYY-MM-DD)", appt['date'])
                                with c3: edit_time = st.text_input("Time", appt['time'])
                                
                                current_status_index = ["Pending", "Approved", "Completed"].index(status) if status in ["Pending", "Approved", "Completed"] else 0
                                edit_status = st.selectbox("Override Status", ["Pending", "Approved", "Completed"], index=current_status_index)
                                
                                if st.form_submit_button("💾 Save Appointment Changes", type="primary"):
                                    try:
                                        supabase.table('appointments').update({
                                            "doctor": edit_doc,
                                            "date": edit_date,
                                            "time": edit_time,
                                            "status": edit_status
                                        }).eq('id', appt_id).execute()
                                        
                                        st.success("Appointment successfully updated!")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating database: {e}")
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🚨 Hard Delete Appointment", key=f"admin_del_appt_{appt_id}", type="secondary", use_container_width=True):
                                try:
                                    supabase.table('appointments').delete().eq('id', appt_id).execute()
                                    st.toast("Appointment permanently deleted.", icon="🗑️")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting from database: {e}")
        except Exception as e:
            st.error(f"Could not load global appointments. Database error: {e}")