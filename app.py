import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Dershane Analiz - Tam Çözüm", layout="wide")

st.title("🎯 Nokta Atışı Analiz Sistemi")
st.info("Bu sistem, yüklenen karne PDF'indeki 'HÜCRE 1010' gibi gizli desenleri tarar.")

uploaded_file = st.file_uploader("Karne PDF'ini Yükle (Örn: 3D TYT Karne)", type=["pdf"])

def extract_data_aggressive(file):
    student_data = []
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            # Sayfayı metin olarak al (layout=True ile boşlukları koruruz)
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if not text: continue
            
            lines = text.split('\n')
            
            # 1. ÖĞRENCİ ADI BULMA (Agresif Yöntem)
            student_name = "Bilinmeyen Öğrenci"
            class_name = "Belirsiz"
            
            for line in lines:
                # Genelde İsim: veya Sayın: ile başlar ya da büyük harfli isim satırıdır
                if "Sayın" in line or "İsim" in line or "Öğrenci" in line:
                    # İsim satırını temizle
                    clean_line = line.replace("Sayın", "").replace("İsim", "").replace("Öğrenci", "").strip()
                    # Eğer satırda harf varsa isimdir
                    if len(clean_line) > 5:
                        student_name = clean_line
                        break
            
            # Eğer yukarıdaki çalışmazsa, PDF'in en üstündeki büyük harfli satır isim olabilir
            if student_name == "Bilinmeyen Öğrenci":
                 for line in lines[:5]: # İlk 5 satıra bak
                     if len(line) > 5 and not "YAPRAK" in line and not "TYT" in line:
                         student_name = line
                         break

            # 2. KONU VE PERFORMANS BULMA (REGEX)
            # Desen: Türkçe karakterli kelimeler + boşluk + sadece 0 ve 1'lerden oluşan kod
            # Örnek: "HÜCRE 1010" veya "SÖZCÜKTE ANLAM 1110"
            
            # Regex Açıklaması:
            # ([A-ZİĞÜŞÖÇ\s\(\)-]{3,}) -> En az 3 harfli BÜYÜK HARFLİ konu adı (HÜCRE vb.)
            # \s+ -> Boşluk
            # ([01\s]{2,}) -> En az 2 haneli 1 ve 0 serisi (1010 gibi)
            pattern = re.compile(r"([A-ZİĞÜŞÖÇ\s\(\)-]{3,})\s+([01\s]{2,})")
            
            for line in lines:
                match = pattern.search(line)
                if match:
                    konu = match.group(1).strip()
                    kod = match.group(2).replace(" ", "") # Aradaki boşlukları sil "1 0 1" -> "101"
                    
                    # Hatalı yakalamaları ele (Sadece rakam olanları veya çok uzun metinleri at)
                    if len(konu) > 40 or len(kod) < 1: continue
                    if "TYT" in konu or "TOPLAM" in konu: continue # Başlıkları at
                    
                    # Veriyi Analiz Et
                    dogru = kod.count('1')
                    yanlis_bos = kod.count('0')
                    toplam = len(kod)
                    basari = int((dogru/toplam)*100) if toplam > 0 else 0
                    
                    student_data.append({
                        "Öğrenci": student_name,
                        "Konu": konu,
                        "Analiz Kodu": kod, # Debug için bunu görelim
                        "Soru": toplam,
                        "Doğru": dogru,
                        "Yanlış/Boş": yanlis_bos,
                        "Başarı %": basari
                    })
                    
    return pd.DataFrame(student_data)

if uploaded_file:
    st.write("Dosya işleniyor...")
    df = extract_data_aggressive(uploaded_file)
    
    if not df.empty:
        st.success(f"Analiz Başarılı! {len(df)} adet konu verisi çekildi.")
        
        # Öğrenci Seçimi (Birden fazla karne varsa)
        selected_student = st.selectbox("Öğrenci Seçin:", df["Öğrenci"].unique())
        student_df = df[df["Öğrenci"] == selected_student]
        
        # Üst Metrikler
        col1, col2, col3 = st.columns(3)
        toplam_d = student_df["Doğru"].sum()
        toplam_y = student_df["Yanlış/Boş"].sum()
        ort_basari = student_df["Başarı %"].mean()
        
        col1.metric("Toplam Doğru", toplam_d)
        col2.metric("Toplam Yanlış/Boş", toplam_y)
        col3.metric("Ortalama Konu Başarısı", f"%{ort_basari:.1f}")
        
        st.divider()
        
        # 1. KRİTİK KONULAR TABLOSU
        st.subheader("🔴 Alarm Veren Konular (Başarı < %50)")
        kritik = student_df[student_df["Başarı %"] < 50]
        if not kritik.empty:
            st.dataframe(kritik[["Konu", "Doğru", "Yanlış/Boş", "Başarı %"]], use_container_width=True)
        else:
            st.success("Kritik seviyede konu yok, tebrikler!")
            
        # 2. DETAYLI LİSTE
        with st.expander("Tüm Konu Analizini Gör"):
            st.dataframe(student_df)
            
    else:
        st.error("Veri çekilemedi! PDF'in metin formatı beklenen 'KONU 1010' yapısında olmayabilir.")
        # Debug Modu: Kullanıcıya PDF'in metnini gösterelim ki ne gördüğümüzü anlasın
        with pdfplumber.open(uploaded_file) as pdf:
            st.text("SİSTEMİN GÖRDÜĞÜ METİN (İlk Sayfa):")
            st.code(pdf.pages[0].extract_text())
