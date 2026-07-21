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

# NOT: "p_tavan" (Cover Tavanı) tamamen kaldırıldı — RPT artık üst sınır olmadan

# sadece "Genel Hedef Cover" / grup bazlı Min Cover hedefine göre hesaplanıyor.

DEFAULTS = {

    "gecici_kurallar": [],

    "aktif_kurallar": [],

    "hesaplandi": False,      # DataFrame yerine sadece bool tutuyoruz

    "p_hedef": 150,

    "p_moq": 250,

    "p_kat": 50,

    "p_lead": 3,

    "urun_gruplari": [],

}
 
for k, v in DEFAULTS.items():

    if k not in st.session_state:

        st.session_state[k] = v
 
# --- TAKVİM ---

bugun = datetime.now()

aylar_sim, default_katsayilar = [], []

aylik_katsayilar = {1:1.35,2:1.35,3:1.25,4:1.20,5:1.10,6:1.00,7:1.00,8:1.00,9:1.25,10:1.40,11:1.80,12:1.40}

for i in range(18):

    d = datetime(bugun.year, bugun.month, 1) + pd.DateOffset(months=i)

    aylar_sim.append(d.strftime("%Y%m"))

    default_katsayilar.append(aylik_katsayilar.get(d.month, 1.0))
 
def ceyrek_uret(aylar):

    p = {}

    for ay in aylar:

        yil, ay_no = int(ay[:4]), int(ay[4:])

        q = (ay_no - 1) // 3 + 1

        p.setdefault(f"{yil}Q{q}", []).append(ay)

    return p
 
periyotlar = ceyrek_uret(aylar_sim)
 
# --- FONKSİYONLAR ---

@st.cache_data(show_spinner=False)

def veriyi_yukle(dosya_bytes):

    try:

        df = pd.read_excel(io.BytesIO(dosya_bytes), header=1)

    except Exception as e:

        return None, f"Excel okunamadı: {e}"

    df = df.rename(columns={

        'Ürün Kodu': 'SKU',

        'Toplam Stok': 'Acilis_Stogu',

        'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'

    })

    eksik = [k for k in ['SKU','Acilis_Stogu','Son_3_Ay_Ort_Satis','Ana Kategori','Ürün Grubu','Ürün Adı']

             if k not in df.columns]

    if eksik:

        return None, f"Eksik kolonlar: {', '.join(eksik)}"

    return df, None
 
 
def hesapla_rpt(df, aylar_sim, mevsimsellik, h_gun, m_moq, v_kat, lead):

    """

    Cover Tavanı kısıtı kaldırıldı. RPT artık sadece hedef cover'a (h_gun)

    ulaşacak şekilde hesaplanıyor; ayrıca bir üst sınırla kesilmiyor.

    """

    devreden = df['Acilis_Stogu'].fillna(0).to_numpy(float)

    ort_satis = df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)

    for i, ay in enumerate(aylar_sim):

        kat = mevsimsellik.get(ay, 1.0)

        beklenen_satis = ort_satis * kat

        gelen = df[int(ay)].fillna(0).to_numpy(float) if int(ay) in df.columns else np.zeros(len(df))

        baslangic = devreden + gelen

        hedef_stok = (h_gun / 30.0) * beklenen_satis

        ihtiyac = hedef_stok - baslangic

        rpt = np.where(

            i >= lead,

            np.where(ihtiyac <= 0, 0,

                np.where(ihtiyac <= m_moq, m_moq,

                    np.ceil(ihtiyac / np.where(v_kat > 0, v_kat, 1)) * v_kat)),

            0

        )

        df[f'{ay}_RPT'] = rpt

        df[f'{ay}_Kapanis_Stogu'] = np.maximum(baslangic + rpt - beklenen_satis, 0)

        df[f'{ay}_Cover_Gun'] = np.where(

            ort_satis > 0, ((baslangic + rpt) / ort_satis) * 30, 999

        )

        devreden = df[f'{ay}_Kapanis_Stogu'].to_numpy()

    return df
 
# --- SIDEBAR ---

