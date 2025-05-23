import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openai import OpenAI
import matplotlib.dates as mdates

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

TRAD = {
    "es": {
        "title": "📊 Generador de Resumen Macroeconómico",
        "address": "Introduce una dirección europea:",
        "words": "Número de palabras en el resumen:",
        "kpis": "Selecciona los indicadores a incluir:",
        "generate": "Generar resumen",
        "results": "📊 Resultados por indicador",
        "conclusion_es": "🧠 Conclusión final – ES",
        "conclusion_en": "🧠 Final conclusion – EN",
        "error_country": "❌ No se pudo detectar el país."
    },
    "en": {
        "title": "📊 Macroeconomic Summary Generator",
        "address": "Enter a European address:",
        "words": "Number of words in the summary:",
        "kpis": "Select indicators to include:",
        "generate": "Generate summary",
        "results": "📊 Results by indicator",
        "conclusion_es": "🧠 Final conclusion – ES",
        "conclusion_en": "🧠 Final conclusion – EN",
        "error_country": "❌ Could not detect the country."
    }
}

idioma_ui = st.selectbox("🌐 Select interface language / Selecciona idioma de la interfaz:", ["es", "en"])
ui = TRAD[idioma_ui]

st.title(ui["title"])
direccion = st.text_input(ui["address"])
longitud = st.slider(ui["words"], 100, 300, 150, step=25)
idioma_resumen = st.radio("Idioma del resumen / Summary language", ["español", "english"])
idioma_resumen_cod = "es" if idioma_resumen == "español" else "en"

kpis_seleccionados = st.multiselect(
    ui["kpis"],
    ["HICP – Harmonized Inflation", "GDP – Gross Domestic Product", "Unemployment Rate", "Government Bond Yield – 10Y"]
)

