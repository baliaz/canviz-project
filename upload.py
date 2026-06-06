import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import streamlit as st
import numpy as np
from PIL import Image
import datetime
import matplotlib.cm as cm
import base64

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

# -------------------------------------------------------------
# PYTORCH MODEL BLUEPRINTS & SETUP
# -------------------------------------------------------------
def build_model(num_classes=13):
    model = resnet50(weights=None)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.50),
        nn.Linear(in_features, 512),
        nn.BatchNorm1d(512),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.25),
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

# GPU Accelerated Optimization
IMG_SIZE = 256
CLASS_NAMES = [
    "Blood Cancer - Stage 1", "Blood Cancer - Stage 2", "Blood Cancer - Stage 3",
    "Breast Cancer", "Colon Cancer", "Kidney Cancer",
    "Lung Cancer - Stage 1", "Lung Cancer - Stage 2",
    "Healthy Blood", "Healthy Breast", "Healthy Colon",
    "Healthy Kidney", "Healthy Lung"
]

preprocess = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
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
    cnn_model = build_model(num_classes=13)
    checkpoint = torch.load("best_resnet50_histopathology_gradcam_classifier.pth", map_location=device)
    cnn_model.load_state_dict(checkpoint['model_state_dict'])
    cnn_model.to(device)
    cnn_model.eval()
    gradcam = GradCAM(cnn_model, cnn_model.layer4[-1])
    return cnn_model, gradcam, device

cnn_model, gradcam, compute_device = load_assets()

def get_base64_image(path):
    try:
        with open(path, "rb") as img: return base64.b64encode(img.read()).decode()
    except Exception: return "" 

def show_upload_page():
    if st.session_state.get("role") != "doctor":
        st.error("🛑 Security Violation: Unauthorized Access. Medical Staff Only.")
        st.stop()
        
    doc_name = st.session_state.get("name", "Doctor")

    st.markdown("""
    <style>
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
            st.rerun()
    with head_col3:
        st.markdown(f"""
        <div style="background: #000000; padding: 8px 18px; border-radius: 10px; color: white; font-family: monospace; font-weight: bold; text-align: center;">
            👨‍⚕️ Dr. {doc_name}
        </div>
        """, unsafe_allow_html=True)
            
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    
    st.markdown('<div class="clinical-title">AI Histopathology Scanner</div>', unsafe_allow_html=True)
    st.markdown('<div class="clinical-subtitle">Dedicated hardware-accelerated instance for biopsy screening.</div>', unsafe_allow_html=True)
    
    if 'last_scan_result' in st.session_state:
        ls = st.session_state.last_scan_result
        st.success(f"✅ Screening Complete. Result securely logged to @{ls['target']}'s clinical history. You can now return to the main dashboard to establish a protocol.")
        
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
        if st.button("✅ Acknowledge & Scan Another Patient", type="primary", use_container_width=True):
            del st.session_state.last_scan_result
            st.rerun()

    else:
        st.markdown("<div style='background-color:#F8FAFC; padding:20px; border-radius:10px; border:1px solid #cbd5e1; margin-bottom:25px;'>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: #0F766E; margin-top:0;'>1. Select Target Patient</h5>", unsafe_allow_html=True)
        
        try:
            assigned_res = supabase.table('patient_assignments').select('patient_username').eq('doctor_name', doc_name).execute()
            assigned_usernames = [row['patient_username'] for row in assigned_res.data]
        except Exception: assigned_usernames = []
            
        if not assigned_usernames:
            st.warning("⚠️ You must assign a patient to your roster in the main dashboard before you can run an AI scan.")
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
                st.info("✅ Secure connection established. GPU ready.")
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
                                    'target': target_patient, 'result': result,
                                    'confidence': confidence, 'color': color,
                                    'border_color': border_color, 'scan_id': scan_id
                                }
                                st.rerun() 
                            except Exception as e: st.error(f"Cloud Database error: {e}")