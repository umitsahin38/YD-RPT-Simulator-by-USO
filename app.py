import streamlit as st
import pandas as pd
import numpy as np
import io
import time
from datetime import datetime

st.set_page_config(page_title="Tedarik Simülatörü", layout="wide")

# --- MENÜ VE GEREKSİZ BUTONLARI GİZLEME (CSS) ---
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- GLOBAL HAFIZA VE GÜVENLİK ---
@st.cache_resource
def get_auth_state():
    return {"attempts": {}, "lockouts": {}}

auth_state = get_auth_state()

def get_user_ip():
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            ip = st.context.headers.get("X-Forwarded-For", "unknown_ip")
            return ip.split(",")[0].strip()
        return "unknown_ip"
    except:
        return "unknown_ip"

def check_password():
    ip = get_user_ip()
    current_time = time.time()
    
    if ip in auth_state["lockouts"]:
        lockout_end = auth_state["lockouts"][ip]
        if current_time < lockout_end:
            kalan_dakika = int((lockout_end - current_time) / 60) + 1
            st.error(f"🚨 Güvenlik nedeniyle sistem bu IP adresine {kalan_dakika} dakika bloke edilmiştir.")
            return False
        else:
            del auth_state["lockouts"][ip]
            auth_state["attempts"][ip] = 0

    def password_entered():
        islem_zamani = time.time()
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]: 
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
            auth_state["attempts"][ip] = 0 
        else:
            st.session_state["password_correct"] = False
            auth_state["attempts"][ip] = auth_state["attempts"].get(ip, 0) + 1
            if auth_state["attempts"][ip] >= 4:
                auth_state["lockouts"][ip] = islem_zamani + 900

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Simülatöre giriş için şifreyi yazın:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Simülatöre giriş için şifreyi yazın:", type="password", on_change=password_entered, key="password")
        if auth_state["attempts"].get(ip, 0) < 4:
            kalan_hak = 4 - auth_state["attempts"].get(ip, 0)
            st.warning(f"❌ Hatalı şifre! Kalan hakkınız: {kalan_hak}")
        return False
    return True

if not check_password():
    st.stop()

# --- ŞİFRE DOĞRUYSA AÇILACAK ASIL UYGULAMA ---
st.title("📦 RPT ve Cover Simülatörü (Varış Planlaması)")

if "eklenen_kurallar" not in st.session_state:
    st.session_state["eklenen_kurallar"] = []

# --- TAKVİM VE MEVSİMSELLİK MANTIĞI ---
aylik_katsayilar = {
    1: 1.35, 2: 1.35, 3: 1.25, 4: 1.20, 5: 1.10, 6: 1.00,
    7: 1.00, 8: 1.00, 9: 1.25, 10: 1.40, 11: 1.80, 12: 1.40
}
bitis_yili, bitis_ayi = 2027, 12
bugun = datetime.now()
aylar_sim, varsayilan_katsayilar = [], []
kalan_ay_sayisi = ((bitis_yili - bugun.year) * 12) + (bitis_ayi - bugun.month) + 1
if kalan_ay_sayisi <= 0: kalan_ay_sayisi = 1
for i in range(kalan_ay_sayisi):
    gecerli_ay = bugun.month + i
    yil = bugun.year + (gecerli_ay - 1) // 12
    ay = (gecerli_ay - 1) % 12 + 1
    aylar_sim.append(f"{yil}{ay:02d}")
    varsayilan_katsayilar.append(aylik_katsayilar[ay])

