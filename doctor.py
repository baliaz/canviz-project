import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import streamlit as st
import pandas as pd
import requests
import time
import datetime
import base64
import numpy as np
import math
from PIL import Image
import matplotlib.cm as cm
from fpdf import FPDF

from supabase import create_client, Client

# --- PyTorch & AI Imports ---
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from torchvision.models import resnet50

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FLASK_URL = "http://127.0.0.1:5000"

# -------------------------------------------------------------
# 🌟 HIGH-SPEED API CACHING ENGINE 🌟
# -------------------------------------------------------------
@st.cache_data(ttl=30)
def fetch_global_users():
    try:
        res = requests.get(f"{FLASK_URL}/users", timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=15)
def get_pending_appointments(doc_name):
    res = supabase.table('appointments').select('*').eq('doctor', doc_name).neq('status', 'Completed').order('date', desc=False).execute()
    return res.data

@st.cache_data(ttl=15)
def get_completed_appointments(doc_name):
    res = supabase.table('appointments').select('*').eq('doctor', doc_name).eq('status', 'Completed').eq('doctor_deleted', 0).order('date', desc=True).execute()
    return res.data

@st.cache_data(ttl=15)
def get_all_history():
    res = supabase.table('history').select('*').order('date', desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

@st.cache_data(ttl=15)
def get_assigned_patients(doc_name):
    res = supabase.table('patient_assignments').select('patient_username').eq('doctor_name', doc_name).execute()
    return [row['patient_username'] for row in res.data]

@st.cache_data(ttl=15)
def get_treatment_plans(patient_username):
    res = supabase.table('treatment_plans').select('*').eq('patient_username', patient_username).execute()
    return res.data

# Callback to fix the 2-click issue
def execute_db_action(action_type, record_id, update_data=None):
    try:
        if action_type == "delete_plan":
            supabase.table('treatment_plans').delete().eq('id', record_id).execute()
        elif action_type == "update_appt":
            supabase.table('appointments').update(update_data).eq('id', record_id).execute()
        elif action_type == "delete_appt":
            supabase.table('appointments').delete().eq('id', record_id).execute()
        elif action_type == "unassign_patient":
            doc, pat = record_id
            supabase.table('patient_assignments').delete().eq('doctor_name', doc).eq('patient_username', pat).execute()
        # Force cache refresh after mutation
        st.cache_data.clear()
    except Exception as e:
        print(f"DB Action Error: {e}")

# -------------------------------------------------------------
# PYTORCH MODEL BLUEPRINTS & SETUP (UPDATED FOR HIGHER ACCURACY)
# -------------------------------------------------------------
def build_model(num_classes=13, dropout=0.50):
    model = resnet50(weights=None)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, 512),
        nn.BatchNorm1d(512),
        nn.ReLU(inplace=True),
        nn.Dropout(p=dropout * 0.5),
        nn.Linear(512, num_classes),
    )
    return model

class GradCAM:
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None
        self.forward_hook = target_layer.register_forward_hook(self._save_activation)
        self.backward_hook = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, inputs, output):
        self.activations = output.detach()

    def _save_gradient(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def __call__(self, image_tensor, class_idx=None):
        self.model.eval()
        logits = self.model(image_tensor)
        probs = F.softmax(logits, dim=1)[0]
        if class_idx is None: class_idx = int(logits.argmax(dim=1).item())
        self.model.zero_grad()
        logits[0, class_idx].backward()
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1).squeeze()
        cam = F.relu(cam)
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)
        cam = F.interpolate(cam[None, None], size=(IMG_SIZE, IMG_SIZE), mode='bilinear', align_corners=False)[0, 0]
        return cam.cpu().numpy(), probs.detach().cpu().numpy(), class_idx

IMG_SIZE = 512
CLASS_NAMES = [
    "Blood Cancer - Stage 1", "Blood Cancer - Stage 2", "Blood Cancer - Stage 3",
    "Breast Cancer", "Colon Cancer", "Kidney Cancer",
    "Lung Cancer - Stage 1", "Lung Cancer - Stage 2",
    "Healthy Blood", "Healthy Breast", "Healthy Colon",
    "Healthy Kidney", "Healthy Lung"
]
CANCER_ONLY_CLASSES = [c for c in CLASS_NAMES if "Healthy" not in c]

