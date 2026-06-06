import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
import datetime
import requests

# 🌟 Supabase Cloud Import
from supabase import create_client, Client

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FLASK_URL = "http://127.0.0.1:5000"

# --- HELPER: GENERATE PDF REPORT ---
def generate_pdf_report(patient_name, scan_id, date, filename, result, confidence, img_path, hm_path, ov_path):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 102, 204) # Medical Blue
    pdf.cell(0, 10, "CanViz Diagnostic Report", ln=True, align="C")
    
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    
    # Patient & Scan Details
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
    
    # Diagnostic Results
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 10, "AI Analysis Results", ln=True)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 8, "Detection:", border=1)
    
    # Color code the result text in the PDF
    if result in ["Healthy Tissue", "Healthy Colon", "Healthy Lung"]:
        pdf.set_text_color(16, 185, 129) # Green
    elif result == "Inconclusive / Not Recognized":
        pdf.set_text_color(245, 158, 11) # Orange
    else:
        pdf.set_text_color(239, 68, 68) # Red
        
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f" {result}", border=1, ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Confidence:", border=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f" {confidence}", border=1, ln=True)
    pdf.ln(10)

    # Embed Images
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 10, "Clinical Imagery", ln=True)
    
    # Align 3 images side-by-side using exact X, Y coordinates
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