with st.sidebar:

    st.header("⚙️ Genel Parametreler")

    with st.form("parametre_formu"):

        f_hedef = st.number_input("Genel Hedef Cover (gün)", value=st.session_state["p_hedef"], step=10)

        f_moq   = st.number_input("Genel MOQ (adet)",         value=st.session_state["p_moq"],   step=50)

        f_kat   = st.number_input("Sipariş Yuvarlama Katı",   value=st.session_state["p_kat"],   step=10)

        f_lead  = st.number_input("Tedarik Süresi (ay)",      value=st.session_state["p_lead"],  step=1)

        # "Cover Tavanı (gün)" input'u kaldırıldı.

        if st.form_submit_button("💾 Parametreleri Kaydet"):

            st.session_state["p_hedef"] = int(f_hedef)

            st.session_state["p_moq"]   = int(f_moq)

            st.session_state["p_kat"]   = int(f_kat)

            st.session_state["p_lead"]  = int(f_lead)

            st.session_state["hesaplandi"] = False

            st.success("Kaydedildi.")
 
    # Alias — her zaman session_state'den okunur, form'a bağlı değil

    v_hedef = st.session_state["p_hedef"]

    v_moq   = st.session_state["p_moq"]

    v_kat   = st.session_state["p_kat"]

    v_lead  = st.session_state["p_lead"]
 
    st.markdown("---")

    st.subheader("📋 Ürün Grubu Özel Parametreler")

    grup_listesi = sorted(st.session_state.get("urun_gruplari", []))

    if grup_listesi:

        secilen_grup = st.selectbox("Grup Seçin", grup_listesi)

        col_c, col_m = st.columns(2)

        ozel_cover = col_c.number_input("Min Cover", min_value=10, value=120, step=10)

        ozel_moq   = col_m.number_input("MOQ (ad)",  min_value=0,  value=100, step=50)
 
        if st.button("➕ Kural Ekle", use_container_width=True):

            if any(k["Ürün Grubu"] == secilen_grup for k in st.session_state["gecici_kurallar"]):

                st.error("Bu grup zaten listede!")

            else:

                st.session_state["gecici_kurallar"].append(

                    {"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq}

                )

                st.rerun()
 
        if st.session_state["gecici_kurallar"]:

            st.markdown("---")

            h0, h1, h2, h3 = st.columns([0.7, 4, 1.8, 1.8])

            h1.markdown("<p style='font-size:11px;font-weight:700;color:#888;margin:0;'>ÜRÜN GRUBU</p>", unsafe_allow_html=True)

            h2.markdown("<p style='font-size:11px;font-weight:700;color:#888;margin:0;'>MIN COVER</p>", unsafe_allow_html=True)

            h3.markdown("<p style='font-size:11px;font-weight:700;color:#888;margin:0;'>MOQ (AD)</p>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:2px 0 6px 0;border:none;border-top:1px solid #ddd;'>", unsafe_allow_html=True)
 
            for idx, k in enumerate(st.session_state["gecici_kurallar"]):

                c0, c1, c2, c3 = st.columns([0.7, 4, 1.8, 1.8])

                if c0.button("✕", key=f"del_{idx}", help="Sil"):

                    st.session_state["gecici_kurallar"].pop(idx)

                    st.rerun()

                c1.markdown(f"<p style='font-size:12px;margin:6px 0;'>{k['Ürün Grubu']}</p>", unsafe_allow_html=True)

                c2.markdown(f"<p style='font-size:13px;font-weight:600;color:#1a73e8;margin:6px 0;'>{k['Cover']}</p>", unsafe_allow_html=True)

                c3.markdown(f"<p style='font-size:13px;font-weight:600;color:#1a73e8;margin:6px 0;'>{k['MOQ']}</p>", unsafe_allow_html=True)
 
            st.markdown("---")

            if st.button("✅ Kuralları Onayla", use_container_width=True, type="primary"):

                st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy()

                st.session_state["hesaplandi"] = False

                st.success("Kurallar onaylandı!")

    else:

        st.info("Önce Excel yükleyin — gruplar otomatik listelenir.")
 
    st.markdown("---")

    st.caption("Mevsimsellik Katsayıları")

    mevsimsellik_df = st.data_editor(

        pd.DataFrame({"Ay": aylar_sim, "Katsayi": default_katsayilar}),

        hide_index=True, key="mevsim_editor"

    )

    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))
 
# --- ANA AKIŞ ---

yuklenen_dosya = st.file_uploader("Rapor Data Excel Dosyasını Yükleyin (.xlsx)", type=['xlsx'])
 
if yuklenen_dosya is None:

    st.stop()
 
df_ham, hata = veriyi_yukle(yuklenen_dosya.getvalue())

if hata:

    st.error(f"❌ {hata}")

    st.stop()
 
# Ürün gruplarını sidebar için kaydet

st.session_state["urun_gruplari"] = df_ham['Ürün Grubu'].dropna().unique().tolist()
 
# Eksik satış uyarısı

bos_satis = df_ham['Son_3_Ay_Ort_Satis'].isna().sum()

if bos_satis > 0:

    st.warning(f"⚠️ {bos_satis} satırda satış verisi boş — 0 satış olarak hesaplanacak.")
 
# ADIM 1 — Kısıtları göster

st.markdown("---")

st.header("① Uygulanacak Kısıtlar")

