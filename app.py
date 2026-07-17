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
st.title("📦 RPT ve Cover Programı")

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
        if any(k["Ürün Grubu"] == secilen_grup for k in st.session_state["gecici_kurallar"]):
            st.error("❌ Bu Gruba Ait Bir Kural Tanımlanmıştır!")
        else:
            st.session_state["gecici_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq})
            st.rerun()
    
    if st.session_state["gecici_kurallar"]:
        st.write("Tanımlı Kurallar:")
        # BAŞLIK SATIRI
        h1, h2, h3, h4 = st.columns([1, 4, 2, 2])
        h1.caption("Sil")
        h2.caption("Ürün Grubu")
        h3.caption("Min Cover")
        h4.caption("MOQ")
        
        # VERİ SATIRLARI
        for i, k in enumerate(st.session_state["gecici_kurallar"]):
            cols = st.columns([1, 4, 2, 2])
            if cols[0].button("➖", key=f"del_{i}"):
                st.session_state["gecici_kurallar"].pop(i)
                st.rerun()
            cols[1].write(k["Ürün Grubu"])
            cols[2].write(k["Cover"])
            cols[3].write(k["MOQ"])
        
        if st.button("✅ Kuralları Tanımla"):
            st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy()
            st.success("Kurallar ayarlandı!")
            
    st.markdown("---")
    mevsimsellik_df = st.data_editor(pd.DataFrame({"Ay": aylar_sim, "Katsayi": katsayilar}), hide_index=True, key="mevsim_editor")
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# Simülasyon kodun aynı kalıyor...
