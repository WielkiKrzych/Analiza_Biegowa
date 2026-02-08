import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def render_hemo_tab(target_df):
    st.header("Profil Hemodynamiczny (Mechanika vs Metabolizm)")
    st.markdown(
        "Analiza relacji objętości krwi (THb) do saturacji (SmO2). Pozwala wykryć okluzję (ucisk) i limitery przepływu."
    )

    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik.")
        return

    col_thb = next(
        (c for c in ["thb", "total_hemoglobin", "total_hgb"] if c in target_df.columns), None
    )
    col_smo2 = (
        "smo2_smooth" if "smo2_smooth" in target_df else ("smo2" if "smo2" in target_df else None)
    )

    if col_thb and col_smo2:
        if f"{col_thb}_smooth" not in target_df.columns:
            target_df[f"{col_thb}_smooth"] = (
                target_df[col_thb].rolling(window=10, center=True).mean()
            )

        thb_val = f"{col_thb}_smooth"

        if "smo2" in target_df.columns:
            target_df["smo2_smooth_10s_hemo_trend"] = (
                target_df["smo2"].rolling(window=10, center=True).mean()
            )
            col_smo2_hemo_trend = "smo2_smooth_10s_hemo_trend"
        else:
            col_smo2_hemo_trend = col_smo2

        # 2. Wykres XY (Scatter) - SmO2 vs THb
        # Kolorujemy punktami Mocy, żeby widzieć co się dzieje na wysokich watach

        # Próbkowanie dla szybkości (oryginalne zachowanie)
        df_hemo = target_df.sample(min(len(target_df), 5000))

        fig_hemo = px.scatter(
            df_hemo,
            x=col_smo2,
            y=thb_val,
            color="watts" if "watts" in df_hemo.columns else None,
            title="Hemo-Scatter: SmO2 (Oś X) vs THb (Oś Y)",
            labels={
                col_smo2: "SmO2 (Saturacja) [%]",
                thb_val: "THb (Objętość Krwi) [a.u.]",
                "watts": "Moc [W]",
            },
            hover_data={
                col_smo2: ":.1f",
                thb_val: ":.1f",
                "watts": ":.0f" if "watts" in df_hemo.columns else False,
            },
            template="plotly_dark",
            color_continuous_scale="Turbo",
        )

        # Odwracamy oś X dla SmO2 (zwyczajowo w fizjologii wykresy czyta się od prawej do lewej dla desaturacji)
        fig_hemo.update_xaxes(autorange="reversed")

        fig_hemo.update_traces(marker=dict(size=5, opacity=0.6))
        fig_hemo.update_layout(height=600, margin=dict(l=20, r=20, t=40, b=20))

        # Dodajemy adnotacje "ćwiartek" (Uproszczona interpretacja)
        # To wymagałoby znania średnich, ale damy opisy w rogach
        fig_hemo.add_annotation(
            xref="paper",
            yref="paper",
            x=0.05,
            y=0.95,
            text="<b>Stres Metaboliczny</b><br>(Wazodylatacja)",
            showarrow=False,
            font=dict(color="#00cc96"),
        )
        fig_hemo.add_annotation(
            xref="paper",
            yref="paper",
            x=0.05,
            y=0.05,
            text="<b>OKLUZJA / UCISK</b><br>(Limit Przepływu)",
            showarrow=False,
            font=dict(color="#ef553b"),
        )
        fig_hemo.add_annotation(
            xref="paper",
            yref="paper",
            x=0.95,
            y=0.95,
            text="<b>Regeneracja</b><br>(Napływ)",
            showarrow=False,
            font=dict(color="#ffa15a"),
        )

        st.plotly_chart(fig_hemo, use_container_width=True)

        # 3. Wykres Liniowy w czasie (Dual Axis)
        st.subheader("Trendy w Czasie (Szukanie Rozjazdu)")

        # Prepare time formatting for hover
        if "time" in target_df.columns:
            time_str_trend = pd.to_datetime(target_df["time"], unit="s").dt.strftime("%H:%M:%S")
        else:
            time_str_trend = target_df["time_min"].apply(
                lambda x: f"{int(x // 60):02d}:{int(x % 60):02d}:00"
            )

        fig_trend = go.Figure()

        # SmO2 (Oś Lewa)
        fig_trend.add_trace(
            go.Scatter(
                x=target_df["time_min"],
                y=target_df[col_smo2_hemo_trend],
                customdata=time_str_trend,
                name="SmO2",
                line=dict(color="#ab63fa", width=2),
                hovertemplate="<b>Czas:</b> %{customdata}<br><b>SmO2:</b> %{y:.1f}%<extra></extra>",
            )
        )

        # THb (Oś Prawa)
        fig_trend.add_trace(
            go.Scatter(
                x=target_df["time_min"],
                y=target_df[thb_val],
                customdata=time_str_trend,
                name="THb",
                line=dict(color="#ffa15a", width=2),
                yaxis="y2",
                hovertemplate="<b>Czas:</b> %{customdata}<br><b>THb:</b> %{y:.2f} g/dL<extra></extra>",
            )
        )

        # Tło - Moc (dla kontekstu)
        if "watts_smooth_30s" in target_df:
            fig_trend.add_trace(
                go.Scatter(
                    x=target_df["time_min"],
                    y=target_df["watts_smooth_30s"],
                    name="Moc",
                    line=dict(color="rgba(255,255,255,0.1)", width=1),
                    fill="tozeroy",
                    fillcolor="rgba(255,255,255,0.05)",
                    yaxis="y3",
                    hoverinfo="skip",
                )
            )

        # Poprawiony Layout dla fig_trend (bez titlefont)
        fig_trend.update_layout(
            template="plotly_dark",
            title="SmO2 vs THb w Czasie",
            xaxis=dict(title="Czas [min]", tickformat=".0f", hoverformat=".0f"),
            hovermode="x unified",
            yaxis=dict(title=dict(text="SmO2 [%]", font=dict(color="#ab63fa"))),
            yaxis2=dict(
                title=dict(text="THb [g/dL]", font=dict(color="#ffa15a")),
                overlaying="y",
                side="right",
            ),
            yaxis3=dict(
                title="Moc", overlaying="y", side="right", showgrid=False, showticklabels=False
            ),
            height=450,
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # 4. Teoria dla Fizjologii
        st.info("""
        **💡 Interpretacja Hemodynamiczna (THb + SmO2):**
        
        THb (Total Hemoglobin) to wskaźnik objętości krwi ("tHb = pompa paliwowa"). SmO2 to wskaźnik zużycia ("SmO2 = bak").
        
        * **Scenariusz 1: Dobra praca (Wazodylatacja)**
            * **SmO2 SPADA 📉 | THb ROŚNIE 📈**
            * *Co to znaczy:* Mięsień pracuje mocno, metabolizm zużywa tlen, ale układ krążenia reaguje prawidłowo, rozszerzając naczynia i pompując więcej krwi. To zdrowy limit metaboliczny.
        
        * **Scenariusz 2: Okluzja / Limit Mechaniczny (UWAGA!)**
            * **SmO2 SPADA 📉 | THb SPADA 📉 (lub płaskie)**
            * *Co to znaczy:* "Wyżymanie gąbki". Napięcie mięśnia jest tak duże (lub kadencja za niska), że ciśnienie wewnątrzmięśniowe blokuje dopływ świeżej krwi.
            * *Działanie:* Zwiększ kadencję, sprawdź siodełko (czy nie uciska tętnic), popraw fit.
        
        * **Scenariusz 3: Venous Pooling (Zastój)**
            * **SmO2 ROŚNIE 📈 | THb ROŚNIE 📈**
            * *Kiedy:* Często podczas nagłego zatrzymania po wysiłku. Krew napływa, ale pompa mięśniowa nie odprowadza jej z powrotem.
        """)

    else:
        st.warning(
            "⚠️ Brak danych THb (Total Hemoglobin). Sensor Moxy/Train.Red powinien dostarczać tę kolumnę (często jako 'thb' lub 'total_hemoglobin'). Bez tego analiza hemodynamiczna jest niemożliwa."
        )
        st.markdown("Dostępne kolumny w pliku: " + ", ".join(target_df.columns))
