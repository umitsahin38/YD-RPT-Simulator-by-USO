import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.set_page_config(page_title="Tedarik Simülatörü", layout="wide", initial_sidebar_state="expanded")

# --- CSS: MENÜ GİZLEME ---
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    button[kind="header"] {display: none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- GÜVENLİK ---
if "password_correct" not in st.session_state:
    st.text_input("🔒 Şifreyi girin:", type="password", key="password")
    if st.session_state.get("password") == st.secrets["APP_PASSWORD"]:
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- UYGULAMA ---
st.title("📦 RPT ve Cover Simülatörü")

if "gecici_kurallar" not in st.session_state: st.session_state["gecici_kurallar"] = []
if "aktif_kurallar" not in st.session_state: st.session_state["aktif_kurallar"] = []

# Takvim
aylik_katsayilar = {1: 1.35, 2: 1.35, 3: 1.25, 4: 1.20, 5: 1.10, 6: 1.00, 7: 1.00, 8: 1.00, 9: 1.25, 10: 1.40, 11: 1.80, 12: 1.40}
bugun = datetime.now()
aylar_sim, katsayilar = [], []
for i in range(((2027 - bugun.year) * 12) + (12 - bugun.month) + 1):
    gecerli = bugun.month + i
    aylar_sim.append(f"{bugun.year + (gecerli - 1) // 12}{(gecerli - 1) % 12 + 1:02d}")
    katsayilar.append(aylik_katsayilar[(gecerli - 1) % 12 + 1])

# Sidebar
with st.sidebar:
    st.header("⚙️ Genel Parametreler")
    v_hedef = st.number_input("Genel Hedef Cover", 150, step=10)
    v_moq = st.number_input("Genel MOQ", 250, step=50)
    v_kat = st.number_input("Katsayı", 50, step=10)
    lead = st.number_input("Tedarik Süresi", 3, step=1)
    
    st.markdown("---")
    st.subheader("Ürün Grubu Özel Parametreler")
    secilen_grup = st.selectbox("Grup Seçin", sorted(["KEK KALIBI", "BANYO AKSESUARI", "DEKORATİF OBJE", "EV DÜZENLEYİCİLER", "HAVLU", "ŞİŞE/SÜRAHİ", "TEK PİKE", "DEKORATİF TEPSİ", "SALON AKSESUAR", "ÇERÇEVE", "KOZMETİK", "MUM", "SOFRA AKSESUARI", "SOFRA TEKSTİLİ", "SUPLA", "BAR AKSESUARI", "MUMLUK", "12 KİŞİLİK YEMEK TAKIMI", "ÇAY FİNCANI", "KAHVE FİNCANI", "KESME VE SUNUM TAHTASI", "SAKLAMA KABI", "HAVLU SETİ", "MUTFAK ÖNLÜĞÜ", "TEK ÇARŞAF", "TEK YASTIK KILIFI", "YASTIK", "YORGAN", "NEVRESİM PİKE TAKIMI", "AİLE BANYO SETİ", "HAMAM SETİ", "NEVRESİM BATTANİYE TAKIMI", "ÇARŞAF TAKIMI", "NEVRESİM YATAK ÖRTÜSÜ TAKIMI", "HALI", "PASPAS", "KİLİM", "TOST MAKİNESİ", "EĞLENCELİK VE YARDIMCI ÜRÜNLER", "FİLTRE KAHVE MAKİNESİ", "MUTFAK ROBOTU", "IZGARA", "KAHVE ÖĞÜTÜCÜ", "KATI MEYVE SIKACAĞI", "PIZZA MAKER", "SÜPÜRGE", "ÜTÜ", "YEMEK YAPMA MAKİNESİ", "SERVİS GEREÇLERİ", "TEK TENCERE-TAVA", "TENCERE SETİ", "FRENCH PRESS", "ÇAYDANLIK", "DÜDÜKLÜ TENCERE", "MUTFAK AKSESUARLARI", "BAHARAT DEĞİRMENİ", "BIÇAK SETİ", "TEKLİ SERVİS ÜRÜNLERİ", "MUG", "6 KİŞİLİK KAHVALTI TAKIMI", "ÇAY SETİ", "SOFRA SERVİS", "TEKLİ ÇKB", "BARDAK GRUBU", "DİGER", "6 KİŞİLİK ÇKB TAKIMI", "TEPSİ", "12 KİŞİLİK ÇKB TAKIMI", "KAHVALTILIK", "PASTA TAKIMI", "MAMA TAKIMI"]))
    ozel_cover = st.number_input("Özel Cover", 120, step=10)
    ozel_moq = st.number_input("Özel MOQ", 100, step=50)
    
    if st.button("➕ Kural Ekle"):
        st.session_state["gecici_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq})
        st.rerun()
    
    # Tanımlı Kurallar Listesi (Satır bazlı silme)
    if st.session_state["gecici_kurallar"]:
        st.write("Tanımlı Kurallar:")
        for i, k in enumerate(st.session_state["gecici_kurallar"]):
            cols = st.columns([1, 4])
            if cols[0].button("➖", key=f"del_{i}"):
                st.session_state["gecici_kurallar"].pop(i)
                st.rerun()
            cols[1].write(f"{k['Ürün Grubu']} | C:{k['Cover']} M:{k['MOQ']}")
        
        if st.button("✅ Kuralları Tamamla"):
            st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy()
            st.success("Kurallar başarıyla ayarlandı!")
            
    st.markdown("---")
    mevsimsellik_df = st.data_editor(pd.DataFrame({"Ay": aylar_sim, "Katsayi": katsayilar}), hide_index=True, key="mevsim_editor")
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# Simülasyon
file = st.file_uploader("Excel Yükle", type=['xlsx'])
if file:
    df = pd.read_excel(file, header=1).rename(columns={'Ürün Kodu': 'SKU', 'Toplam Stok': 'Acilis_Stogu', 'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'})
    
    def run(df):
        h_gun, m_moq = np.full(len(df), v_hedef, float), np.full(len(df), v_moq, float)
        # Aktif kuralları simülasyona yansıt
        for k in st.session_state["aktif_kurallar"]:
            mask = df['Ürün Grubu'] == k["Ürün Grubu"]
            h_gun[mask], m_moq[mask] = float(k["Cover"]), float(k["MOQ"])
            
        devreden, ort_satis = df['Acilis_Stogu'].fillna(0).to_numpy(float), df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)
        for i, ay in enumerate(aylar_sim):
            satis = ort_satis * mevsimsellik[ay]
            df[f'{ay}_Beklenen_Satis'] = satis
            baslangic = devreden + (df[int(ay)].fillna(0).to_numpy(float) if int(ay) in df.columns else np.zeros(len(df)))
            df[f'{ay}_RPT'] = np.where(i >= lead, np.where(((h_gun/30.0)*ort_satis)-baslangic <= 0, 0, np.where(((h_gun/30.0)*ort_satis)-baslangic <= m_moq, m_moq, np.ceil((((h_gun/30.0)*ort_satis)-baslangic)/v_kat)*v_kat)), 0)
            df[f'{ay}_Kapanis_Stogu'] = np.maximum(baslangic + df[f'{ay}_RPT'] - satis, 0)
            df[f'{ay}_Cover_Gun'] = np.where(ort_satis > 0, ((baslangic + df[f'{ay}_RPT']) / ort_satis) * 30, 999)
            devreden = df[f'{ay}_Kapanis_Stogu'].to_numpy()
    
    run(df)
    
    cols = ['SKU', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis'] + \
           [f"{ay}_Beklenen_Satis" for ay in aylar_sim] + [f"{ay}_Kapanis_Stogu" for ay in aylar_sim] + \
           [f"{ay}_Cover_Gun" for ay in aylar_sim] + [f"{ay}_RPT" for ay in aylar_sim]
    
    st.dataframe(df[cols])
    output = io.BytesIO()
    df[cols].to_excel(output, index=False)
    st.download_button("📥 Excel İndir", output.getvalue(), f"{datetime.now().strftime('%d.%m.%y')}_rpt_dosyası.xlsx")
