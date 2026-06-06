import streamlit as st
import history
import appointment
import user_profile
import admin
import doctor
import base64

# ---------------------
# HELPER: LOAD IMAGE AS BASE64
# ---------------------
def get_base64_image(path):
    try:
        with open(path, "rb") as img:
            return base64.b64encode(img.read()).decode()
    except FileNotFoundError:
        return "" 

def show_homepage():

    # ---------------------
    # PAGE CONFIG
    # ---------------------
    st.set_page_config(
        page_title="CanViz | Portal",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# ---------------------
    # SESSION STATE
    # ---------------------
    if "username" not in st.session_state:
        st.session_state.username = "Guest"
    if "role" not in st.session_state:
        st.session_state.role = "user"

    if "page" not in st.session_state:
        st.session_state.page = "home"

    # 🌟 THE FIX: Read the URL, then immediately wipe it clean!
    if "page" in st.query_params:
        st.session_state.page = st.query_params["page"]
        st.query_params.clear() # <--- This stops the URL from freezing your buttons!

    # ---------------------
    # HANDLE LOGOUT
    # ---------------------
    if "tab" in st.query_params and st.query_params["tab"] == "Logout":
        st.session_state.logged_in = False
        st.session_state.username = "Guest"
        st.session_state.role = "user"
        st.session_state.page = "Login"
        st.query_params.clear()
        st.rerun()
    # ---------------------
    # CSS STYLING
    # ---------------------
    st.markdown("""
    <style>
    [data-testid="stHeader"] { display: none; }
    .main .block-container { padding-top: 1rem; max-width: 95%; }
    .nav-container { background-color: #000000; padding: 12px 30px; margin-bottom: 30px; border-radius: 18px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0px 8px 16px rgba(0,0,0,0.4); }
    .nav-left { display: flex; align-items: center; gap: 40px; }
    .brand-group { display: flex; align-items: center; }
    .brand-logo { height: 45px; width: auto; object-fit: contain; }
    .nav-links { display: flex; gap: 5px; }
    .nav-item { color: white !important; font-size: 13px; font-weight: 600; padding: 10px 20px; border-radius: 10px; text-decoration: none !important; transition: background 0.3s; }
    .nav-item:hover { background: rgba(255,255,255,0.1); }
    .nav-active { background: #333333 !important; }
    .nav-admin { background: #E11D48 !important; }
    .nav-admin:hover { background: #BE123C !important; }
    .nav-right { background: white; padding: 8px 18px; border-radius: 10px; display: flex; align-items: center; gap: 8px; }
    .user-name { font-family: monospace; font-size: 14px; font-weight: 700; color: black; }
    
    /* Hero & Card Styles */
    .hero-title { font-size: 3rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #0284C7, #007bff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 10px; }
    .feature-card { background-color: #ffffff; border-top: 4px solid #007bff; border-radius: 10px; padding: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); height: 100%; transition: transform 0.2s; border-left: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;}
    .feature-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); }
    .card-icon { font-size: 2.5rem; margin-bottom: 15px; }
    .card-title { font-weight: bold; font-size: 1.2rem; color: #0f172a; margin-bottom: 8px; }
    .card-desc { font-size: 0.95rem; color: #64748b; line-height: 1.5; }
    </style>
    """, unsafe_allow_html=True)

    # ---------------------
    # 🌟 SMART NAV BAR LOGIC
    # ---------------------
    def render_navbar():
        current_page = st.session_state.page
        current_user = st.session_state.username
        current_name = st.session_state.get("name", current_user) 
        current_role = st.session_state.get("role", "user")

        if current_role == "admin":
            nav_data = { "⚙️ Admin Control Panel": "admin" }
            user_display = f"⚙️ Admin: {current_name}"
            if current_page not in ["admin"]:
                st.session_state.page = "admin"
                st.rerun()
                
        elif current_role == "doctor":
            nav_data = { "🩺 Dashboard": "doctor_dashboard" } 
            user_display = f"👨‍⚕️ Dr. {current_name}"
            if current_page != "doctor_dashboard":
                st.session_state.page = "doctor_dashboard"
                st.rerun()
                
        else:
            nav_data = {
                "Home": "home",
                "History": "history",
                "Appointment": "appointment",
                "Profile": "profile"
            }
            # 🌟 CHANGE THIS LINE:
            user_display = f"👤{current_user}"
            
            if current_page in ["admin", "doctor_dashboard"]:
                st.session_state.page = "home"
                st.rerun()

        links_html = ""
        for label, page in nav_data.items():
            active = "nav-active" if current_page == page else ""
            admin_style = "nav-admin" if page == "admin" else ""
            links_html += f'<a href="?page={page}&user={current_user}" class="nav-item {active} {admin_style}" target="_self">{label.upper()}</a>'

        links_html += '<a href="?tab=Logout" class="nav-item" target="_self">LOGOUT</a>'
        
        logo_base64 = get_base64_image("assets/logo_canviz.png")

        nav_html = f"""
        <div class="nav-container">
            <div class="nav-left">
                <div class="brand-group">
                    <img src="data:image/png;base64,{logo_base64}" class="brand-logo">
                </div>
                <div class="nav-links">{links_html}</div>
            </div>
            <div class="nav-right">
                <span class="user-name">{user_display}</span>
            </div>
        </div>
        """
        st.markdown(nav_html, unsafe_allow_html=True)

    # ---------------------
    # 🌟 SMART FOOTER LOGIC
    # ---------------------
    def render_footer():
        logo_base64 = get_base64_image("assets/logo_canviz.png")
        footer_html = f"""
<style>
.footer-container {{ background-color: #0F172A; color: #94A3B8; padding: 40px 30px 20px 30px; border-radius: 16px; margin-top: 60px; box-shadow: 0 -4px 10px rgba(0,0,0,0.05); font-family: 'Inter', sans-serif; }}
.footer-grid {{ display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr; gap: 20px; margin-bottom: 30px; }}
.footer-col h4 {{ color: #F8FAFC; font-size: 1.1rem; font-weight: 600; margin-bottom: 15px; margin-top: 0; }}
.footer-col p, .footer-col a {{ font-size: 0.9rem; color: #94A3B8; text-decoration: none; line-height: 1.6; display: block; margin-bottom: 8px; transition: 0.2s; }}
.footer-col a:hover {{ color: #38BDF8; padding-left: 5px; }}
.footer-bottom {{ border-top: 1px solid #1E293B; padding-top: 20px; text-align: center; font-size: 0.85rem; }}
.contact-item {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; font-size: 0.9rem; }}
.contact-item i {{ color: #38BDF8; margin-top: 4px; width: 16px; text-align: center; }}
</style>
<div class="footer-container">
<div class="footer-grid">
<div class="footer-col">
<img src="data:image/png;base64,{logo_base64}" style="height: 45px; margin-bottom: 15px; filter: brightness(0) invert(1);">
<p style="padding-right: 20px;">CanViz is a premier medical intelligence platform combining state-of-the-art deep learning with clinical expertise to provide rapid, accurate oncology screening and biopsy analysis.</p>
</div>
<div class="footer-col">
<h4>Patients</h4>
<a href="#">Book Consultation</a>
<a href="#">Patient Portal</a>
<a href="#">Prepare for Biopsy</a>
<a href="#">Privacy Policy</a>
</div>
<div class="footer-col">
<h4>Clinical</h4>
<a href="#">For Oncologists</a>
<a href="#">AI Methodology</a>
<a href="#">Research & Data</a>
<a href="#">HIPAA Compliance</a>
</div>
<div class="footer-col">
<h4>Contact Us</h4>
<div class="contact-item"><i class="fa-solid fa-phone"></i> +60 3-1234 5678</div>
<div class="contact-item"><i class="fa-solid fa-envelope"></i> support@canviz.medical</div>
<div class="contact-item"><i class="fa-solid fa-location-dot"></i> KL Sentral Medical Hub<br>Kuala Lumpur, Malaysia</div>
</div>
</div>
<div class="footer-bottom">
&copy; 2026 CanViz Multi-Cancer Detection Systems. All rights reserved. <br>
<span style="font-size: 0.75rem; color: #64748B;">Disclaimer: The CanViz AI platform is an assistive diagnostic tool and does not replace professional medical diagnosis by a certified physician.</span>
</div>
</div>
"""
        st.markdown(footer_html, unsafe_allow_html=True)

    # Render Navigation
    render_navbar()

    # ---------------------
    # PAGE CONTENT ROUTER
    # ---------------------
    if st.session_state.page == "home":
        st.markdown(f'<div class="hero-title">Welcome to CanViz, {st.session_state.get("name", "Patient")}</div>', unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#666; font-size:1.15rem; margin-bottom: 40px;'>Your comprehensive medical portal for oncological screening and specialist consultations.</p>", unsafe_allow_html=True)

        st.markdown("#### Quick Actions")
        col1, col2 = st.columns(2, gap="medium")
        
        with col1:
            if st.button("📅 Book Consultation", use_container_width=True):
                st.session_state.page = "appointment"
                st.rerun()
        with col2:
            if st.button("🔬 View Latest Scans", use_container_width=True):
                st.session_state.page = "history"
                st.rerun()

        st.markdown("<br><hr><br>", unsafe_allow_html=True) 
        
        st.subheader("How CanViz Works")
        st.markdown("<br>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""<div class="feature-card"><div class="card-icon">🩺</div><div class="card-title">1. Secure Imaging</div><div class="card-desc">Upload high-resolution biopsy scans securely into our encrypted system. We support standard medical image formats.</div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("""<div class="feature-card"><div class="card-icon">🧠</div><div class="card-title">2. AI Diagnostics</div><div class="card-desc">Our proprietary deep learning algorithm analyzes tissue morphology, extracting Grad-CAM heatmaps to detect anomalies instantly.</div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown("""<div class="feature-card"><div class="card-icon">👨‍⚕️</div><div class="card-title">3. Specialist Review</div><div class="card-desc">Attach your AI results directly to an appointment. Certified oncologists will review the heatmaps to provide clinical advice.</div></div>""", unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("ℹ️ **Disclaimer:** CanViz is an assistive tool for medical professionals. Final diagnosis should always be confirmed by a certified specialist.")


    elif st.session_state.page == "history":
        history.show_history_page()
    
    elif st.session_state.page == "appointment":
        appointment.show_appointment_page()

    elif st.session_state.page == "profile":
        user_profile.show_profile_page()
        
    elif st.session_state.page == "admin":
        admin.show_admin_page()
        
    elif st.session_state.page == "doctor_dashboard": 
        doctor.show_doctor_page()

    # Render Footer (Hidden on Upload Page)
    if st.session_state.page != "upload":
        render_footer()

if __name__ == "__main__":
    show_homepage()