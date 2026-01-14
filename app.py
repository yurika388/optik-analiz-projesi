import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Sınıf ve İsim Odaklı Analiz", layout="wide")

st.title("🎯 İsim/Sınıf Listesi ile Analiz Sistemi")

# --- KULLANICI ARAYÜZÜ ---
col1, col2 = st.columns(2)
with col1:
    uploaded_pdf = st.file_uploader("1. Deneme Sonuç PDF'ini Yükle", type=["pdf"])
with col2:
    # Normalde burası Excel yükleme alanı olacak, şimdilik manuel giriş yapalım
    st.info("Sisteme kayıtlı öğrenci listesi (Simülasyon)")
    student_list_text = st.text_area("Öğrenci İsimlerini Yazın (Her satıra bir isim)", 
                                     value="FEYAS PEKER\nRUKİYE GÖNEN\nAHMET YILMAZ")

def analyze_by_name(pdf_file, target_names):
    """
    Belirli isimleri PDF'te arar ve o ismin bulunduğu bölgedeki konu analizlerini çeker.
    """
    results = []
    target_names = [name.strip().upper() for name in target_names.split('\n') if name.strip()]
    
    with pdfplumber.open(pdf_file) as pdf:
        # Tüm sayfaları tek tek gez
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            # Bu sayfada hedef listeden kimse var mı?
            found_student = None
            for name in target_names:
                if name in text:
                    found_student = name
                    break
            
            if found_student:
                # Öğrenci bulundu! Şimdi o sayfadaki konu analizlerini çekelim.
                # PDF'teki satırları geziyoruz
                lines = text.split('\n')
                
                for line in lines:
                    # KONU ANALİZİ YAKALAMA (Regex ile konu ve puanları bul)
                    # Mantık: Konu Adı (Metin) + Boşluk + Sayısal Veriler (Net, Doğru, Yanlış vs.)
                    # Örnek Satır: "HÜCRE 1010" veya "TÜREV 4 2 2"
                    
                    # Regex: En az 3 harfli bir kelime ile başla, sonunda rakamlar olsun
                    match = re.search(r'([A-ZİĞÜŞÖÇ\s\(\)-]{3,})\s+([0-9\s]+)$', line)
                    
                    if match:
                        konu = match.group(1).strip()
                        rakamlar = match.group(2).strip()
                        
                        # Filtreler (Gereksiz satırları at)
                        if "TYT" in konu or "TOPLAM" in konu or "NET" in konu: continue
                        if len(konu) < 3: continue
                        
                        # Rakamları çözümle (Bu kısım PDF tipine göre değişir)
                        # Eğer 1010 ise karakter say, eğer 4 2 1 ise boşluktan ayır
                        if "0" in rakamlar and "1" in rakamlar and len(rakamlar) > 2 and not " " in rakamlar:
                            # Bu 1010 formatıdır
                            dogru = rakamlar.count('1')
                            yanlis = rakamlar.count('0')
                            toplam = len(rakamlar)
                            tip = "Kodlu"
                        else:
                            # Bu muhtemelen "Soru Doğru Yanlış" formatıdır (Boşluklu sayılar)
                            parts = [int(s) for s in rakamlar.split() if s.isdigit()]
                            if len(parts) >= 2:
                                toplam = parts[0]
                                dogru = parts[1] if len(parts) > 1 else 0
                                yanlis = toplam - dogru
                                tip = "Sayısal"
                            else:
                                continue # Anlamsız veri
                                
                        basari = int((dogru / toplam) * 100) if toplam > 0 else 0
                        
                        results.append({
                            "Sınıf": "12-A (Listeden)", # Burası Excel'den gelecek
                            "Öğrenci": found_student,
                            "Konu": konu,
                            "Doğru": dogru,
                            "Yanlış/Boş": yanlis,
                            "Başarı %": basari
                        })

    return pd.DataFrame(results)

if uploaded_pdf and student_list_text:
    st.write("Analiz ediliyor...")
    df = analyze_by_name(uploaded_pdf, student_list_text)
    
    if not df.empty:
        st.success("Veriler başarıyla çekildi!")
        
        # Sınıf Bazlı Analiz Sekmesi
        tab1, tab2 = st.tabs(["Öğrenci Detay", "Sınıf Genel Analiz"])
        
        with tab1:
            st.dataframe(df)
            
        with tab2:
            st.subheader("Sınıfın En Çok Zorlandığı Konular")
            # Konuya göre grupla ve ortalama başarıyı al
            sinif_analiz = df.groupby("Konu")["Başarı %"].mean().sort_values().head(10)
            st.bar_chart(sinif_analiz)
            
            st.warning("Bu konular için etüt planlanabilir!")
    else:
        st.error("Eşleşen öğrenci veya konu verisi bulunamadı. İsimlerin PDF'teki ile birebir aynı olduğundan emin olun.")
        # Debug için metni göster
        with pdfplumber.open(uploaded_pdf) as pdf:
            st.text("PDF İçeriği (İlk 500 karakter):")
            st.text(pdf.pages[0].extract_text()[:500])
