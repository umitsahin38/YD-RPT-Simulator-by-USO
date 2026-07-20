import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.set_page_config(page_title="RPT HESAPLAMA PROGRAMI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} .stDeployButton {display:none;}
    button[kind="header"] {display: none;}
</style>
""", unsafe_allow_html=True)

# --- GÜVENLİK ---
if "password_correct" not in st.session_state:
    girilen_sifre = st.text_input("Şifreyi girin:", type="password", key="password")
    if girilen_sifre:
        if girilen_sifre == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Şifre yanlış.")
    st.stop()

st.title("📦 RPT HESAPLAMA PROGRAMI")

# --- SESSION STATE ---
DEFAULTS = {
    "gecici_kurallar": [], "aktif_kurallar": [], "hesaplandi": False,
    "p_hedef": 150, "p_moq": 250, "p_kat": 50, "p_lead": 3, "p_tavan": 220, "urun_gruplari": [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

# --- TAKVİM ---
bugun = datetime.now()
aylar_sim, default_katsayilar = [], []
aylik_katsayilar = {1:1.35, 2:1.35, 3:1.25, 4:1.20, 5:1.10, 6:1.00, 7:1.00, 8:1.00, 9:1.25, 10:1.40, 11:1.80, 12:1.40}
for i in range(18):
    d = datetime(bugun.year, bugun.month, 1) + pd.DateOffset(months=i)
    aylar_sim.append(d.strftime("%Y%m"))
    default_katsayilar.append(aylik_katsayilar.get(d.month, 1.0))

# --- FONKSİYONLAR ---
@st.cache_data(show_spinner=False)
def veriyi_yukle(dosya_bytes):
    df = pd.read_excel(io.BytesIO(dosya_bytes), header=1)
    df = df.rename(columns={'Ürün Kodu': 'SKU', 'Toplam Stok': 'Acilis_Stogu', 'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'})
    return df, None

def hesapla_rpt(df, aylar_sim, mevsimsellik, h_gun, m_moq, v_kat, lead, tavan_cover):
    devreden = df['Acilis_Stogu'].fillna(0).to_numpy(float)
    ort_satis = df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)
    
    for i, ay in enumerate(aylar_sim):
        kat = mevsimsellik.get(ay, 1.0)
        beklenen_satis = ort_satis * kat
        gelen = df[str(int(ay))].fillna(0).to_numpy(float) if str(int(ay)) in df.columns else np.zeros(len(df))
        
        baslangic = devreden + gelen
        hedef_stok = (h_gun / 30.0) * beklenen_satis
        ihtiyac = hedef_stok - baslangic
        
        # TAMSAYI HESAPLAMA (Küsüratsız)
        rpt_ham = np.where(i >= lead, 
                           np.where(ihtiyac <= 0, 0, np.where(ihtiyac <= m_moq, m_moq, np.ceil(ihtiyac / np.where(v_kat > 0, v_kat, 1)) * v_kat)), 
                           0).astype(int)
        
        tavan_stok = (tavan_cover / 30.0) * beklenen_satis
        kalan = np.maximum(tavan_stok - baslangic, 0).astype(int)
        rpt = np.minimum(rpt_ham, kalan)
        
        df[f'{ay}_Beklenen_Satis'] = beklenen_satis
        df[f'{ay}_RPT'] = rpt
        df[f'{ay}_Kapanis_Stogu'] = np.maximum(baslangic + rpt - beklenen_satis, 0)
        df[f'{ay}_Cover_Gun'] = np.where(beklenen_satis > 0, ((baslangic + rpt) / beklenen_satis) * 30, 999)
        devreden = df[f'{ay}_Kapanis_Stogu'].to_numpy()
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Genel Parametreler")
    with st.form("parametre_formu"):
        st.session_state["p_hedef"] = st.number_input("Genel Hedef Cover", value=st.session_state["p_hedef"], step=10)
        st.session_state["p_moq"]   = st.number_input("Genel MOQ", value=st.session_state["p_moq"], step=50)
        st.session_state["p_kat"]   = st.number_input("Sipariş Katı", value=st.session_state["p_kat"], step=10)
        st.session_state["p_lead"]  = st.number_input("Tedarik Süresi", value=st.session_state["p_lead"], step=1)
        st.session_state["p_tavan"] = st.number_input("Cover Tavanı", value=st.session_state["p_tavan"], step=10)
        if st.form_submit_button("💾 Kaydet"): st.rerun()

    st.subheader("📋 Grup Özel Kurallar")
    grup_listesi = sorted(st.session_state.get("urun_gruplari", []))
    if grup_listesi:
        secilen_grup = st.selectbox("Grup Seçin", grup_listesi)
        c1, c2 = st.columns(2)
        ozel_cover = c1.number_input("Min Cover", value=120, step=10)
        ozel_moq = c2.number_input("MOQ", value=100, step=50)
        if st.button("➕ Ekle"):
            st.session_state["gecici_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq})
            st.rerun()
        if st.button("✅ Onayla"): st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy()

    mevsimsellik_df = st.data_editor(pd.DataFrame({"Ay": aylar_sim, "Katsayi": default_katsayilar}), hide_index=True)
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# --- ANA AKIŞ ---
yuklenen_dosya = st.file_uploader("Excel Yükle", type=['xlsx'])
if yuklenen_dosya:
    df_ham, _ = veriyi_yukle(yuklenen_dosya.getvalue())
    st.session_state["urun_gruplari"] = df_ham['Ürün Grubu'].dropna().unique().tolist()
    
    if st.button("🚀 HESAPLA"):
        h_gun = np.full(len(df_ham), float(st.session_state["p_hedef"]))
        m_moq = np.full(len(df_ham), float(st.session_state["p_moq"]))
        for k in st.session_state["aktif_kurallar"]:
            mask = df_ham['Ürün Grubu'] == k["Ürün Grubu"]
            h_gun[mask] = float(k["Cover"])
            m_moq[mask] = float(k["MOQ"])
            
        df = hesapla_rpt(df_ham.copy(), aylar_sim, mevsimsellik, h_gun, m_moq, float(st.session_state["p_kat"]), int(st.session_state["p_lead"]), float(st.session_state["p_tavan"]))
        
        # BLOKLU EXCEL SIRALAMASI
        out_cols = ['SKU','Ana Kategori','Ürün Grubu','Ürün Adı','Acilis_Stogu','Son_3_Ay_Ort_Satis']
        for ay in aylar_sim:
            out_cols.extend([f'{ay}_Kapanis_Stogu', f'{ay}_Cover_Gun', f'{ay}_RPT'])
            
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df[out_cols].to_excel(writer, index=False)
        st.download_button("📥 RPT Exceli İndir", buf.getvalue(), "rpt_raporu.xlsx")
