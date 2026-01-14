import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Dershane Analiz - Tablo Modu", layout="wide")

st.title("🛡️ Tablo Tabanlı Kesin Çözüm")
st.info("Bu modül, PDF içindeki tabloları doğrudan analiz eder. Metin kaymalarından etkilenmez.")

uploaded_file = st.file_uploader("PDF Dosyasını Yükle", type=["pdf"])

def clean_text(text):
    """Metindeki gereksiz boşlukları ve satır atlamaları temizler."""
    if text:
        return str(text).replace('\n', ' ').strip()
    return ""

def is_topic_row(row):
    """
    Bir satırın 'Konu Analiz Satırı' olup olmadığını anlamaya çalışır.
    Mantık: İlk sütun metin olmalı, diğer sütunlarda rakamlar (1010 veya net sayısı) olmalı.
    """
    # Satır boşsa veya çok kısaysa atla
    clean_row = [x for x in row if x is not None and str(x).strip() != ""]
    if len(clean_row) < 2:
        return False
    
    first_cell = clean_text(clean_row[0])
    last_cell = clean_text(clean_row[-1])
    
    # Konu adı çok kısa olamaz (Örn: "A", "B" şıkkı değildir)
    if len(first_cell) < 3: 
        return False
        
    # İlk hücrede "TOPLAM", "NET", "SIRA" gibi başlıklar varsa atla
    forbidden_words = ["TOPLAM", "GENEL", "SIRA", "ADI", "SOYADI", "TYT", "NET"]
    if any(word in first_cell.upper() for word in forbidden_words):
        return False

    # Son hücrede veya ikinci hücrede rakam var mı? (10101 veya 3 1 2)
    # Rakam barındırıyor mu kontrolü
    has_digits = any(char.isdigit() for char in last_cell)
    
    return has_digits

def extract_tables_logic(file):
    all_data = []
    debug_tables = [] # Ne gördüğümüzü anlamak için
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Sayfadaki tüm tabloları çıkar
            tables = page.extract_tables()
            
            for table in tables:
                if not table: continue
                
                # Tablodaki her satıra bak
                for row in table:
                    # Satır boş mu?
                    if not any(row): continue
                    
                    # Bu satır bir konu analizi mi?
                    if is_topic_row(row):
                        # Veriyi temizle
                        konu = clean_text(row[0]) # Genelde ilk sütun konudur
                        
                        # Verinin geri kalanı (Performans)
                        # Bazen sütunlar kayar, geri kalan tüm dolu hücreleri birleştirelim
                        diger_hucreler = [clean_text(x) for x in row[1:] if x is not None]
                        veri_yigini = " ".join(diger_hucreler)
                        
                        all_data.append({
                            "Sayfa": page_num + 1,
                            "Konu Olasılığı": konu,
                            "Veri": veri_yigini
                        })
                
                # Debug için tabloyu kaydedelim (İlk 5 satır)
                debug_tables.append(pd.DataFrame(table).head(3))

    return pd.DataFrame(all_data), debug_tables

if uploaded_file:
    st.write("Tablolar taranıyor...")
    
    try:
        df_results, debug_info = extract_tables_logic(uploaded_file)
        
        if not df_results.empty:
            st.success(f"Toplam {len(df_results)} adet veri satırı bulundu!")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("📊 Çıkarılan Ham Veriler")
                st.dataframe(df_results, use_container_width=True)
                
            with col2:
                st.subheader("🔍 Nasıl Yorumlamalı?")
                st.markdown("""
                Sistem PDF'teki tablo satırlarını çıkardı.
                - **Konu Olasılığı:** Satırın başındaki yazı.
                - **Veri:** Yanındaki rakamlar (1010 veya doğru/yanlış sayıları).
                
                Eğer burada verileri doğru görüyorsan, artık bunları sayıya döküp grafiğe çevirmek çocuk oyuncağı.
                """)
                
        else:
            st.error("Tablo yapısı tespit edilemedi veya veriler beklenen formatta değil.")
            st.warning("Aşağıdaki 'Sistemin Gördüğü' kısmına bakarak PDF'in nasıl okunduğunu kontrol et.")
            
        with st.expander("🛠️ Geliştirici Modu: Sistemin Gördüğü Tablolar (Debug)"):
            st.write("PDF Plumber bu dosyada şunları görüyor:")
            for i, tbl in enumerate(debug_info):
                st.write(f"Tablo {i+1}:")
                st.dataframe(tbl)
                
    except Exception as e:
        st.error(f"Hata oluştu: {e}")