preprocess = transforms.Compose([
    transforms.Resize(int(IMG_SIZE * 1.08)),
    transforms.CenterCrop(IMG_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def unnormalize(tensor):
    mean = torch.tensor([0.485, 0.456, 0.406])[:, None, None]
    std = torch.tensor([0.229, 0.224, 0.225])[:, None, None]
    image = tensor.cpu() * std + mean
    return image.clamp(0, 1).permute(1, 2, 0).numpy()

@st.cache_resource
def load_assets():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = torch.load("best_resnet50_histopathology_gradcam_classifier1.pth", map_location=device)
    state_dict = checkpoint['model_state_dict']

    num_classes = checkpoint.get("num_classes", len(CLASS_NAMES))
    dropout = checkpoint.get("dropout", 0.50)
    
    cnn_model = build_model(num_classes=num_classes, dropout=dropout)
    cnn_model.load_state_dict(state_dict)
    cnn_model.to(device)
    cnn_model.eval()
    
    gradcam = GradCAM(cnn_model, cnn_model.layer4[-1])
    return cnn_model, gradcam, device

cnn_model, gradcam, compute_device = load_assets()

def get_base64_image(path):
    try:
        with open(path, "rb") as img: return base64.b64encode(img.read()).decode()
    except Exception: return "" 

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

def generate_referral_letter(doctor_name, patient_name, scan_id, date, result, confidence, target_hospital, notes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "CLINICAL ONCOLOGY REFERRAL", ln=True, align="C")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Date: {datetime.datetime.now().strftime('%d %B %Y')}", ln=True)
    pdf.cell(0, 6, f"Referring Physician: {doctor_name}", ln=True)
    pdf.cell(0, 6, "To: Oncology & Specialist Department", ln=True)
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, f"SUBJECT: CLINICAL REFERRAL TO {target_hospital.upper()} FOR PATIENT {patient_name.upper()}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 11)
    body_text = (
        f"Dear Colleague at {target_hospital},\n\n"
        f"I am formally referring my patient, {patient_name}, for specialist evaluation, further histopathological confirmation, and subsequent treatment management.\n\n"
        f"On {date}, a tissue biopsy sample (Scan ID: {scan_id}) was analyzed utilizing the CanViz AI Diagnostic System. The computational neural network flagged the morphology as abnormal, yielding the following results:\n\n"
        f"Primary AI Finding: {result}\n"
        f"AI Confidence Score: {confidence}\n\n"
        f"Clinical Notes & Reason for Referral:\n{notes}\n\n"
        f"Given the AI-assisted indications of this case, I would greatly appreciate your expert consultation and intervention at {target_hospital}.\n\n"
        f"The patient's full AI Diagnostic Report, including Grad-CAM heatmaps and morphological overlays, has been attached to their electronic health record for your review.\n\n"
        f"Sincerely,\n\n"
        f"{doctor_name}\n"
        f"CanViz Medical Command Center"
    )
    pdf.multi_cell(0, 6, body_text)
    return bytes(pdf.output())

# 🌟 FAST UI FRAGMENTS 🌟
@st.fragment
def render_booking_fragment(plan, doc_name, selected_treat_patient, user_map):
    b_col1, b_col2 = st.columns([1, 1.5])
    with b_col1:
        b_date = st.date_input("Date", min_value=datetime.date.today(), key=f"book_date_{plan['id']}")
    with b_col2:
        available_times = []
        if b_date:
            try:
                res = requests.post(f"{FLASK_URL}/get_available_times", json={"doctor_name": doc_name, "date": str(b_date)})
                if res.status_code == 200: available_times = res.json().get("available_times", [])
            except: pass
        
        if not available_times:
            st.error("No slots available for this date.")
            b_time = None
        else:
            b_time = st.selectbox("Time", available_times, key=f"book_time_{plan['id']}")
            
    b_notes = st.text_input("Session Notes (Optional):", key=f"b_notes_{plan['id']}")
            
    if b_time and st.button("✅ Book Session & Notify Patient", key=f"btn_book_{plan['id']}", type="primary"):
        target_email = user_map.get(selected_treat_patient, {}).get('email', 'DISABLED')
        target_name = user_map.get(selected_treat_patient, {}).get('name', selected_treat_patient)
        
        protocol_stamp = f"Protocol Session: {plan['treatment_type']}"
        final_note = f"{protocol_stamp}. Note: {b_notes}" if b_notes else protocol_stamp
        
        payload = {
            "username": selected_treat_patient, "email": target_email, "name": target_name,
            "date": str(b_date), "time": b_time, "doctor": doc_name,
            "notes": final_note, "attached_scan": "None" 
        }
        with st.spinner("Booking session..."):
            try:
                response = requests.post(f"{FLASK_URL}/book_appointment", json=payload)
                if response.status_code == 200:
                    supabase.table('appointments').update({"status": "Approved"}).eq('username', selected_treat_patient).eq('doctor', doc_name).eq('status', 'Pending').execute()
                    st.cache_data.clear() # Clear cache so schedule updates instantly
                    st.toast("Session Scheduled! Check the Appointments tab.", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
            except Exception as e: st.error(f"Error: {e}")

@st.fragment
def render_new_protocol_fragment(doc_name, selected_treat_patient, user_map, scan_options):
    with st.container(border=True):
        t_cancer_target = st.selectbox("🎯 Target Cancer Diagnosis (Linked to Scan)", scan_options)
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            t_type = st.selectbox("Primary Treatment Modality", ["Chemotherapy", "Radiation Therapy", "Targeted Therapy", "Surgery Follow-up", "Observation/Monitoring"])
            t_duration = st.number_input("Duration (in Months)", min_value=1, max_value=60, value=6)
        with t_col2:
            t_freq = st.selectbox("Session Frequency", ["Weekly", "Bi-Weekly", "Monthly", "Quarterly", "As Needed"])
            
        st.markdown("##### 📅 Book First Clinical Session (Anchor)")
        b_col1, b_col2 = st.columns([1, 1.5])
        with b_col1:
            t_start = st.date_input("Session Date", min_value=datetime.date.today(), key="plan_start_date")
        with b_col2:
            available_times = []
            if t_start:
                try:
                    res = requests.post(f"{FLASK_URL}/get_available_times", json={"doctor_name": doc_name, "date": str(t_start)})
                    if res.status_code == 200: available_times = res.json().get("available_times", [])
                except: pass
            
            if not available_times:
                st.warning("No slots available for this date.")
                b_time = None
            else:
                b_time = st.selectbox("Session Time", available_times)
                
        t_notes = st.text_area("Clinical Notes & Protocol Details", placeholder="Specify dosage, machine targets, or secondary medications...")
        
        if b_time and st.button("💾 Establish Protocol & Notify Patient", type="primary"):
            target_email = user_map.get(selected_treat_patient, {}).get('email', 'DISABLED')
            target_name = user_map.get(selected_treat_patient, {}).get('name', selected_treat_patient)
            combined_treatment = f"{t_type} for {t_cancer_target}"
            
            with st.spinner("Saving Protocol and Booking Session..."):
                try:
                    supabase.table('treatment_plans').insert({
                        "doctor_name": doc_name, "patient_username": selected_treat_patient,
                        "treatment_type": combined_treatment, "duration_months": t_duration,
                        "frequency": t_freq, "start_date": str(t_start), "notes": t_notes
                    }).execute()
                    
                    payload = {
                        "username": selected_treat_patient, "email": target_email, "name": target_name,
                        "date": str(t_start), "time": b_time, "doctor": doc_name,
                        "notes": f"Protocol Session: {combined_treatment}. Doctor's Note: {t_notes}", "attached_scan": "None" 
                    }
                    response = requests.post(f"{FLASK_URL}/book_appointment", json=payload)
                    
                    if response.status_code == 200:
                        supabase.table('appointments').update({"status": "Approved"}).eq('username', selected_treat_patient).eq('doctor', doc_name).eq('status', 'Pending').execute()
                        st.cache_data.clear()
                        st.success("Treatment protocol established and initial session booked successfully.")
                        time.sleep(0.5)
                        st.rerun()
                    else: st.error("Protocol saved, but failed to book the initial appointment.")
                except Exception as e: st.error(f"Error: {e}")

# -------------------------------------------------------------
# MAIN DOCTOR PAGE RENDERING
# -------------------------------------------------------------
def show_doctor_page():
    if st.session_state.get("role") != "doctor":
        st.error("🛑 Security Violation: Unauthorized Access. Medical Staff Only.")
        st.stop()

    doc_name = st.session_state.get("name", "Doctor")
    current_username = st.session_state.get("username", "Unknown")

    if "doc_scan_page" not in st.session_state: st.session_state.doc_scan_page = 1
    if "doc_ref_page" not in st.session_state: st.session_state.doc_ref_page = 1

    global_users = fetch_global_users()
    user_map = {u['username']: u for u in global_users}

    st.markdown("""
    <style>
    [data-baseweb="tab-list"] { background-color: #000000 !important; padding: 15px 20px; border-radius: 16px; box-shadow: 0px 8px 16px rgba(0,0,0,0.6); margin-bottom: 25px; gap: 15px; }
    [data-baseweb="tab"] { background-color: #1E293B !important; border: 2px solid #475569 !important; border-radius: 8px !important; padding: 12px 24px !important; transition: all 0.3s ease; }
    [data-baseweb="tab"], [data-baseweb="tab"] *, [data-baseweb="tab"] span, [data-baseweb="tab"] p { color: #FFFFFF !important; font-weight: 800 !important; font-size: 14px !important; letter-spacing: 0.05em !important; }
    [data-baseweb="tab"]:hover { background-color: #334155 !important; border-color: #94A3B8 !important; transform: translateY(-2px); }
    [data-baseweb="tab"][aria-selected="true"] { background-color: #06B6D4 !important; border-color: #06B6D4 !important; box-shadow: 0 4px 12px rgba(6, 182, 212, 0.6) !important; }
    [data-baseweb="tab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] *, [data-baseweb="tab"][aria-selected="true"] span, [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; }
    [data-baseweb="tab-highlight"] { display: none !important; }
    .hero-title { font-size: 2.8rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #0F766E, #06B6D4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 10px; }
    .feature-card { background-color: #ffffff; border-top: 4px solid #06B6D4; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); height: 100%; transition: transform 0.2s ease; border: 1px solid #e2e8f0; }
    .feature-card:hover { transform: translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.1); }
    .card-icon { font-size: 2.5rem; margin-bottom: 15px; }
    .card-title { font-weight: 800; font-size: 1.25rem; color: #0f172a; margin-bottom: 10px; }
    .card-desc { font-size: 0.95rem; color: #64748b; line-height: 1.6; }
    .appt-card { background-color: #F8FAFC; border-left: 5px solid #06B6D4; padding: 20px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #E2E8F0; }
    .appt-title { font-size: 1.15rem; font-weight: 800; color: #0F172A; }
    .appt-time { color: #0284C7; font-weight: 600; font-size: 0.95rem; margin-top: 5px;}
    .patient-note { margin-top: 12px; color: #475569; font-size: 0.95rem; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px dashed #cbd5e1;}
    .clinical-title { font-size: 2.5rem; font-weight: 700; color: #0f172a; text-align: center; margin-bottom: 0px; letter-spacing: -0.02em; }
    .clinical-subtitle { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 40px; }
    [data-testid="stFileUploader"] { background-color: #e0f2fe !important; border: 3px dashed #2563eb !important; border-radius: 16px !important; padding: 15px !important; }
    [data-testid="stFileUploadDropzone"] { background-color: transparent !important; }
    [data-testid="stFileUploader"] button { background-color: #2563eb !important; color: #ffffff !important; font-size: 18px !important; font-weight: 800 !important; padding: 12px 30px !important; border-radius: 8px !important; border: none !important; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3) !important; text-transform: uppercase !important; transition: all 0.3s ease !important; }
    [data-testid="stFileUploader"] button:hover { background-color: #1d4ed8 !important; transform: scale(1.05) !important; }
    [data-testid="stFileUploadDropzoneInstructions"] > div > span { color: #1e3a8a !important; font-size: 1.2rem !important; font-weight: 700 !important; }
    [data-testid="stFileUploadDropzoneInstructions"] > div > small { color: #334155 !important; font-size: 1rem !important; font-weight: 600 !important; }
    .result-card { background-color: #ffffff; border-radius: 8px; padding: 25px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); text-align: center; margin-top: 10px; border: 1px solid #e2e8f0; }
    .diagnosis-header { color: #475569; font-size: 0.95rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .confidence-text { font-size: 1.15rem; color: #334155; margin-top: 10px; }
    .section-divider { margin-top: 40px; margin-bottom: 20px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }
    .page-indicator { text-align: center; font-weight: bold; font-size: 1.1rem; color: #0F766E; margin-top: 5px; }
    .comment-box { background: #f8fafc; padding: 10px 15px; border-radius: 8px; border-left: 3px solid #3b82f6; margin-bottom: 8px; font-size: 0.95rem; }
    .comment-author { font-weight: bold; color: #1e293b; font-size: 0.85rem; }
    .comment-date { font-size: 0.75rem; color: #94a3b8; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)

    logo_base64 = get_base64_image("assets/logo_canviz.png")
    head_col1, head_col2, head_col3 = st.columns([3.5, 0.8, 1.2], vertical_alignment="center")
    with head_col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 15px;">
            <img src="data:image/png;base64,{logo_base64}" style="height: 45px; width: auto; object-fit: contain;">
            <span style="font-size: 1.8rem; font-weight: 900; background: linear-gradient(135deg, #0F766E, #06B6D4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">MEDICAL COMMAND CENTER</span>
        </div>
        """, unsafe_allow_html=True)
    with head_col2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()
    with head_col3:
        st.markdown(f"""
        <div style="background: #000000; padding: 8px 18px; border-radius: 10px; color: white; font-family: monospace; font-weight: bold; text-align: center;">
            👨‍⚕️{doc_name}
        </div>
        """, unsafe_allow_html=True)
            
    st.markdown("<br>", unsafe_allow_html=True)

    tab_dash, tab_diagnose, tab_patients, tab_appt, tab_history, tab_profile = st.tabs([
        "DASHBOARD", "AI DIAGNOSIS", "PATIENTS", "APPOINTMENTS", "HISTORY", "PROFILE"
    ])

    # ==========================================
    # ROUTE: DASHBOARD
    # ==========================================
    with tab_dash:
        st.markdown(f'<div class="hero-title">{doc_name}\'s Workspace</div>', unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#64748b; font-size:1.15rem; margin-bottom: 40px;'>Streamline your clinical workflow, review AI diagnostics, and manage patient consultations.</p>", unsafe_allow_html=True)
        st.markdown("<br><hr><br>", unsafe_allow_html=True) 
        st.subheader("Workspace Capabilities")
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("""<div class="feature-card"><div class="card-icon">📅</div><div class="card-title">Consultation Queue</div><div class="card-desc">Approve pending patient requests, review reported symptoms, and manage your daily appointments efficiently.</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown("""<div class="feature-card"><div class="card-icon">🧠</div><div class="card-title">AI Scan Verification</div><div class="card-desc">Access the global database to cross-reference patient biopsies with our Grad-CAM neural network overlays.</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown("""<div class="feature-card"><div class="card-icon">⏱️</div><div class="card-title">Schedule Control</div><div class="card-desc">Manage your clinic hours and sync your availability instantly with the patient portal.</div></div>""", unsafe_allow_html=True)

    # ==========================================
    # ROUTE: APPOINTMENTS
    # ==========================================
    with tab_appt:
        st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #0F766E;">Consultation Queue</div><br>', unsafe_allow_html=True)
        
        appointments = get_pending_appointments(doc_name)
        
        if not appointments:
            st.info("You have no active appointment requests at this time.")
        else:
            for appt in appointments:
                appt_id = appt['id']
                p_user = appt['username']
                p_date = appt['date']
                p_time = appt['time']
                p_notes = appt['notes']
                status = appt['status'] if 'status' in appt.keys() else "Pending"
                attached_scan = appt['attached_scan'] if 'attached_scan' in appt.keys() else "None"
                
                is_doctor_booking = "Protocol Session:" in str(p_notes) or "Doctor's Note:" in str(p_notes)
                if status == "Pending" and is_doctor_booking:
                    execute_db_action("update_appt", appt_id, {"status": "Approved"})
                    status = "Approved" 
                
                with st.container(border=True):
                    c1, c2 = st.columns([3.5, 1.5], vertical_alignment="center")
                    with c1:
                        notes_display = p_notes if p_notes else "No specific symptoms reported by patient."
                        attachment_html = f"<div style='margin-top:10px; padding:8px; background:#EFF6FF; color:#1D4ED8; border-radius:6px; font-weight:700; font-size:0.95rem;'>📎 AI Scan Attached: {attached_scan}</div>" if attached_scan and attached_scan != "None" else ""

                        status_text = "Ready for Session" if status == "Approved" else "Awaiting Your Approval"

                        st.markdown(f"""
                        <div class="appt-card">
                            <div class="appt-title">Patient: @{p_user}</div>
                            <div class="appt-time">🕒 {p_date} at {p_time} | Status: <b>{status} ({status_text})</b></div>
                            <div class="patient-note"><b>Session Notes:</b> {notes_display}</div>
                            {attachment_html}
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with c2:
                        if status == "Pending":
                            st.button("✅ Approve Request", key=f"app_{appt_id}", type="primary", use_container_width=True, on_click=execute_db_action, args=("update_appt", appt_id, {"status": "Approved"}))
                            st.button("❌ Reject", key=f"rej_{appt_id}", use_container_width=True, on_click=execute_db_action, args=("delete_appt", appt_id))
                        if status == "Approved":
                            with st.form(key=f"complete_form_{appt_id}"):
                                st.markdown("<h6 style='color: #0F766E;'>📝 Formal Clinical Assessment</h6>", unsafe_allow_html=True)
                                col_diag, col_treat = st.columns(2)
                                with col_diag: diag_input = st.text_area("🔍 Primary Findings", height=100)
                                with col_treat: treat_input = st.text_area("💊 Treatment Applied", height=100)
                                col_foll, col_life = st.columns(2)
                                with col_foll: follow_input = st.text_input("📅 Follow-up")
                                with col_life: life_input = st.text_input("🍎 Lifestyle Advice")
                                    
                                if st.form_submit_button("🏁 Complete & Archive Session", type="primary", use_container_width=True):
                                    formatted_advice = f"**🔍 Findings:**\n{diag_input if diag_input else 'None.'}\n\n**💊 Treatment Applied:**\n{treat_input if treat_input else 'None.'}\n\n**📅 Follow-up:**\n{follow_input if follow_input else 'None.'}\n\n**🍎 Advice:**\n{life_input if life_input else 'Standard care advised.'}"
                                    final_notes = f"{p_notes} | Assessment: {formatted_advice}"
                                    
                                    execute_db_action("update_appt", appt_id, {"status": "Completed", "doctor_advice": formatted_advice, "notes": final_notes})
                                    st.toast("Appointment archived to history with clinical notes!", icon="✅")
                                    time.sleep(1)
                                    st.rerun()
                        
                    if attached_scan and attached_scan != "None":
                        with st.expander(f"🔬 Review Patient's Attached Scan ({attached_scan})"):
                            img_path = f"uploaded_scans/{attached_scan}.jpg"
                            hm_path = f"uploaded_scans/{attached_scan}_heatmap.jpg"
                            ov_path = f"uploaded_scans/{attached_scan}_overlay.jpg"
                            if os.path.exists(img_path) and os.path.exists(hm_path):
                                v1, v2, v3 = st.columns(3)
                                v1.image(img_path, caption="Original Scan", use_container_width=True)
                                v2.image(hm_path, caption="Grad-CAM Heatmap", use_container_width=True)
                                v3.image(ov_path, caption="Detection Overlay", use_container_width=True)

    # ==========================================
    # ROUTE: HISTORY
    # ==========================================
    with tab_history:
        st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #0F766E;">Clinical History Archive</div><br>', unsafe_allow_html=True)
        
        sub_scan_hist, sub_appt_hist, sub_ref_hist = st.tabs(["🔬 Clinical Scan History", "📅 Appointment History", "📄 Referral Letters"])
        
        df_all_hist = get_all_history()

        with sub_scan_hist:
            st.write("Search, filter, and review all standard AI Biopsy records.")
            
            if not df_all_hist.empty:
                df_hist = df_all_hist[~df_all_hist['scan_id'].astype(str).str.startswith("REF_", na=False)].copy()
            else:
                df_hist = pd.DataFrame()

            if df_hist.empty:
                st.info("No biopsy scan records found in the system.")
            else:
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1: search_query = st.text_input("🔍 Search Scan ID or Filename:", placeholder="e.g., IMG_170...")
                with f_col2:
                    patient_list = ["All Patients"] + sorted(df_hist['username'].dropna().unique().tolist())
                    selected_patient_filter = st.selectbox("👤 Filter by Patient:", patient_list)
                with f_col3: filter_date = st.date_input("📅 Filter by Exact Date", value=None)

                filtered_df = df_hist.copy()
                if search_query:
                    if 'filename' not in filtered_df.columns: filtered_df['filename'] = "Legacy Scan"
                    filtered_df = filtered_df[filtered_df['scan_id'].str.contains(search_query, case=False, na=False) | filtered_df['filename'].str.contains(search_query, case=False, na=False)]
                if selected_patient_filter != "All Patients": filtered_df = filtered_df[filtered_df['username'] == selected_patient_filter]
                if filter_date: filtered_df = filtered_df[filtered_df['date'].str.startswith(str(filter_date), na=False)]

                if filtered_df.empty:
                    st.warning("No scans match your criteria.")
                else:
                    items_per_page = 10
                    total_items = len(filtered_df)
                    total_pages = math.ceil(total_items / items_per_page)
                    if total_pages == 0: total_pages = 1
                    if st.session_state.doc_scan_page > total_pages: st.session_state.doc_scan_page = 1

                    st.markdown("---")
                    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                    with p_col1:
                        if st.button("⬅️ Previous Page", disabled=(st.session_state.doc_scan_page == 1), use_container_width=True):
                            st.session_state.doc_scan_page -= 1
                            st.rerun()
                    with p_col2: st.markdown(f"<div class='page-indicator'>Page {st.session_state.doc_scan_page} of {total_pages} (Showing {total_items} Total Scans)</div>", unsafe_allow_html=True)
                    with p_col3:
                        if st.button("Next Page ➡️", disabled=(st.session_state.doc_scan_page == total_pages), use_container_width=True):
                            st.session_state.doc_scan_page += 1
                            st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

                    start_idx = (st.session_state.doc_scan_page - 1) * items_per_page
                    paginated_df = filtered_df.iloc[start_idx : start_idx + items_per_page]

                    for _, row in paginated_df.iterrows():
                        with st.container(border=True):
                            res_val = row["result"]
                            color = "green" if "Healthy" in res_val else ("orange" if "Inconclusive" in res_val else "red")
                            c1, c2 = st.columns([3, 1], vertical_alignment="center")
                            c1.markdown(f"**Patient:** {row['username']} | **Scan ID:** {row['scan_id']} | **Date:** {row['date']}")
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
                                    target_p_name = user_map.get(row['username'], {}).get('name', row['username'])
                                    target_p_email = user_map.get(row['username'], {}).get('email', '')
                                    pdf_bytes = generate_pdf_report(target_p_name, row['scan_id'], row['date'], row.get('filename', 'System Scan'), res_val, row['confidence'], img_path, hm_path, ov_path)
                                    
                                    btn_col1, btn_col2 = st.columns(2)
                                    with btn_col1:
                                        st.download_button(label="📄 Download PDF Report", data=pdf_bytes, file_name=f"CanViz_Report_{row['scan_id']}.pdf", mime="application/pdf", type="primary", use_container_width=True, key=f"dl_pdf_h_{row['scan_id']}")
                                    with btn_col2:
                                        if st.button(f"📧 Email Report to Patient ({target_p_email})", use_container_width=True, disabled=(not target_p_email), key=f"em_pdf_pt_{row['scan_id']}"):
                                            with st.spinner(f"Sending to {target_p_email}..."):
                                                files = {'pdf_file': (f"CanViz_Report_{row['scan_id']}.pdf", pdf_bytes, 'application/pdf')}
                                                data = {'email': target_p_email, 'name': target_p_name, 'scan_id': row['scan_id']}
                                                try:
                                                    resp = requests.post(f"{FLASK_URL}/email_report", data=data, files=files)
                                                    if resp.status_code == 200: st.success("Report sent to patient!")
                                                    else: st.error("Server failed to send email.")
                                                except Exception as e: st.error(f"Error: {e}")
                                                
                                    st.markdown("---")
                                    st.markdown("##### 💬 Clinical Scan Comments")
                                    try:
                                        comments_res = supabase.table('scan_comments').select('*').eq('scan_id', row['scan_id']).order('created_at').execute()
                                        if not comments_res.data: st.info("No comments on this scan yet.")
                                        else:
                                            for c in comments_res.data:
                                                st.markdown(f"<div class='comment-box'><span class='comment-author'>Dr. {c['doctor_name']}</span><span class='comment-date'>{c['created_at'][:16]}</span><br>{c['comment']}</div>", unsafe_allow_html=True)
                                    except: pass
                                        
                                    with st.form(key=f"comment_form_{row['scan_id']}"):
                                        new_comment = st.text_input("Add a clinical note to this scan:", placeholder="E.g., Margins appear irregular, recommending secondary biopsy.")
                                        if st.form_submit_button("Post Comment"):
                                            if new_comment:
                                                supabase.table('scan_comments').insert({"scan_id": row['scan_id'], "doctor_name": doc_name, "comment": new_comment}).execute()
                                                st.rerun()
                                else:
                                    st.warning("Image files purged from server.")

        with sub_appt_hist:
            st.write("Review your past completed consultations and clinical notes.")
            past_appts = get_completed_appointments(doc_name)
            
            if not past_appts:
                st.info("You do not have any completed appointments on record.")
            else:
                for appt in past_appts:
                    appt_id = appt['id']
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1], vertical_alignment="center")
                        with c1:
                            st.markdown(f"**Patient:** @{appt['username']} | **Date:** {appt['date']}")
                            advice = appt['doctor_advice'] if appt['doctor_advice'] else "No advice recorded."
                            st.markdown(f"<div style='background:#F8FAFC; padding:12px; border-radius:8px; border: 1px dashed #cbd5e1; color:#475569;'><b>Your Notes:</b><br>{advice}</div>", unsafe_allow_html=True)
                        with c2:
                            st.button("🗑️ Delete", key=f"del_doc_{appt_id}", use_container_width=True, on_click=execute_db_action, args=("update_appt", appt_id, {"doctor_deleted": 1}))

        with sub_ref_hist:
            st.write("Archive of all generated Clinical Referral Letters.")
            
            if not df_all_hist.empty:
                df_refs = df_all_hist[df_all_hist['scan_id'].astype(str).str.startswith("REF_", na=False)].copy()
            else:
                df_refs = pd.DataFrame()

            if df_refs.empty:
                st.info("No referral letters found in the system.")
            else:
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1: search_query_ref = st.text_input("🔍 Search Record ID:", placeholder="e.g., REF_170...", key="ref_search")
                with f_col2:
                    patient_list_ref = ["All Patients"] + sorted(df_refs['username'].dropna().unique().tolist())
                    selected_patient_filter_ref = st.selectbox("👤 Filter by Patient:", patient_list_ref, key="ref_pat_filter")
                with f_col3: filter_date_ref = st.date_input("📅 Filter by Exact Date", value=None, key="ref_date_filter")

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
                    if st.session_state.doc_ref_page > total_pages: st.session_state.doc_ref_page = 1

                    st.markdown("---")
                    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                    with p_col1:
                        if st.button("⬅️ Previous Page", disabled=(st.session_state.doc_ref_page == 1), use_container_width=True, key="ref_prev"):
                            st.session_state.doc_ref_page -= 1
                            st.rerun()
                    with p_col2: st.markdown(f"<div class='page-indicator'>Page {st.session_state.doc_ref_page} of {total_pages} (Showing {total_items} Total Referrals)</div>", unsafe_allow_html=True)
                    with p_col3:
                        if st.button("Next Page ➡️", disabled=(st.session_state.doc_ref_page == total_pages), use_container_width=True, key="ref_next"):
                            st.session_state.doc_ref_page += 1
                            st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

                    start_idx = (st.session_state.doc_ref_page - 1) * items_per_page
                    paginated_df_refs = filtered_df_refs.iloc[start_idx : start_idx + items_per_page]

                    for _, row in paginated_df_refs.iterrows():
                        with st.container(border=True):
                            c1, c2 = st.columns([3, 1], vertical_alignment="center")
                            c1.markdown(f"**Patient:** {row['username']} | **Record ID:** {row['scan_id']} | **Date:** {row['date']}")
                            c2.markdown(f"<span style='color:#0284c7; font-weight:bold;'>Clinical Referral ({row['confidence']})</span>", unsafe_allow_html=True)
                            
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
                                            supabase.table('scan_comments').insert({"scan_id": row['scan_id'], "doctor_name": doc_name, "comment": new_comment}).execute()
                                            st.rerun()

    # ==========================================
    # ROUTE: PATIENTS DIRECTORY
    # ==========================================
    with tab_patients:
        st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #0F766E;">Unified Patient Management</div><br>', unsafe_allow_html=True)
        
        sub_my_patients, sub_master_list, sub_treat_sched, sub_referral = st.tabs([
            "📋 Assigned Patients", "🌐 Master List", "💉 Treatment & Scheduling", "📄 Referral Letters"
        ])
        
        assigned_usernames = get_assigned_patients(doc_name)
        
        with sub_my_patients:
            st.subheader("Your Patient Roster")
            if not assigned_usernames:
                st.info("You haven't assigned any patients to yourself yet. Go to the Master User List to add patients.")
            else:
                st.success(f"You have {len(assigned_usernames)} active patients.")
                for p_uname in assigned_usernames:
                    with st.container(border=True):
                        st.markdown(f"👤 **Patient ID:** @{p_uname}")
                        st.button("Unassign", key=f"unassign_{p_uname}", on_click=execute_db_action, args=("unassign_patient", (doc_name, p_uname)))
        
        with sub_master_list:
            st.subheader("Global System Directory")
            st.write("Search and assign users to your personal roster.")
            
            all_patients = [u for u in user_map.values() if u.get("role") == "user"]
            search_pt = st.text_input("🔍 Search User by Name or Username:")
            
            if search_pt:
                all_patients = [p for p in all_patients if search_pt.lower() in p['username'].lower() or search_pt.lower() in p['name'].lower()]
            
            if all_patients:
                for p in all_patients:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1], vertical_alignment="center")
                        c1.markdown(f"**Name:** {p['name']} | **Username:** @{p['username']} <br><span style='color:gray;font-size:0.85em;'>{p['email']}</span>", unsafe_allow_html=True)
                        if p['username'] in assigned_usernames:
                            c2.button("Assigned ✓", disabled=True, key=f"al_ass_{p['username']}")
                        else:
                            if c2.button("➕ Assign to Me", key=f"ass_{p['username']}", type="primary"):
                                try:
                                    existing = supabase.table('patient_assignments').select('*').eq('doctor_name', doc_name).eq('patient_username', p['username']).execute()
                                    if not existing.data:
                                        supabase.table('patient_assignments').insert({"doctor_name": doc_name, "patient_username": p['username']}).execute()
                                        st.cache_data.clear()
                                        st.toast(f"@{p['username']} added to your roster!", icon="✅")
                                    time.sleep(0.5)
                                except Exception: pass
                                st.rerun()
            else: 
                st.info("No users match your search.")

        with sub_treat_sched:
            st.subheader("Patient Timeline: Protocol & Scheduling")
            if not assigned_usernames:
                st.info("Please assign a patient to yourself before managing their treatment timeline.")
            else:
                selected_treat_patient = st.selectbox("Select Patient to Manage:", assigned_usernames)
                
                # Using cached calls
                all_pat_appts_res = supabase.table('appointments').select('*').eq('username', selected_treat_patient).eq('doctor', doc_name).eq('doctor_deleted', 0).execute()
                all_pat_appts = all_pat_appts_res.data if all_pat_appts_res.data else []
                
                st.markdown("---")
                st.markdown(f"#### 1️⃣ Active Protocols for @{selected_treat_patient}")
                plan_data = get_treatment_plans(selected_treat_patient)
                
                if plan_data:
                    for plan in plan_data:
                        with st.expander(f"💉 {plan['treatment_type']} | Started: {plan['start_date']}", expanded=True):
                            st.markdown(f"**Target Duration:** {plan['duration_months']} Months | **Frequency:** {plan['frequency']}")
                            st.markdown(f"**Protocol Details:** {plan['notes']}")
                            
                            freq_map = {"Weekly": 4, "Bi-Weekly": 2, "Monthly": 1, "Quarterly": 0.33, "As Needed": 1}
                            sessions_per_month = freq_map.get(plan['frequency'], 1)
                            target_total_sessions = int(plan['duration_months'] * sessions_per_month)
                            if target_total_sessions < 1: target_total_sessions = 1
                            
                            completed_count = 0
                            for a in all_pat_appts:
                                if a.get('status') == 'Completed' and plan['treatment_type'] in str(a.get('notes', '')):
                                    completed_count += 1
                                    
                            display_count = min(completed_count, target_total_sessions)
                            progress = min(display_count / target_total_sessions, 1.0)
                            percent_complete = int(progress * 100)
                            
                            st.progress(progress)
                            st.markdown(f"<div style='text-align:right; font-weight:bold; color:#0369A1; margin-bottom:10px;'>{display_count}/{target_total_sessions} Sessions Completed ({percent_complete}%)</div>", unsafe_allow_html=True)
                            
                            st.markdown("---")
                            
                            pending_for_plan = [a for a in all_pat_appts if a.get('status') != 'Completed' and plan['treatment_type'] in str(a.get('notes', ''))]
                            
                            if pending_for_plan:
                                next_appt = sorted(pending_for_plan, key=lambda x: x['date'])[0]
                                st.success(f"📅 **Next Session Confirmed:** Patient is scheduled for **{next_appt['date']} at {next_appt['time']}**.")
                            else:
                                st.warning("⚠️ **Action Required:** No upcoming session scheduled for this protocol.")
                                st.markdown("##### Schedule Next Session:")
                                
                                # 🌟 FAST UI INJECTION 🌟
                                render_booking_fragment(plan, doc_name, selected_treat_patient, user_map)

                            st.markdown("---")
                            # Callback handles instantaneous deletion
                            st.button("🛑 Terminate Protocol", key=f"term_btn_{plan['id']}", type="secondary", on_click=execute_db_action, args=("delete_plan", plan['id']))
                else:
                    st.info("No active treatment plans established.")
                st.markdown("---")
                
                st.markdown(f"#### 2️⃣ Establish New Protocol & Anchor Session")
                patient_hist = supabase.table('history').select('*').eq('username', selected_treat_patient).order('date', desc=True).execute()
                scan_options = []
                if patient_hist.data:
                    for r in patient_hist.data:
                        if "Healthy" not in r["result"] and "Inconclusive" not in r["result"] and not str(r['scan_id']).startswith("REF_"):
                            scan_options.append(f"{r['result']} | {r['confidence']} [Scan ID: {r['scan_id']}]")
                            
                if not scan_options: 
                    scan_options = ["No Malignant Scans Found - Manual Selection: " + c for c in CANCER_ONLY_CLASSES]

                # 🌟 FAST UI INJECTION 🌟
                render_new_protocol_fragment(doc_name, selected_treat_patient, user_map, scan_options)

        with sub_referral:
            st.subheader("Generate Clinical Referral Letter")
            st.write("Generate formal documentation to refer patients for specialized oncology treatment.")
            
            if not assigned_usernames:
                st.info("Please assign a patient to yourself first.")
            else:
                r_patient_user = st.selectbox("Select Patient to Refer:", assigned_usernames, key="ref_patient")
                r_patient_name = user_map.get(r_patient_user, {}).get('name', r_patient_user)
                
                try:
                    ref_hist = supabase.table('history').select('*').eq('username', r_patient_user).order('date', desc=True).execute()
                    ref_scans = [r for r in ref_hist.data if "Healthy" not in r["result"] and not str(r['scan_id']).startswith("REF_")]
                    
                    if not ref_scans:
                        st.warning(f"@{r_patient_user} has no malignant AI scans on record to base a referral on.")
                    else:
                        scan_dict = {f"{s['result']} | Confidence: {s['confidence']} [{s['scan_id']}]": s for s in ref_scans}
                        selected_ref_scan_str = st.selectbox("Select Abnormal Scan to Attach:", list(scan_dict.keys()))
                        
                        # 🌟 THE FIX: Replaced Urgency Dropdown with Specific Target Hospital Dropdown
                        ref_hospital = st.selectbox("Target Hospital for Transfer:", [
                            "National Cancer Institute (IKN), Putrajaya",
                            "Hospital Kuala Lumpur (HKL)",
                            "Sunway Medical Centre",
                            "Subang Jaya Medical Centre (SJMC)",
                            "Gleneagles Hospital Kuala Lumpur"
                        ])
                        
                        ref_notes = st.text_area("Clinical Justification / Detailed Notes:", placeholder="Patient presents with severe localized pain. Requesting immediate biopsy review.", height=150)
                        
                        if st.button("📄 Prepare Referral Letter", type="primary", use_container_width=True):
                            if not ref_notes: st.error("Please provide clinical justification notes.")
                            else:
                                target_scan = scan_dict[selected_ref_scan_str]
                                
                                # Generate the PDF bytes using the new hospital name parameter
                                letter_bytes = generate_referral_letter(doc_name, r_patient_name, target_scan['scan_id'], target_scan['date'], target_scan['result'], target_scan['confidence'], ref_hospital, ref_notes)
                                
                                ref_scan_id = f"REF_{int(time.time())}"
                                os.makedirs("uploaded_scans", exist_ok=True)
                                with open(f"uploaded_scans/{ref_scan_id}.pdf", "wb") as f:
                                    f.write(letter_bytes)
                                
                                try:
                                    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    supabase.table('history').insert({
                                        "username": r_patient_user,
                                        "scan_id": ref_scan_id,
                                        "date": date_str,
                                        "result": "Clinical Referral",
                                        "confidence": ref_hospital, # Saving hospital name here to display in history
                                        "status": "Completed",
                                        "filename": f"Referral_{r_patient_user}.pdf"
                                    }).execute()
                                    st.cache_data.clear()
                                    st.toast("Referral securely logged to Clinical History Archive!", icon="✅")
                                except Exception as e:
                                    st.error(f"Error saving referral to database: {e}")

                                st.session_state[f'ref_letter_{r_patient_user}'] = letter_bytes
                                st.session_state[f'ref_scan_{r_patient_user}'] = ref_scan_id
                        
                        if f'ref_letter_{r_patient_user}' in st.session_state:
                            st.success("Referral Letter Prepared! Choose an action below:")
                            letter_bytes = st.session_state[f'ref_letter_{r_patient_user}']
                            scan_id_ref = st.session_state[f'ref_scan_{r_patient_user}']

                            d_col1, d_col2 = st.columns(2)
                            with d_col1:
                                st.download_button(label="⬇️ Download PDF", data=letter_bytes, file_name=f"Referral_{r_patient_user}_{scan_id_ref}.pdf", mime="application/pdf", use_container_width=True)
                            with d_col2:
                                target_p_email = user_map.get(r_patient_user, {}).get('email', '')
                                if st.button("📧 Email to Patient", use_container_width=True):
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
    # 🌟 ROUTE: AI DIAGNOSIS
    # ==========================================
    with tab_diagnose:
        st.markdown('<div class="clinical-title">Histopathology Analysis System</div>', unsafe_allow_html=True)
        st.markdown('<div class="clinical-subtitle">Upload biopsy scan for automated screening and Grad-CAM assessment</div>', unsafe_allow_html=True)
        
        if 'last_scan_result' in st.session_state:
            ls = st.session_state.last_scan_result
            st.success(f"✅ Screening Complete. Result securely logged to @{ls['target']}'s clinical history. You can now switch tabs to establish a protocol.")
            
            st.markdown(f"""
            <div class="result-card" style="border-top: 5px solid {ls['border_color']};">
                <div class="diagnosis-header">AI Pathology Report</div>
                <h1 style="color: {ls['color']}; font-size: 2.2rem; margin: 10px 0;">{ls['result']}</h1>
                <div class="confidence-text">Confidence Level: <b>{ls['confidence'] * 100:.2f}%</b></div>
            </div>
            """, unsafe_allow_html=True)

            img_path = f"uploaded_scans/{ls['scan_id']}.jpg"
            hm_path = f"uploaded_scans/{ls['scan_id']}_heatmap.jpg"
            ov_path = f"uploaded_scans/{ls['scan_id']}_overlay.jpg"
            
            if os.path.exists(img_path) and os.path.exists(hm_path):
                st.markdown('<div class="section-divider"><h4 style="color: #0f172a; margin: 0;">🔬 Neural Network Visualization</h4></div>', unsafe_allow_html=True)
                st.write("Grad-CAM highlights identifying morphological features. Warmer areas (red/yellow) indicate maximum neural activation influencing the diagnosis.")
                st.markdown("<br>", unsafe_allow_html=True)
                
                vis_col1, vis_col2, vis_col3 = st.columns(3, gap="medium")
                with vis_col1:
                    with st.container(border=True):
                        st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>1. Standardized Scan</div>", unsafe_allow_html=True)
                        st.image(img_path, use_container_width=True)
                with vis_col2:
                    with st.container(border=True):
                        st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>2. Grad-CAM Heatmap</div>", unsafe_allow_html=True)
                        st.image(hm_path, use_container_width=True)
                with vis_col3:
                    with st.container(border=True):
                        st.markdown("<div style='text-align: center; color: #475569; font-weight: 600; padding-bottom: 10px;'>3. Detection Overlay</div>", unsafe_allow_html=True)
                        st.image(ov_path, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Clear Viewer & Scan Another Patient", type="primary", use_container_width=True):
                del st.session_state.last_scan_result
                st.rerun()

        else:
            st.markdown("<div style='background-color:#F8FAFC; padding:20px; border-radius:10px; border:1px solid #cbd5e1; margin-bottom:25px;'>", unsafe_allow_html=True)
            st.markdown("<h5 style='color: #0F766E; margin-top:0;'>1. Select Target Patient</h5>", unsafe_allow_html=True)
            
            try:
                assigned_res = supabase.table('patient_assignments').select('patient_username').eq('doctor_name', doc_name).execute()
                assigned_usernames = [row['patient_username'] for row in assigned_res.data]
            except Exception as e: assigned_usernames = []
                
            if not assigned_usernames:
                st.warning("⚠️ You must assign a patient to your roster (in the PATIENTS tab) before you can run an AI scan.")
                st.stop()
                
            target_patient = st.selectbox("Assign diagnostic results to:", assigned_usernames)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<h5 style='text-align: center; color: #1e3a8a;'>📥 2. Drag & Drop Biopsy Scan</h5>", unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader(" ", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if uploaded_file is not None:
                col_input, col_action = st.columns([1, 1.2], gap="large")
                with col_input:
                    with st.container(border=True):
                        st.markdown(f"<h5 style='text-align: center; color: #1e3a8a; margin-bottom: 15px;'>Scan Input for @{target_patient}</h5>", unsafe_allow_html=True)
                        st.image(uploaded_file, use_container_width=True)
                with col_action:
                    st.markdown("<h5 style='color: #1e3a8a;'>System Controls</h5>", unsafe_allow_html=True)
                    st.info("✅ Secure connection established. Image ready for screening.")
                    if st.button("▶ Initialize AI Diagnosis", type="primary", use_container_width=True):
                        with st.spinner("Processing tissue morphology and analyzing confidence levels..."):
                            image = Image.open(uploaded_file).convert("RGB")
                            img_tensor = preprocess(image).unsqueeze(0).to(compute_device)
                            cam, probs, class_idx = gradcam(img_tensor)
                            confidence = float(probs[class_idx])
                            result = CLASS_NAMES[class_idx]
                            
                            if confidence < 0.40:
                                st.error("🛑 **Scan Rejected: Invalid Image Detected**")
                                st.warning(f"The AI confidence level is too low ({confidence * 100:.1f}%). The system does not recognize this as a valid histopathology medical scan. Please upload a legitimate biopsy image.")
                            else:
                                if "Cancer" in result: color, border_color = "#dc2626", "#ef4444"
                                else: color, border_color = "#16a34a", "#22c55e"

                                display_img = unnormalize(img_tensor[0].cpu())
                                heatmap = cm.jet(cam)[:, :, :3]
                                overlay = np.clip(0.55 * display_img + 0.45 * heatmap, 0, 1)

                                scan_id = f"IMG_{int(datetime.datetime.now().timestamp())}"
                                date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                original_filename = uploaded_file.name
                                
                                os.makedirs("uploaded_scans", exist_ok=True)
                                image.save(f"uploaded_scans/{scan_id}.jpg")
                                Image.fromarray((heatmap * 255).astype(np.uint8)).save(f"uploaded_scans/{scan_id}_heatmap.jpg")
                                Image.fromarray((overlay * 255).astype(np.uint8)).save(f"uploaded_scans/{scan_id}_overlay.jpg")
                                
                                try:
                                    supabase.table('history').insert({
                                        "username": target_patient, "scan_id": scan_id, "date": date_str,
                                        "result": result, "confidence": f"{confidence*100:.2f}%",
                                        "status": "Pending", "filename": original_filename
                                    }).execute()
                                    
                                    st.session_state.last_scan_result = {
                                        'target': target_patient,
                                        'result': result,
                                        'confidence': confidence,
                                        'color': color,
                                        'border_color': border_color,
                                        'scan_id': scan_id
                                    }
                                    st.rerun() 
                                except Exception as e: st.error(f"Cloud Database error: {e}")

    # ==========================================
    # ROUTE: PROFILE
    # ==========================================
    with tab_profile:
        st.markdown('<div style="font-size: 2rem; font-weight: bold; color: #0F766E;">Doctor Profile</div><br>', unsafe_allow_html=True)
        st.write("Manage your account security and update your password.")
        
        with st.container(border=True):
            st.markdown(f"**Name:** Dr. {doc_name}")
            st.markdown(f"**System ID (Username):** {current_username}")
            st.markdown("---")
            st.markdown("##### 🔐 Change Password")
            
            with st.form("change_password_form"):
                current_pass = st.text_input("Current Password", type="password")
                new_pass = st.text_input("New Password", type="password")
                confirm_pass = st.text_input("Confirm New Password", type="password")
                
                if st.form_submit_button("💾 Save New Password", type="primary"):
                    if not current_pass: st.error("⚠️ You must enter your current password to make changes.")
                    elif not new_pass: st.error("⚠️ Please enter a new password.")
                    elif new_pass != confirm_pass: st.error("⚠️ New passwords do not match!")
                    elif len(new_pass) < 6: st.error("⚠️ New password must be at least 6 characters.")
                    else:
                        payload = {"username": current_username, "current_password": current_pass, "new_password": new_pass, "update_type": "password"}
                        try:
                            with st.spinner("Verifying and securing account..."):
                                response = requests.put(f"{FLASK_URL}/update_profile", json=payload)
                            if response.status_code == 200:
                                st.success("✅ Password updated successfully!")
                                time.sleep(1.5)
                                st.rerun()
                            elif response.status_code == 401: st.error("🛑 The current password you entered is incorrect.")
                            else: st.error(f"Failed to update password. Server returned {response.status_code}")
                        except Exception as e: st.error(f"Connection Error: {e}")