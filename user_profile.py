import streamlit as st
import requests
import time
import random
import smtplib
from email.message import EmailMessage

# 🌟 NEW: Supabase Import (Replaced sqlite3)
from supabase import create_client, Client

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FLASK_URL = "http://127.0.0.1:5000"

# --- HELPER: DELETE ACCOUNT ---
def delete_account_api():
    try:
        payload = {"username": st.session_state.username}
        response = requests.delete(f"{FLASK_URL}/delete_account", json=payload)
        return response.status_code == 200
    except:
        return False

# --- HELPER: SEND MFA EMAIL ---
def send_mfa_email(target_email, user_name, otp_code):
    try:
        SENDER_EMAIL = "ejeniris11@gmail.com" 
        APP_PASSWORD = "oydqwruzatcpmdhn" 

        msg = EmailMessage()
        msg['Subject'] = 'CanViz Security: Password Reset Verification Code'
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email
        msg.set_content(f"""
Hello {user_name},

A request to change your password was just made on your CanViz account.

Your 6-digit verification code is: {otp_code}

If you did not request this change, please ignore this email and your password will remain safe.

Thank you,
CanViz Security Team
        """)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        return False

# --- MAIN PROFILE PAGE ---
def show_profile_page():
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.switch_page("main.py")
        return

    # 🌟 THE FIX: Initialize ALL MFA & Preference states INSIDE the function 
    # so Streamlit never forgets them when routing through homepage.py!
    if "email_notifications" not in st.session_state:
        st.session_state.email_notifications = True
    if "mfa_stage" not in st.session_state:
        st.session_state.mfa_stage = 1
    if "generated_otp" not in st.session_state:
        st.session_state.generated_otp = ""
    if "pending_password_payload" not in st.session_state:
        st.session_state.pending_password_payload = None

    st.markdown("""
    <style>
    .modern-header {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #1E293B, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        text-align: center;
    }
    .modern-sub {
        color: #64748B;
        font-size: 1.05rem;
        font-weight: 400;
        margin-bottom: 30px;
        text-align: center;
    }
    .avatar-wrapper {
        display: flex;
        justify-content: center;
        margin-bottom: 15px; 
    }
    .avatar-circle {
        background: linear-gradient(135deg, #E2E8F0, #F1F5F9);
        height: 120px;
        width: 120px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 60px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border: 4px solid white;
    }
    .section-title {
        color: #0F172A;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 15px;
    }
    div[data-testid="metric-container"] {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        text-align: center;
    }
    .otp-box input {
        text-align: center;
        font-size: 1.5rem;
        letter-spacing: 5px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="modern-header">User Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="modern-sub">Manage your account details and security preferences</div>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="avatar-wrapper">
            <div class="avatar-circle">👤</div>
        </div>
    """, unsafe_allow_html=True)

    current_user = st.session_state.get("username", "")
    current_name = st.session_state.get("name", "")
    current_email = st.session_state.get("email", "")

    total_scans = 0
    try:
        res = supabase.table('history').select('*', count='exact').eq('username', current_user).execute()
        total_scans = res.count if res.count is not None else 0
    except Exception:
        total_scans = 0

    m1, m2, m3, m4 = st.columns([1, 2, 2, 1])
    with m2:
        st.metric("Total Scans Analyzed", str(total_scans), help="This will sync with your uploaded scans.")
    with m3:
        st.metric("Account Status", "Active", delta="Verified", delta_color="normal")
    
    st.markdown("<br>", unsafe_allow_html=True)

    tab_profile, tab_security, tab_prefs = st.tabs(["📄 General Info", "🔒 Security & Password", "⚙️ Preferences"])

    # ---------------------------------------------------------
    # TAB 1: ACCOUNT INFORMATION
    # ---------------------------------------------------------
    with tab_profile:
        with st.container(border=True):
            st.markdown('<div class="section-title">Personal Details</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Email Address", value=current_email, disabled=True, help="Email cannot be changed.")
            with col2:
                new_name = st.text_input("Full Name", value=current_name, disabled=True, help="Full Name cannot be changed.")
                
            new_username = st.text_input("Username", value=current_user)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Save Profile Changes", type="primary"):
                payload = {
                    "username": current_user,
                    "new_username": new_username,
                    "update_type": "profile" 
                }
                
                try:
                    with st.spinner("Updating profile..."):
                        response = requests.put(f"{FLASK_URL}/update_profile", json=payload)
                        
                    if response.status_code == 200:
                        st.session_state.username = new_username
                        st.toast("Profile Updated Successfully!", icon="✅")
                        time.sleep(1) 
                        st.rerun()
                    elif response.status_code == 409:
                        st.error("That username is already taken.")
                    else:
                        st.error("Failed to update profile.")
                        
                except Exception as e: 
                    st.error(f"System Error: {e}") 

    # ---------------------------------------------------------
    # TAB 2: SECURITY & PASSWORD (NOW WITH MFA!)
    # ---------------------------------------------------------
    with tab_security:
        with st.container(border=True):
            st.markdown('<div class="section-title">Update Password (MFA Secured)</div>', unsafe_allow_html=True)
            
            # 🌟 STAGE 1: Standard Password Entry
            if st.session_state.mfa_stage == 1:
                with st.form("change_password_form"):
                    current_password = st.text_input("Current Password", type="password", help="Required to verify your identity.")
                    st.markdown("---")
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        new_password = st.text_input("New Password", type="password")
                    with col4:
                        confirm_pass = st.text_input("Confirm New Password", type="password")

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("Request Password Change", type="primary"):
                        if not current_password:
                            st.error("⚠️ You must enter your current password to make changes.")
                        elif not new_password:
                            st.error("⚠️ Please enter a new password.")
                        elif new_password != confirm_pass:
                            st.error("⚠️ New passwords do not match!")
                        elif len(new_password) < 6:
                            st.error("⚠️ New password must be at least 6 characters.")
                        else:
                            # Verify the current password against Flask BEFORE sending email
                            verify_payload = {
                                "email": current_email,
                                "password": current_password
                            }
                            try:
                                with st.spinner("Authenticating credentials..."):
                                    auth_check = requests.post(f"{FLASK_URL}/login", json=verify_payload)
                                    
                                if auth_check.status_code == 200:
                                    # Credentials match! Generate OTP and send email
                                    with st.spinner("Generating security token and sending email..."):
                                        otp = str(random.randint(100000, 999999))
                                        email_sent = send_mfa_email(current_email, current_name, otp)
                                        
                                        if email_sent:
                                            st.session_state.generated_otp = otp
                                            st.session_state.pending_password_payload = {
                                                "username": current_user,
                                                "current_password": current_password,
                                                "new_password": new_password,
                                                "update_type": "password"
                                            }
                                            st.session_state.mfa_stage = 2
                                            st.rerun()
                                        else:
                                            st.error("Failed to dispatch security email. Please try again.")
                                else:
                                    st.error("🛑 Incorrect current password. Access denied.")
                            except Exception as e:
                                st.error(f"Connection Error: {e}")
                                
            # 🌟 STAGE 2: MFA Verification
            elif st.session_state.mfa_stage == 2:
                st.info(f"📩 A 6-digit security code has been sent to **{current_email}**. Please enter it below to confirm your identity.")
                
                with st.form("mfa_otp_form"):
                    st.markdown("<div class='otp-box'>", unsafe_allow_html=True)
                    entered_otp = st.text_input("Enter 6-Digit Code", max_chars=6)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("✅ Verify & Change Password", type="primary"):
                        if entered_otp.strip() == st.session_state.generated_otp:
                            try:
                                with st.spinner("Verification successful. Updating database..."):
                                    response = requests.put(f"{FLASK_URL}/update_profile", json=st.session_state.pending_password_payload)
                                    
                                if response.status_code == 200:
                                    st.session_state.mfa_stage = 1
                                    st.session_state.generated_otp = ""
                                    st.session_state.pending_password_payload = None
                                    st.success("🔒 Multi-Factor Authentication complete! Password successfully updated.")
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Failed to update database. Server rejected the new password.")
                            except Exception as e:
                                st.error(f"Connection Error: {e}")
                        else:
                            st.error("❌ Invalid Security Code. Please try again.")
                
                if st.button("Cancel & Return", type="secondary"):
                    st.session_state.mfa_stage = 1
                    st.session_state.generated_otp = ""
                    st.session_state.pending_password_payload = None
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="section-title" style="color: #DC3545;">⚠️ Danger Zone</div>', unsafe_allow_html=True)
            st.write("Once you delete your account, there is no going back. Please be certain.")
            
            if "confirm_delete" not in st.session_state:
                st.session_state.confirm_delete = False

            if not st.session_state.confirm_delete:
                if st.button("🗑️ Delete Account", type="secondary"):
                    st.session_state.confirm_delete = True
                    st.rerun()
            else:
                st.warning("🚨 **Are you sure? All your medical history will be permanently erased.**")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ YES, Delete my account", type="primary", use_container_width=True):
                        with st.spinner("Deleting account..."):
                            if delete_account_api():
                                st.session_state.logged_in = False
                                st.session_state.username = ""
                                st.session_state.name = ""
                                st.session_state.email = ""
                                st.session_state.confirm_delete = False
                                st.success("Account deleted. Redirecting...")
                                time.sleep(1.5) 
                                st.switch_page("main.py")
                            else:
                                st.error("Could not delete account. Server error.")
                with col_no:
                    if st.button("❌ NO, Keep my account", use_container_width=True):
                        st.session_state.confirm_delete = False
                        st.rerun()

    # ---------------------------------------------------------
    # TAB 3: PREFERENCES (FULLY SYNCED WITH SUPABASE)
    # ---------------------------------------------------------
    with tab_prefs:
        with st.container(border=True):
            st.markdown('<div class="section-title">Communication Settings</div>', unsafe_allow_html=True)
            st.write("Control how the CanViz system contacts you regarding your appointments.")
            
            try:
                # 🌟 SUPABASE: Get user email preference
                pref_res = supabase.table('preferences').select('email_notif').eq('username', st.session_state.username).execute()
                if len(pref_res.data) > 0:
                    current_pref = bool(pref_res.data[0]['email_notif'])
                else:
                    current_pref = True
            except:
                current_pref = True
            
            with st.form("preferences_form"):
                # Use the Database value (current_pref) for the toggle's starting position!
                email_choice = st.toggle("📧 Send me Appointment Confirmations via Email", value=current_pref)
                
                if st.form_submit_button("💾 Save Preferences", type="primary"):
                    
                    db_value = 1 if email_choice else 0
                    # 🌟 SUPABASE: Save preference using upsert (insert or update)
                    supabase.table('preferences').upsert({
                        "username": st.session_state.username, 
                        "email_notif": db_value
                    }).execute()
                    
                    if email_choice:
                        st.success("✅ Preferences permanently saved! Emails are now ON.")
                    else:
                        st.warning("🔕 Preferences permanently saved! Emails are now OFF.")