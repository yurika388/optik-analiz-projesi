import streamlit as st
import pandas as pd
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_bytes
import re

st.set_page_config(layout="wide")
st.title("🎯 Yaprak PDF Zeka Motoru")

uploaded = st.file_uploader("PDF Yükle", type="pdf")

# ---------------- OCR ----------------

def ocr_page(img):
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    return pytesseract.image_to_string(gray, lang="tur")

# ---------------- Öğrenci Yakalama ----------------

def find_student(text):
    for line in text.split("\n"):
        if line.isupper() and len(line)>10 and not any(x in line for x in ["TYT","YAPRAK","LIST","SIRA","TOPLAM"]):
            return line.strip()
    return "BULUNAMADI"

# ---------------- Konu Satırı Yakalama ----------------

def parse_topic(line):
    # 101001 format
    bin_match = re.search(r'([01]{4,})$', line)
    if bin_match:
        code = bin_match.group(1)
        konu = line.replace(code,"").strip()
        return konu, code.count("1"), code.count("0"), len(code)

    # 4 3 1 format
    num_match = re.search(r'(\d+)\s+(\d+)\s+(\d+)$', line)
    if num_match:
        t,d,y = num_match.groups()
        konu = line.replace(num_match.group(0),"").strip()
        return konu, int(d), int(y), int(t)

    return None

# ---------------- PDF ANALİZ ----------------

if uploaded:
    images = convert_from_bytes(uploaded.read(), dpi=300)

    results = []

    for i, img in enumerate(images):
        text = ocr_page(img)
        student = find_student(text)

        for line in text.split("\n"):
            parsed = parse_topic(line)
            if parsed:
                konu, d, y, t = parsed
                if len(konu)>3:
                    results.append({
                        "Öğrenci": student,
                        "Sayfa": i+1,
                        "Konu": konu,
                        "Doğru": d,
                        "Yanlış": y,
                        "Toplam": t,
                        "Başarı %": int(d/t*100) if t>0 else 0
                    })

    df = pd.DataFrame(results)

    if not df.empty:
        st.success(f"{len(df)} adet konu yakalandı")
        st.dataframe(df)

        st.subheader("📊 Öğrenci Başarıları")
        st.bar_chart(df.groupby("Öğrenci")["Başarı %"].mean())
    else:
        st.error("Bu PDF’te veri bulunamadı")