def show_history_page():
    # --- MODERN DASHBOARD CSS ---
    st.markdown("""
    <style>
    .modern-header { font-size: 2.5rem; font-weight: 900; background: linear-gradient(135deg, #1E293B, #3B82F6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0px; }
    .modern-sub { color: #64748B; font-size: 1.05rem; font-weight: 400; margin-bottom: 30px; }
    .badge-soft { padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; text-transform: uppercase; display: inline-block; }
    .badge-safe { background-color: #DEF7EC; color: #03543F; } 
    .badge-alert { background-color: #FDE8E8; color: #9B1C1C; } 
    .badge-warn { background-color: #FEF08A; color: #723B13; }  
    .badge-ref { background-color: #E0F2FE; color: #075985; }
    .scan-id { font-size: 1.1rem; font-weight: 700; color: #0F172A; }
    .scan-date { font-size: 0.85rem; color: #64748B; margin-top: 4px; }
    .scan-file { font-size: 0.85rem; color: #0284c7; margin-top: 2px; font-weight: 500; } 
    .conf-wrapper { width: 100%; background-color: #E2E8F0; border-radius: 10px; height: 8px; margin-top: 6px; overflow: hidden; }
    .conf-fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
    .conf-text { font-size: 0.85rem; font-weight: 600; color: #334155; display: block; }
    .comment-box { background: #f8fafc; padding: 10px 15px; border-radius: 8px; border-left: 3px solid #3b82f6; margin-bottom: 8px; font-size: 0.95rem; }
    .comment-author { font-weight: bold; color: #1e293b; font-size: 0.85rem; }
    .comment-date { font-size: 0.75rem; color: #94a3b8; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)

    # --- UI HEADER ---
    st.markdown('<div class="modern-header">Patient Archive</div>', unsafe_allow_html=True)
    st.markdown('<div class="modern-sub">Manage and review AI diagnostic history & clinical referrals</div>', unsafe_allow_html=True)
    st.markdown("---")

    # -----------------------------
    # CORE LOGIC 
    # -----------------------------
    if "username" not in st.session_state:
        st.error("Please log in first.")
        return

    user = st.session_state.username

    if "confirm_id" not in st.session_state:
        st.session_state.confirm_id = None

    try:
        # 🌟 THE SUPABASE CLOUD FETCH 🌟
        response = supabase.table('history').select('*').eq('username', user).order('date', desc=True).execute()
        df_all = pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error loading history: {e}")
        return

    if df_all.empty:
        st.info("No clinical records found for this account.")
        return

    # 🌟 DATA SPLIT: Separate Scans from Referrals 🌟
    df_scans = df_all[~df_all['scan_id'].astype(str).str.startswith("REF_", na=False)]
    df_refs = df_all[df_all['scan_id'].astype(str).str.startswith("REF_", na=False)]

    tab_scans, tab_refs = st.tabs(["🔬 AI Biopsy Scans", "📄 Official Referrals"])

    # ==========================================
    # TAB 1: AI BIOPSY SCANS
    # ==========================================
    with tab_scans:
        if df_scans.empty:
            st.info("No AI biopsy scans on record.")
        else:
            for _, row in df_scans.iterrows():
                with st.container(border=True):
                    res = row["result"]
                    if res in ["Healthy Tissue", "Healthy Colon", "Healthy Lung", "Healthy Blood", "Healthy Kidney", "Healthy Breast"]:
                        b_class, fill_color = "badge-safe", "#10B981" 
                    elif res == "Inconclusive / Not Recognized":
                        b_class, fill_color = "badge-warn", "#F59E0B" 
                    else:
                        b_class, fill_color = "badge-alert", "#EF4444" 

                    conf_str = str(row['confidence']).replace('%', '')
                    try: conf_val = float(conf_str)
                    except ValueError: conf_val = 0.0

                    fname = row.get("filename")
                    if pd.isna(fname) or not fname: fname = "Legacy Scan (No Name)"

                    cols = st.columns([3.5, 2.5, 3, 2], vertical_alignment="center")
                    
                    cols[0].markdown(f"""
                        <div class='scan-id'>⚕️ {row['scan_id']}</div>
                        <div class='scan-date'>📅 {row['date']}</div>
                        <div class='scan-file'>📁 {fname}</div>
                    """, unsafe_allow_html=True)
                    
                    cols[1].markdown(f"<div class='badge-soft {b_class}'>{res}</div>", unsafe_allow_html=True)
                    
                    cols[2].markdown(f"""
                        <span class='conf-text'>Confidence: {row['confidence']}</span>
                        <div class='conf-wrapper'>
                            <div class='conf-fill' style='width: {conf_val}%; background-color: {fill_color};'></div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Delete Logic
                    if st.session_state.confirm_id != row["scan_id"]:
                        if cols[3].button("🗑️ Delete", key=f"del_{row['scan_id']}", help="Delete this record", use_container_width=True):
                            st.session_state.confirm_id = row["scan_id"]
                            st.rerun()
                    else:
                        with cols[3]:
                            st.markdown("<span style='color:#dc3545; font-size:0.85em; font-weight:800;'>Confirm?</span>", unsafe_allow_html=True)
                            col_yes, col_no = st.columns(2)
                            
                            if col_yes.button("✅", key=f"yes_{row['scan_id']}"):
                                base_path = f"uploaded_scans/{row['scan_id']}"
                                for ext in [".jpg", "_heatmap.jpg", "_overlay.jpg"]:
                                    if os.path.exists(base_path + ext):
                                        try: os.remove(base_path + ext)
                                        except: pass 
                                        
                                supabase.table('history').delete().eq('scan_id', row["scan_id"]).eq('username', user).execute()
                                st.session_state.confirm_id = None
                                st.toast("Record & Scans permanently deleted", icon="🗑️")
                                st.rerun() 
                            
                            if col_no.button("❌", key=f"no_{row['scan_id']}"):
                                st.session_state.confirm_id = None
                                st.rerun() 

                    # Expander for Scans
                    with st.expander("🔬 View Clinical Scans, Heatmaps & Doctor Notes"):
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
                                    st.markdown(f"<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>Patient: {user} | Legacy Scan Only</div>", unsafe_allow_html=True)
                                    st.image(img_path, width=350)
                        else:
                            st.warning("⚠️ Image files not found on server.")

                        st.markdown("---")
                        st.markdown("##### 💬 Doctor's Comments")
                        try:
                            comments_res = supabase.table('scan_comments').select('*').eq('scan_id', row['scan_id']).order('created_at').execute()
                            if not comments_res.data:
                                st.info("No comments from doctors on this scan yet.")
                            else:
                                for c in comments_res.data:
                                    st.markdown(f"""
                                    <div class='comment-box'>
                                        <span class='comment-author'>Dr. {c['doctor_name']}</span>
                                        <span class='comment-date'>{c['created_at'][:16]}</span><br>
                                        {c['comment']}
                                    </div>
                                    """, unsafe_allow_html=True)
                        except Exception as e:
                            st.error("Unable to load comments.")

                        st.markdown("<br>", unsafe_allow_html=True)
                        pdf_bytes = generate_pdf_report(st.session_state.name, row['scan_id'], row['date'], fname, res, row['confidence'], img_path, hm_path, ov_path)
                        
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            st.download_button(label="📄 Download Diagnostic PDF", data=pdf_bytes, file_name=f"CanViz_Report_{row['scan_id']}.pdf", mime="application/pdf", type="primary", use_container_width=True, key=f"dl_pdf_{row['scan_id']}")
                        with btn_col2:
                            if st.button("📧 Send to My Email", use_container_width=True, key=f"email_pdf_{row['scan_id']}"):
                                with st.spinner("Preparing and sending email..."):
                                    files = {'pdf_file': (f"CanViz_Report_{row['scan_id']}.pdf", pdf_bytes, 'application/pdf')}
                                    data = {'email': st.session_state.email, 'name': st.session_state.name, 'scan_id': row['scan_id']}
                                    try:
                                        resp = requests.post(f"{FLASK_URL}/email_report", data=data, files=files)
                                        if resp.status_code == 200: st.success(f"Report successfully sent to {st.session_state.email}!")
                                        else: st.error("Server failed to send the email.")
                                    except Exception as e:
                                        st.error(f"Connection Error: {e}")

    # ==========================================
    # TAB 2: CLINICAL REFERRALS
    # ==========================================
    with tab_refs:
        if df_refs.empty:
            st.info("No clinical referrals issued for this account.")
        else:
            for _, row in df_refs.iterrows():
                with st.container(border=True):
                    cols = st.columns([4, 2, 2], vertical_alignment="center")
                    
                    cols[0].markdown(f"""
                        <div class='scan-id'>📄 {row['scan_id']}</div>
                        <div class='scan-date'>📅 Issued on: {row['date']}</div>
                    """, unsafe_allow_html=True)
                    
                    urgency_text = row['confidence'] # Doctor saves Urgency in confidence column for referrals
                    urgency_color = "#dc2626" if "High" in urgency_text else ("#d97706" if "Moderate" in urgency_text else "#0f172a")
                    
                    cols[1].markdown(f"<div class='badge-soft badge-ref'>Referral Letter</div><br><span style='color:{urgency_color}; font-size:0.85rem; font-weight:700;'>Urgency: {urgency_text}</span>", unsafe_allow_html=True)
                    
                    # Delete Logic for Referrals
                    if st.session_state.confirm_id != row["scan_id"]:
                        if cols[2].button("🗑️ Delete", key=f"del_ref_{row['scan_id']}", help="Delete this referral", use_container_width=True):
                            st.session_state.confirm_id = row["scan_id"]
                            st.rerun()
                    else:
                        with cols[2]:
                            st.markdown("<span style='color:#dc3545; font-size:0.85em; font-weight:800;'>Confirm?</span>", unsafe_allow_html=True)
                            col_yes, col_no = st.columns(2)
                            
                            if col_yes.button("✅", key=f"yes_ref_{row['scan_id']}"):
                                pdf_path = f"uploaded_scans/{row['scan_id']}.pdf"
                                if os.path.exists(pdf_path):
                                    try: os.remove(pdf_path)
                                    except: pass
                                    
                                supabase.table('history').delete().eq('scan_id', row["scan_id"]).eq('username', user).execute()
                                st.session_state.confirm_id = None
                                st.toast("Referral deleted successfully", icon="🗑️")
                                st.rerun() 
                            
                            if col_no.button("❌", key=f"no_ref_{row['scan_id']}"):
                                st.session_state.confirm_id = None
                                st.rerun()
                                
                    # Expander for Referrals
                    with st.expander("📄 Download / Email Referral Letter"):
                        pdf_path = f"uploaded_scans/{row['scan_id']}.pdf"
                        if os.path.exists(pdf_path):
                            with open(pdf_path, "rb") as f:
                                letter_bytes = f.read()
                                
                            d_col1, d_col2 = st.columns(2)
                            with d_col1:
                                st.download_button(label="⬇️ Download PDF", data=letter_bytes, file_name=f"{row['scan_id']}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_ref_btn_{row['scan_id']}")
                            with d_col2:
                                if st.button("📧 Email to Me", use_container_width=True, key=f"email_ref_btn_{row['scan_id']}"):
                                    with st.spinner("Sending..."):
                                        files = {'pdf_file': (f"{row['scan_id']}.pdf", letter_bytes, 'application/pdf')}
                                        data = {'email': st.session_state.email, 'name': st.session_state.name, 'scan_id': row['scan_id']}
                                        try:
                                            resp = requests.post(f"{FLASK_URL}/email_report", data=data, files=files)
                                            if resp.status_code == 200: st.success("Referral sent to your email!")
                                            else: st.error("Server failed to send.")
                                        except Exception as e: st.error(f"Error: {e}")
                        else:
                            st.warning("Referral document missing from server.")