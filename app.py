import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.set_page_config(page_title="Tedarik Simülatörü", layout="wide", initial_sidebar_state="expanded")

# --- CSS ---
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}.stDeployButton {display:none;}
    button[kind="header"] {display: none;}
    [data-testid="stDataFrame"] {color: #000000 !important;}
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
st.title("📦 RPT ve Cover Programı")

if "gecici_kurallar" not in st.session_state: st.session_state["gecici_kurallar"] = []
if "aktif_kurallar" not in st.session_state: st.session_state["aktif_kurallar"] = []

# Tarih/Takvim
bugun = datetime.now()
aylar_sim = [f"{bugun.year + (i // 12)}{((bugun.month + i - 1) % 12 + 1):02d}" for i in range(12)]

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
        if any(k["Ürün Grubu"] == secilen_grup for k in st.session_state["gecici_kurallar"]): st.error("❌ Bu grup zaten listede!")
        else: st.session_state["gecici_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq}); st.rerun()
    
    if st.session_state["gecici_kurallar"]:
        st.write("Tanımlı Kurallar:")
        h1, h2, h3, h4 = st.columns([1, 4, 2, 2])
        h1.caption("Sil"); h2.caption("Grup"); h3.caption("C"); h4.caption("M")
        for i, k in enumerate(st.session_state["gecici_kurallar"]):
            cols = st.columns([1, 4, 2, 2])
            if cols[0].button("➖", key=f"del_{i}"): st.session_state["gecici_kurallar"].pop(i); st.rerun()
            cols[1].write(k["Ürün Grubu"]); cols[2].write(k["Cover"]); cols[3].write(k["MOQ"])
        if st.button("✅ Kuralları Tamamla"): st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy(); st.success("Kurallar ayarlandı!")
            
    st.markdown("---")
    mevsimsellik_df = st.data_editor(pd.DataFrame({"Ay": aylar_sim, "Katsayi": [1.0]*12}), hide_index=True, key="mevsim_editor")
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# Simülasyon
yuklenen_dosya = st.file_uploader("Rapor Data Excel Dosyasını Yükle (.xlsx)", type=['xlsx'])
if yuklenen_dosya:
    df = pd.read_excel(yuklenen_dosya, header=1).rename(columns={'Ürün Kodu': 'SKU', 'Toplam Stok': 'Acilis_Stogu', 'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'})
    
    h_gun, m_moq = np.full(len(df), v_hedef, float), np.full(len(df), v_moq, float)
    for k in st.session_state["aktif_kurallar"]:
        mask = df['Ürün Grubu'] == k["Ürün Grubu"]
        h_gun[mask], m_moq[mask] = float(k["Cover"]), float(k["MOQ"])
            
    devreden, ort_satis = df['Acilis_Stogu'].fillna(0).to_numpy(float), df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)
    for i, ay in enumerate(aylar_sim):
        satis = ort_satis * mevsimsellik[ay]
        baslangic = devreden + (df[int(ay)].fillna(0).to_numpy(float) if int(ay) in df.columns else np.zeros(len(df)))
        df[f'{ay}_RPT'] = np.where(i >= lead, np.where(((h_gun/30.0)*ort_satis)-baslangic <= 0, 0, np.where(((h_gun/30.0)*ort_satis)-baslangic <= m_moq, m_moq, np.ceil((((h_gun/30.0)*ort_satis)-baslangic)/v_kat)*v_kat)), 0)
        devreden = np.maximum(baslangic + df[f'{ay}_RPT'] - satis, 0)
    
    st.dataframe(df, use_container_width=True)
    
    # Excel Çıktı
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Ana_Liste', index=False)
        # Özet raporu gizlice 2. sayfaya yaz
        df_ozet = df.copy() 
        df_ozet.to_excel(writer, sheet_name='Ozet_Rapor', index=False)
    
    st.download_button("📥 Özet Raporu İndir", output.getvalue(), f"{datetime.now().strftime('%d.%m.%y')}_ozet_rpt.xlsx")