ozet_df = pd.DataFrame(

    [{"Ürün Grubu": "GENEL (özel kural yok)", "Min Cover (gün)": v_hedef, "MOQ (adet)": v_moq}] +

    [{"Ürün Grubu": k["Ürün Grubu"], "Min Cover (gün)": k["Cover"], "MOQ (adet)": k["MOQ"]}

     for k in st.session_state["aktif_kurallar"]]

)

st.dataframe(ozet_df, use_container_width=True, hide_index=True)

st.caption(f"Tedarik süresi: **{v_lead} ay** · Yuvarlama katı: **{v_kat}**")
 
onaysiz = len(st.session_state["gecici_kurallar"]) != len(st.session_state["aktif_kurallar"])

if onaysiz:

    st.warning("⚠️ Sidebar'da onaylanmamış taslak kurallar var — 'Kuralları Onayla' butonuna basılmadan hesaba dahil edilmez.")
 
# ADIM 2 — Hesapla

st.markdown("---")

st.header("② RPT Hesapla")

hesapla_tetik = st.button("🚀 Yukarıdaki kısıtlarla RPT'yi Hesapla", type="primary")
 
# DataFrame'i session_state'de TUTMUYORUZ — her hesaplama butonuna basılınca sıfırdan üretiyoruz.

if hesapla_tetik:

    st.session_state["hesaplandi"] = True
 
if not st.session_state["hesaplandi"]:

    st.stop()
 
# --- HESAPLAMA (her rerun'da taze) ---

h_gun = np.full(len(df_ham), float(v_hedef))

m_moq = np.full(len(df_ham), float(v_moq))

for k in st.session_state["aktif_kurallar"]:

    mask = df_ham['Ürün Grubu'] == k["Ürün Grubu"]

    h_gun[mask] = float(k["Cover"])

    m_moq[mask] = float(k["MOQ"])
 
with st.spinner("Hesaplanıyor..."):

    df = hesapla_rpt(

        df_ham.copy(), aylar_sim, mevsimsellik,

        h_gun, m_moq, float(v_kat), int(v_lead)

    )
 
st.success("✅ RPT hesaplandı.")
 
# --- SONUÇLAR ---

# Cover tavanı uyarı bloğu kaldırıldı (artık tavan kısıtı yok).
 
# Özet tablo

st.markdown("---")

st.header("📊 Kategori Bazlı En Yüksek 5 RPT İhtiyacı")

ozet = []

for kat in df['Ana Kategori'].dropna().unique():

    df_k = df[df['Ana Kategori'] == kat].copy()

    for q, aylar_q in periyotlar.items():

        cols_r = [f"{a}_RPT" for a in aylar_q if f"{a}_RPT" in df_k.columns]

        if cols_r:

            df_k[f"{q}_RPT"] = df_k[cols_r].sum(axis=1)

            for _, row in df_k[df_k[f"{q}_RPT"] > 0].nlargest(5, f"{q}_RPT").iterrows():

                ozet.append({

                    "Kategori": kat,

                    "Ürün Grubu": row['Ürün Grubu'],

                    "Stok Kodu": row['SKU'],

                    "Stok Adı": row['Ürün Adı'],

                    "Periyot": q,

                    "Adet": int(row[f"{q}_RPT"])

                })
 
if ozet:

    st.dataframe(

        pd.DataFrame(ozet).pivot_table(

            index=['Kategori','Ürün Grubu','Stok Kodu','Stok Adı'],

            columns='Periyot', values='Adet', fill_value=0

        ),

        use_container_width=True

    )

else:

    st.info("Bu parametrelerle hiçbir üründe RPT ihtiyacı oluşmadı.")
 
# --- FAZLA STOK HESABI ---

# Kontrol noktaları: her 6 ayda bir — 202612 ve 202706 kapanış stokları

# Formül: Kapanış Stoğu - (5 × Ort. Aylık Satış) > 0 ise fazla var

# 5 = 150 gün / 30 = hedef cover'ın ay karşılığı

KONTROL_AYLARI = ["202612", "202706"]

kontrol_aylari_mevcut = [a for a in KONTROL_AYLARI if f"{a}_Kapanis_Stogu" in df.columns]
 
fazla_stok_listesi = []