def obtener_codigo_pais(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "macro-app/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers)
        data = r.json()
        if data:
            return data[0]["address"].get("country_code", "").upper()
    except:
        return None

def mostrar_grafico(df, titulo, color_linea, unidad_y):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(df["Periodo"], df["Valor"], color=color_linea, linewidth=2)
    ticks = [p for i, p in enumerate(df["Periodo"]) if "-Q1" in p or "-01" in p]
    ax.set_xticks(ticks)
    ax.set_xticklabels(ticks, rotation=0, fontsize=8)
    ax.set_title(titulo, fontsize=12)
    ax.set_ylabel(unidad_y)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.rcParams.update({
        'text.color': '#333333',
        'axes.labelcolor': '#333333',
        'xtick.color': '#333333',
        'ytick.color': '#333333',
        'axes.edgecolor': '#CCCCCC',
    })
    st.pyplot(fig)

if st.button(ui["generate"]) and direccion and kpis_seleccionados:
    codigo_pais = obtener_codigo_pais(direccion)
    if not codigo_pais:
        st.error(ui["error_country"])
    else:
        nombre_pais = {
            "NL": "Países Bajos", "ES": "España", "FR": "Francia",
            "IT": "Italia", "DE": "Alemania", "BE": "Bélgica"
        }.get(codigo_pais, f"País ({codigo_pais})")

        anio_corte = datetime.today().year - 5
        texto_kpis = ""
        parrafos = []

        def obtener_df(dataset, extra_params, periodo="Q"):
            url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
            params = {"format": "JSON", "lang": "EN", "geo": codigo_pais}
            params.update(extra_params)
            r = requests.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            idx = data["dimension"]["time"]["category"]["index"]
            lbl = data["dimension"]["time"]["category"]["label"]
            ix_map = {str(v): lbl[k] for k, v in idx.items()}
            valores = [{"Periodo": ix_map[k], "Valor": v} for k, v in data["value"].items()]
            df = pd.DataFrame(valores)
            df = df[df["Periodo"].str[:4].astype(int) >= anio_corte]
            df["Periodo"] = pd.PeriodIndex(df["Periodo"], freq=periodo).astype(str)
            return df

        try:
            if "HICP – Harmonized Inflation" in kpis_seleccionados:
                df_hicp = obtener_df("prc_hicp_midx", {"coicop": "CP00", "unit": "I15"})
                texto_kpis += f"\n\n📌 HICP – Harmonized Inflation:\n{df_hicp.to_string(index=False)}"

            if "GDP – Gross Domestic Product" in kpis_seleccionados:
                df_pib = obtener_df("namq_10_gdp", {"na_item": "B1GQ", "unit": "CLV10_MNAC", "s_adj": "NSA"})
                texto_kpis += f"\n\n📌 GDP – Gross Domestic Product:\n{df_pib.to_string(index=False)}"

            if "Unemployment Rate" in kpis_seleccionados:
                df_unemp = obtener_df("une_rt_m", {
                    "unit": "PC_ACT", "sex": "T", "age": "TOTAL", "s_adj": "SA"
                }, periodo="M")
                texto_kpis += f"\n\n📌 Unemployment Rate:\n{df_unemp.to_string(index=False)}"

            if "Government Bond Yield – 10Y" in kpis_seleccionados:
                zona_euro = {
                    "AT","BE","CY","EE","FI","FR","DE","GR","IE","IT",
                    "LV","LT","LU","MT","NL","PT","SK","SI","ES","HR"
                }
                divisas_no_euro = {
                    "BG": "BGN", "CZ": "CZK", "DK": "DKK", "HU": "HUF",
                    "PL": "PLN", "RO": "RON", "SE": "SEK"
                }
                if codigo_pais in zona_euro:
                    divisa = "EUR"
                elif codigo_pais in divisas_no_euro:
                    divisa = divisas_no_euro[codigo_pais]
                else:
                    raise Exception("No hay datos de bonos para este país.")

                serie_bce = f"M.{codigo_pais}.L.L40.CI.0000.{divisa}.N.Z"
                url = f"https://data-api.ecb.europa.eu/service/data/IRS/{serie_bce}?format=csvdata&startPeriod={anio_corte}-01"
                r = requests.get(url)
                r.raise_for_status()
                df_bonos = pd.read_csv(StringIO(r.text))
                df_bonos = df_bonos[["TIME_PERIOD", "OBS_VALUE"]].rename(
                    columns={"TIME_PERIOD": "Periodo", "OBS_VALUE": "Valor"}
                )
                df_bonos["Periodo"] = pd.to_datetime(df_bonos["Periodo"]).dt.to_period("M").astype(str)
                texto_kpis += f"\n\n📌 Government Bond Yield – 10Y:\n{df_bonos.to_string(index=False)}"

            prompt = f"""
{"Eres un economista. Redacta" if idioma_resumen_cod == "es" else "You are an economist. Write"} a technical macroeconomic summary of approximately {longitud} words for {nombre_pais}, using the following data from Eurostat and ECB:

{texto_kpis}

{"Escribe un párrafo por indicador y concluye con uno final que los relacione." if idioma_resumen_cod == "es" else "Write one paragraph per indicator and end with a concluding paragraph that links them."}
"""

            respuesta = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6
            )

            parrafos = respuesta.choices[0].message.content.strip().split("\n\n")
            st.markdown(f"## {ui['results']}")
            idx = 0

            if "HICP – Harmonized Inflation" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    mostrar_grafico(df_hicp, "HICP – Harmonized Inflation", "#DAA520", "Índice")
                with col2:
                    st.write(parrafos[idx])
                    idx += 1

            if "GDP – Gross Domestic Product" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    mostrar_grafico(df_pib, "GDP – Gross Domestic Product", "#4682B4", "Volumen")
                with col2:
                    st.write(parrafos[idx])
                    idx += 1

            if "Unemployment Rate" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    mostrar_grafico(df_unemp, "Unemployment Rate", "#2F4F4F", "%")
                with col2:
                    st.write(parrafos[idx])
                    idx += 1

            if "Government Bond Yield – 10Y" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    mostrar_grafico(df_bonos, "Bond Yield – 10Y", "#8B4513", "%")
                with col2:
                    st.write(parrafos[idx])
                    idx += 1

            st.markdown("## 🧩 " + (ui["conclusion_es"] if idioma_resumen_cod == "es" else ui["conclusion_en"]))
            st.write(parrafos[-1])

        except Exception as e:
            st.error(f"❌ Error al procesar: {e}")




