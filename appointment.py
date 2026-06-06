import os
import streamlit as st
import requests
import datetime
import time
import math
from fpdf import FPDF

from supabase import create_client, Client

SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FLASK_URL = "http://127.0.0.1:5000"

def generate_pdf_report(patient_name, scan_id, date, filename, result, confidence, img_path, hm_path, ov_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 10, "CanViz Diagnostic Report", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 8, "Patient Name:", border=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f" {patient_name}", border=1, ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Scan ID:", border=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f" {scan_id}", border=1, ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Date of Scan:", border=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f" {date}", border=1, ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 10, "AI Analysis Results", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 8, "Detection:", border=1)
    if result in ["Healthy Tissue", "Healthy Colon", "Healthy Lung"]: pdf.set_text_color(16, 185, 129)
    elif result == "Inconclusive / Not Recognized": pdf.set_text_color(245, 158, 11)
    else: pdf.set_text_color(239, 68, 68)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f" {result}", border=1, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Confidence:", border=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f" {confidence}", border=1, ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 10, "Clinical Imagery", ln=True)
    y_position = pdf.get_y()
    if os.path.exists(img_path):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, y_position)
        pdf.cell(60, 5, "Standardized Scan", align="C")
        pdf.image(img_path, x=10, y=y_position + 5, w=60)
    if os.path.exists(hm_path):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(75, y_position)
        pdf.cell(60, 5, "Grad-CAM Heatmap", align="C")
        pdf.image(hm_path, x=75, y=y_position + 5, w=60)
    if os.path.exists(ov_path):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(140, y_position)
        pdf.cell(60, 5, "Detection Overlay", align="C")
        pdf.image(ov_path, x=140, y=y_position + 5, w=60)
    return bytes(pdf.output())