for ay in kontrol_aylari_mevcut:

    kap_col = f"{ay}_Kapanis_Stogu"

    ort_satis = df['Son_3_Ay_Ort_Satis'].fillna(0)

    hedef_stok_adeti = 5 * ort_satis          # 150 gün = 5 ay

    fazla = df[kap_col].fillna(0) - hedef_stok_adeti

    mask = fazla > 0

    df_fazla = df[mask].copy()

    df_fazla[f"{ay}_Fazla_Stok"] = fazla[mask].round(0).astype(int)

    df_fazla[f"{ay}_Cover_Gun_Hesap"] = (df_fazla[kap_col] / ort_satis[mask].replace(0, np.nan) * 30).round(1)

    for _, row in df_fazla.iterrows():

        fazla_stok_listesi.append({

            "Kontrol Ayı":        ay,

            "Ana Kategori":       row.get("Ana Kategori", ""),

            "Ürün Grubu":         row.get("Ürün Grubu", ""),

            "Stok Kodu":          row["SKU"],

            "Stok Adı":           row.get("Ürün Adı", ""),

            "Ort. Aylık Satış":   int(ort_satis[row.name]) if ort_satis[row.name] > 0 else 0,

            "Kapanış Stoğu":      int(row[kap_col]),

            "Hedef Stok (5 ay)":  int(hedef_stok_adeti[row.name]),

            "Fazla Stok (adet)":  int(row[f"{ay}_Fazla_Stok"]),

            "Cover (gün)":        row[f"{ay}_Cover_Gun_Hesap"],

        })
 
df_fazla_rapor = pd.DataFrame(fazla_stok_listesi) if fazla_stok_listesi else pd.DataFrame()
 
# Ekranda önizleme

st.markdown("---")

st.header("📦 Fazla Stok Tespiti (202612 & 202706)")

if not df_fazla_rapor.empty:

    for ay in kontrol_aylari_mevcut:

        df_ay = df_fazla_rapor[df_fazla_rapor["Kontrol Ayı"] == ay]

        st.subheader(f"🗓 {ay[:4]}/{ay[4:]} — {len(df_ay)} ürün fazla stok taşıyor")

        st.dataframe(

            df_ay.drop(columns=["Kontrol Ayı"]).sort_values("Fazla Stok (adet)", ascending=False),

            use_container_width=True, hide_index=True

        )

else:

    st.info("Her iki kontrol noktasında da 150 gün üzerinde stok taşıyan ürün bulunamadı.")
 
# --- EXCEL ÇIKTISI (iki sayfa: RPT + FAZLA_STOK) ---

out_cols = (

    ['SKU','Ana Kategori','Ürün Grubu','Ürün Adı','Acilis_Stogu','Son_3_Ay_Ort_Satis'] +

    [f"{ay}_Kapanis_Stogu" for ay in aylar_sim] +

    [f"{ay}_Cover_Gun"     for ay in aylar_sim] +

    [f"{ay}_RPT"           for ay in aylar_sim]

)

out_cols = [c for c in out_cols if c in df.columns]
 
# Tarihli dosya adı: GG.AA.YYYY_RPT_RAPORU.xlsx

dosya_adi = f"{datetime.now().strftime('%d.%m.%Y')}_RPT_RAPORU.xlsx"
 
buf = io.BytesIO()

with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:

    # Sayfa 1: RPT

    df[out_cols].to_excel(writer, index=False, sheet_name='RPT')

    wb = writer.book

    ws_rpt = writer.sheets['RPT']

    baslik_fmt = wb.add_format({'bold':True,'bg_color':'#1F4E78','font_color':'white','border':1})

    kritik_fmt = wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006'})

    for i, col in enumerate(out_cols):

        ws_rpt.write(0, i, col, baslik_fmt)

        ws_rpt.set_column(i, i, max(12, len(str(col)) + 2))

    ws_rpt.freeze_panes(1, 4)

    cover_start = 6 + len(aylar_sim)

    for j in range(len(aylar_sim)):

        ci = cover_start + j

        ws_rpt.conditional_format(1, ci, len(df), ci,

            {'type':'cell','criteria':'<','value':30,'format':kritik_fmt})
 
    # Sayfa 2: FAZLA_STOK

    if not df_fazla_rapor.empty:

        df_fazla_rapor.to_excel(writer, index=False, sheet_name='FAZLA_STOK')

        ws_fs = writer.sheets['FAZLA_STOK']

        baslik_fmt2  = wb.add_format({'bold':True,'bg_color':'#C00000','font_color':'white','border':1})

        fazla_vurgu  = wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006','bold':True})

        for i, col in enumerate(df_fazla_rapor.columns):

            ws_fs.write(0, i, col, baslik_fmt2)

            ws_fs.set_column(i, i, max(14, len(str(col)) + 2))

        ws_fs.freeze_panes(1, 0)

        # Fazla stok sütununu (index 8) kırmızı vurgula

        ws_fs.conditional_format(1, 8, len(df_fazla_rapor), 8,

            {'type':'cell','criteria':'>','value':0,'format':fazla_vurgu})

    else:

        # Yine de boş sayfa oluştur

        pd.DataFrame(columns=["Kontrol Ayı","Stok Kodu","Fazla Stok (adet)"]).to_excel(

            writer, index=False, sheet_name='FAZLA_STOK'

        )
 
st.download_button("📥 RPT Exceli İndir", buf.getvalue(), dosya_adi)
 
