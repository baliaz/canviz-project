from flask import Flask, jsonify, request
import smtplib
from email.message import EmailMessage
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from supabase import create_client, Client

# 🌟 YOUR SUPABASE CLOUD CREDENTIALS 🌟
SUPABASE_URL = "https://brzkfyyirszktcfqoowc.supabase.co" # e.g., "https://brzkfyyirszktcfqoowc.supabase.co/rest/v1/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyemtmeXlpcnN6a3RjZnFvb3djIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTM4NDAxOSwiZXhwIjoyMDk0OTYwMDE5fQ.MPbeYpeA7SVmJ8sFPv3nY-BdlbnWcN5mlgGcvebeZm0" # e.g., "eyJhbG..."

# Initialize the Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.json.sort_keys = False 

@app.route('/')
def home():
    return "CanViz Supabase Flask Backend is running!"

# --- REGISTER ENDPOINT ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    email = data.get('email')
    role = data.get('role', 'user')

    if not username or not password or not email:
        return jsonify({"message": "Missing fields"}), 400

    try:
        # Check if username already exists
        existing_user = supabase.table('users').select('*').eq('username', username).execute()
        if len(existing_user.data) > 0:
            return jsonify({"message": "Username already exists"}), 409
            
        # Check if email already exists
        existing_email = supabase.table('users').select('*').eq('email', email).execute()
        if len(existing_email.data) > 0:
            return jsonify({"message": "Email already registered"}), 409

        hashed_password = generate_password_hash(password)
        
        # Insert into Supabase
        supabase.table('users').insert({
            "username": username,
            "password": hashed_password,
            "name": name,
            "email": email,
            "role": role
        }).execute()
        
        return jsonify({"message": "Registration successful"}), 201
    except Exception as e:
        # 🌟 THE FIX: Print the EXACT Supabase error to your terminal!
        print(f"SUPABASE REGISTRATION ERROR: {str(e)}")
        return jsonify({"message": "Database rejected the registration."}), 409

