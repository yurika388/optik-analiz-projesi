import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# Sayfa Ayarları
st.set_page_config(page_title="Dershane Konu Analizi", layout="wide")

st.title("📊 Dershane Sınav Analiz Sistemi")
st.markdown("""
Bu sistem, **Yaprak Kurs Merkezi** ve benzeri formatlardaki karne PDF'lerini analiz eder.
Öğrenci bazlı konu eksiklerini tespit etmek için geliştirilmiştir.
""")

uploaded_file = st.file_uploader("PDF Dosyasını Yükleyin", type=["pdf"])

def extract_student_and_questions(file):
    """
    PDF'ten öğrenci adı, sınıfı ve konu bazlı doğru/yanlış verilerini çıkarır.
    """
    results = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            
            # Mevcut öğrenci bilgileri
            current_student = None
            current_class = "Belirtilmemiş"
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # --- 1. ÖĞRENCİ ADI TESPİTİ ---
                # İsim genelde büyük harflerle yazılır ve belirli anahtar kelimelerden sonra gelir
                # Örnek: "Sayın VELİ", "Öğrenci: AHMET" veya direkt satırda isim
                
                # Basit ve etkili bir isim yakalama mantığı:
                # Satırda "İsim", "Öğrenci" varsa veya satır sadece büyük harfli isimden oluşuyorsa
                if ("İsim" in line or "Öğrenci" in line) and i+1 < len(lines):
                     # Alt satıra bak
                     candidate = lines[i+1].strip()
                     if len(candidate) > 5 and not any(k in candidate for k in ["TYT", "NET", "PUAN"]):
                         current_student = candidate
                elif line.isupper() and len(line) > 6 and " " in line:
                    # Satır tamamen büyük harf ve içinde boşluk varsa (AD SOYAD gibi)
                    # Ancak ders isimleri veya başlıklar olmamalı
                    yasakli_kelimeler = ["TYT", "AYT", "LİSTESİ", "SINAVI", "MERKEZİ", "TÜRKÇE", "MATEMATİK", "SOSYAL", "FEN"]
                    if not any(y in line for y in yasakli_kelimeler):
                        current_student = line

                # --- 2. SINIF BİLGİSİ ---
                if "Sınıf" in line or "SINIF" in line:
                    class_match = re.search(r'(Sınıf|SINIF)[:\s]*(\d+\s*[A-Za-z]?)', line)
                    if class_match:
                        current_class = class_match.group(2)
                
                # --- 3. KONU VE VERİ ANALİZİ ---
                # Sadece öğrenci bulunduktan sonra veri aramaya başla
                # (Ancak bazı PDF'lerde isim en altta olabilir, o yüzden bu şartı esnetiyoruz)
                
                # Potansiyel konu adı (uzun metin)
                # Başlıkları ele (TYT, TOPLAM vb.)
                if len(line) > 5 and not any(x in line for x in ["TYT", "SOSYAL", "MATEMATİK", "FEN", "TOPLAM", "GENEL", "NET", "ORTALAMA"]):
                    
                    match = None
                    match_type = None
                    
                    # Regex Desenleri
                    # Format 1: "Konu Adı 4 3 1 75" (Soru - Doğru - Yanlış - Net/Puan)
                    pattern1 = r'(.+?)\s+(\d+)\s+(\d+)\s+(\d+)(\s+[\d\.,]+)?$'
                    
                    # Format 2: "Konu Adı 1010" (Binary Sistem)
                    pattern2 = r'(.+?)\s+([01\s]{3,})$'
                    
                    # Önce Sayısal (3 2 1) dene
                    m1 = re.match(pattern1, line)
                    if m1:
                        # Sayısal mantık kontrolü: Toplam = Doğru + Yanlış mı?
                        try:
                            toplam = int(m1.group(2))
                            dogru = int(m1.group(3))
                            yanlis = int(m1.group(4))
                            if toplam >= dogru + yanlis: # Mantıklı veri
                                match = m1
                                match_type = "numeric"
                        except: pass

                    # Eğer sayısal değilse Binary (1010) dene
                    if not match:
                        m2 = re.match(pattern2, line)
                        if m2:
                            binary_part = m2.group(2).replace(" ", "")
                            if all(c in "01" for c in binary_part):
                                match = m2
                                match_type = "binary"
                    
                    # EŞLEŞME VARSA KAYDET
                    if match:
                        if match_type == "numeric":
                            konu = match.group(1).strip()
                            toplam = int(match.group(2))
                            dogru = int(match.group(3))
                            yanlis = int(match.group(4))
                            basari = int((dogru/toplam)*100) if toplam > 0 else 0
                            
                        elif match_type == "binary":
                            konu = match.group(1).strip()
                            binary_str = match.group(2).replace(" ", "")
                            toplam = len(binary_str)
                            dogru = binary_str.count('1')
                            yanlis = binary_str.count('0')
                            basari = int((dogru/toplam)*100) if toplam > 0 else 0

                        # Konu adı temizliği (Gereksiz kısa veya anlamsız şeyleri at)
                        if len(konu) > 2:
                            results.append({
                                "Öğrenci": current_student if current_student else "İsimsiz Öğrenci",
                                "Sınıf": current_class,
                                "Konu": konu,
                                "Toplam Soru": toplam,
                                "Doğru": dogru,
                                "Yanlış": yanlis,
                                "Başarı %": basari
                            })
                
                i += 1
    
    return pd.DataFrame(results)

