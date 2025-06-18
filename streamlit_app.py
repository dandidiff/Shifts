import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import numpy as np
import os
import plotly.graph_objects as go

st.set_page_config(page_title="Analisi Turnazioni vs Vendite", layout="wide")

st.title("Streamlit Analisi Turnazioni vs Vendite")

# Carica i dati di vendita storici da file CSV
sales_df = pd.read_csv('vendite.csv')
sales_df['data'] = pd.to_datetime(sales_df['data'], dayfirst=True)

# Lista dei negozi
negozi_lista = [
    "BHR", "MAD", "BIR", "SRV", "LBM", "PAR", "ROM", "MIL", "ECI", "NBS", "STT", "CAP", "FLO", "NYC", "MAR", "GLA", "LRM", "BMP", "CAS"
]

negozio_scelto = st.sidebar.selectbox("Seleziona il negozio da analizzare", negozi_lista)

# Function to analyze scheduling vs sales
def analyze_scheduling(sales_df, schedule_df):
    # Add day of week to sales data
    sales_df['giorno_settimana'] = sales_df['data'].dt.day_name()
    
    # Calculate average sales by day of week
    avg_sales_by_day = sales_df.groupby('giorno_settimana')['vendite'].mean()
    
    # Add day of week to schedule data
    schedule_df['giorno_settimana'] = pd.to_datetime(schedule_df['data']).dt.day_name()
    
    # Calculate staff count by day
    staff_by_day = schedule_df.groupby('giorno_settimana')['num_persone'].sum()
    
    # Calculate sales per staff member
    sales_per_staff = avg_sales_by_day / staff_by_day
    
    # Identify anomalies (days with significantly different sales/staff ratio)
    mean_sales_per_staff = sales_per_staff.mean()
    std_sales_per_staff = sales_per_staff.std()
    
    anomalies = []
    for day in sales_per_staff.index:
        ratio = sales_per_staff[day]
        if abs(ratio - mean_sales_per_staff) > 1.5 * std_sales_per_staff:
            anomalies.append({
                'giorno': day,
                'vendite_medie': avg_sales_by_day[day],
                'staff_programmato': staff_by_day[day],
                'vendite_per_persona': ratio,
                'deviazione': (ratio - mean_sales_per_staff) / std_sales_per_staff
            })
    
    return pd.DataFrame(anomalies)

# Function to analyze scheduling vs sales per DATA
def analyze_scheduling_by_date(sales_df, schedule_df):
    # Merge vendite e persone per data
    vendite_per_data = sales_df.groupby('data')['vendite'].sum().reset_index()
    persone_per_data = schedule_df.groupby('data')['num_persone'].sum().reset_index()
    merged = pd.merge(vendite_per_data, persone_per_data, on='data', how='inner')
    merged['vendite_per_persona'] = merged['vendite'] / merged['num_persone']
    # Calcolo media e std
    mean_ratio = merged['vendite_per_persona'].mean()
    std_ratio = merged['vendite_per_persona'].std()
    # Anomalia: rapporto molto diverso dalla media
    anomalies = merged[abs(merged['vendite_per_persona'] - mean_ratio) > 1.5 * std_ratio].copy()
    anomalies['deviazione_std'] = (anomalies['vendite_per_persona'] - mean_ratio) / std_ratio
    return anomalies[['data', 'vendite', 'num_persone', 'vendite_per_persona', 'deviazione_std']]

def week_of_month(dt):
    first_day = dt.replace(day=1)
    dom = dt.day
    adjusted_dom = dom + first_day.weekday()
    return int((adjusted_dom - 1) / 7) + 1

# Funzione per preparare i dati per confronto per settimana e giorno della settimana
def prepare_weekday_week_data(df, date_col):
    df = df.copy()
    df['mese'] = df[date_col].dt.month
    df['anno'] = df[date_col].dt.year
    df['giorno_settimana'] = df[date_col].dt.day_name()
    df['settimana_mese'] = df[date_col].apply(week_of_month)
    df['num_persone'] = 1  # Ogni riga = una persona
    return df

# Funzione di analisi allineata per settimana e giorno della settimana
def analyze_by_weekday_week(sales_df, schedule_df):
    vendite = prepare_weekday_week_data(sales_df, 'data')
    turni = prepare_weekday_week_data(schedule_df, 'data')
    # Media vendite storiche per combinazione
    vendite_grouped = vendite.groupby(['mese', 'giorno_settimana', 'settimana_mese'])['vendite'].mean().reset_index()
    # Media persone programmate per combinazione
    turni_grouped = turni.groupby(['mese', 'giorno_settimana', 'settimana_mese'])['num_persone'].sum().reset_index()
    # Merge
    merged = pd.merge(vendite_grouped, turni_grouped, on=['mese', 'giorno_settimana', 'settimana_mese'], how='outer').fillna(0)
    merged['vendite_per_persona'] = merged['vendite'] / merged['num_persone'].replace(0, np.nan)
    # Anomalia: rapporto molto diverso dalla media
    mean_ratio = merged['vendite_per_persona'].mean()
    std_ratio = merged['vendite_per_persona'].std()
    merged['deviazione_std'] = (merged['vendite_per_persona'] - mean_ratio) / std_ratio
    anomalies = merged[abs(merged['vendite_per_persona'] - mean_ratio) > 1.5 * std_ratio]
    return merged, anomalies

