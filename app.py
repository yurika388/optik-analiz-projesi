import streamlit as st
import pandas as pd
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_bytes
import re

st.set_page_config(layout="wide")
st.title("📄 Yaprak PDF Zeka Motoru")

uploaded = st.file_uploader("PDF Yükle", type="pdf")

# ---------- OCR ----------
def ocr_image(img):
    img = np.array(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return pytesseract.image_to_string(gray, lang="tur")

# ---------- Öğrenci ----------
def extract_student(text):
    for line in text.split("\n"):
        l = line.strip()
        if l.isupper() and len(l) > 8 and not any(x in l for x in ["TYT","YAPRAK","LIST","SIRA","TOPLAM"]):
            return l
    return "BULUNAMADI"

# ---------- Konu ----------
def parse_line(line):
    # 10100101 format
    b = re.search(r'([01]{4,})$', line)
    if b:
        code = b.group(1)
        konu = line.replace(code,"").strip()
        return konu, code.count("1"), code.count("0"), len(code)

    # 4 3 1 format
    n = re.search(r'(\d+)\s+(\d+)\s+(\d+)$', line)
    if n:
        t,d,y = n.groups()
        konu = line.replace(n.group(0),"").strip()
        return konu, int(d), int(y), int(t)

    return None

# ---------- Çalıştır ----------
if uploaded:
    with st.spinner("PDF işleniyor..."):
        images = convert_from_bytes(uploaded.read(), dpi=300)

    data = []

    for i, img in enumerate(images):
        text = ocr_image(img)
        student = extract_student(text)

        for line in text.split("\n"):
            parsed = parse_line(line)
            if parsed:
                konu, d, y, t = parsed
                if len(konu) > 3:
                    data.append({
                        "Öğrenci": student,
                        "Sayfa": i+1,
                        "Konu": konu,
                        "Doğru": d,
                        "Yanlış": y,
                        "Toplam": t,
                        "Başarı %": int((d/t)*100) if t>0 else 0
                    })

    df = pd.DataFrame(data)

    if not df.empty:
        st.success(f"{len(df)} adet konu bulundu")
        st.dataframe(df, use_container_width=True)

        st.subheader("📊 Öğrenci Ortalama Başarı")
        st.bar_chart(df.groupby("Öğrenci")["Başarı %"].mean())

    else:
        st.error("Bu PDF’te analiz edilebilir veri bulunamadı.")
