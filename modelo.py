"""Modelo Seguidor Solar EPN: lee datos reales de encuesta, calcula backlog y flujo."""
import numpy as np
import pandas as pd


def encuesta():
    # Lee los datos reales de su archivo CSV
    df = pd.read_csv('datos_encuesta.csv')

    # Renombramos las columnas largas de Google Forms para que Python las procese fácil
    df.columns = ['fecha', 'propiedad', 'sistema_actual', 'presupuesto', 'adopcion', 'barrera']

    # Filtramos a quienes NO tienen espacio físico (como hicimos en el análisis)
    df = df[df['propiedad'] != 'Departamento en edificio sin acceso a techo'].copy()

    # Mapeamos su pregunta de adopción a niveles de intención de compra
    intencion_map = {
        'Inmediatamente (Me gusta probar nueva tecnología)': 'Sí',
        'En 6 a 12 meses (Prefiero investigar un poco más primero)': 'Tal vez',
        'En 1 a 2 años (Cuando vea que a otras personas les funciona bien)': 'Tal vez',
        'No lo compraría': 'No'
    }
    df['intencion'] = df['adopcion'].map(intencion_map).fillna('No')

    # Mapeamos su pregunta de presupuesto a valores numéricos para cálculo financiero
    presupuesto_map = {
        'Hasta $300': 300,
        'De $300 a $500': 500,
        'De $500 a $800': 800,
        'Más de $800': 1000
    }
    df['presupuesto_usd'] = df['presupuesto'].map(presupuesto_map).fillna(0)

    # Asumimos 1 máquina por vivienda encuestada
    df['unidades'] = 1
    return df


def calcular(df, p):
    # Ponderación de demanda basada en su conversión
    peso = df.intencion.map({'Sí': p['conversion'], 'Tal vez': p['conversion'] * 0.3, 'No': 0})
    potencial = p['viviendas_objetivo'] * float((df.unidades * peso * (df.presupuesto_usd >= p['precio'])).mean())
    meses = np.arange(1, 121)  # Ciclo de vida proyectado a 10 años (120 meses)

    # Curva de adopción a lo largo del tiempo
    nodos = [1, p['lanzamiento'], p['madurez'], p['declive'], 120]
    niveles = [0, 0.15, 1, 1, p['cola']]
    curva = np.interp(meses, nodos, niveles)
    curva[meses < p['lanzamiento']] = 0
    deseada = potencial * curva / curva.sum() if curva.sum() else np.zeros(120)
    demanda_nuevos = np.floor(np.cumsum(deseada) + 1e-9).astype(int)
    demanda_nuevos = np.diff(np.r_[0, demanda_nuevos])

    # Lógica de Producción: Lista de Espera (Backlog)
    ventas = np.zeros(120, dtype=int)
    backlog_arr = np.zeros(120, dtype=int)
    backlog_actual = 0

    for i in range(120):
        demanda_total = demanda_nuevos[i] + backlog_actual
        ventas[i] = min(demanda_total, p['capacidad'])
        backlog_actual = demanda_total - ventas[i]
        backlog_arr[i] = backlog_actual

    precio = p['precio'] * (1 + p['precio_var']) ** ((meses - 1) // 12)
    costo = p['variable'] * (1 + p['inflacion']) ** ((meses - 1) // 12)
    fijo = p['fijo'] * (1 + p['inflacion']) ** ((meses - 1) // 12)
    ingresos = ventas * precio
    variable = ventas * costo
    ebitda = ingresos - variable - fijo

    # Depreciación a 10 años según normativa
    depreciacion = np.full(120, p['activo'] / 120)
    utilidad = ebitda - depreciacion

    # Impuestos Ecuatorianos (15% trabajadores + 25% IR = ~36.25%)
    impuestos = np.where(utilidad > 0, utilidad * 0.3625, 0)
    flujo = ebitda - impuestos
    flujo[0] -= p['inversion']

    acumulado = np.cumsum(flujo)
    tasa = (1 + p['descuento']) ** (1 / 12) - 1
    van = -p['inversion'] + sum(flujo / (1 + tasa) ** meses)
    recuperacion = np.flatnonzero(acumulado >= 0)

    etapa = np.select([meses < p['lanzamiento'], meses < p['madurez'], meses < p['saturacion'], meses < p['declive']],
                      ['Desarrollo', 'Crecimiento', 'Madurez', 'Saturación'], default='Obsolescencia')

    tabla = pd.DataFrame({'Mes': meses, 'Año': (meses - 1) // 12 + 1, 'Etapa': etapa, 'Demanda': demanda_nuevos,
                          'Ventas': ventas, 'Lista de Espera': backlog_arr, 'Precio': precio, 'Ingresos': ingresos,
                          'Costo variable': variable, 'Costo fijo': fijo, 'EBITDA': ebitda,
                          'Depreciación': depreciacion,
                          'Utilidad operativa': utilidad, 'Impuestos': impuestos, 'Flujo neto': flujo,
                          'Caja acumulada': acumulado})

    return tabla, {'potencial': potencial, 'van': van,
                   'payback': int(recuperacion[0] + 1) if len(recuperacion) else None}


# Supuestos financieros de arranque
DEFAULT = dict(viviendas_objetivo=5000, conversion=0.43, precio=300, variable=200, fijo=800, inversion=2000,
               activo=1500, capacidad=150, inflacion=0.03, precio_var=-0.01, descuento=0.12,
               lanzamiento=4, madurez=24, saturacion=60, declive=84, cola=0.0)