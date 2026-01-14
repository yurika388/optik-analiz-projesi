import streamlit as st
import pdfplumber
import pandas as pd
import re
from collections import defaultdict

st.set_page_config(page_title="Dershane Konu Analizi", layout="wide")
st.title("📊 Dershane Sınav Analiz Sistemi")
st.markdown("Öğrenci bazlı konu analizi - PDF'ten veri çekme aracı")

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
            current_class = None
            in_subject_section = False
            current_subject = None
            
            # Ders isimleri
            subjects = ["TYT Türkçe", "TYT Sosyal", "TYT Matematik", "TYT Fen", 
                       "Türkçe", "Sosyal", "Matematik", "Fen", 
                       "Tarih-1", "Coğrafya-1", "Felsefe", "Din Kül. ve Ahl. Bil.",
                       "Fizik", "Kimya", "Biyoloji", "Matematik-1", "Geometri"]
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 1. ÖĞRENCİ ADI TESPİTİ
                # "Öğrenci" kelimesi içeren satırlardan sonra gelen satır ad olabilir
                if "Öğrenci" in line and i+1 < len(lines):
                    student_line = lines[i+1].strip()
                    if student_line and len(student_line) > 2:
                        # Numara ve sınıf kontrolü
                        if not any(char.isdigit() for char in student_line[:5]):
                            current_student = student_line
                            # Sınıf bilgisi için bir sonraki satırları kontrol et
                            for j in range(i+1, min(i+5, len(lines))):
                                if lines[j].strip().isdigit() or re.match(r'\d+[A-Za-z]?', lines[j].strip()):
                                    current_class = lines[j].strip()
                                    break
                
                # 2. SINIF BİLGİSİ
                if "Sınıf:" in line or "SINIF:" in line:
                    class_match = re.search(r'SINIF:\s*(\d+[A-Z]?)', line)
                    if class_match:
                        current_class = class_match.group(1)
                
                # 3. KONU BAZLI ANALİZ SATIRLARI
                # "1010" formatı veya "3 2 1" formatı arayalım
                # Örnek: "SÖZCÜKTE VE SÖZ ÖBEKLERİNDE ANLAM 3 2 0 67"
                # Örnek: "HÜCRE 1 0 1 0"
                
                # Potansiyel konu adı (uzun metin)
                if len(line) > 10 and not any(x in line for x in ["TYT", "SOSYAL", "MATEMATİK", "FEN", "TOPLAM", "GENEL"]):
                    # "3 2 1" veya "1010" formatı var mı?
                    # Format 1: "Konu 4 3 1 75"
                    pattern1 = r'(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$'
                    # Format 2: "Konu 1 0 1 0"
                    pattern2 = r'(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$'
                    # Format 3: "Konu 1010"
                    pattern3 = r'(.+?)\s+([01]{3,})$'
                    
                    match = None
                    match_type = None
                    
                    # Önce pattern1 ve pattern2'yi dene
                    for pattern in [pattern1, pattern2]:
                        m = re.match(pattern, line)
                        if m:
                            match = m
                            match_type = "numeric"
                            break
                    
                    # Pattern3'ü dene
                    if not match:
                        m = re.match(pattern3, line)
                        if m:
                            match = m
                            match_type = "binary"
                    
                    if match and current_student:
                        if match_type == "numeric":
                            konu = match.group(1).strip()
                            # Grupları al (sayılar)
                            numbers = [int(x) for x in match.groups()[1:] if x.isdigit()]
                            if len(numbers) >= 3:
                                toplam = numbers[0]
                                dogru = numbers[1]
                                yanlis = numbers[2] if len(numbers) > 2 else toplam - dogru
                                basari = int((dogru/toplam)*100) if toplam > 0 else 0
                                
                                results.append({
                                    "Öğrenci": current_student,
                                    "Sınıf": current_class,
                                    "Sayfa": page_num + 1,
                                    "Konu": konu,
                                    "Toplam Soru": toplam,
                                    "Doğru": dogru,
                                    "Yanlış": yanlis,
                                    "Başarı %": basari,
                                    "Ham Satır": line[:50] + "..."
                                })
                        
                        elif match_type == "binary":
                            konu = match.group(1).strip()
                            binary_str = match.group(2).strip()
                            # Boşlukları kaldır
                            binary_str = binary_str.replace(" ", "")
                            
                            if binary_str and all(c in "01" for c in binary_str):
                                toplam = len(binary_str)
                                dogru = binary_str.count('1')
                                yanlis = binary_str.count('0')
                                basari = int((dogru/toplam)*100) if toplam > 0 else 0
                                
                                results.append({
                                    "Öğrenci": current_student,
                                    "Sınıf": current_class,
                                    "Sayfa": page_num + 1,
                                    "Konu": konu,
                                    "Toplam Soru": toplam,
                                    "Doğru": dogru,
                                    "Yanlış": yanlis,
                                    "Başarı %": basari,
                                    "Ham Satır": line[:50] + "..."
                                })
                
                i += 1
    
    return pd.DataFrame(results)

