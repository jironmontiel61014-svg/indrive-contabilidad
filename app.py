import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Configuración de página
st.set_page_config(page_title="InDrive Contabilidad", page_icon="🏍️", layout="centered")

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Menú Principal
st.title("🏍️ InDrive Contabilidad")
opcion = st.sidebar.radio("Navegación", ["Registrar Día", "Resumen Semanal", "Fondos Acumulados"])

# 1. REGISTRAR DÍA (VIAJES Y GASTOS)
if opcion == "Registrar Día":
    st.header("📝 Registro Diario")
    fecha = st.date_input("Fecha", datetime.date.today())
    
    st.subheader("Caja Chica Diario")
    st.info("💡 Fondo de caja chica: **C$ 200.00** (Solo cambio, no cuenta como ingreso).")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Registrar Viaje")
        with st.form("form_viaje", clear_on_submit=True):
            num_viaje = st.number_input("Número de Viaje", min_value=1, step=1)
            monto_viaje = st.number_input("Valor Pagado (C$)", min_value=0.0, step=10.0)
            propina = st.number_input("Propina (C$)", min_value=0.0, step=5.0)
            btn_viaje = st.form_submit_button("Guardar Viaje")
            
            if btn_viaje:
                supabase.table("viajes").insert({
                    "fecha": str(fecha),
                    "numero_viaje": num_viaje,
                    "monto": monto_viaje,
                    "propina": propina
                }).execute()
                st.success(f"Viaje {num_viaje} registrado correctamente.")

    with col2:
        st.subheader("Registrar Gasto")
        with st.form("form_gasto", clear_on_submit=True):
            categoria = st.selectbox("Categoría de Gasto", ["fee_indrive", "gasolina", "personal", "otros"])
            monto_gasto = st.number_input("Monto del Gasto (C$)", min_value=0.0, step=10.0)
            descripcion = st.text_input("Descripción (opcional)")
            btn_gasto = st.form_submit_button("Guardar Gasto")
            
            if btn_gasto:
                supabase.table("gastos").insert({
                    "fecha": str(fecha),
                    "categoria": categoria,
                    "monto": monto_gasto,
                    "descripcion": descripcion
                }).execute()
                st.success("Gasto registrado correctamente.")

# 2. RESUMEN SEMANAL
elif opcion == "Resumen Semanal":
    st.header("📊 Resumen de la Semana")
    
    # Cálculo del rango semanal (Domingo a Sábado)
    hoy = datetime.date.today()
    idx = (hoy.weekday() + 1) % 7
    inicio_semana = hoy - datetime.timedelta(days=idx)
    fin_semana = inicio_semana + datetime.timedelta(days=6)
    
    st.write(f"**Corte Actual:** Del {inicio_semana.strftime('%d/%m/%Y')} al {fin_semana.strftime('%d/%m/%Y')}")

    # Obtener Viajes
    res_viajes = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_semana)).lte("fecha", str(fin_semana)).execute()
    df_viajes = pd.DataFrame(res_viajes.data)
    
    total_ingresos = 0.0
    if not df_viajes.empty:
        total_ingresos = float(df_viajes["monto"].sum() + df_viajes["propina"].sum())

    # Obtener Gastos
    res_gastos = supabase.table("gastos").select("monto").gte("fecha", str(inicio_semana)).lte("fecha", str(fin_semana)).execute()
    df_gastos = pd.DataFrame(res_gastos.data)
    
    total_gastos = 0.0
    if not df_gastos.empty:
        total_gastos = float(df_gastos["monto"].sum())

    ganancia_neta = max(0.0, total_ingresos - total_gastos)

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Totales", f"C$ {total_ingresos:.2f}")
    c2.metric("Gastos Operativos", f"C$ {total_gastos:.2f}")
    c3.metric("Ganancia Neta", f"C$ {ganancia_neta:.2f}")

    if st.button("Procesar Distribución a Fondos"):
        if ganancia_neta > 0:
            fondos = supabase.table("acumuladores").select("*").execute().data
            for f in fondos:
                monto_agregar = ganancia_neta * (float(f["porcentaje"]) / 100.0)
                nuevo_saldo = float(f["saldo"]) + monto_agregar
                supabase.table("acumuladores").update({"saldo": nuevo_saldo}).eq("id", f["id"]).execute()
            st.success("Ganancia distribuida con éxito a los acumuladores.")
        else:
            st.warning("No hay ganancia neta para distribuir en esta semana.")

# 3. FONDOS ACUMULADOS
elif opcion == "Fondos Acumulados":
    st.header("💰 Estado de Acumuladores")
    
    res_fondos = supabase.table("acumuladores").select("*").order("id").execute()
    fondos = res_fondos.data
    
    for f in fondos:
        col_f1, col_f2, col_f3 = st.columns([3, 2, 2])
        col_f1.write(f"**{f['nombre']}** ({f['porcentaje']}%)")
        col_f2.write(f"C$ {float(f['saldo']):.2f}")
        
        if col_f3.button("Poner en 0", key=f"btn_{f['id']}"):
            supabase.table("acumuladores").update({"saldo": 0.00}).eq("id", f["id"]).execute()
            st.experimental_rerun()