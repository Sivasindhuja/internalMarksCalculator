#imports
import os
import smtplib
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

# Load env
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
CR_EMAIL = os.getenv("CR_EMAIL")


#clean the text table and convert to list of dicts.

def parse_text_table(text):
    lines = text.strip().split("\n")
    data = []

    for line in lines:
        if "Roll Number" in line or "---" in line:
            continue

        parts = [p.strip() for p in line.split("|") if p.strip()]

        if len(parts) == 3:
            roll_no, name, marks = parts
            data.append({
                "roll_no": roll_no,
                "name": name,
                "marks": marks
            })

    return data

#handling absent marks and non-numeric values by converting them to 0. 
def parse_mark(value):
    if not value or str(value).lower() == "ab":
        return 0
    try:
        return float(value)
    except:
        return 0

#calculate final internals based on the given formula and save to excel.
def calculate(m1, m2):
    df1 = pd.DataFrame(m1).rename(columns={"marks": "mid1"})
    df2 = pd.DataFrame(m2).rename(columns={"marks": "mid2"})

    df = pd.merge(
        df1[["roll_no", "name", "mid1"]],
        df2[["roll_no", "mid2"]],
        on="roll_no",
        how="outer"
    )

    df["name"] = df["name"].fillna("Unknown")
    df["mid1"] = df["mid1"].apply(parse_mark)
    df["mid2"] = df["mid2"].apply(parse_mark)

    df["final_internal"] = df.apply(
        lambda r: (min(r["mid1"], r["mid2"]) * 0.2) +
                  (max(r["mid1"], r["mid2"]) * 0.8),
        axis=1
    )

    df["final_internal"] = df["final_internal"].round(2)
    df = df.sort_values(by="roll_no")

    file_path = "Final_Internal_Marks.xlsx"
    df.to_excel(file_path, index=False)

    return df, file_path

#send an email to the CR with the generated report as an attachment.
def send_email(file_path):
    msg = MIMEMultipart()
    msg["Subject"] = "Internal Marks Report"
    msg["From"] = EMAIL_USER
    msg["To"] = CR_EMAIL

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={file_path}")
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)


#UI with Streamlit

st.title("Internal Marks Processor")

mid1 = st.text_area("Paste Mid 1 Data")
mid2 = st.text_area("Paste Mid 2 Data")

#  Generate Report
if st.button("Generate Report"):
    m1 = parse_text_table(mid1)
    m2 = parse_text_table(mid2)

    df, file_path = calculate(m1, m2)

    st.session_state["df"] = df
    st.session_state["file_path"] = file_path


#  Show result (persistent)
if "df" in st.session_state:
    df = st.session_state["df"]
    file_path = st.session_state["file_path"]

    st.success("Report Generated!")
    st.dataframe(df)

   
    with open(file_path, "rb") as f:
        st.download_button(
            "Download Excel",
            f,
            file_name=file_path
        )

    #  Email button (separate)
    if st.button("Send Email"):
        send_email(file_path)
        st.success("✅ Email Sent!")