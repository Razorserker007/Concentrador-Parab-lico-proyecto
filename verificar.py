import numpy as np
from modelo import (cargar_encuesta, calcular, DEFAULT, MOMENTOS, PROPIEDADES, SIN_TECHO, PRECIO_MAX_USD,
                    mercado_objetivo, barrido_precio, costo_variable_objetivo)

b = cargar_encuesta()
t, k = calcular(b, DEFAULT)

# --- Datos: la tabla limpia es consistente ---
assert len(b) == 611
assert set(b.momento) <= set(MOMENTOS) and set(b.propiedad) <= set(PROPIEDADES)
assert (b.tiene_techo == (b.propiedad != SIN_TECHO)).all()
assert b.precio_rango.isin(PRECIO_MAX_USD).all()
assert (b.precio_max_usd == b.precio_rango.map(PRECIO_MAX_USD)).all()
assert (b.unidades == 1).all()

# --- Modelo: los mismos controles del original ---
assert len(t) == 48
assert (t.Ventas <= DEFAULT['capacidad']).all()
assert (t.Ventas <= t.Demanda).all()
assert (t.loc[t.Mes < DEFAULT['lanzamiento'], 'Ventas'] == 0).all()
assert np.isclose(t['Flujo neto'].sum(), t.EBITDA.sum() - DEFAULT['inversion'])
assert np.isclose(k['van'], -DEFAULT['inversion'] + sum(t.EBITDA / (1 + DEFAULT['descuento']) ** (t.Mes / 12)))
p = DEFAULT.copy(); p['capacidad'] = 0
z, _ = calcular(b, p); assert z.Ventas.sum() == 0
p = DEFAULT.copy(); p['conversion'] = 0
z, _ = calcular(b, p); assert z.Demanda.sum() == 0

# --- Controles de este proyecto: filtros de precio y techo ---
p = DEFAULT.copy(); p['precio'] = 10000
z, _ = calcular(b, p); assert z.Demanda.sum() == 0
sin_techo = b.copy(); sin_techo['tiene_techo'] = False
z, kz = calcular(sin_techo, DEFAULT); assert kz['potencial'] == 0 and z.Demanda.sum() == 0
for criterio in ('superior', 'medio'):
    pot = []
    for precio in [100, 150, 151, 300, 301, 400, 401, 500, 501, 650, 651, 800, 801]:
        p = DEFAULT.copy(); p['criterio_precio'] = criterio; p['precio'] = precio
        pot.append(calcular(b, p)[1]['potencial'])
    assert all(x >= y - 1e-9 for x, y in zip(pot, pot[1:])), criterio   # subir el precio nunca aumenta el potencial
p = DEFAULT.copy(); p['hogares'] *= 2
assert np.isclose(calcular(b, p)[1]['potencial'], 2 * k['potencial'])
assert t.Ventas.sum() <= k['potencial'] + 1e-9

# --- Correcciones nuevas ---
# Excluir "Ninguno" y "Panel solar" nunca aumenta el potencial y saca exactamente a esas personas.
a = DEFAULT.copy(); a['excluir_sin_calentador'] = False
c = DEFAULT.copy(); c['excluir_sin_calentador'] = True
assert calcular(b, c)[1]['potencial'] < calcular(b, a)[1]['potencial']
assert mercado_objetivo(b, a).sum() == 450 and mercado_objetivo(b, c).sum() == 450 - ((b.tiene_techo) & b.sistema.isin(['Ninguno', 'Panel solar'])).sum()
# El criterio conservador (punto medio) nunca da más potencial que el optimista (extremo superior).
for ex in (False, True):
    s_, m_ = DEFAULT.copy(), DEFAULT.copy(); s_['excluir_sin_calentador'] = m_['excluir_sin_calentador'] = ex
    s_['criterio_precio'], m_['criterio_precio'] = 'superior', 'medio'
    assert calcular(b, m_)[1]['potencial'] <= calcular(b, s_)[1]['potencial']
# Costo variable objetivo: con ese costo el VAN es 0, y con uno menor es positivo.
cv = costo_variable_objetivo(b, DEFAULT)
assert cv is not None
p = DEFAULT.copy(); p['variable'] = cv
assert abs(calcular(b, p)[1]['van']) < 1e-6
p['variable'] = cv * 0.9
assert calcular(b, p)[1]['van'] > 0
# Si no hay ventas, no existe costo objetivo.
p = DEFAULT.copy(); p['conversion'] = 0
assert costo_variable_objetivo(b, p) is None
# El barrido de precios coincide con calcular() en cada punto.
bar = barrido_precio(b, DEFAULT, 100, 600, 100)
for fila in bar.itertuples():
    p = DEFAULT.copy(); p['precio'] = fila.Precio
    assert np.isclose(fila.VAN, calcular(b, p)[1]['van'])

print('Modelo: datos, demanda, capacidad, caja, VAN, filtros de precio/techo/calentador, costo objetivo y escenarios extremos correctos.')
