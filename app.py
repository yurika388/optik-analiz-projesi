import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Kesin Çözüm Analiz", layout="wide")
st.title("🎯 Koordinatlı Karne Analiz Sistemi")
st.markdown("**Hedef:** Sadece öğrenci karnelerini (1. Tip PDF) hatasız okumak.")

uploaded_file = st.file_uploader("Karne PDF'ini Yükle", type=["pdf"])

def clean_subject_name(text):
    """Konu ismindeki gereksiz karakterleri ve TYT/AYT gibi başlıkları temizler."""
    if not text: return ""
    text = text.strip()
    # Başında rakam varsa sil (Örn: "1. HÜCRE" -> "HÜCRE")
    text = re.sub(r'^\d+[\.,\-\s]*', '', text)
    return text

def parse_row_data(line):
    """
    Bir satırın sonundaki veri desenini analiz eder.
    Dönen değer: (Veri Tipi, Veri Sözlüğü, Veri Başlangıç İndeksi)
    """
    line = line.rstrip()
    if not line: return None, None, 0
    
    # DESEN 1: "1 0 1 0" veya "1010" (Binary)
    # Satır sonundaki 0 ve 1'lerden oluşan kümeyi bul.
    # Örn: "HÜCRE BÖLÜNMELERİ                           1 0 1 0"
    binary_match = re.search(r'([01\s]{3,})$', line)
    
    if binary_match:
        raw_data = binary_match.group(1)
        clean_data = raw_data.replace(" ", "")
        # Sadece 0 ve 1'den oluştuğuna emin ol (bazen sayfa numarası karışabilir)
        if all(c in "01" for c in clean_data) and len(clean_data) >= 1:
            return "binary", {
                "binary_string": clean_data,
                "toplam": len(clean_data),
                "dogru": clean_data.count('1'),
                "yanlis": clean_data.count('0')
            }, binary_match.start()

    # DESEN 2: "4 2 2" veya "4 2 2 1,5" (Sayısal: Soru Doğru Yanlış Net)
    # Satır sonunda boşluklarla ayrılmış sayılar kümesi
    numeric_match = re.search(r'(\d+\s+\d+\s+\d+(\s+[\d\.,]+)?)$', line)
    
    if numeric_match:
        raw_data = numeric_match.group(1)
        # Sayıları ayıkla
        nums = re.findall(r'[\d\.,]+', raw_data)
        if len(nums) >= 3:
            try:
                toplam = int(nums[0])
                dogru = int(nums[1])
                yanlis = int(nums[2])
                # Mantık kontrolü: Toplam soru sayısı doğru+yanlıştan küçük olamaz (boş yoksa)
                # ve toplam soru sayısı aşırı büyük olamaz (sayfa nosu karışmasın diye)
                if toplam < 50 and toplam >= (dogru + yanlis): 
                    return "numeric", {
                        "toplam": toplam,
                        "dogru": dogru,
                        "yanlis": yanlis
                    }, numeric_match.start()
            except:
                pass

    return None, None, 0

