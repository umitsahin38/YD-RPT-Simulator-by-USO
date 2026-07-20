import streamlit as st  # Web arayüzü oluşturmak için gerekli kütüphane
import pandas as pd      # Veri manipülasyonu ve Excel işlemleri için
import numpy as np       # Matematiksel hesaplamalar ve dizi işlemleri için
import io                # Bellek üzerinde Excel dosyası oluşturmak için
import json              # Kural setlerini kaydetmek/yüklemek için
from datetime import datetime  # Tarih hesaplamaları için

# Web arayüzü düzenini geniş (wide) olarak ayarla
st.set_page_config(page_title="RPT HESAPLAMA PROGRAMI", layout="wide", initial_sidebar_state="expanded")

# Arayüzden gereksiz Streamlit öğelerini (footer, menü) gizlemek için CSS
hide_streamlit_style = """
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} .stDeployButton {display:none;}
    button[kind="header"] {display: none;}
    [data-testid="stDataFrame"] {color: #000000 !important;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- GÜVENLİK ---
# Uygulamaya şifreli giriş koruması (DÜZELTME: yanlış şifre girildiğinde artık uyarı gösteriliyor)
if "password_correct" not in st.session_state:
    girilen_sifre = st.text_input("🔒 Şifreyi girin:", type="password", key="password")
    if girilen_sifre:
        if girilen_sifre == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Şifre yanlış. Tekrar deneyin.")
    st.stop()

st.title("📦 RPT HESAPLAMA PROGRAMI")

# --- YARDIMCI FONKSİYONLAR ---
BEKLENEN_KOLONLAR = ['Ürün Kodu', 'Toplam Stok', 'Son 3 Ay Ort Satış', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı']

@st.cache_data(show_spinner=False)
def veriyi_yukle(dosya_bytes):
    """Excel dosyasını okur ve gerekli kolon isimlerini standardize eder.
    DÜZELTME: artık eksik kolon / bozuk dosya durumunda kullanıcıya anlaşılır hata veriyor,
    uygulamayı çökertmek yerine None döndürüyor."""
    try:
        df = pd.read_excel(io.BytesIO(dosya_bytes), header=1)
    except Exception as e:
        st.error(f"❌ Excel dosyası okunamadı: {e}")
        return None

    df = df.rename(columns={
        'Ürün Kodu': 'SKU',
        'Toplam Stok': 'Acilis_Stogu',
        'Son 3 Ay Ort Satış': 'Son_3_Ay_Ort_Satis'
    })

    eksik = [k for k in ['SKU', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı'] if k not in df.columns]
    if eksik:
        st.error(f"❌ Excel dosyasında beklenen kolonlar eksik: {', '.join(eksik)}\n\n"
                 f"Beklenen kolon isimleri: {', '.join(BEKLENEN_KOLONLAR)}")
        return None

    # Veri kalitesi uyarısı: satış verisi tamamen boş olan satır sayısı
    eksik_satis_sayisi = df['Son_3_Ay_Ort_Satis'].isna().sum()
    if eksik_satis_sayisi > 0:
        st.warning(f"⚠️ {eksik_satis_sayisi} satırda satış verisi boş. Bu satırlar 0 satış olarak "
                   f"hesaplanacak, RPT ihtiyacı yanlış çıkabilir — kaynak veriyi kontrol edin.")
    return df


def hesapla_rpt(df, aylar_sim, mevsimsellik, h_gun, m_moq, v_kat, lead):
    """Her ay için RPT (sipariş ihtiyacı) ve kapanış stoğunu hesaplar.

    DÜZELTME (mevsimsellik): Hedef stok artık sadece 'ortalama satış' değil,
    o ayın mevsimsellik katsayısıyla çarpılmış BEKLENEN satışa göre hesaplanıyor.
    Böylece örneğin Kasım'a (katsayı 1.80) girerken hedef stok da yüksek sezona
    göre büyütülüyor; eskiden hedef hep 'ortalama satış' baz alınıyordu ve
    yüksek sezon öncesi ihtiyaç olduğundan düşük çıkabiliyordu.

    Lead time mantığı: RPT, o ay için varış hedefi/adedi olarak yazılıyor
    (kullanıcının onayladığı şekilde) — sipariş, o ayda depoya varması
    planlanan miktar olarak ele alınıyor.
    """
    devreden = df['Acilis_Stogu'].fillna(0).to_numpy(float)
    ort_satis = df['Son_3_Ay_Ort_Satis'].fillna(0).to_numpy(float)

    for i, ay in enumerate(aylar_sim):
        kat = mevsimsellik.get(ay, 1.0)
        beklenen_satis = ort_satis * kat  # o ayki mevsimselliğe göre beklenen satış
        baslangic = devreden + (df[int(ay)].fillna(0).to_numpy(float) if int(ay) in df.columns else np.zeros(len(df)))

        # DÜZELTME: hedef stok hesaplamasında ort_satis yerine beklenen_satis kullanılıyor
        hedef_stok = (h_gun / 30.0) * beklenen_satis
        ihtiyac = hedef_stok - baslangic

        rpt = np.where(
            i >= lead,
            np.where(
                ihtiyac <= 0, 0,
                np.where(ihtiyac <= m_moq, m_moq, np.ceil(ihtiyac / v_kat) * v_kat)
            ),
            0
        )
        df[f'{ay}_RPT'] = rpt
        df[f'{ay}_Kapanis_Stogu'] = np.maximum(baslangic + rpt - beklenen_satis, 0)
        df[f'{ay}_Cover_Gun'] = np.where(ort_satis > 0, ((baslangic + rpt) / ort_satis) * 30, 999)
        devreden = df[f'{ay}_Kapanis_Stogu'].to_numpy()

    return df


# Kural yönetimi için session_state tanımları
if "gecici_kurallar" not in st.session_state: st.session_state["gecici_kurallar"] = []
if "aktif_kurallar" not in st.session_state: st.session_state["aktif_kurallar"] = []

# --- TAKVİM (18 AYLIK DÖNGÜ) ---
bugun = datetime.now()
aylar_sim = []
default_katsayilar = []
aylik_katsayilar = {1: 1.35, 2: 1.35, 3: 1.25, 4: 1.20, 5: 1.10, 6: 1.00, 7: 1.00, 8: 1.00, 9: 1.25, 10: 1.40, 11: 1.80, 12: 1.40}

for i in range(18):
    d = datetime(bugun.year, bugun.month, 1) + pd.DateOffset(months=i)
    aylar_sim.append(d.strftime("%Y%m"))
    default_katsayilar.append(aylik_katsayilar.get(d.month, 1.0))

# DÜZELTME: periyot listesi artık dinamik üretiliyor (2027Q4'e kadar), hardcoded 3 çeyrekle sınırlı değil
def ceyrek_uret(aylar):
    periyotlar = {}
    for ay in aylar:
        yil, ay_no = int(ay[:4]), int(ay[4:])
        q = (ay_no - 1) // 3 + 1
        anahtar = f"{yil}Q{q}"
        periyotlar.setdefault(anahtar, []).append(ay)
    return periyotlar

periyotlar = ceyrek_uret(aylar_sim)

# --- SIDEBAR (PARAMETRELER) ---
with st.sidebar:
    st.header("⚙️ Genel Parametreler")

    with st.form("parametre_formu"):
        v_hedef = st.number_input("Genel Hedef Cover", 150, step=10)
        v_moq = st.number_input("Genel MOQ", 250, step=50)
        v_kat = st.number_input("Katsayı (Sipariş Yuvarlama Katı)", 50, step=10)
        lead = st.number_input("Tedarik Süresi (ay)", 3, step=1)
        hesapla_butonu = st.form_submit_button("🔄 Parametreleri Uygula / Hesapla")

    st.markdown("---")
    st.subheader("Ürün Grubu Özel Parametreler")

    # DÜZELTME: ürün grubu listesi artık yüklenen dosyadan dinamik çekiliyor.
    # Dosya henüz yüklenmediyse boş liste gösteriliyor.
    grup_listesi = sorted(st.session_state.get("urun_gruplari", []))
    if grup_listesi:
        secilen_grup = st.selectbox("Grup Seçin", grup_listesi)
        ozel_cover = st.number_input("Özel Cover", 120, step=10)
        ozel_moq = st.number_input("Özel MOQ", 100, step=50)

        if st.button("➕ Kural Ekle"):
            if any(k["Ürün Grubu"] == secilen_grup for k in st.session_state["gecici_kurallar"]):
                st.error("❌ Bu grup zaten listede!")
            else:
                st.session_state["gecici_kurallar"].append({"Ürün Grubu": secilen_grup, "Cover": ozel_cover, "MOQ": ozel_moq})
                st.rerun()

        if st.session_state["gecici_kurallar"]:
            for i, k in enumerate(st.session_state["gecici_kurallar"]):
                cols = st.columns([1, 4, 2, 2])
                if cols[0].button("➖", key=f"del_{i}"):
                    st.session_state["gecici_kurallar"].pop(i)
                    st.rerun()
                cols[1].write(k["Ürün Grubu"]); cols[2].write(k["Cover"]); cols[3].write(k["MOQ"])
            if st.button("✅ Kuralları Onayla"):
                st.session_state["aktif_kurallar"] = st.session_state["gecici_kurallar"].copy()
                st.success("Kurallar ayarlandı!")

        # YENİ: Kural setlerini JSON olarak kaydet / yükle
        st.markdown("---")
        st.caption("Kural setini kaydet / yükle")
        kural_json = json.dumps(st.session_state["aktif_kurallar"], ensure_ascii=False)
        st.download_button("💾 Kuralları İndir (JSON)", kural_json, "rpt_kurallari.json")
        yuklenen_kural = st.file_uploader("📂 Kural Dosyası Yükle", type=['json'], key="kural_yukle")
        if yuklenen_kural is not None:
            try:
                st.session_state["aktif_kurallar"] = json.loads(yuklenen_kural.read())
                st.success("Kurallar yüklendi!")
            except Exception as e:
                st.error(f"Kural dosyası okunamadı: {e}")
    else:
        st.info("Ürün grubu listesi için önce bir Excel dosyası yükleyin.")

    st.markdown("---")
    mevsimsellik_df = st.data_editor(
        pd.DataFrame({"Ay": aylar_sim, "Katsayi": default_katsayilar}),
        hide_index=True, key="mevsim_editor"
    )
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))

# --- ANA AKIŞ ---
yuklenen_dosya = st.file_uploader("Rapor Data Excel Dosyasını Yükleyin (.xlsx)", type=['xlsx'])

if yuklenen_dosya:
    df = veriyi_yukle(yuklenen_dosya.getvalue())

    if df is not None:
        # Ürün grubu listesini session_state'e yaz (sidebar bir sonraki rerun'da bunu kullanacak)
        st.session_state["urun_gruplari"] = df['Ürün Grubu'].dropna().unique().tolist()

        # Genel ve özel parametreleri array olarak eşleştir
        h_gun, m_moq = np.full(len(df), v_hedef, float), np.full(len(df), v_moq, float)
        for k in st.session_state["aktif_kurallar"]:
            mask = df['Ürün Grubu'] == k["Ürün Grubu"]
            h_gun[mask], m_moq[mask] = float(k["Cover"]), float(k["MOQ"])

        df = hesapla_rpt(df, aylar_sim, mevsimsellik, h_gun, m_moq, v_kat, lead)

        # EKRANDA ÖZET TABLO (artık tüm periyotları kapsıyor: 2027Q4'e kadar)
        st.markdown("---")
        st.header("📊 Kategori Bazlı En Yüksek 5 RPT İhtiyacı")

        ozet_listesi = []
        for kat in df['Ana Kategori'].dropna().unique():
            df_kat = df[df['Ana Kategori'] == kat].copy()
            for q, aylik_liste in periyotlar.items():
                cols_r = [f"{a}_RPT" for a in aylik_liste if f"{a}_RPT" in df_kat.columns]
                if cols_r:
                    df_kat[f"{q}_RPT"] = df_kat[cols_r].sum(axis=1)
                    for _, row in df_kat[df_kat[f"{q}_RPT"] > 0].nlargest(5, f"{q}_RPT").iterrows():
                        ozet_listesi.append({
                            "Kategori": kat, "Ürün Grubu": row['Ürün Grubu'], "Stok Kodu": row['SKU'],
                            "Stok Adı": row['Ürün Adı'], "Periyot": q, "Adet": row[f"{q}_RPT"]
                        })

        if ozet_listesi:
            st.dataframe(
                pd.DataFrame(ozet_listesi).pivot_table(
                    index=['Kategori', 'Ürün Grubu', 'Stok Kodu', 'Stok Adı'],
                    columns='Periyot', values='Adet', fill_value=0
                ),
                use_container_width=True
            )
        else:
            st.info("Bu parametrelerle hiçbir üründe RPT ihtiyacı oluşmadı.")

        # EXCEL ÇIKTISI (biçimlendirmeli: kritik cover günü kırmızı vurgulu)
        cols = ['SKU', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis'] + \
               [f"{ay}_Kapanis_Stogu" for ay in aylar_sim] + [f"{ay}_Cover_Gun" for ay in aylar_sim] + [f"{ay}_RPT" for ay in aylar_sim]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df[cols].to_excel(writer, index=False, sheet_name='RPT')
            workbook = writer.book
            worksheet = writer.sheets['RPT']

            # YENİ: kolon genişlikleri ve başlık biçimlendirmesi
            baslik_format = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1})
            for idx, col in enumerate(cols):
                worksheet.write(0, idx, col, baslik_format)
                worksheet.set_column(idx, idx, max(12, len(col) + 2))
            worksheet.freeze_panes(1, 4)  # ilk 4 kolonu ve başlık satırını dondur

            # YENİ: Cover gün 30'un altındaysa kırmızı, 200'ün üstündeyse mavi vurgula (kritik / fazla stok)
            kritik_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            fazla_format = workbook.add_format({'bg_color': '#DDEBF7', 'font_color': '#1F4E78'})
            cover_start = 6 + len(aylar_sim)
            for j, ay in enumerate(aylar_sim):
                col_idx = cover_start + j
                worksheet.conditional_format(1, col_idx, len(df), col_idx,
                                              {'type': 'cell', 'criteria': '<', 'value': 30, 'format': kritik_format})
                worksheet.conditional_format(1, col_idx, len(df), col_idx,
                                              {'type': 'cell', 'criteria': '>', 'value': 200, 'format': fazla_format})

        st.download_button("📥 RPT Exceli İndir", output.getvalue(), "rpt_raporu.xlsx")
