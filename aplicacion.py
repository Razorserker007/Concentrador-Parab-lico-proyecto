import json
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from modelo import encuesta, calcular, DEFAULT

st.set_page_config(page_title='Proyecto Grado EPN | Seguidor Solar', page_icon='☀️', layout='wide')
st.markdown(
    '''<style>.stApp{background:#f6f8fc} h1,h2,h3{color:#102c50} div[data-testid="stMetric"]{background:white;padding:18px;border-radius:12px;border:1px solid #dce5ef}</style>''',
    unsafe_allow_html=True)
st.title('Seguidor Solar Térmico Automatizado')
st.caption('Laboratorio de Mecatrónica EPN · Datos de mercado reales · Horizonte de 120 meses')
st.warning('ESTUDIO VALIDADO. Los datos gráficos provienen directamente de la encuesta "datos_encuesta.csv".')

if 'base' not in st.session_state:
    try:
        st.session_state.base = encuesta()
    except Exception as e:
        st.error("Por favor asegúrese de que el archivo 'datos_encuesta.csv' esté en la misma carpeta que este script.")
        st.stop()

p = DEFAULT.copy()

with st.sidebar:
    st.header('Simulador Financiero')
    p['viviendas_objetivo'] = st.number_input('Viviendas totales en el sector', 1, 100000, 5000)
    p['conversion'] = st.slider('Ratio de conversión real a compra', 0., 1., 0.43, .01)
    p['precio'] = st.number_input('Precio por sistema instalado (USD)', 50, 5000, 300, 10)
    p['variable'] = st.number_input('Costo de ensamble por unid. (USD)', 0, 5000, 200, 10)
    p['fijo'] = st.number_input('Costos fijos mensuales de taller (USD)', 0, 10000, 800, 50)
    p['inversion'] = st.number_input('Inversión inicial prototipo (USD)', 0, 50000, 2000, 100)
    p['activo'] = st.number_input('Activos depreciables (USD)', 0, p['inversion'], min(1500, p['inversion']), 100)
    p['capacidad'] = st.number_input('Capacidad de producción/mes', 0, 1000, 150)
    p['inflacion'] = st.slider('Inflación anual', 0., .15, .03, .01)
    p['descuento'] = st.slider('Tasa de Descuento (WACC)', 0., .3, .12, .01)

    st.subheader('Ciclo de vida mecánico (Meses)')
    p['lanzamiento'] = st.slider('Inicio comercial', 1, 24, 4)
    p['madurez'] = st.slider('Inicio de madurez', p['lanzamiento'] + 1, 72, 24)
    p['saturacion'] = st.slider('Inicio de saturación', p['madurez'] + 1, 96, 60)
    p['declive'] = st.slider('Fallo por fatiga (Declive)', p['saturacion'] + 1, 119, 84)
    p['cola'] = st.slider('Ventas residuales', 0., 1., 0., .05)

tabla, k = calcular(st.session_state.base, p)

cols = st.columns(4)
for col, label, value in zip(cols, ['Máquinas vendidas (10 años)', 'Ingresos Brutos (USD)', 'VAN Neto (USD)',
                                    'Mes de Recuperación'],
                             [f'{tabla.Ventas.sum():,}', f'{tabla.Ingresos.sum():,.0f}', f'{k["van"]:,.0f}',
                              f'{k["payback"]}' if k['payback'] else 'No recupera']):
    col.metric(label, value)

tabs = st.tabs(['1 · Demanda Real', '2 · Curva Comercial', '3 · Flujo a 10 Años', '4 · Diseño Mecatrónico'])

with tabs[0]:
    df = st.session_state.base
    a, b = st.columns(2)
    # Aquí mapeamos las columnas directas de SU encuesta
    a.plotly_chart(
        px.histogram(df, x='propiedad', color='intencion', barmode='group', title='Intención según tipo de propiedad'),
        width='stretch')
    b.plotly_chart(px.histogram(df, x='barrera', title='Miedos técnicos (Viento, Mantenimiento, Peso)'),
                   width='stretch')

    st.subheader("Datos crudos analizados")
    st.dataframe(df[['fecha', 'propiedad', 'sistema_actual', 'presupuesto', 'adopcion', 'intencion']])

with tabs[1]:
    st.plotly_chart(
        px.line(tabla, x='Mes', y=['Demanda', 'Ventas', 'Lista de Espera'], title='Demanda vs Capacidad de Taller'),
        width='stretch')

with tabs[2]:
    st.plotly_chart(px.line(tabla, x='Mes', y=['Ingresos', 'Costo variable', 'Costo fijo', 'Utilidad operativa'],
                            title='Evolución Mensual (USD)'), width='stretch')
    caja = pd.concat(
        [pd.DataFrame({'Mes': [0], 'Caja acumulada': [-p['inversion']]}), tabla[['Mes', 'Caja acumulada']]])
    st.plotly_chart(px.line(caja, x='Mes', y='Caja acumulada', title='Punto de Equilibrio'), width='stretch')
    margen = p['precio'] - p['variable']
    st.write(f'Ganancia bruta por máquina: **USD {margen:,.0f}**')

with tabs[3]:
    st.subheader('Parámetros de Diseño')
    requisitos = pd.DataFrame([
        ['Estructura', 'Evitar carga de viento', 'Perfil T-slot / PVC aerodinámico',
         'Base rígida ante los vientos andinos'],
        ['Seguimiento', 'Lectura Solar', 'ESP32-CAM (Python + OpenCV)', 'Visión externa en PC elimina latencia de IA'],
        ['Transmisión', 'Autobloqueo mecánico', 'Motor NEMA 17 + Corona Sinfín',
         'Evita movimiento del plato cuando no hay energía'],
        ['Térmico', 'Concentración de calor', 'Tubo de Cobre + Bomba 12V', 'Intercambio térmico rápido por alto flujo']
    ], columns=['Subsistema', 'Problema (Encuesta)', 'Solución Mecatrónica', 'Justificación'])
    st.dataframe(requisitos, hide_index=True)