def extract_exact_data(file):
    results = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # layout=True: Bu parametre satır hizasını korumak için hayati önem taşır!
            text = page.extract_text(layout=True) 
            if not text: continue
            
            lines = text.split('\n')
            
            current_student = "Bilinmeyen Öğrenci"
            
            # --- 1. ADIM: ÖĞRENCİ ADI BULMA (Sayfanın üst %20'sinde) ---
            header_lines = lines[:15] # İlk 15 satıra bak
            for line in header_lines:
                clean_line = line.strip()
                # Genelde İsim satırında "İsim", "Öğrenci", "Sayın" yazar veya sadece isim vardır.
                # Regex ile "Adı Soyadı" formatı yakala (En az iki kelime, hepsi büyük harf)
                if len(clean_line) > 5 and " " in clean_line:
                    # Yasaklı kelimeler (Başlıklar)
                    if any(x in clean_line for x in ["YAPRAK", "MERKEZİ", "TYT", "AYT", "LİSTESİ", "SINAV", "TARİH"]):
                        continue
                    
                    # İsim genellikle büyük harflerle yazılır
                    if clean_line.isupper() and not any(char.isdigit() for char in clean_line):
                        current_student = clean_line
                        break # İsmi bulduk, döngüden çık
            
            # --- 2. ADIM: SATIR SATIR VERİ ANALİZİ ---
            last_valid_index = -1 # Çok satırlı konuları birleştirmek için
            
            for i, line in enumerate(lines):
                # Başlık kısımlarını atla (TYT Türkçe vb.)
                if "TYT" in line or "Toplam" in line or "Genel Ortalama" in line:
                    continue

                type, data, data_start_index = parse_row_data(line)
                
                if type:
                    # Veriyi bulduk! Şimdi konuyu alalım.
                    # Verinin başladığı yerden öncesi konudur.
                    raw_subject = line[:data_start_index].strip()
                    
                    # ÇOK SATIRLI KONU KONTROLÜ
                    # Eğer konu adı boşsa veya çok kısaysa, bir üst satıra bakmalıyız.
                    # Örn: 
                    # Satır 10: "HÜCRE" (Burada puan yok)
                    # Satır 11: "BÖLÜNMELERİ           1010" (Burada puan var)
                    
                    final_subject = raw_subject
                    
                    if len(final_subject) < 3 and i > 0:
                         prev_line = lines[i-1].strip()
                         # Üst satırda sayısal veri yoksa, o satır konu devamıdır.
                         _, prev_data, _ = parse_row_data(prev_line)
                         if not prev_data:
                             final_subject = prev_line + " " + final_subject
                    
                    final_subject = clean_subject_name(final_subject)
                    
                    # Eğer hala konu adı yoksa (tablo kaymışsa) atla
                    if len(final_subject) < 2: continue

                    # Başarı oranı hesabı
                    basari = 0
                    if data["toplam"] > 0:
                        basari = int((data["dogru"] / data["toplam"]) * 100)

                    results.append({
                        "Öğrenci": current_student,
                        "Sayfa": page_num + 1,
                        "Konu": final_subject,
                        "Toplam": data["toplam"],
                        "Doğru": data["dogru"],
                        "Yanlış": data["yanlis"],
                        "Başarı %": basari,
                        "Veri Tipi": type
                    })

    return pd.DataFrame(results)

if uploaded_file:
    st.info("PDF taranıyor... 'Layout Modu' devrede.")
    
    try:
        df = extract_exact_data(uploaded_file)
        
        if not df.empty:
            st.success(f"Analiz Tamamlandı! {len(df)} konu verisi bulundu.")
            
            # --- ANA EKRAN ---
            # Öğrenci Bazlı Gösterim
            students = df["Öğrenci"].unique()
            selected_student = st.selectbox("Öğrenci Seçin", students)
            
            student_df = df[df["Öğrenci"] == selected_student].copy()
            
            # Metrikler
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Soru", student_df["Toplam"].sum())
            c2.metric("Toplam Doğru", student_df["Doğru"].sum())
            c3.metric("Genel Başarı", f"%{int(student_df['Doğru'].sum() / student_df['Toplam'].sum() * 100)}")
            
            st.divider()
            
            col_table, col_chart = st.columns([1.5, 1])
            
            with col_table:
                st.subheader("📝 Konu Karnesi")
                # Görsellik için dataframe'i boyayalım
                st.dataframe(
                    student_df[["Konu", "Toplam", "Doğru", "Yanlış", "Başarı %"]],
                    use_container_width=True,
                    height=500
                )
            
            with col_chart:
                st.subheader("🚨 Alarm Veren Konular")
                # %50 altı başarı olan konular
                weak_topics = student_df[student_df["Başarı %"] < 50].sort_values("Başarı %")
                if not weak_topics.empty:
                    st.error(f"{len(weak_topics)} konuda eksik tespit edildi!")
                    st.bar_chart(weak_topics.set_index("Konu")["Başarı %"])
                else:
                    st.success("Kritik eksik konu bulunamadı!")

            # Excel İndirme
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Tum_Veriler')
            
            st.download_button(
                "📥 Tüm Verileri Excel İndir",
                data=output.getvalue(),
                file_name="detayli_karne_analizi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.error("Veri çekilemedi. PDF formatı çok farklı olabilir.")
            st.write("Debug: PDF'in ilk sayfasının ham görüntüsü:")
            with pdfplumber.open(uploaded_file) as pdf:
                st.text(pdf.pages[0].extract_text(layout=True))

    except Exception as e:
        st.error(f"Kritik Hata: {e}")
