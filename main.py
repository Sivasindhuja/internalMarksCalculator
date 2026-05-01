import os
import smtplib
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

# 1. SETUP
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
CR_EMAIL = os.getenv("CR_EMAIL", "cr_email@example.com")


# 2. PARSE TEXT TABLE
def parse_text_table(text: str) -> List[Dict[str, str]]:
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


# 3. MARK CONVERSION
def parse_mark(value: str) -> float:
    if value is None:
        return 0.0

    cleaned = str(value).strip()

    if cleaned == "" or cleaned.lower() == "ab":
        return 0.0

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# 4. CALCULATION
def calculate_internals(m1_list, m2_list) -> Tuple[str, pd.DataFrame]:
    df1 = pd.DataFrame(m1_list).rename(columns={"marks": "mid1"})
    df2 = pd.DataFrame(m2_list).rename(columns={"marks": "mid2"})

    df = pd.merge(df1[["roll_no", "name", "mid1"]],
                  df2[["roll_no", "mid2"]],
                  on="roll_no",
                  how="inner")

    df["mid1"] = df["mid1"].apply(parse_mark)
    df["mid2"] = df["mid2"].apply(parse_mark)

    df["final_internal"] = df.apply(
        lambda r: (min(r["mid1"], r["mid2"]) * 0.2) +
                  (max(r["mid1"], r["mid2"]) * 0.8),
        axis=1
    )

    output_path = os.path.join("output", "Final_Internal_Marks.xlsx")
    df.to_excel(output_path, index=False)

    return output_path, df


# 5. EMAIL
def send_email_to_cr(file_path: str):
    msg = MIMEMultipart()
    msg["Subject"] = "Internal Marks Update - Mid 1 & 2"
    msg["From"], msg["To"] = EMAIL_USER, CR_EMAIL

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f"attachment; filename={os.path.basename(file_path)}")
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("✅ Email sent successfully.")


# 6. MAIN
if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    # 🔥 Paste your ChatGPT output here
    mid1_text = """
    Roll Number | Name      | Marks
    --------------------------------
    2371092     | Sindhu    | 12
    2371093     | Sowmya    | 13
    2371094     | soumya.D  | 14
    2371095     | Soumya.V  | 15
    2371096     | Spandana  | 16
    """

    mid2_text = """
    Roll Number | Name      | Marks
    --------------------------------
    2371092     | Sindhu    | 14
    2371093     | Sowmya    | 12
    2371094     | soumya.D  | 15
    2371095     | Soumya.V  | 18
    2371096     | Spandana  | Ab
    """

    # Parse
    m1_data = parse_text_table(mid1_text)
    m2_data = parse_text_table(mid2_text)

    # Calculate
    report, df = calculate_internals(m1_data, m2_data)

    print("\nGenerated Report:")
    print(df.to_string(index=False))

    # Send email
    send_email_to_cr(report)