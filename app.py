# --- TAKVİM HESAPLAMASI (GÜNCELLENMİŞ) ---
    bugun = datetime.now()
    aylar_sim = []
    default_katsayilar = []
    
    # 12 aylık katsayı sözlüğü
    aylik_katsayilar = {1: 1.35, 2: 1.35, 3: 1.25, 4: 1.20, 5: 1.10, 6: 1.00, 7: 1.00, 8: 1.00, 9: 1.25, 10: 1.40, 11: 1.80, 12: 1.40}
    
    for i in range(18): # 18 ay (2027 sonuna kadar)
        d = datetime(bugun.year, bugun.month, 1) + pd.DateOffset(months=i)
        aylar_sim.append(d.strftime("%Y%m"))
        # Ayın katsayısını sözlükten çek
        default_katsayilar.append(aylik_katsayilar.get(d.month, 1.0))
    
    st.markdown("---")
    st.subheader("Mevsimsellik Katsayıları")
    # Tabloya default_katsayilar değerlerini varsayılan olarak veriyoruz
    mevsimsellik_df = st.data_editor(pd.DataFrame({"Ay": aylar_sim, "Katsayi": default_katsayilar}), hide_index=True, key="mevsim_editor")
    mevsimsellik = dict(zip(mevsimsellik_df["Ay"], mevsimsellik_df["Katsayi"]))
