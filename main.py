import os
import re
import smtplib
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader

# 1. SETUP & CONFIGURATION
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")  # Google App Password
CR_EMAIL = os.getenv("CR_EMAIL", "cr_email@example.com")


# 2. OCR/TEXT EXTRACTION FROM PDF
ROW_PATTERN = re.compile(
    r"(?P<roll_no>\d{6,})\s+(?P<name>[A-Za-z][A-Za-z .'-]*)\s+(?P<marks>Ab|AB|ab|\d+(?:\.\d+)?)"
)

def parse_mark(value: str) -> float:
    """Convert marks to float; treat Ab/blank as 0."""
    if value is None:
        return 0.0
    cleaned = str(value).strip()
    if cleaned == "" or cleaned.lower() == "ab":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_rows_from_text(raw_text: str) -> List[Dict[str, str]]:
    """Extract roll number, name, marks rows from OCR/text content."""
    results: List[Dict[str, str]] = []
    for line in raw_text.splitlines():
        normalized = re.sub(r"\s+", " ", line).strip()
        if not normalized:
            continue
        match = ROW_PATTERN.search(normalized)
        if match:
            results.append(match.groupdict())
    return results


import pdfplumber
import pytesseract
from PIL import Image

def extract_marks_from_pdf(pdf_path):
    print(f"--- Processing: {pdf_path} ---")

    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:

            # Try normal text extraction first
            text = page.extract_text()

            if not text:
                # Fallback → OCR
                img = page.to_image(resolution=300).original
                text = pytesseract.image_to_string(img)

            print("\nOCR/Text Output:\n", text)

            rows = extract_rows_from_text(text)
            all_rows.extend(rows)

    if not all_rows:
        raise ValueError("Still no rows found. OCR couldn't read properly.")

    return all_rows


# 3. THE DETERMINISTIC LOGIC (Software Engineering)
def calculate_internals(m1_list: List[Dict[str, str]], m2_list: List[Dict[str, str]]) -> Tuple[str, pd.DataFrame]:
    df1 = pd.DataFrame(m1_list).rename(columns={"marks": "mid1"})
    df2 = pd.DataFrame(m2_list).rename(columns={"marks": "mid2"})

    # Merge on Roll Number (Keep Name from the first sheet)
    df = pd.merge(df1[["roll_no", "name", "mid1"]], df2[["roll_no", "mid2"]], on="roll_no", how="inner")

    # Data Cleaning: Convert 'Ab' or blanks to 0 for math
    df["mid1"] = df["mid1"].apply(parse_mark)
    df["mid2"] = df["mid2"].apply(parse_mark)

    # Apply Formula: (min * 0.2) + (max * 0.8)
    df["final_internal"] = df.apply(
        lambda r: (min(r["mid1"], r["mid2"]) * 0.2) + (max(r["mid1"], r["mid2"]) * 0.8),
        axis=1,
    )

    output_path = os.path.join("output", "Final_Internal_Marks.xlsx")
    df.to_excel(output_path, index=False)
    return output_path, df


# 4. THE DISPATCHER
def send_email_to_cr(file_path: str) -> None:
    if not EMAIL_USER or not EMAIL_PASS:
        raise ValueError("Missing EMAIL_USER/EMAIL_PASS in environment.")

    msg = MIMEMultipart()
    msg["Subject"] = "Internal Marks Update - Mid 1 & 2"
    msg["From"], msg["To"] = EMAIL_USER, CR_EMAIL

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(file_path)}")
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print("✅ Email successfully sent to the CR.")


# 5. MAIN WORKFLOW
if __name__ == "__main__":
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    mid1_path = "input/mid1.pdf"
    mid2_path = "input/mid2.pdf"

    if not os.path.exists(mid1_path) or not os.path.exists(mid2_path):
        print("Error: Please place mid1.pdf and mid2.pdf in the 'input/' folder.")
    else:
        m1_data = extract_marks_from_pdf(mid1_path)
        m2_data = extract_marks_from_pdf(mid2_path)

        report, merged_df = calculate_internals(m1_data, m2_data)
        print(f"Generated report: {report}")
        print(merged_df.head(10).to_string(index=False))

        # Auto-send email as requested
        send_email_to_cr(report)