# Analisi: confronto turni con media vendite storiche per combinazione (mese, settimana, giorno)
def analyze_turni_vs_vendite(sales_df, schedule_df):
    # Prepara turni: una riga per data, con persone programmate
    turni = schedule_df.copy()
    turni['mese'] = turni['data'].dt.month
    turni['settimana_mese'] = turni['data'].apply(week_of_month)
    turni['giorno_settimana'] = turni['data'].dt.day_name()
    # Prepara vendite storiche: media per mese, settimana, giorno
    vendite = sales_df.copy()
    vendite['mese'] = vendite['data'].dt.month
    vendite['settimana_mese'] = vendite['data'].apply(week_of_month)
    vendite['giorno_settimana'] = vendite['data'].dt.day_name()
    vendite_grouped = vendite.groupby(['mese', 'settimana_mese', 'giorno_settimana'])['vendite'].mean().reset_index()
    # Merge: per ogni data dei turni, associa la media vendite storiche corrispondente
    result = pd.merge(turni, vendite_grouped, on=['mese', 'settimana_mese', 'giorno_settimana'], how='left')
    result = result[['data', 'num_persone', 'vendite', 'mese', 'settimana_mese', 'giorno_settimana']]
    result['vendite_per_persona'] = result['vendite'] / result['num_persone']
    return result

# Main interface
st.header("Carica Turnazioni")
uploaded_file = st.file_uploader("Carica il file delle turnazioni (CSV o XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.xlsx':
        schedule_raw = pd.read_excel(uploaded_file, sheet_name='Shifts')
    else:
        schedule_raw = pd.read_csv(uploaded_file)
    st.dataframe(schedule_raw)
    
    # Preprocessing: estrai la data e conta le persone per giorno
    if 'Start Date' in schedule_raw.columns:
        schedule_raw['data'] = pd.to_datetime(schedule_raw['Start Date'])
        schedule_df = schedule_raw.groupby('data').size().reset_index(name='num_persone')
    else:
        st.error("Il file deve contenere la colonna 'Start Date'.")
        schedule_df = None
    
    if schedule_df is not None:
        st.subheader(f"Turnazioni aggregate per giorno per il negozio: {negozio_scelto}")
        st.dataframe(schedule_df)
        
        if st.button("Analizza Turnazioni"):
            vendite_negozio = sales_df[sales_df['negozio'] == negozio_scelto]
            if vendite_negozio.empty:
                st.warning(f"Non ci sono dati di vendita storici per il negozio '{negozio_scelto}'. Carica i dati nel file vendite.csv.")
            else:
                # --- ANALISI: confronto turni vs media vendite storiche per combinazione ---
                confronto = analyze_turni_vs_vendite(vendite_negozio, schedule_df)
                # Grafico in cima
                st.header("Grafico: Persone programmate e media vendite storiche")
                confronto['data_label'] = confronto['data'].dt.strftime('%Y-%m-%d') + ' (' + confronto['giorno_settimana'] + ')'
                fig5 = go.Figure()
                fig5.add_trace(go.Bar(x=confronto['data_label'], y=confronto['vendite'], name='Media vendite storiche', marker_color='blue'))
                fig5.add_trace(go.Scatter(x=confronto['data_label'], y=confronto['num_persone'], name='Persone programmate', mode='lines+markers', marker_color='orange', yaxis='y2'))
                fig5.update_layout(
                    title=f"Persone programmate e media vendite storiche per data - {negozio_scelto}",
                    xaxis_title="Data (Giorno della settimana)",
                    yaxis_title="Media vendite storiche",
                    yaxis2=dict(title="Persone programmate", overlaying='y', side='right', tickformat=',d', dtick=1),
                    legend=dict(x=0.01, y=0.99, bordercolor="Black", borderwidth=1)
                )
                st.plotly_chart(fig5)
                # Tabella dopo il grafico
                st.header("Confronto turni programmati vs media vendite storiche")
                st.dataframe(confronto)

# Instructions
st.sidebar.header("Istruzioni")
st.sidebar.markdown(f"""
1. Seleziona il negozio da analizzare dal menu a tendina
2. Carica il file CSV delle turnazioni esportato dal gestionale, che deve contenere almeno le colonne:
   - Start Date (data, formato MM/DD/YYYY o YYYY-MM-DD)
   - Group (codice negozio)
3. Ogni riga deve rappresentare una persona programmata per un determinato giorno e negozio
4. Clicca su 'Analizza Turnazioni' per vedere i risultati relativi al negozio selezionato
""") 