def parse_binary_pattern(line):
    """1010 formatını parse eder"""
    # Örnek: "SÖZCÜKTE VE SÖZ ÖBEKLERİNDE ANLAM 1 0 1 0"
    # veya "HÜCRE 1010"
    
    # 1. "1 0 1 0" formatı
    parts = line.strip().split()
    if len(parts) >= 5:
        try:
            # Son 4 karakter sayı mı?
            last_four = parts[-4:]
            if all(x.isdigit() for x in last_four):
                konu = " ".join(parts[:-4])
                binary_str = "".join(last_four)
                if all(c in "01" for c in binary_str):
                    return {
                        "konu": konu,
                        "binary": binary_str,
                        "toplam": len(binary_str),
                        "dogru": binary_str.count('1'),
                        "yanlis": binary_str.count('0')
                    }
        except:
            pass
    
    # 2. "1010" formatı (bitişik)
    match = re.search(r'(.+?)\s+([01]{3,})$', line)
    if match:
        konu = match.group(1).strip()
        binary_str = match.group(2).strip().replace(" ", "")
        if all(c in "01" for c in binary_str):
            return {
                "konu": konu,
                "binary": binary_str,
                "toplam": len(binary_str),
                "dogru": binary_str.count('1'),
                "yanlis": binary_str.count('0')
            }
    
    return None

if uploaded_file:
    st.write("📂 PDF analiz ediliyor...")
    
    with st.spinner("Veriler çıkarılıyor..."):
        df = extract_student_and_questions(uploaded_file)
    
    if not df.empty:
        st.success(f"✅ {len(df)} adet konu analizi bulundu!")
        st.write(f"📊 Toplam {df['Öğrenci'].nunique()} öğrenci tespit edildi")
        
        # Veriyi göster
        st.subheader("📋 Çıkarılan Veriler")
        st.dataframe(df)
        
        # Filtreleme
        st.subheader("🔍 Filtrele")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_student = st.selectbox(
                "Öğrenci Seçin",
                options=["Tümü"] + list(df["Öğrenci"].unique())
            )
        
        with col2:
            min_success = st.slider("Minimum Başarı %", 0, 100, 0)
        
        # Filtre uygula
        filtered_df = df.copy()
        if selected_student != "Tümü":
            filtered_df = filtered_df[filtered_df["Öğrenci"] == selected_student]
        
        filtered_df = filtered_df[filtered_df["Başarı %"] >= min_success]
        
        if not filtered_df.empty:
            st.write(f"Filtrelenmiş {len(filtered_df)} kayıt")
            st.dataframe(filtered_df)
            
            # İstatistikler
            st.subheader("📈 İstatistikler")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_success = filtered_df["Başarı %"].mean()
                st.metric("Ortalama Başarı %", f"{avg_success:.1f}%")
            
            with col2:
                total_questions = filtered_df["Toplam Soru"].sum()
                st.metric("Toplam Soru Sayısı", total_questions)
            
            with col3:
                total_correct = filtered_df["Doğru"].sum()
                st.metric("Toplam Doğru Sayısı", total_correct)
            
            # Grafik
            st.subheader("📊 Konu Bazlı Başarı Grafiği")
            if selected_student != "Tümü":
                chart_df = filtered_df.sort_values("Başarı %", ascending=False).head(15)
                st.bar_chart(chart_df.set_index("Konu")["Başarı %"])
            else:
                # Tüm öğrenciler için en zor konular
                hard_topics = df.groupby("Konu")["Başarı %"].mean().sort_values().head(10)
                st.bar_chart(hard_topics)
        
        # Excel'e indirme
        st.subheader("💾 İndirme")
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 CSV olarak indir",
            data=csv,
            file_name="dershane_analiz.csv",
            mime="text/csv"
        )
        
    else:
        st.error("❌ Hiç veri bulunamadı! PDF formatı farklı olabilir.")
        st.info("""
        **Sorun Giderme Önerileri:**
        1. PDF'in metin içerdiğinden emin olun (tarama/resim değil)
        2. Farklı bir PDF yüklemeyi deneyin
        3. PDF formatı çok karmaşıksa, OCR uygulanmış bir PDF kullanın
        """)
        
        # Debug için ham metin göster
        with st.expander("🔧 Debug: Ham PDF Metni"):
            with pdfplumber.open(uploaded_file) as pdf:
                sample_text = pdf.pages[0].extract_text()
                st.text_area("İlk sayfanın ham metni:", sample_text, height=300)
else:
    st.info("👈 Lütfen bir PDF dosyası yükleyin")
    st.markdown("""
    **Beklenen PDF Formatı:**
    - Yaprak Kurs Merkezi sınav sonuçları
    - Öğrenci adı ve konu analizi içeren sayfalar
    - "1010" veya "3 2 1" formatında doğru/yanlış verileri
    """)
