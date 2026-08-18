import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Configuración de Página
st.set_page_config(page_title="InDrive Contabilidad", page_icon="🏍️", layout="centered")

# Diccionario de Meses en Español
MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Función Auxiliar para Calcular Rango Semanal (Domingo a Sábado)
def obtener_rango_semanal(fecha_ref):
    idx = (fecha_ref.weekday() + 1) % 7
    inicio = fecha_ref - datetime.timedelta(days=idx)
    fin = inicio + datetime.timedelta(days=6)
    return inicio, fin

# Función para Actualizar Acumuladores Automáticamente
def actualizar_acumuladores_automatico(monto_neto_cambio):
    if monto_neto_cambio != 0:
        res_fondos = supabase.table("acumuladores").select("*").execute()
        for f in res_fondos.data:
            porcentaje = float(f["porcentaje"]) / 100.0
            incremento = monto_neto_cambio * porcentaje
            nuevo_saldo = float(f["saldo"]) + incremento
            supabase.table("acumuladores").update({"saldo": nuevo_saldo}).eq("id", f["id"]).execute()

# Diálogo de Confirmación para Poner Fondo en 0
@st.dialog("Confirmar Reinicio de Fondo")
def confirmar_poner_cero(fondo_id, fondo_nombre):
    st.write(f"¿En verdad quieres poner el fondo **{fondo_nombre}** en C$ 0.00?")
    c_si, c_no = st.columns(2)
    if c_si.button("Sí, Confirmar", key=f"yes_{fondo_id}"):
        supabase.table("acumuladores").update({"saldo": 0.00}).eq("id", fondo_id).execute()
        st.success(f"El fondo **{fondo_nombre}** ha sido reajustado a C$ 0.00")
        st.rerun()
    if c_no.button("No, Cancelar", key=f"no_{fondo_id}"):
        st.rerun()

# Título Principal de la Aplicación
st.title("🏍️ InDrive Contabilidad")

# Navegación Superior por Pestañas
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Registrar Día", 
    "📊 Resumen Semanal", 
    "💰 Distribución de Ganancias", 
    "📈 Reportes"
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: REGISTRAR DÍA
# ------------------------------------------------------------------------------
with tab1:
    st.header("📝 Registro Diario De Operaciones")
    fecha_seleccionada = st.date_input("Fecha De Registro", datetime.date.today())
    
    st.info("💡 Fondo De Caja Chica: **C$ 200.00** (Exclusivo Para Cambio A Pasajeros, No Genera Ingreso Ni Gasto).")

    # Obtener Siguiente Número De Viaje Automático Para La Fecha
    res_v_dia = supabase.table("viajes").select("numero_viaje").eq("fecha", str(fecha_seleccionada)).execute()
    viajes_existentes = [v["numero_viaje"] for v in res_v_dia.data] if res_v_dia.data else []
    siguiente_numero_viaje = max(viajes_existentes, default=0) + 1

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Registrar Nuevo Viaje")
        with st.form("form_viaje", clear_on_submit=True):
            st.text_input("Número De Viaje (Automático)", value=f"Viaje #{siguiente_numero_viaje}", disabled=True)
            monto_viaje = st.number_input("Valor Pagado (C$)", min_value=0.0, step=10.0)
            propina = st.number_input("Propina (C$)", min_value=0.0, step=5.0)
            btn_viaje = st.form_submit_button("Guardar Viaje")
            
            if btn_viaje:
                supabase.table("viajes").insert({
                    "fecha": str(fecha_seleccionada),
                    "numero_viaje": siguiente_numero_viaje,
                    "monto": monto_viaje,
                    "propina": propina
                }).execute()
                
                # Distribución Automática Inmediata En Fondos
                ganancia_viaje = monto_viaje + propina
                actualizar_acumuladores_automatico(ganancia_viaje)
                
                st.success(f"Viaje #{siguiente_numero_viaje} Registrado Y Distribuido Correctamente.")
                st.rerun()

    with col2:
        st.subheader("Registrar Nuevo Gasto")
        with st.form("form_gasto", clear_on_submit=True):
            categoria = st.selectbox("Categoría De Gasto", ["Recarga InDrive", "Gasolina", "Consumo Personal", "Otros"])
            monto_gasto = st.number_input("Monto Del Gasto (C$)", min_value=0.0, step=10.0)
            descripcion = st.text_input("Descripción Del Gasto (Opcional)")
            btn_gasto = st.form_submit_button("Guardar Gasto")
            
            if btn_gasto:
                supabase.table("gastos").insert({
                    "fecha": str(fecha_seleccionada),
                    "categoria": categoria,
                    "monto": monto_gasto,
                    "descripcion": descripcion
                }).execute()
                
                # Descuento Automático En Fondos
                actualizar_acumuladores_automatico(-monto_gasto)
                
                st.success("Gasto Registrado Y Descontado Correctamente.")
                st.rerun()

    st.divider()
    st.subheader(f"Detalle De Hoy ({fecha_seleccionada.strftime('%d/%m/%Y')})")
    
    col_v, col_g = st.columns(2)
    with col_v:
        st.write("**Viajes Del Día**")
        df_v_hoy = pd.DataFrame(res_v_dia.data)
        if not df_v_hoy.empty:
            st.dataframe(df_v_hoy, use_container_width=True)
        else:
            st.caption("No Hay Viajes Registrados Hoy.")
            
    with col_g:
        st.write("**Gastos Del Día**")
        res_g_dia = supabase.table("gastos").select("categoria, monto, descripcion").eq("fecha", str(fecha_seleccionada)).execute()
        df_g_hoy = pd.DataFrame(res_g_dia.data)
        if not df_g_hoy.empty:
            st.dataframe(df_g_hoy, use_container_width=True)
        else:
            st.caption("No Hay Gastos Registrados Hoy.")

