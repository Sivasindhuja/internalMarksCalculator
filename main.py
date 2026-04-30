import os
import json
import pandas as pd
import smtplib
import time
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# 1. SETUP & CONFIGURATION
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") # Google App Password
CR_EMAIL = "cr_email@example.com"

# Using Florence-2 for high-precision document extraction
MODEL_ID = "microsoft/Florence-2-large"
client = InferenceClient(token=HF_TOKEN)

# 2. THE AI EXTRACTION COMPONENT
def extract_marks_from_image(image_path):
    print(f"--- Processing: {os.path.basename(image_path)} ---")
    
    # Prompting Florence-2 for OCR with Table focus
    # The prompt format <OCR_WITH_REGION> is specific to Florence-2
    prompt = "<OCR_WITH_REGION> Extract the table columns: Roll Number, Name, Marks."
    
    with open(image_path, "rb") as f:
        image_data = f.read()

    # Call the serverless API
    response = client.post(data=image_data, model=MODEL_ID, headers={"x-wait-for-model": "true"})
    
    # Florence-2 returns text; we need to parse it into a structured format
    # In a real scenario, you might use a regex or a secondary cheap LLM call 
    # to convert the raw OCR text into the list below.
    print("AI Extraction Complete.")
    
    # MOCK DATA STRUCTURE based on what Florence-2 typically extracts
    # For your actual run, the AI response text would be parsed here.
    return [
        {"roll_no": "21VC1A0501", "name": "Siva", "marks": "18"},
        {"roll_no": "21VC1A0502", "name": "Anusha", "marks": "Ab"},
        {"roll_no": "21VC1A0503", "name": "Rahul", "marks": "15"}
    ]

# 3. THE DETERMINISTIC LOGIC (Software Engineering)
def calculate_internals(m1_list, m2_list):
    df1 = pd.DataFrame(m1_list).rename(columns={'marks': 'mid1'})
    df2 = pd.DataFrame(m2_list).rename(columns={'marks': 'mid2'})
    
    # Merge on Roll Number (Keep Name from the first sheet)
    df = pd.merge(df1, df2[['roll_no', 'mid2']], on='roll_no')

    # Data Cleaning: Convert 'Ab' or blanks to 0 for math
    for col in ['mid1', 'mid2']:
        df[col] = pd.to_numeric(df[col].replace('Ab', 0), errors='coerce').fillna(0)

    # Apply Formula: (min * 0.2) + (max * 0.8)
    df['final_internal'] = df.apply(
        lambda r: (min(r['mid1'], r['mid2']) * 0.2) + (max(r['mid1'], r['mid2']) * 0.8), 
        axis=1
    )
    
    output_path = os.path.join("output", "Final_Internal_Marks.xlsx")
    df.to_excel(output_path, index=False)
    return output_path

# 4. THE DISPATCHER
def send_email_to_cr(file_path):
    msg = MIMEMultipart()
    msg['Subject'] = "Internal Marks Update - Mid 1 & 2"
    msg['From'], msg['To'] = EMAIL_USER, CR_EMAIL

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(file_path)}")
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("✅ Email successfully sent to the CR.")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# 5. MAIN WORKFLOW
if __name__ == "__main__":
    # Ensure folders exist
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    mid1_path = "input/mid1.png"
    mid2_path = "input/mid2.png"

    if not os.path.exists(mid1_path) or not os.path.exists(mid2_path):
        print("Error: Please place mid1.png and mid2.png in the 'input/' folder.")
    else:
        # Step 1: Extraction
        m1_data = extract_marks_from_image(mid1_path)
        m2_data = extract_marks_from_image(mid2_path)

        # Step 2: Calculation
        report = calculate_internals(m1_data, m2_data)

        # Step 3: Human-in-the-Loop
        print(f"\n[ACTION]: Open {report} and verify the data.")
        choice = input("Everything looks good? Send email to CR? (y/n): ")

        if choice.lower() == 'y':
            send_email_to_cr(report)
        else:
            print("Process stopped. You can manually edit the Excel and send it later.")