# ... (Kodun üst kısımları, Sidebar ve Simülasyon fonksiyonu aynı)

    run(df)
    
    # 1. ÖZET TABLOYU ARAYÜZDE GÖSTER (Renksiz, sade)
    st.markdown("---")
    st.header("📊 Kategori Bazlı 3 Aylık En Yüksek 5 RPT İhtiyacı")
    periyotlar = {
        "2026Q3": ["202607", "202608", "202609"], "2026Q4": ["202610", "202611", "202612"],
        "2027Q1": ["202701", "202702", "202703"], "2027Q2": ["202704", "202705", "202706"]
    }
    ozet_listesi = []
    for kategori in df['Ana Kategori'].unique():
        df_kat = df[df['Ana Kategori'] == kategori].copy()
        for q, aylik_liste in periyotlar.items():
            col_names = [f"{a}_RPT" for a in aylik_liste if f"{a}_RPT" in df_kat.columns]
            if col_names:
                df_kat[f"{q}_Top_RPT"] = df_kat[col_names].sum(axis=1)
                top_5 = df_kat[df_kat[f"{q}_Top_RPT"] > 0].nlargest(5, f"{q}_Top_RPT")
                for _, row in top_5.iterrows():
                    ozet_listesi.append({"Ana Kategori": kategori, "Ürün Grubu": row['Ürün Grubu'], "Stok Kodu": row['SKU'], "Stok Adı": row['Ürün Adı'], "Periyot": q, "RPT Adeti": row[f"{q}_Top_RPT"]})
    
    if ozet_listesi:
        pivot_df = pd.DataFrame(ozet_listesi).pivot_table(index=['Ana Kategori', 'Ürün Grubu', 'Stok Kodu', 'Stok Adı'], columns='Periyot', values='RPT Adeti', fill_value=0)
        st.dataframe(pivot_df, use_container_width=True)

    # 2. ANA TABLOYU GÖSTER
    st.markdown("---")
    cols = ['SKU', 'Ana Kategori', 'Ürün Grubu', 'Ürün Adı', 'Acilis_Stogu', 'Son_3_Ay_Ort_Satis'] + \
           [f"{ay}_Beklenen_Satis" for ay in aylar_sim] + [f"{ay}_Kapanis_Stogu" for ay in aylar_sim] + \
           [f"{ay}_Cover_Gun" for ay in aylar_sim] + [f"{ay}_RPT" for ay in aylar_sim]
    st.dataframe(df[cols], use_container_width=True)
    
    # 3. SADECE ANA TABLOYU EXCEL'E AKTAR
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, sheet_name='RPT_Raporu', index=False)
    
    st.download_button("📥 RPT Exceli İndir", output.getvalue(), f"{datetime.now().strftime('%d.%m.%y')}_rpt_dosyası.xlsx")
