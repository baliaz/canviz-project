import streamlit as st
import requests
from google import genai
from google.genai import types
from supabase import create_client, Client

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def show_floating_interface():
    # 1. 100% FIXED CSS POSITIONING
    st.markdown("""
    <style>
    /* Pin the Native Streamlit Chat Container to Bottom Right */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 40px !important;
        right: 40px !important; /* Lock it to the right edge */
        z-index: 9999 !important;
        width: 280px !important; /* 👈 Lock the invisible box size to match the button */
        display: flex !important;
        justify-content: flex-end !important; /* 👈 Force button to stick to the right */
    }

    /* Target the button */
    div[data-testid="stPopover"] button {
        background: linear-gradient(135deg, #007bff, #00d4ff) !important; /* Vibrant interactive gradient */
        color: #ffffff !important; /* White text */
        border-radius: 50px !important; /* Perfect pill shape */
        padding: 15px 30px !important; /* Much larger padding */
        font-size: 22px !important; /* Makes the text AND the 🤖 logo much bigger */
        font-weight: 800 !important; /* Extra bold text */
        border: 3px solid #ffffff !important; /* Clean white border to make it pop */
        box-shadow: 0 8px 24px rgba(0, 123, 255, 0.5) !important; /* Glowing drop-shadow */
        width: 280px !important; /* Matches wrapper width */
        height: 65px !important; /* Taller button */
        transition: all 0.3s ease !important; /* Smooth animation */
    }

    /* Make the text inside the button larger too */
    div[data-testid="stPopover"] button p {
        font-size: 22px !important;
        margin: 0 !important;
    }

    /* Hover effect - makes it grow and glow more when the mouse touches it */
    div[data-testid="stPopover"] button:hover {
        transform: translateY(-5px) scale(1.05) !important;
        box-shadow: 0 12px 30px rgba(0, 123, 255, 0.8) !important;
        background: linear-gradient(135deg, #0056b3, #00a3cc) !important;
    }

    /* Pin Patient Profile Box right above the popover button */
    .fixed-profile {
        position: fixed;
        bottom: 120px; 
        right: 40px;
        z-index: 9998;
        background-color: white;
        border-radius: 10px;
        padding: 8px 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border: 1px solid #ddd;
        display: flex;
        align-items: center;
        gap: 12px;
        width: 200px;
    }

    /* Pin Disclaimer Box to Bottom Left */
    .fixed-disclaimer {
        position: fixed;
        bottom: 40px;
        left: 40px;
        right: 340px; 
        z-index: 9998;
        background-color: #e5f0ff;
        color: #1e3a8a;
        border-radius: 10px;
        padding: 15px 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        gap: 15px;
        font-family: sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

    # 2. DYNAMIC CONTEXT INJECTION (Fetch User Data from Supabase)
    user_context = "No specific clinical scheduling data available."
    username = st.session_state.get("username")
    
    if username:
        try:
            # Fetch active treatment plans
            plan_res = supabase.table('treatment_plans').select('*').eq('patient_username', username).execute()
            # Fetch upcoming approved appointments
            appt_res = supabase.table('appointments').select('*').eq('username', username).eq('status', 'Approved').execute()
            
            context_str = f"Patient Username: {username}\n"
            if plan_res.data:
                context_str += "Active Treatment Protocols:\n"
                for p in plan_res.data:
                    context_str += f"- {p['treatment_type']} (Duration: {p['duration_months']} months, Frequency: {p['frequency']}, Started: {p['start_date']}). Notes: {p['notes']}\n"
            if appt_res.data:
                context_str += "Upcoming Approved Appointments:\n"
                for a in appt_res.data:
                    context_str += f"- {a['date']} at {a['time']} with Dr. {a['doctor']} (Notes: {a['notes']})\n"
                    
            if plan_res.data or appt_res.data:
                user_context = context_str
        except Exception:
            pass

    # 3. Initialize Gemini AI Client
    if "ai_client" not in st.session_state:
        try:
            st.session_state.ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        except Exception as e:
            st.warning("⚠️ Please check your Gemini API Key.")

    # 4. Initialize Chat Session with Dynamic Context
    if "chat_session" not in st.session_state and "ai_client" in st.session_state:
        st.session_state.chat_session = st.session_state.ai_client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are CanViz AI, a professional medical assistant integrated into the CanViz clinical platform. "
                    "You must ONLY answer questions related to cancer, oncology, tumors, histopathology, "
                    "and the patient's specific treatment schedule or protocols.\n\n"
                    f"Patient Context & Schedule:\n{user_context}\n\n"
                    "CRITICAL RULES:\n"
                    "1. Treat the patient's schedule as shared mental context. If they ask 'when is my next chemo?', answer them directly and naturally using the schedule data.\n"
                    "2. NEVER use phrases like 'Based on your records', 'According to the database', or 'I see here that you have'. Speak seamlessly as if you simply know it.\n"
                    "3. Keep answers short, empathetic, and highly concise."
                )
            )
        )

    # 5. Render Streamlit Chat Popover
    with st.popover("🤖 Ask CanViz AI"):
        st.markdown("### 🔬 CanViz AI Assistant")
        st.caption("Ask me anything about your cancer treatment or schedule.")
        
        chat_container = st.container(height=350)
        
        # Hardcoded initial greeting
        with chat_container.chat_message("assistant"):
            st.markdown("Hello! I am the CanViz Oncology Assistant. Do you have any questions about your treatment plan, schedule, or histology?")

        # Show previous chat history
        if "chat_session" in st.session_state:
            for message in st.session_state.chat_session.get_history():
                role = "assistant" if message.role == "model" else "user"
                with chat_container.chat_message(role):
                    st.markdown(message.parts[0].text)

        # Handle user input
        if prompt := st.chat_input("Ask about your treatment..."):
            with chat_container.chat_message("user"):
                st.markdown(prompt)
            
            with chat_container.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.chat_session.send_message(prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        # 🌟 GRACEFUL ERROR HANDLING FOR 503 SERVER ERRORS 🌟
                        error_msg = str(e)
                        if "503" in error_msg or "UNAVAILABLE" in error_msg:
                            st.warning("⚠️ The AI server is currently experiencing a high volume of global traffic and is temporarily busy. Please wait a few seconds and try sending your message again.")
                        else:
                            st.error(f"Connection failed. Please check your network or API key.")