# 1) SIDEBAR
with st.sidebar:
    st.header("⚙️ Genel Parametreler")
    varsayilan_hedef_gun = st.number_input("Varsayılan Hedef Cover (gün)", value=150, step=5)
    varsayilan_moq = st.number_input("Varsayılan MOQ", value=250, step=10)
    varsayilan_kat = st.number_input("Varsayılan Katsayı", value=50, step=5)
    lead_time = st.number_input("Tedarik Süresi (ay)", value=3, step=1)
    
    st.markdown("---")
    st.header("🎯 Özel Ürün Grubu Kuralları")
    urun_gruplari_listesi = ["KEK KALIBI", "BANYO AKSESUARI", "DEKORATİF OBJE", "EV DÜZENLEYİCİLER", "HAVLU", "ŞİŞE/SÜRAHİ", "TEK PİKE", "DEKORATİF TEPSİ", "SALON AKSESUAR", "ÇERÇEVE", "KOZMETİK", "MUM", "SOFRA AKSESUARI", "SOFRA TEKSTİLİ", "SUPLA", "BAR AKSESUARI", "MUMLUK", "12 KİŞİLİK YEMEK TAKIMI", "ÇAY FİNCANI", "KAHVE FİNCANI", "KESME VE SUNUM TAHTASI", "SAKLAMA KABI", "HAVLU SETİ", "MUTFAK ÖNLÜĞÜ", "TEK ÇARŞAF", "TEK YASTIK KILIFI", "YASTIK", "YORGAN", "NEVRESİM PİKE TAKIMI", "AİLE BANYO SETİ", "HAMAM SETİ", "NEVRESİM BATTANİYE TAKIMI", "ÇARŞAF TAKIMI", "NEVRESİM YATAK ÖRTÜSÜ TAKIMI", "HALI", "PASPAS", "KİLİM", "TOST MAKİNESİ", "EĞLENCELİK VE YARDIMCI ÜRÜNLER", "FİLTRE KAHVE MAKİNESİ", "MUTFAK ROBOTU", "IZGARA", "KAHVE ÖĞÜTÜCÜ", "KATI MEYVE SIKACAĞI", "PIZZA MAKER", "SÜPÜRGE", "ÜTÜ", "YEMEK YAPMA MAKİNESİ", "SERVİS GEREÇLERİ", "TEK TENCERE-TAVA", "TENCERE SETİ", "FRENCH PRESS", "ÇAYDANLIK", "DÜDÜKLÜ TENCERE", "MUTFAK AKSESUARLARI", "BAHARAT DEĞİRMENİ", "BIÇAK SETİ", "TEKLİ SERVİS ÜRÜNLERİ", "MUG", "6 KİŞİLİK KAHVALTI TAKIMI", "ÇAY SETİ", "SOFRA SERVİS", "TEKLİ ÇKB", "BARDAK GRUBU", "DİĞER", "6 KİŞİLİK ÇKB TAKIMI", "TEPSİ", "12 KİŞİLİK ÇKB TAKIMI", "KAHVALTILIK", "PASTA TAKIMI", "MAMA TAKIMI"]
    secilen_grup = st.selectbox("🔍 Ürün Grubu Seçin", sorted(list(set(urun_gruplari_listesi))))
    ozel_cover = st.number_input(f"'{secilen_grup}' için Özel Cover", value=120, step=5)
    ozel_moq = st.number_input(f"'{secilen_grup}' için Özel MOQ", value=100, step=10)
    
    if st.button("➕ Kuralı Kaydet"):
        mevcutlar = [k["Ürün Grubu"] for k in st.session_state["eklenen_kurallar"]]
        if secilen_grup in mevcutlar:
            for k in st.session_state["eklenen_kurallar"]:
                if k["Ürün Grubu"] == secilen_grup: k["Cover"], k["MOQ"] = ozel_cover, ozel_moq
        else: st.session_state["eklenen_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq})
        st.rerun()
            
    if len(st.session_state["eklenen_kurallar"]) > 0:
        st.write("**Tanımlı Kurallar:**", pd.DataFrame(st.session_state["eklenen_kurallar"]))
        if st.button("✅ Kuralları Tamamla"): st.success("Kurallar kilitlendi!")
            
    st.markdown("---")
    mevsim_df = pd.DataFrame({"Ay": aylar_sim, "Katsayi": varsayilan_katsayilar})
    # DÜZELTİLEN SATIR:
    mevsimsellik_df = st.data_editor(mevsim_df, hide_index=True)
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# 2) SİMÜLASYON
yuklenen_dosya = st.file_uploader("Rapor Data Excel Dosyasını Yükle (.xlsx)", type=['xlsx'])
if yuklenen_dosya is not None:
    df = pd.read_excel(yuklenen_dosya, header=1).rename(columns={'Ürün Kodu': 'SKU', 'Toplam Stok': 'Acilis_Stogu', 'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'})
    def simulasyonu_calistir(df):
        n = len(df)
        devreden, ort_satis = df['Acilis_Stogu'].fillna(0).to_numpy(float), df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)
        hedef_gun_dizisi, moq_dizisi = np.full(n, varsayilan_hedef_gun, float), np.full(n, varsayilan_moq, float)
        for kural in st.session_state["eklenen_kurallar"]:
            mask = df['Ürün Grubu'] == kural["Ürün Grubu"]
            hedef_gun_dizisi[mask], moq_dizisi[mask] = float(kural["Cover"]), float(kural["MOQ"])
        for i, ay in enumerate(aylar_sim):
            satis = ort_satis * mevsimsellik[ay]
            df[f'{ay}_Beklenen_Satis'] = satis
            baslangic = devreden + (df[int(ay)].fillna(0).to_numpy(float) if int(ay) in df.columns else np.zeros(n))
            df[f'{ay}_RPT'] = np.where(i >= lead_time, np.where(((hedef_gun_dizisi/30.0)*ort_satis)-baslangic <= 0, 0, np.where(((hedef_gun_dizisi/30.0)*ort_satis)-baslangic <= moq_dizisi, moq_dizisi, np.ceil((((hedef_gun_dizisi/30.0)*ort_satis)-baslangic)/varsayilan_kat)*varsayilan_kat)), 0)
            df[f'{ay}_Kapanis_Stogu'] = np.maximum(baslangic + df[f'{ay}_RPT'] - satis, 0)
            devreden = df[f'{ay}_Kapanis_Stogu'].to_numpy()
            df[f'{ay}_Cover_Gun'] = np.where(ort_satis > 0, ((baslangic + df[f'{ay}_RPT']) / ort_satis) * 30, 999)
            
    simulasyonu_calistir(df)
    cols = ['SKU', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis'] + [f"{ay}_{c}" for ay in aylar_sim for c in ['Beklenen_Satis', 'RPT', 'Kapanis_Stogu', 'Cover_Gun']]
    st.dataframe(df[cols])
    output = io.BytesIO()
    df[cols].to_excel(output, index=False)
    st.download_button("📥 Excel İndir", output.getvalue(), "Simulasyon_Final.xlsx")