# ------------------------------------------------------------------------------
# PESTAÑA 2: RESUMEN SEMANAL
# ------------------------------------------------------------------------------
with tab2:
    st.header("📊 Resumen Semanal De Operaciones")
    
    hoy = datetime.date.today()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    
    str_inicio = f"{inicio_sem.day} De {MESES[inicio_sem.month]}"
    str_fin = f"{fin_sem.day} De {MESES[fin_sem.month]} De {fin_sem.year}"
    
    st.subheader(f"Corte Actual: Del {str_inicio} Al {str_fin}")

    res_v_sem = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_v_sem = pd.DataFrame(res_v_sem.data)
    ingresos_semana = float(df_v_sem["monto"].sum() + df_v_sem["propina"].sum()) if not df_v_sem.empty else 0.0

    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_g_sem = pd.DataFrame(res_g_sem.data)
    gastos_semana = float(df_g_sem["monto"].sum()) if not df_g_sem.empty else 0.0

    ganancia_semana = ingresos_semana - gastos_semana

    m1, m2, m3 = st.columns(3)
    m1.metric("Ingresos Totales De Esta Semana", f"C$ {ingresos_semana:.2f}")
    m2.metric("Gastos Operativos De Esta Semana", f"C$ {gastos_semana:.2f}")
    m3.metric("Ganancia Neta De Esta Semana", f"C$ {ganancia_semana:.2f}")

    st.info("⚡ La Distribución De La Ganancia Neta Se Realiza De Forma Automática En Cada Registro.")

# ------------------------------------------------------------------------------
# PESTAÑA 3: DISTRIBUCIÓN DE GANANCIAS
# ------------------------------------------------------------------------------
with tab3:
    st.header("💰 Distribución De Ganancias")
    
    hoy = datetime.date.today()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    str_inicio = f"{inicio_sem.day} De {MESES[inicio_sem.month]}"
    str_fin = f"{fin_sem.day} De {MESES[fin_sem.month]}"
    
    st.caption(f"Colectado Hasta El Momento Esta Semana ({str_inicio} Al {str_fin})")
    
    res_fondos = supabase.table("acumuladores").select("*").order("id").execute()
    fondos = res_fondos.data
    
    for f in fondos:
        col_f1, col_f2, col_f3 = st.columns([4, 3, 2])
        col_f1.markdown(f"**{f['nombre']}** ({f['porcentaje']}%)")
        col_f2.markdown(f"**C$ {float(f['saldo']):.2f}**")
        
        if col_f3.button("Poner En 0", key=f"btn_cero_{f['id']}"):
            confirmar_poner_cero(f["id"], f["nombre"])

# ------------------------------------------------------------------------------
# PESTAÑA 4: REPORTES
# ------------------------------------------------------------------------------
with tab4:
    st.header("📈 Reportes De Ingresos, Gastos Y Distribución")
    
    tipo_reporte = st.selectbox("Filtro De Reporte", ["Diario", "Semanal", "Mensual"])
    
    if tipo_reporte == "Diario":
        f_rep = st.date_input("Seleccionar Día De Reporte", datetime.date.today())
        inicio_f, fin_f = f_rep, f_rep
    elif tipo_reporte == "Semanal":
        f_ref = st.date_input("Seleccionar Fecha De La Semana", datetime.date.today())
        inicio_f, fin_f = obtener_rango_semanal(f_ref)
        st.caption(f"Rango Seleccionado: Del {inicio_f.strftime('%d/%m/%Y')} Al {fin_f.strftime('%d/%m/%Y')}")
    else:
        mes_sel = st.selectbox("Seleccionar Mes", list(MESES.values()), index=datetime.date.today().month - 1)
        num_mes = list(MESES.keys())[list(MESES.values()).index(mes_sel)]
        anio_sel = st.number_input("Año", min_value=2024, max_value=2030, value=datetime.date.today().year)
        inicio_f = datetime.date(anio_sel, num_mes, 1)
        if num_mes == 12:
            fin_f = datetime.date(anio_sel, 12, 31)
        else:
            fin_f = datetime.date(anio_sel, num_mes + 1, 1) - datetime.timedelta(days=1)

    # Consulta De Datos Para El Reporte
    res_v_rep = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_v_r = pd.DataFrame(res_v_rep.data)
    ing_rep = float(df_v_r["monto"].sum() + df_v_r["propina"].sum()) if not df_v_r.empty else 0.0

    res_g_rep = supabase.table("gastos").select("monto").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_g_r = pd.DataFrame(res_g_rep.data)
    gas_rep = float(df_g_r["monto"].sum()) if not df_g_r.empty else 0.0

    gan_rep = ing_rep - gas_rep

    r1, r2, r3 = st.columns(3)
    r1.metric("Ingresos Totales", f"C$ {ing_rep:.2f}")
    r2.metric("Gastos Operativos", f"C$ {gas_rep:.2f}")
    r3.metric("Ganancia Neta", f"C$ {gan_rep:.2f}")

    st.subheader("Distribución Proyectada De La Ganancia En El Período")
    
    res_acum = supabase.table("acumuladores").select("nombre, porcentaje").order("id").execute()
    datos_distribucion = []
    
    for ac in res_acum.data:
        pct = float(ac["porcentaje"])
        monto_distribuido = max(0.0, gan_rep) * (pct / 100.0)
        datos_distribucion.append({
            "Categoría De Fondo": ac["nombre"],
            "Porcentaje (%)": f"{pct:.0f}%",
            "Monto Generado (C$)": f"C$ {monto_distribuido:.2f}"
        })

    df_dist = pd.DataFrame(datos_distribucion)
    st.table(df_dist)