if uploaded_file:
    st.write("📂 PDF analiz ediliyor... Lütfen bekleyin.")
    
    with st.spinner("Veriler taranıyor..."):
        try:
            df = extract_student_and_questions(uploaded_file)
            
            if not df.empty:
                st.success(f"✅ İşlem Başarılı! Toplam {len(df)} veri satırı çekildi.")
                
                # Öğrenci Filtresi (Varsa)
                ogrenciler = df["Öğrenci"].unique()
                selected_student = st.selectbox("Öğrenci Seçin:", ["Tümü"] + list(ogrenciler))
                
                if selected_student != "Tümü":
                    display_df = df[df["Öğrenci"] == selected_student]
                else:
                    display_df = df

                # Veri Gösterimi
                st.subheader("📋 Analiz Tablosu")
                st.dataframe(display_df, use_container_width=True)
                
                # İstatistikler
                col1, col2, col3 = st.columns(3)
                col1.metric("Ortalama Başarı", f"%{display_df['Başarı %'].mean():.1f}")
                col2.metric("Toplam Soru", display_df['Toplam Soru'].sum())
                col3.metric("Toplam Doğru", display_df['Doğru'].sum())
                
                # Grafik
                st.subheader("📊 Konu Başarı Grafiği (En Zayıf 15 Konu)")
                chart_data = display_df.groupby("Konu")["Başarı %"].mean().sort_values().head(15)
                st.bar_chart(chart_data)
                
                # Excel İndirme Butonu
                st.subheader("💾 Raporu İndir")
                
                # Excel formatı için buffer kullanımı
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Analiz')
                processed_data = output.getvalue()
                
                st.download_button(
                    label="📥 Excel Olarak İndir (.xlsx)",
                    data=processed_data,
                    file_name='dershane_analiz_raporu.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
            else:
                st.error("Veri bulunamadı. PDF formatı desteklenmiyor olabilir.")
                st.warning("Debug: PDF metnini kontrol etmek için aşağıya bakabilirsiniz.")
                with pdfplumber.open(uploaded_file) as pdf:
                    st.text(pdf.pages[0].extract_text())
                    
        except Exception as e:
            st.error(f"Bir hata oluştu: {e}")
            
else:
    st.info("Sol üstteki menüden bir PDF yükleyerek başlayın.")