def show_appointment_page():
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.switch_page("main.py")
        return
        
    if st.session_state.get("role") != "user":
        st.warning("Only registered patients can book new appointments.")
        return

    # Initialize Pagination States
    if "pat_appt_page" not in st.session_state:
        st.session_state.pat_appt_page = 1
    if "pat_scan_page" not in st.session_state:
        st.session_state.pat_scan_page = 1

    st.markdown("""
    <style>
    .modern-header {
        font-size: 2.5rem; font-weight: 900;
        background: linear-gradient(135deg, #0284C7, #0369A1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .modern-sub { color: #64748B; font-size: 1.05rem; font-weight: 400; margin-bottom: 20px; }
    div.row-widget.stRadio > div { flex-direction: row; flex-wrap: wrap; gap: 10px; }
    div.row-widget.stRadio > div > label { background-color: #F8FAFC; padding: 10px 20px; border-radius: 8px; border: 1px solid #CBD5E1; cursor: pointer; transition: 0.2s; }
    div.row-widget.stRadio > div > label:hover { background-color: #E2E8F0; }
    .history-card { background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981; margin-bottom: 15px; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;}
    .history-doc { font-size: 1.1rem; font-weight: bold; color: #0F172A; }
    .history-date { color: #64748B; font-size: 0.9rem; margin-bottom: 10px;}
    .history-advice { background: #F8FAFC; padding: 10px; border-radius: 5px; color: #334155; font-style: italic; border: 1px dashed #cbd5e1;}
    .tracker-box { background: white; padding: 20px 30px; border-radius: 12px; border: 1px solid #E2E8F0; border-top: 5px solid #0284C7; box-shadow: 0 4px 6px rgba(0,0,0,0.02);}
    .step { text-align: center; position: relative; width: 100px; }
    .step-icon { width: 40px; height: 40px; border-radius: 50%; background: #F1F5F9; color: #94A3B8; line-height: 40px; font-size: 1.1rem; margin: 0 auto 8px; z-index: 2; position: relative; transition: 0.3s; }
    .step-label { font-size: 0.85rem; color: #94A3B8; font-weight: 700; transition: 0.3s; }
    .step.active .step-icon { background: #0284C7; color: white; box-shadow: 0 0 0 5px #E0F2FE; }
    .step.active .step-label { color: #0284C7; }
    .step.approved .step-icon { background: #10B981; color: white; box-shadow: 0 0 0 5px #D1FAE5; }
    .step.approved .step-label { color: #10B981; }
    .tracker-line { flex-grow: 1; height: 4px; background: #F1F5F9; margin: 0 5px; position: relative; top: -14px; transition: 0.3s; z-index: 1; border-radius: 2px;}
    .tracker-line.active { background: #0284C7; }
    .tracker-line.approved { background: #10B981; }
    .macro-plan-box { background: linear-gradient(135deg, #1E293B, #0F172A); padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);}
    .macro-title { font-size: 1.4rem; font-weight: 900; color: #38BDF8; margin-bottom: 5px; }
    .macro-meta { font-size: 0.95rem; color: #94A3B8; margin-bottom: 15px; }
    .next-session-box { background-color: #E0F2FE; border-left: 4px solid #0284C7; padding: 15px; border-radius: 6px; margin-top: 15px; }
    .comment-box { background: #f8fafc; padding: 10px 15px; border-radius: 8px; border-left: 3px solid #3b82f6; margin-bottom: 8px; font-size: 0.95rem; }
    .comment-author { font-weight: bold; color: #1e293b; font-size: 0.85rem; }
    .comment-date { font-size: 0.75rem; color: #94a3b8; margin-left: 10px; }
    .page-indicator { text-align: center; font-weight: bold; font-size: 1.1rem; color: #0284C7; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="modern-header">Consultation Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="modern-sub">Manage your medical appointments and track their status</div>', unsafe_allow_html=True)
    st.markdown("---")

    tab_treatment, tab_book, tab_active, tab_history = st.tabs(["💉 My Treatment Plan", "📅 Book Consultation", "⏳ Active Appointments", "📜 Clinical History"])

    active_appts = []
    past_appts = []
    active_plans = []
    
    try:
        # DB Call
        res = supabase.table('appointments').select('*').eq('username', st.session_state.username).eq('patient_deleted', 0).order('date', desc=True).execute()
        all_appts = res.data
        active_appts = [a for a in all_appts if a.get('status') != 'Completed']
        past_appts = [a for a in all_appts if a.get('status') == 'Completed']
        
        plan_res = supabase.table('treatment_plans').select('*').eq('patient_username', st.session_state.username).execute()
        active_plans = plan_res.data
    except: pass

    with tab_treatment:
        if not active_plans:
            st.info("You do not have any active, long-term treatment protocols assigned by a doctor.")
        else:
            for plan in active_plans:
                st.markdown(f"""
                <div class="macro-plan-box">
                    <div class="macro-title">{plan['treatment_type']}</div>
                    <div class="macro-meta">Assigned by: Dr. {plan['doctor_name']} | Started: {plan['start_date']}</div>
                    <p style="color: #E2E8F0; font-size: 0.95rem;"><b>Protocol Details:</b> {plan['notes']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.markdown("##### 🎯 Protocol Progress Tracker")
                    freq_map = {"Weekly": 4, "Bi-Weekly": 2, "Monthly": 1, "Quarterly": 0.33, "As Needed": 1}
                    sessions_per_month = freq_map.get(plan['frequency'], 1)
                    target_total_sessions = int(plan['duration_months'] * sessions_per_month)
                    if target_total_sessions < 1: target_total_sessions = 1
                    
                    completed_count = 0
                    for a in past_appts:
                        if a['doctor'] == plan['doctor_name'] and plan['treatment_type'] in str(a.get('notes', '')):
                            completed_count += 1
                            
                    display_count = min(completed_count, target_total_sessions)
                    progress = min(display_count / target_total_sessions, 1.0)
                    percent_complete = int(progress * 100)
                    
                    st.progress(progress)
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Target:** {target_total_sessions} Sessions ({plan['frequency']})")
                    c2.markdown(f"<div style='text-align:right; font-weight:bold; color:#0369A1;'>{display_count}/{target_total_sessions} Sessions Completed ({percent_complete}%)</div>", unsafe_allow_html=True)
                    
                    next_sessions = [a for a in active_appts if a['doctor'] == plan['doctor_name'] and plan['treatment_type'] in str(a.get('notes', ''))]
                    if next_sessions:
                        next_session = sorted(next_sessions, key=lambda x: x['date'])[0]
                        st.markdown(f"""
                        <div class="next-session-box">
                            <strong style="color: #0369A1;">📅 Upcoming Protocol Session Confirmed:</strong><br>
                            You are scheduled to see Dr. {plan['doctor_name']} on <b>{next_session['date']}</b> at <b>{next_session['time']}</b>.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning(f"⚠️ **Action Required:** You currently have no upcoming sessions scheduled. Please contact Dr. {plan['doctor_name']} to book your next session.")

    with tab_book:
        doctors = []
        try:
            res = requests.get(f"{FLASK_URL}/users")
            if res.status_code == 200: doctors = [u['name'] for u in res.json() if u.get('role') == 'doctor']
        except: st.error("Could not connect to the database.")

        if not doctors:
            st.info("No medical specialists are currently registered.")
        else:
            st.markdown("### 1️⃣ Select Specialist")
            doctor = st.selectbox("Choose your preferred doctor", doctors, label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("### 2️⃣ Choose Date & Time")
            col_date, col_time = st.columns([1, 1.5], gap="large")
            with col_date:
                today = datetime.date.today()
                selected_date = st.date_input("🗓️ Select a Date", min_value=today)
            with col_time:
                available_times = []
                if doctor and selected_date:
                    try:
                        res = requests.post(f"{FLASK_URL}/get_available_times", json={"doctor_name": doctor, "date": str(selected_date)})
                        if res.status_code == 200: available_times = res.json().get("available_times", [])
                    except: pass
                st.markdown("⏰ **Available Time Slots**")
                if not available_times:
                    st.warning(f" {doctor} has no available slots for this date.")
                    selected_time = None
                else:
                    selected_time = st.radio("Select Time", available_times, horizontal=True, label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("### 3️⃣ Attach Medical Scan (Optional)")
            patient_history = []
            try:
                hist_res = requests.post(f"{FLASK_URL}/get_patient_history", json={"username": st.session_state.username})
                if hist_res.status_code == 200: patient_history = hist_res.json()
            except: pass

            if not patient_history:
                st.info("You do not have any recent AI biopsy scans saved to your profile.")
                selected_scan_id = "None"
            else:
                scan_options = ["None (Do not attach a scan)"]
                scan_map = {}
                for scan in patient_history:
                    readable_string = f"{scan['date']} | {scan['result']} ({scan['confidence']}) - {scan['scan_id']}"
                    scan_options.append(readable_string)
                    scan_map[readable_string] = scan['scan_id']
                selected_option = st.selectbox("Select a previous AI scan to send to the doctor:", scan_options)
                selected_scan_id = scan_map.get(selected_option, "None")
            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("### 4️⃣ Consultation Details")
            notes = st.text_area("Any specific symptoms or concerns? (Optional)", placeholder="E.g., I have been experiencing fatigue.")
            st.markdown("<br>", unsafe_allow_html=True)
            if selected_time: 
                if st.button("✅ Confirm & Book Appointment", type="primary", use_container_width=True):
                    try:
                        pref_res = supabase.table('preferences').select('email_notif').eq('username', st.session_state.username).execute()
                        user_wants_emails = bool(pref_res.data[0]['email_notif']) if len(pref_res.data) > 0 else True
                    except: user_wants_emails = True
                    
                    email_to_send = st.session_state.email if user_wants_emails else "DISABLED"
                    payload = {
                        "username": st.session_state.username, "email": email_to_send, 
                        "name": st.session_state.name, "date": str(selected_date),
                        "time": selected_time, "doctor": doctor, "notes": notes, "attached_scan": selected_scan_id 
                    }
                    with st.spinner("Securing your appointment..."):
                        try:
                            response = requests.post(f"{FLASK_URL}/book_appointment", json=payload)
                            if response.status_code == 200:
                                st.success(f"Success! Appointment booked with {doctor} for {selected_date} at {selected_time}.")
                                st.balloons()
                                time.sleep(2)
                                st.rerun() 
                            else: st.error(f"Failed to book appointment. Database Error: {response.json().get('message', '')}")
                        except Exception as e: st.error("Connection Error.")

    with tab_active:
        st.subheader("⏳ Upcoming Sessions")
        if not active_appts:
            st.info("You have no pending or upcoming appointments at this time.")
        else:
            for appt in active_appts:
                appt_id = appt['id']
                doctor_name = appt['doctor']
                appt_date = appt['date']
                appt_time = appt['time']
                status = appt.get('status', "Pending")
                
                s1_class = "active" 
                if status == "Approved": s2_class, l1_class = "approved", "approved"
                else: s2_class, l1_class = "", ""
                
                tracker_html = f"""
                <div class="tracker-box" style="margin-bottom: 0px;">
                    <div style="margin-bottom: 15px; color: #0F172A; font-weight: bold; font-size: 1.1rem;">
                        👨‍⚕️{doctor_name} <span style="color:#64748B; font-weight:normal; font-size:0.95rem;">| {appt_date} at {appt_time}</span>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: center; padding: 0 40px; width: 100%;">
                        <div class="step {s1_class}"><div class="step-icon"><i class="fa-solid fa-paper-plane"></i></div><div class="step-label">Requested</div></div>
                        <div class="tracker-line {l1_class}"></div>
                        <div class="step {s2_class}"><div class="step-icon"><i class="fa-solid fa-check"></i></div><div class="step-label">Approved</div></div>
                    </div>
                </div>
                """
                col_track, col_cancel = st.columns([5, 1], vertical_alignment="center")
                with col_track: st.markdown(tracker_html, unsafe_allow_html=True)
                with col_cancel:
                    if st.button("❌ Cancel", key=f"cancel_act_{appt_id}", use_container_width=True, help="Cancel this upcoming appointment"):
                        supabase.table('appointments').delete().eq('id', appt_id).execute()
                        st.toast("Appointment Cancelled.", icon="✅")
                        time.sleep(1)
                        st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

    with tab_history:
        sub_consults, sub_scans = st.tabs(["📅 Consultation Notes", "🔬 My AI Scans & Reports"])
        
        # ------------------- CONSULTATION NOTES (PAGINATED & CORRECTLY SORTED) -------------------
        with sub_consults:
            if not past_appts:
                st.info("You do not have any completed appointments in your history yet.")
            else:
                # 🌟 THE FIX: Python-side sorting that strictly uses ID!
                # By tying the sort to the Supabase row ID, we bypass any weird AM/PM alphabetical sorting bugs.
                # The newest created row (highest ID) for the newest date will always be pinned to the top!
                sorted_past_appts = sorted(past_appts, key=lambda x: (x.get('date', ''), x.get('id', 0)), reverse=True)
                
                items_per_page = 10
                total_items = len(sorted_past_appts)
                total_pages = math.ceil(total_items / items_per_page)
                if total_pages == 0: total_pages = 1
                if st.session_state.pat_appt_page > total_pages: st.session_state.pat_appt_page = 1

                st.markdown("---")
                p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                with p_col1:
                    if st.button("⬅️ Previous Page", disabled=(st.session_state.pat_appt_page == 1), use_container_width=True, key="pat_appt_prev"):
                        st.session_state.pat_appt_page -= 1
                        st.rerun()
                with p_col2: 
                    st.markdown(f"<div class='page-indicator'>Page {st.session_state.pat_appt_page} of {total_pages} (Showing {total_items} Consultations)</div>", unsafe_allow_html=True)
                with p_col3:
                    if st.button("Next Page ➡️", disabled=(st.session_state.pat_appt_page == total_pages), use_container_width=True, key="pat_appt_next"):
                        st.session_state.pat_appt_page += 1
                        st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

                start_idx = (st.session_state.pat_appt_page - 1) * items_per_page
                paginated_appts = sorted_past_appts[start_idx : start_idx + items_per_page]

                for appt in paginated_appts:
                    appt_id = appt['id']
                    doctor_name = appt['doctor']
                    appt_date = appt['date']
                    advice = appt.get('doctor_advice') if appt.get('doctor_advice') else "No additional advice was recorded."
                    
                    c1, c2 = st.columns([4, 1], vertical_alignment="center")
                    with c1:
                        st.markdown(f"""
                        <div class="history-card" style="margin-bottom: 0px;">
                            <div class="history-doc">👨‍⚕️{doctor_name} <span style="color:#10B981; font-size:0.9rem;">(Completed)</span></div>
                            <div class="history-date">Session Date: {appt_date}</div>
                            <div class="history-advice"><b>📋 Doctor's Assessment:</b><br>{advice}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        if st.button("🗑️ Hide Record", key=f"del_pat_{appt_id}", use_container_width=True):
                            supabase.table('appointments').update({"patient_deleted": 1}).eq('id', appt_id).execute()
                            st.toast("Record removed from your history.", icon="✅")
                            time.sleep(1)
                            st.rerun()

        # ------------------- AI SCANS & REPORTS (PAGINATED) -------------------
        with sub_scans:
            try:
                res = supabase.table('history').select('*').eq('username', st.session_state.username).order('date', desc=True).execute()
                pat_hist = res.data
                if not pat_hist:
                    st.info("You do not have any saved AI scans.")
                else:
                    items_per_page = 10
                    total_items = len(pat_hist)
                    total_pages = math.ceil(total_items / items_per_page)
                    if total_pages == 0: total_pages = 1
                    if st.session_state.pat_scan_page > total_pages: st.session_state.pat_scan_page = 1

                    st.markdown("---")
                    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                    with p_col1:
                        if st.button("⬅️ Previous Page", disabled=(st.session_state.pat_scan_page == 1), use_container_width=True, key="pat_scan_prev"):
                            st.session_state.pat_scan_page -= 1
                            st.rerun()
                    with p_col2: 
                        st.markdown(f"<div class='page-indicator'>Page {st.session_state.pat_scan_page} of {total_pages} (Showing {total_items} Scans)</div>", unsafe_allow_html=True)
                    with p_col3:
                        if st.button("Next Page ➡️", disabled=(st.session_state.pat_scan_page == total_pages), use_container_width=True, key="pat_scan_next"):
                            st.session_state.pat_scan_page += 1
                            st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

                    start_idx = (st.session_state.pat_scan_page - 1) * items_per_page
                    paginated_scans = pat_hist[start_idx : start_idx + items_per_page]

                    for row in paginated_scans:
                        with st.container(border=True):
                            res_val = row["result"]
                            color = "green" if "Healthy" in res_val else ("orange" if "Inconclusive" in res_val else "red")
                            c1, c2 = st.columns([3, 1], vertical_alignment="center")
                            c1.markdown(f"**Scan ID:** {row['scan_id']} | **Date:** {row['date']}")
                            c2.markdown(f"<span style='color:{color}; font-weight:bold;'>{res_val} ({row['confidence']})</span>", unsafe_allow_html=True)
                            
                            with st.expander("🔬 View Clinical Imagery, Reports & Comments"):
                                img_path = f"uploaded_scans/{row['scan_id']}.jpg"
                                hm_path = f"uploaded_scans/{row['scan_id']}_heatmap.jpg"
                                ov_path = f"uploaded_scans/{row['scan_id']}_overlay.jpg"
                                
                                if os.path.exists(img_path) and os.path.exists(hm_path):
                                    v1, v2, v3 = st.columns(3)
                                    v1.image(img_path, caption="Original Scan", use_container_width=True)
                                    v2.image(hm_path, caption="Grad-CAM Heatmap", use_container_width=True)
                                    v3.image(ov_path, caption="Detection Overlay", use_container_width=True)
                                    
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    
                                    pdf_bytes = generate_pdf_report(st.session_state.name, row['scan_id'], row['date'], row.get('filename', 'System Scan'), res_val, row['confidence'], img_path, hm_path, ov_path)
                                    st.download_button(label="📄 Download Diagnostic PDF", data=pdf_bytes, file_name=f"CanViz_Report_{row['scan_id']}.pdf", mime="application/pdf", type="primary", use_container_width=True, key=f"dl_pdf_pat_{row['scan_id']}")
                                                
                                    st.markdown("---")
                                    st.markdown("##### 💬 Doctor's Comments")
                                    try:
                                        comments_res = supabase.table('scan_comments').select('*').eq('scan_id', row['scan_id']).order('created_at').execute()
                                        if not comments_res.data: st.info("No comments from doctors on this scan yet.")
                                        else:
                                            for c in comments_res.data:
                                                st.markdown(f"<div class='comment-box'><span class='comment-author'>Dr. {c['doctor_name']}</span><span class='comment-date'>{c['created_at'][:16]}</span><br>{c['comment']}</div>", unsafe_allow_html=True)
                                    except: pass
                                else:
                                    st.warning("High-resolution image files purged from server.")
            except Exception as e: st.error("Database connection error.")