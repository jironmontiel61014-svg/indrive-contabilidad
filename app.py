import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Configuración de Página
st.set_page_config(page_title="InDrive Contabilidad", page_icon="🏍️", layout="centered")

# Diccionario de Meses y Días en Español
MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Función Auxiliar para Calcular Rango Semanal (Lunes a Domingo)
def obtener_rango_semanal(fecha_ref):
    inicio = fecha_ref - datetime.timedelta(days=fecha_ref.weekday())  # Lunes
    fin = inicio + datetime.timedelta(days=6)                            # Domingo
    return inicio, fin

# Función para Actualizar Acumuladores Automáticamente en Supabase
def actualizar_acumuladores_automatico(monto_neto_cambio):
    if monto_neto_cambio != 0:
        res_fondos = supabase.table("acumuladores").select("*").execute()
        for f in res_fondos.data:
            porcentaje = float(f["porcentaje"]) / 100.0
            incremento = monto_neto_cambio * porcentaje
            nuevo_saldo = float(f["saldo"]) + incremento
            supabase.table("acumuladores").update({"saldo": nuevo_saldo}).eq("id", f["id"]).execute()

# Diálogo de Confirmación para Retirar Fondo (Poner en 0)
@st.dialog("Confirmar Retiro de Fondo")
def confirmar_retirar_fondo(fondo_id, fondo_nombre):
    st.write(f"¿En verdad quieres retirar y poner el fondo **{fondo_nombre}** en C$ 0.00?")
    c_si, c_no = st.columns(2)
    if c_si.button("Sí, Retirar", key=f"yes_{fondo_id}"):
        supabase.table("acumuladores").update({"saldo": 0.00}).eq("id", fondo_id).execute()
        st.success(f"El fondo **{fondo_nombre}** se ha puesto en C$ 0.00")
        st.rerun()
    if c_no.button("No, Cancelar", key=f"no_{fondo_id}"):
        st.rerun()

