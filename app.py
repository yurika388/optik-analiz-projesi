import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Dershane Analiz Pro", layout="wide")

st.title("🎓 Dershane Gelişmiş Analiz Sistemi")
st.markdown("PDF dosyanızı yükleyin. Sistem, **Sıralı Listeleri** ve **Öğrenci Karnelerini** otomatik ayırt edip analiz eder.")

uploaded_file = st.file_uploader("PDF Dosyasını Buraya Sürükleyin", type=["pdf"])

def parse_pdf_content(file):
    """
    PDF içindeki hem 'Sıralı Liste'yi hem de 'Konu Analiz' tablolarını yakalar.
    """
    all_tables = []
    student_reports = []
    class_list_data = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Sayfadaki tüm tabloları çek
            tables = page.extract_tables()
            
            for table in tables:
                # Tablo boşsa atla
                if not table: continue
                
                # --- FORMAT 1: SINIF LİSTESİ ANALİZİ ---
                # Genelde "SIRA NO", "ADI SOYADI", "TYT" gibi başlıklar içerir
                df_temp = pd.DataFrame(table)
                # İlk satırları birleştirip içinde anahtar kelime var mı bak
                header_text = " ".join([str(x) for x in df_temp.head(3).values.flatten()]).upper()
                
                if "ADI SOYADI" in header_text and ("TYT" in header_text or "NET" in header_text):
                    # Bu bir sınıf listesidir, temizleyip alalım
                    # Başlık satırını bulmaya çalış
                    start_row = 0
                    for i, row in enumerate(table):
                        row_str = " ".join([str(x) for x in row if x]).upper()
                        if "ADI SOYADI" in row_str:
                            start_row = i + 1 # Başlıktan sonraki satır veridir
                            break
                    
                    if start_row < len(table):
                        for row in table[start_row:]:
                            # Satırın dolu olduğundan ve bir öğrenci adı içerdiğinden emin ol
                            # Genelde Ad Soyad 2. veya 3. sütundadır
                            clean_row = [x for x in row if x is not None]
                            if len(clean_row) > 3: # En azından Sıra, Ad, Net olmalı
                                class_list_data.append(clean_row)

                # --- FORMAT 2: KONU ANALİZ KARNESİ ---
                # Genelde satırlarda "Cümle Anlamı", "Hücre" gibi konular ve yanlarında rakamlar olur
                # Bu kısım biraz daha "sezgisel" olmalı
                for row in table:
                    # Satırdaki verileri temizle
                    row_clean = [str(x).replace('\n', ' ').strip() for x in row if x]
                    
                    if len(row_clean) >= 2:
                        konu_adi = row_clean[0]
                        # Konu adı genelde metindir, diğerleri sayıdır
                        # Örn: ["Cümle Anlamı", "4", "3", "1", "%75"]
                        
                        # Basit bir filtre: Konu adı çok kısa değilse ve yanındaki sütunlar sayı içeriyorsa
                        if len(konu_adi) > 3 and any(char.isdigit() for char in "".join(row_clean[1:])):
                            # Sayısal verileri ayıkla
                            try:
                                # Sayı bulucu regex
                                numbers = re.findall(r'\d+', " ".join(row_clean[1:]))
                                if len(numbers) >= 2: # En az Toplam ve Doğru sayısı olmalı
                                    toplam = int(numbers[0])
                                    dogru = int(numbers[1])
                                    
                                    # Başarı oranı hesabı (Eğer % sütunu yoksa biz hesaplayalım)
                                    basari = 0
                                    if toplam > 0:
                                        basari = int((dogru / toplam) * 100)
                                    
                                    durum = "🟢 İyi"
                                    if basari < 50: durum = "🔴 Kritik"
                                    elif basari < 70: durum = "🟡 Orta"
                                    
                                    student_reports.append({
                                        "Sayfa": page_num + 1,
                                        "Konu": konu_adi,
                                        "Toplam Soru": toplam,
                                        "Doğru": dogru,
                                        "Başarı %": basari,
                                        "Durum": durum
                                    })
                            except:
                                pass # Sayısal çevrim hatası olursa geç

    return class_list_data, pd.DataFrame(student_reports)

if uploaded_file:
    with st.spinner('PDF taranıyor, tablolar ayrıştırılıyor...'):
        try:
            class_data, topic_df = parse_pdf_content(uploaded_file)
            
            st.success("İşlem Tamamlandı!")
            
            tab1, tab2 = st.tabs(["📋 Sınıf Sıralama Listesi", "📊 Detaylı Konu Analizi"])
            
            with tab1:
                st.subheader("Sınıf Genel Listesi (Bulunan Veriler)")
                if class_data:
                    # Ham veriyi göster (Sütun isimlerini dinamik yapıyoruz çünkü her PDF farklıdır)
                    df_class = pd.DataFrame(class_data)
                    st.dataframe(df_class)
                    st.info("Not: Bu tablo PDF'den ham olarak çekilmiştir. İlk sütunlar genelde Sıra ve İsimdir.")
                else:
                    st.warning("Bu dosyada toplu sıralama listesi tespit edilemedi veya formatı farklı.")

            with tab2:
                st.subheader("Konu Bazlı Eksik Analizi")
                if not topic_df.empty:
                    # Filtreleme
                    durum_filter = st.multiselect("Filtrele (Durum)", ["🔴 Kritik", "🟡 Orta", "🟢 İyi"], default=["🔴 Kritik"])
                    
                    if durum_filter:
                        filtered_df = topic_df[topic_df["Durum"].isin(durum_filter)]
                    else:
                        filtered_df = topic_df

                    st.dataframe(filtered_df, use_container_width=True)
                    
                    # Grafik
                    st.bar_chart(filtered_df.set_index("Konu")["Başarı %"])
                    
                    st.markdown("### 📢 Öğretmen İçin Özet")
                    kritik_konular = topic_df[topic_df["Durum"] == "🔴 Kritik"]["Konu"].value_counts().head(5)
                    st.write("Sınıf genelinde en çok hata yapılan 5 konu:")
                    for konu, sayi in kritik_konular.items():
                        st.error(f"- {konu} (Bu konu {sayi} kez kritik seviyede çıkmış)")
                else:
                    st.warning("Detaylı konu analizi bulunamadı. PDF sadece sıralı liste olabilir mi?")
                    
        except Exception as e:
            st.error(f"Bir hata oluştu: {e}")
