import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# Sayfa Ayarları
st.set_page_config(page_title="Dershane Analiz Sistemi", layout="wide")

st.title("🎓 Optik Analiz ve Rehberlik Sistemi")
st.markdown("""
Bu sistem, dershane deneme PDF'lerini analiz ederek öğrenci ve sınıf bazlı **konu eksiklerini** tespit eder.
PDF dosyasını aşağıya yükleyin ve sihrin gerçekleşmesini izleyin.
""")

# Yan Menü
st.sidebar.header("Yönetim Paneli")
uploaded_file = st.sidebar.file_uploader("Deneme Sonuç PDF'ini Yükle", type=["pdf"])

def analiz_et(file):
    """
    PDF içindeki karmaşık veriyi (Konu Adı ve 1010 Başarı sırası) ayıklar.
    """
    data = []
    
    with pdfplumber.open(file) as pdf:
        all_text = ""
        for page in pdf.pages:
            all_text += page.extract_text() + "\n"
            
    # Satır satır işleme
    lines = all_text.split('\n')
    
    current_student = "Öğrenci Tespit Edilemedi"
    
    # Basit bir Regex ile öğrenci ismini yakalamaya çalışalım (Örnek: İsim FEYAS PEKER)
    # Not: Gerçek PDF'lerde bu format değişebilir, bu bir prototiptir.
    
    for line in lines:
        # Konu ve Başarı Analizi (Örnek: "HÜCRE 1010")
        # Metin içinde peş peşe 0 ve 1'lerden oluşan en az 3 haneli bir ifade arıyoruz.
        match = re.search(r'([A-Za-zİıĞğÜüŞşÖöÇç\s]+?)\s+([01]{3,})', line)
        
        if match:
            konu_adi = match.group(1).strip()
            binary_code = match.group(2) # "1010" gibi
            
            # Gereksiz kısa metinleri ele
            if len(konu_adi) < 3: continue
            
            dogru = binary_code.count('1')
            yanlis_bos = binary_code.count('0')
            toplam = len(binary_code)
            basari_yuzdesi = int((dogru / toplam) * 100)
            
            durum = "🟢 İyi"
            if basari_yuzdesi < 50:
                durum = "🔴 Kritik (Tekrar Gerekli)"
            elif basari_yuzdesi < 75:
                durum = "🟡 Orta"
                
            data.append({
                "Konu": konu_adi,
                "Soru Sayısı": toplam,
                "Doğru": dogru,
                "Başarı %": basari_yuzdesi,
                "Durum": durum
            })
            
    return pd.DataFrame(data)

if uploaded_file is not None:
    st.success("Dosya başarıyla yüklendi! Analiz başlıyor...")
    
    try:
        df = analiz_et(uploaded_file)
        
        if not df.empty:
            # Özet Metrikler
            col1, col2, col3 = st.columns(3)
            ort_basari = df["Başarı %"].mean()
            kritik_konular = len(df[df["Durum"].str.contains("Kritik")])
            
            col1.metric("Genel Başarı Ortalaması", f"%{ort_basari:.1f}")
            col2.metric("Kritik Konu Sayısı", kritik_konular, delta_color="inverse")
            col3.metric("Toplam Analiz Edilen Konu", len(df))
            
            st.divider()
            
            # Tablo ve Grafikler
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.subheader("📋 Detaylı Konu Analizi")
                st.dataframe(df, use_container_width=True)
                
            with col_right:
                st.subheader("📊 Başarı Dağılımı")
                st.bar_chart(df.set_index("Konu")["Başarı %"])
                
            # Kritik Konular Listesi (Hocaya verilecek liste)
            st.warning("⚠️ **Hocanın Dikkatine: Aşağıdaki konularda sınıf/öğrenci eksik kalmış!**")
            kritik_df = df[df["Durum"].str.contains("Kritik")]
            if not kritik_df.empty:
                for index, row in kritik_df.iterrows():
                    st.write(f"- **{row['Konu']}**: Başarı %{row['Başarı %']} ({row['Doğru']}/{row['Soru Sayısı']})")
            else:
                st.write("Tebrikler, kritik bir eksik görünmüyor.")
                
        else:
            st.error("PDF formatı okunamadı veya uygun veri bulunamadı. Lütfen doğru formatta bir deneme karnesi yükleyin.")
            
    except Exception as e:
        st.error(f"Bir hata oluştu: {e}")
        
else:
    st.info("Lütfen sol menüden bir PDF dosyası yükleyin.")