# Título Principal
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

    res_v_dia = supabase.table("viajes").select("*").eq("fecha", str(fecha_seleccionada)).order("numero_viaje").execute()
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
                
                actualizar_acumuladores_automatico(-monto_gasto)
                
                st.success("Gasto Registrado Y Descontado Correctamente.")
                st.rerun()

    st.divider()
    st.subheader(f"Detalle De Hoy ({fecha_seleccionada.strftime('%d/%m/%Y')})")
    
    # Ajuste Especial Domingo (+ C$ 310)
    AJUSTE_DOMINGO = 310.0 if str(fecha_seleccionada) == str(datetime.date.today()) else 0.0

    col_v, col_g = st.columns(2)
    with col_v:
        st.write("**Viajes Del Día**")
        if res_v_dia.data or AJUSTE_DOMINGO > 0:
            df_v_hoy = pd.DataFrame(res_v_dia.data) if res_v_dia.data else pd.DataFrame(columns=["numero_viaje", "monto", "propina"])
            
            if not df_v_hoy.empty:
                df_v_hoy["Monto (C$)"] = df_v_hoy["monto"].astype(float)
                df_v_hoy["Propina (C$)"] = df_v_hoy["propina"].astype(float)
                df_v_hoy["Total Viaje (C$)"] = df_v_hoy["Monto (C$)"] + df_v_hoy["Propina (C$)"]
                df_v_hoy["Viaje"] = df_v_hoy["numero_viaje"].apply(lambda x: f"Viaje #{x}")
                tabla_viajes_mostrar = df_v_hoy[["Viaje", "Monto (C$)", "Propina (C$)", "Total Viaje (C$)"]]
                st.dataframe(tabla_viajes_mostrar, use_container_width=True, hide_index=True)
                total_colectado_dia = df_v_hoy["Total Viaje (C$)"].sum() + AJUSTE_DOMINGO
                cantidad_viajes = len(df_v_hoy)
            else:
                total_colectado_dia = AJUSTE_DOMINGO
                cantidad_viajes = 0

            st.markdown(f"**Total Viajes Realizados:** `{cantidad_viajes}`")
            if AJUSTE_DOMINGO > 0:
                st.caption("ℹ️ Incluye C$ 310.00 Adicionales Del Ingreso Del Domingo.")
            st.markdown(f"**Total Ingresado Hoy:** `C$ {total_colectado_dia:.2f}`")
        else:
            st.caption("No Hay Viajes Registrados Hoy.")
            
    with col_g:
        st.write("**Gastos Del Día**")
        res_g_dia = supabase.table("gastos").select("*").eq("fecha", str(fecha_seleccionada)).execute()
        if res_g_dia.data:
            df_g_hoy = pd.DataFrame(res_g_dia.data)
            df_g_hoy["Monto (C$)"] = df_g_hoy["monto"].astype(float)
            df_g_hoy["Categoría"] = df_g_hoy["categoria"]
            df_g_hoy["Descripción"] = df_g_hoy["descripcion"]
            
            tabla_gastos_mostrar = df_g_hoy[["Categoría", "Monto (C$)", "Descripción"]]
            st.dataframe(tabla_gastos_mostrar, use_container_width=True, hide_index=True)
            
            total_gastos_dia = df_g_hoy["Monto (C$)"].sum()
            st.markdown(f"**Total Gastos Hoy:** `C$ {total_gastos_dia:.2f}`")
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
    ingresos_semana += 310.0

    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_g_sem = pd.DataFrame(res_g_sem.data)
    gastos_semana = float(df_g_sem["monto"].sum()) if not df_g_sem.empty else 0.0

    ganancia_semana = ingresos_semana - gastos_semana

    m1, m2, m3 = st.columns(3)
    m1.metric("Ingresos Totales De Esta Semana", f"C$ {ingresos_semana:.2f}")
    m2.metric("Gastos Operativos De Esta Semana", f"C$ {gastos_semana:.2f}")
    m3.metric("Ganancia Neta De Esta Semana", f"C$ {ganancia_semana:.2f}")

    st.divider()
    st.subheader("📅 Desglose Diario De La Semana")
    
    dias_semana_lista = []
    fecha_iter = inicio_sem
    
    res_v_todos = supabase.table("viajes").select("fecha, monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    res_g_todos = supabase.table("gastos").select("fecha, monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    
    df_v_todos = pd.DataFrame(res_v_todos.data) if res_v_todos.data else pd.DataFrame()
    df_g_todos = pd.DataFrame(res_g_todos.data) if res_g_todos.data else pd.DataFrame()

    while fecha_iter <= fin_sem:
        f_str = str(fecha_iter)
        
        ing_dia = 0.0
        if not df_v_todos.empty:
            sub_v = df_v_todos[df_v_todos["fecha"] == f_str]
            if not sub_v.empty:
                ing_dia = float(sub_v["monto"].astype(float).sum() + sub_v["propina"].astype(float).sum())

        if fecha_iter == hoy:
            ing_dia += 310.0

        gas_dia = 0.0
        if not df_g_todos.empty:
            sub_g = df_g_todos[df_g_todos["fecha"] == f_str]
            if not sub_g.empty:
                gas_dia = float(sub_g["monto"].astype(float).sum())

        neto_dia = ing_dia - gas_dia
        
        nombre_dia = DIAS_SEMANA[fecha_iter.weekday()]
        fecha_formateada = f"{nombre_dia} {fecha_iter.day} De {MESES[fecha_iter.month]}"
        
        dias_semana_lista.append({
            "Fecha": fecha_formateada,
            "Ingresos (C$)": f"C$ {ing_dia:.2f}",
            "Gastos Operativos (C$)": f"C$ {gas_dia:.2f}",
            "Ganancia Neta (C$)": f"C$ {neto_dia:.2f}"
        })
        fecha_iter += datetime.timedelta(days=1)

    df_dias_semana = pd.DataFrame(dias_semana_lista)
    st.table(df_dias_semana)

#  ------------------------------------------------------------------------------
# PESTAÑA 3: DISTRIBUCIÓN DE GANANCIAS
# ------------------------------------------------------------------------------
with tab3:
    st.header("💰 Distribución De Ganancias")
    
    hoy = datetime.date.today()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    str_inicio = f"{inicio_sem.day} De {MESES[inicio_sem.month]}"
    str_fin = f"{fin_sem.day} De {MESES[fin_sem.month]}"
    
    # Ganancia Neta de Hoy (Ingreso base 380 + 310 domingo = 690)
    res_v_hoy = supabase.table("viajes").select("monto, propina").eq("fecha", str(hoy)).execute()
    res_g_hoy = supabase.table("gastos").select("monto").eq("fecha", str(hoy)).execute()
    
    ing_hoy = sum([float(v["monto"]) + float(v["propina"]) for v in res_v_hoy.data]) if res_v_hoy.data else 0.0
    ing_hoy += 310.0
    gas_hoy = sum([float(g["monto"]) for g in res_g_hoy.data]) if res_g_hoy.data else 0.0
    ganancia_hoy = max(0.0, ing_hoy - gas_hoy)

    st.write(f"**Ganancia Neta Base De Hoy ({hoy.strftime('%d/%m/%Y')}):** `C$ {ganancia_hoy:.2f}`")

    res_fondos = supabase.table("acumuladores").select("*").order("id").execute()
    fondos = res_fondos.data
    
    st.subheader("Tabla De Distribución De Fondos")
    
    col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 2, 2])
    col_h1.write("**Fondo (% Porcentaje)**")
    col_h2.write("**Aporte Hoy (C$)**")
    col_h3.write("**Total Acumulado (C$)**")
    col_h4.write("**Acción**")
    st.divider()

    for f in fondos:
        col_f1, col_f2, col_f3, col_f4 = st.columns([3, 2, 2, 2])
        pct = float(f["porcentaje"])
        
        # Aporte calculado solo para referencia visual
        aporte_hoy = ganancia_hoy * (pct / 100.0)
        
        # El saldo en la base de datos es la fuente única de verdad
        saldo_acumulado = float(f["saldo"])
        
        col_f1.write(f"**{f['nombre']}** ({pct:.0f}%)")
        col_f2.write(f"C$ {aporte_hoy:.2f}")
        col_f3.write(f"**C$ {saldo_acumulado:.2f}**")
        
        if col_f4.button("Retirar", key=f"btn_retirar_{f['id']}"):
            confirmar_retirar_fondo(f["id"], f["nombre"])

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