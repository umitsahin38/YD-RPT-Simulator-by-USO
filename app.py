import streamlit as st
import pandas as pd
import numpy as np
import io
import time

st.set_page_config(page_title="Tedarik Simülatörü", layout="wide")

# --- GLOBAL HAFIZA (IP ve Hatalı Giriş Takibi İçin) ---
@st.cache_resource
def get_auth_state():
    # Sunucu kapanana kadar IP'leri ve bloke sürelerini hafızada tutar
    return {"attempts": {}, "lockouts": {}}

auth_state = get_auth_state()

def get_user_ip():
    try:
        # Kullanıcının IP adresini yakalama (Streamlit Cloud üzerinden)
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            ip = st.context.headers.get("X-Forwarded-For", "unknown_ip")
            return ip.split(",")[0].strip()
        return "unknown_ip"
    except:
        return "unknown_ip"

# --- KİLİT EKRANI (ŞİFRELEME VE BLOKE MANTIGI) ---
def check_password():
    ip = get_user_ip()
    current_time = time.time()
    
    # 1. KONTROL: Bu IP şu an bloke edilmiş mi?
    if ip in auth_state["lockouts"]:
        lockout_end = auth_state["lockouts"][ip]
        if current_time < lockout_end:
            kalan_dakika = int((lockout_end - current_time) / 60) + 1
            st.error(f"🚨 Çok sayıda hatalı giriş yaptınız! Güvenlik nedeniyle sistem bu IP adresine {kalan_dakika} dakika boyunca bloke edilmiştir.")
            return False
        else:
            # Süre dolduysa cezayı kaldır
            del auth_state["lockouts"][ip]
            auth_state["attempts"][ip] = 0

    def password_entered():
        islem_zamani = time.time()
        # ŞİFREYİ BURADAN DEĞİŞTİREBİLİRSİN:
        if st.session_state["password"] == "umitkrcl2026": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
            auth_state["attempts"][ip] = 0 # Başarılı girişte hataları sıfırla
        else:
            st.session_state["password_correct"] = False
            # Hatalı giriş sayısını artır
            auth_state["attempts"][ip] = auth_state["attempts"].get(ip, 0) + 1
            
            # 4 hataya ulaşıldıysa 15 dakika (900 saniye) banla!
            if auth_state["attempts"][ip] >= 4:
                auth_state["lockouts"][ip] = islem_zamani + 900

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Simülatöre giriş için şifreyi yazıp Enter'a basın:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Simülatöre giriş için şifreyi yazıp Enter'a basın:", type="password", on_change=password_entered, key="password")
        
        # Henüz bloke olmadıysa kalan hakkı göster
        if auth_state["attempts"].get(ip, 0) < 4:
            kalan_hak = 4 - auth_state["attempts"].get(ip, 0)
            st.warning(f"❌ Hatalı şifre! Kalan deneme hakkınız: {kalan_hak}")
        return False
    return True

# Şifre doğru girilmezse kodun geri kalanı ASLA çalışmaz
if not check_password():
    st.stop()

# --- ŞİFRE DOĞRUYSA AÇILACAK ASIL UYGULAMA ---
st.title("📦 RPT ve Cover Simülatörü (Varış Planlaması)")

# 1) SIDEBAR: PARAMETRELER VE MEVSİMSELLİK
with st.sidebar:
    st.header("⚙️ Simülasyon Parametreleri")
    hedef_gun = st.number_input("Hedef Stok Cover (gün)", value=150, step=5)
    varsayilan_moq = st.number_input("Varsayılan MOQ", value=250, step=10)
    varsayilan_kat = st.number_input("Varsayılan Katsayı", value=50, step=5)
    lead_time = st.number_input("Tedarik Süresi / Donmuş Bölge (ay)", value=3, step=1)
    
    st.header("📅 Mevsimsellik Katsayıları")
    aylar_sim = ['202607', '202608', '202609', '202610', '202611', '202612', 
                 '202701', '202702', '202703', '202704', '202705', '202706']
    varsayilan_katsayilar = [0.8, 1.0, 1.2, 1.5, 1.2, 1.0, 0.9, 0.9, 0.8, 1.0, 1.0, 1.0]
    
    mevsim_df = pd.DataFrame({"Ay": aylar_sim, "Katsayi": varsayilan_katsayilar})
    mevsimsellik_df = st.data_editor(mevsim_df, hide_index=True)
    
    if st.button("💾 Katsayıları Kaydet / Uygula"):
        st.success("Mevsimsellik katsayıları başarıyla güncellendi!")
        
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# 2) DOSYA YÜKLEME VE SİMÜLASYON
yuklenen_dosya = st.file_uploader("Rapor Data Excel Dosyasını Yükle (.xlsx)", type=['xlsx'])

if yuklenen_dosya is not None:
    df_ana_ham = pd.read_excel(yuklenen_dosya, header=1)
    df_ana = df_ana_ham.rename(columns={'Ürün Kodu': 'SKU', 'Toplam Stok': 'Acilis_Stogu', 'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'})

    def simulasyonu_calistir(df):
        n = len(df)
        devreden = df['Acilis_Stogu'].fillna(0).to_numpy(dtype=float)
        ort_satis = df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(dtype=float)
        
        for i, ay in enumerate(aylar_sim):
            satis = ort_satis * mevsimsellik[ay]
            df[f'{ay}_Beklenen_Satis'] = satis 
            
            sas = df[int(ay)].fillna(0).to_numpy(dtype=float) if int(ay) in df.columns else np.zeros(n)
            df[f'{ay}_SAS'] = sas 
            
            baslangic = devreden + sas
            
            if i >= lead_time:
                eksik = ((hedef_gun/30.0) * ort_satis) - baslangic
                siparis = np.where(eksik <= 0, 0, np.where(eksik <= varsayilan_moq, varsayilan_moq, np.ceil(eksik / varsayilan_kat) * varsayilan_kat))
            else:
                siparis = np.zeros(n)
            
            df[f'{ay}_RPT'] = siparis
            
            kullanilabilir = baslangic + siparis
            df[f'{ay}_Cover_Gun'] = np.where(ort_satis > 0, (kullanilabilir / ort_satis) * 30, 999)
            
            kapanis = np.maximum(kullanilabilir - satis, 0)
            df[f'{ay}_Kapanis_Stogu'] = kapanis
            devreden = kapanis

    df_kuralli = df_ana.copy()
    simulasyonu_calistir(df_kuralli)
    
    base = ['SKU', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis']
    cols = base + \
           [f"{ay}_Beklenen_Satis" for ay in aylar_sim] + \
           [f"{ay}_SAS" for ay in aylar_sim] + \
           [f"{ay}_Kapanis_Stogu" for ay in aylar_sim] + \
           [f"{ay}_Cover_Gun" for ay in aylar_sim] + \
           [f"{ay}_RPT" for ay in aylar_sim]
    
    st.dataframe(df_kuralli[cols])
    
    output = io.BytesIO()
    df_kuralli[cols].to_excel(output, index=False)
    st.download_button("📥 Excel İndir", output.getvalue(), "Simulasyon_Katsayili.xlsx")