# 🌟 ADMIN / DOCTOR / PATIENT LOGIN ROUTE
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        # Fetch user from Supabase
        response = supabase.table('users').select('*').eq('email', email).execute()
        
        if len(response.data) > 0:
            user = response.data[0]
            if check_password_hash(user['password'], password):
                return jsonify({
                    "message": "Login successful",
                    "username": user['username'],
                    "name": user['name'],
                    "email": user['email'],
                    "role": user['role']
                }), 200
            
        return jsonify({"message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"message": f"Server error: {e}"}), 500

# --- UPDATE PROFILE ENDPOINT (For Normal Users) ---
@app.route('/update_profile', methods=['PUT'])
def update_profile():
    data = request.get_json()
    update_type = data.get('update_type')
    current_username = data.get('username') 

    try:
        response = supabase.table('users').select('*').eq('username', current_username).execute()
        if len(response.data) == 0:
            return jsonify({"message": "User not found"}), 404
        user = response.data[0]

        # SCENARIO A: Update Password
        if update_type == "password":
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            
            db_password = str(user.get('password', ''))
            
            # 🌟 SMART CHECKER: Detect if the DB password is encrypted (hashed) or plain text
            is_hashed = db_password.startswith('scrypt:') or db_password.startswith('pbkdf2:')
            is_correct = False

            if is_hashed:
                # If it's a hash, use Werkzeug to verify it
                is_correct = check_password_hash(db_password, current_password)
            else:
                # If it's plain text, check it (and ignore accidental spaces)
                is_correct = (db_password.strip() == current_password.strip())

            if not is_correct:
                return jsonify({"message": "Incorrect current password"}), 401 
                
            # 🌟 SMART SAVER: Hash the new password ONLY if the old one was hashed
            # This prevents you from locking yourself out of your account!
            final_new_password = new_password
            if is_hashed:
                final_new_password = generate_password_hash(new_password)

            supabase.table('users').update({"password": final_new_password}).eq('username', current_username).execute()

        # SCENARIO B: Update Username
        elif update_type == "profile":
            new_username = data.get('new_username')
            # Check if taken
            check = supabase.table('users').select('*').eq('username', new_username).execute()
            if len(check.data) > 0 and new_username != current_username:
                return jsonify({"message": "Username already taken"}), 409
                
            supabase.table('users').update({"username": new_username}).eq('username', current_username).execute()

        return jsonify({"message": "Update successful"}), 200
        
    except Exception as e:
        print(f"Update Profile Error: {e}") # Prints to your VS Code terminal for debugging
        return jsonify({"message": "Database error"}), 500

# 🌟 --- ADMIN SUPERPOWER ENDPOINT --- 🌟
@app.route('/admin_update_user', methods=['PUT'])
def admin_update_user():
    data = request.get_json()
    target_username = data.get('target_username') 
    new_username = data.get('new_username')
    new_name = data.get('new_name')
    new_email = data.get('new_email')
    new_password = data.get('new_password')

    try:
        if new_username != target_username:
            check = supabase.table('users').select('*').eq('username', new_username).execute()
            if len(check.data) > 0:
                return jsonify({"message": "Username already taken"}), 409

        supabase.table('users').update({
            "username": new_username,
            "name": new_name,
            "email": new_email,
            "password": new_password
        }).eq('username', target_username).execute()
        
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Database error"}), 500

# --- DELETE ACCOUNT ENDPOINT ---
@app.route('/delete_account', methods=['DELETE'])
def delete_account():
    username = request.get_json().get('username')
    if not username: return jsonify({"message": "Missing username"}), 400

    try:
        supabase.table('users').delete().eq('username', username).execute()
        return jsonify({"message": "Account deleted successfully"}), 200
    except:
        return jsonify({"message": "Error deleting account"}), 500


# 🌟 --- PATIENT: BOOK APPOINTMENT --- 🌟
@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    doctor = data.get('doctor')
    date = data.get('date')
    time = data.get('time')

    try:
        # 1. Save to Supabase (No need to ALTER TABLE anymore!)
        supabase.table('appointments').insert({
            "username": data.get('username'),
            "email": email,
            "name": name,
            "date": date,
            "time": time,
            "doctor": doctor,
            "notes": data.get('notes'),
            "status": "Pending",
            "attached_scan": data.get('attached_scan', 'None')
        }).execute()

        # 2. SEND THE REAL EMAIL
        SENDER_EMAIL = "ejeniris11@gmail.com" 
        APP_PASSWORD = "oydqwruzatcpmdhn" 

        if email and "@" in email: 
            msg = EmailMessage()
            msg['Subject'] = 'CanViz Medical: Appointment Confirmation'
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            msg.set_content(f"""
        Dear {name},

Your consultation with {doctor} has been successfully scheduled.

    Details:
    Doctor: {doctor}
    Date: {date}
    Time: {time}
            
If you attached an AI scan, the doctor will review your Grad-CAM heatmaps prior to your visit. If not please bring the pdf file with you to your appointment.

    Thank you,
    The CanViz Medical Team
    """)
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(SENDER_EMAIL, APP_PASSWORD)
                smtp.send_message(msg)

        return jsonify({"message": "Appointment booked and email sent successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# 🌟 --- PATIENT: FETCH PERSONAL SCAN HISTORY --- 🌟
@app.route('/get_patient_history', methods=['POST'])
def get_patient_history():
    username = request.get_json().get('username')
    try:
        # History is now in the unified Supabase cloud!
        response = supabase.table('history').select('scan_id, date, result, confidence').eq('username', username).order('date', desc=True).execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify([]), 200
    
# --- SEND PDF REPORT VIA EMAIL ENDPOINT ---
@app.route('/email_report', methods=['POST'])
def email_report():
    patient_email = request.form.get('email')
    patient_name = request.form.get('name')
    scan_id = request.form.get('scan_id')
    pdf_file = request.files.get('pdf_file') 

    if not patient_email or not pdf_file:
        return jsonify({"message": "Missing email or file attachment"}), 400

    try:
        SENDER_EMAIL = "ejeniris11@gmail.com" 
        APP_PASSWORD = "oydqwruzatcpmdhn" 

        msg = EmailMessage()
        msg['Subject'] = f'CanViz Diagnostic Report - {scan_id}'
        msg['From'] = SENDER_EMAIL
        msg['To'] = patient_email
        msg.set_content(f"""
Hello {patient_name},

Please find attached your requested CanViz AI Diagnostic Report for Scan ID: {scan_id}.

This document contains your clinical imagery, Grad-CAM heatmaps, and the AI confidence assessment. 
Please share this document with your certified oncologist for final diagnosis.

Thank you,
The CanViz Medical Team
        """)

        pdf_data = pdf_file.read()
        msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename=pdf_file.filename)

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()

        return jsonify({"message": "Email sent successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Failed to send email"}), 500
    
# 🌟 --- ADMIN: REGISTER DOCTOR ENDPOINT --- 🌟
@app.route('/admin/register_doctor', methods=['POST'])
def register_doctor():
    data = request.get_json()
    try:
        hashed_password = generate_password_hash(data.get('password'))
        supabase.table('users').insert({
            "username": data.get('username'),
            "password": hashed_password,
            "name": data.get('name'),
            "email": data.get('email'),
            "role": 'doctor'
        }).execute()
        return jsonify({"message": "Doctor registered successfully"}), 201
    except Exception:
        return jsonify({"message": "Username or Email already exists"}), 409

# 🌟 --- DOCTOR: FETCH APPOINTMENTS ENDPOINT --- 🌟
@app.route('/doctor/appointments', methods=['POST'])
def get_doctor_appointments():
    doctor_name = request.get_json().get('doctor_name') 
    try:
        response = supabase.table('appointments').select('*').eq('doctor', doctor_name).execute()
        appt_list = [{
            "id": row['id'], 
            "patient_username": row['username'], 
            "date": row['date'],
            "time": row['time'],
            "notes": row['notes']
        } for row in response.data]
        return jsonify(appt_list), 200
    except:
        return jsonify([]), 500

# 🌟 --- PATIENT: FETCH AVAILABLE TIMES --- 🌟
@app.route('/get_available_times', methods=['POST'])
def get_available_times():
    data = request.get_json()
    doctor = data.get('doctor_name')
    date_str = data.get('date')
    
    try:
        blocked_res = supabase.table('blocked_schedule').select('time').eq('doctor', doctor).eq('date', date_str).execute()
        blocked_list = [row['time'] for row in blocked_res.data]
        
        booked_res = supabase.table('appointments').select('time').eq('doctor', doctor).eq('date', date_str).execute()
        booked_list = [row['time'] for row in booked_res.data]
        
        all_times = [
            "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
            "01:00 PM", "01:30 PM", "02:00 PM", "02:30 PM", "03:00 PM", "03:30 PM", "04:00 PM"
        ]
        
        free_times = [t for t in all_times if t not in blocked_list and t not in booked_list]
        
        req_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        current_time = datetime.now().time()
        
        final_times = []
        for t_str in free_times:
            t_obj = datetime.strptime(t_str, "%I:%M %p").time()
            if req_date == today:
                if t_obj > current_time:
                    final_times.append(t_str)
            else:
                final_times.append(t_str)
        
        return jsonify({"available_times": final_times}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# -------------------------------------------------------------
# 🌐 ENDPOINT: FETCH ALL SYSTEM USERS (For Master User List)
# -------------------------------------------------------------
@app.route('/users', methods=['GET'])
def get_all_users():
    """
    Fetches all registered accounts from the Supabase auth/profiles system 
    so doctors can browse and assign users to their roster.
    """
    try:
        response = supabase.table('users').select('name', 'username', 'email', 'role').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------------------
# 📅 ENDPOINT: GET BLOCKED SCHEDULE TIMES
# -------------------------------------------------------------
@app.route('/doctor/get_blocked_times', methods=['POST'])
def get_blocked_times():
    """
    Retrieves all time slots a specific doctor has blocked out for a given date.
    """
    data = request.get_json()
    doctor_name = data.get("doctor_name")
    date_str = data.get("date")

    if not doctor_name or not date_str:
        return jsonify({"error": "Missing doctor_name or date"}), 400

    try:
        # Query your existing schedule or blocked_slots table
        response = supabase.table('blocked_schedules') \
            .select('blocked_time') \
            .eq('doctor_name', doctor_name) \
            .eq('date', date_str) \
            .execute()
        
        # Flatten array of objects into a simple list of strings
        blocked_times = [row['blocked_time'] for row in response.data]
        return jsonify({"blocked_times": blocked_times}), 200
    except Exception as e:
        # If table doesn't exist yet, return empty array gracefully
        return jsonify({"blocked_times": []}), 200


# -------------------------------------------------------------
# 💾 ENDPOINT: BLOCK OUT CLINIC SCHEDULE TIMES
# -------------------------------------------------------------
@app.route('/doctor/block_times', methods=['POST'])
def block_times():
    """
    Overwrites the blocked time slots for a doctor on a specific calendar date.
    """
    data = request.get_json()
    doctor_name = data.get("doctor_name")
    date_str = data.get("date")
    times = data.get("times", []) # List of strings e.g., ["09:00 AM", "10:30 AM"]

    if not doctor_name or not date_str:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # 1. Clear out previous blocks for this doctor on this specific day
        supabase.table('blocked_schedules') \
            .delete() \
            .eq('doctor_name', doctor_name) \
            .eq('date', date_str) \
            .execute()

        # 2. Insert new blocked records if any are checked
        if times:
            insert_data = [
                {"doctor_name": doctor_name, "date": date_str, "blocked_time": t} 
                for t in times
            ]
            supabase.table('blocked_schedules').insert(insert_data).execute()

        return jsonify({"status": "success", "message": "Schedule updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)