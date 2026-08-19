import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Configuración de Página
st.set_page_config(page_title="InDrive Contabilidad", page_icon="🏍️", layout="centered")

# Obtener fecha de HOY en zona horaria Nicaragua (UTC-6)
def obtener_fecha_hoy():
    tz_nicaragua = datetime.timezone(datetime.timedelta(hours=-6))
    return datetime.datetime.now(tz_nicaragua).date()

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

CATEGORIAS_GASTOS = [
    "Recarga InDrive", 
    "Gasolina", 
    "Agua", 
    "Gaseosa o jugo", 
    "Comida en calle", 
    "Antojo de dulce"
]

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Mover ingreso ingresado por error el 19/08/2026 al 18/08/2026 como propina
def corregir_ingreso_19_a_18():
    try:
        res19 = supabase.table("viajes").select("*").eq("fecha", "2026-08-19").execute()
        if res19.data:
            for v in res19.data:
                monto_mover = float(v["monto"]) + float(v["propina"])
                supabase.table("viajes").delete().eq("id", v["id"]).execute()
                
                res18 = supabase.table("viajes").select("*").eq("fecha", "2026-08-18").order("numero_viaje").execute()
                viajes18 = [x["numero_viaje"] for x in res18.data] if res18.data else []
                siguiente_num = max(viajes18, default=0) + 1
                
                supabase.table("viajes").insert({
                    "fecha": "2026-08-18",
                    "numero_viaje": siguiente_num,
                    "monto": 0.0,
                    "propina": monto_mover
                }).execute()
    except Exception:
        pass

corregir_ingreso_19_a_18()

# Asegurar ingreso inicial del Domingo 16 de Agosto (C$ 310)
def asegurar_domingo_16():
    try:
        fecha_domingo = "2026-08-16"
        res_domingo = supabase.table("viajes").select("*").eq("fecha", fecha_domingo).execute()
        if not res_domingo.data:
            supabase.table("viajes").insert({
                "fecha": fecha_domingo,
                "numero_viaje": 1,
                "monto": 310.0,
                "propina": 0.0
            }).execute()
    except Exception:
        pass

asegurar_domingo_16()

# Limpieza y estructuración correcta de fondos
def corregir_y_limpiar_fondos():
    fondos_limpios = [
        {"nombre": "Ofrenda a Dios", "porcentaje": 5.0, "saldo": 133.50},
        {"nombre": "Ayuda a Padres", "porcentaje": 5.0, "saldo": 133.50},
        {"nombre": "Ahorro", "porcentaje": 5.0, "saldo": 133.50},
        {"nombre": "Mantenimiento Moto", "porcentaje": 5.0, "saldo": 78.50},
        {"nombre": "Cuota moto", "porcentaje": 20.0, "saldo": 0.00},
        {"nombre": "Entretenimiento", "porcentaje": 10.0, "saldo": 0.00},
        {"nombre": "Libre/Deuda", "porcentaje": 50.0, "saldo": 0.00},
    ]
    
    res = supabase.table("acumuladores").select("*").execute()
    
    necesita_reset = False
    if not res.data or len(res.data) != 7:
        necesita_reset = True
    else:
        for f in res.data:
            if "%" in f["nombre"]:
                necesita_reset = True
                break

    if necesita_reset:
        for f in res.data:
            supabase.table("acumuladores").delete().eq("id", f["id"]).execute()
            
        for item in fondos_limpios:
            supabase.table("acumuladores").insert(item).execute()

corregir_y_limpiar_fondos()

# Rango Semanal: Inicia el Domingo
def obtener_rango_semanal(fecha_ref):
    idx = (fecha_ref.weekday() + 1) % 7
    inicio = fecha_ref - datetime.timedelta(days=idx)
    fin = inicio + datetime.timedelta(days=6)
    return inicio, fin

# Diálogo de Confirmación para Retirar Fondo Individual
@st.dialog("Confirmar Retiro de Fondo")
def confirmar_retirar_fondo(fondo_id, fondo_nombre):
    st.write(f"¿En verdad quieres retirar y poner el saldo del fondo **{fondo_nombre}** en C$ 0.00?")
    c_si, c_no = st.columns(2)
    if c_si.button("Sí, Retirar", key=f"yes_{fondo_id}"):
        supabase.table("acumuladores").update({
            "saldo": 0.00
        }).eq("id", fondo_id).execute()
        st.success(f"El fondo **{fondo_nombre}** se ha retirado y reiniciado a C$ 0.00")
        st.rerun()
    if c_no.button("No, Cancelar", key=f"no_{fondo_id}"):
        st.rerun()

# Título Principal
st.title("🏍️ InDrive Contabilidad")

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
    fecha_seleccionada = st.date_input("Fecha De Registro", obtener_fecha_hoy())
    
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
                st.success(f"Viaje #{siguiente_numero_viaje} Registrado Correctamente.")
                st.rerun()

    with col2:
        st.subheader("Registrar Nuevo Gasto")
        with st.form("form_gasto", clear_on_submit=True):
            categoria = st.selectbox("Categoría De Gasto", CATEGORIAS_GASTOS)
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
                st.success("Gasto Registrado Correctamente.")
                st.rerun()

    st.divider()
    st.subheader(f"Detalle De Hoy ({fecha_seleccionada.strftime('%d/%m/%Y')})")
    
    col_v, col_g = st.columns(2)
    with col_v:
        st.write("**Viajes Del Día**")
        if res_v_dia.data:
            df_v_hoy = pd.DataFrame(res_v_dia.data)
            df_v_hoy["Monto (C$)"] = df_v_hoy["monto"].astype(float)
            df_v_hoy["Propina (C$)"] = df_v_hoy["propina"].astype(float)
            df_v_hoy["Total Viaje (C$)"] = df_v_hoy["Monto (C$)"] + df_v_hoy["Propina (C$)"]
            df_v_hoy["Viaje"] = df_v_hoy["numero_viaje"].apply(lambda x: f"Viaje #{x}")
            
            st.dataframe(df_v_hoy[["Viaje", "Monto (C$)", "Propina (C$)", "Total Viaje (C$)"]], use_container_width=True, hide_index=True)
            total_colectado_dia = df_v_hoy["Total Viaje (C$)"].sum()
            st.markdown(f"**Total Viajes Realizados:** `{len(df_v_hoy)}`")
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
            
            st.dataframe(df_g_hoy[["Categoría", "Monto (C$)", "Descripción"]], use_container_width=True, hide_index=True)
            total_gastos_dia = df_g_hoy["Monto (C$)"].sum()
            st.markdown(f"**Total Gastos Hoy:** `C$ {total_gastos_dia:.2f}`")
        else:
            st.caption("No Hay Gastos Registrados Hoy.")

# ------------------------------------------------------------------------------
# PESTAÑA 2: RESUMEN SEMANAL
# ------------------------------------------------------------------------------
with tab2:
    st.header("📊 Resumen Semanal De Operaciones")
    
    hoy = obtener_fecha_hoy()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    
    str_inicio = f"{inicio_sem.day} De {MESES[inicio_sem.month]}"
    str_fin = f"{fin_sem.day} De {MESES[fin_sem.month]} De {fin_sem.year}"
    
    st.subheader(f"Corte Actual: Del {str_inicio} Al {str_fin}")

    res_v_sem = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_v_sem = pd.DataFrame(res_v_sem.data) if res_v_sem.data else pd.DataFrame()
    ingresos_semana = float(df_v_sem["monto"].astype(float).sum() + df_v_sem["propina"].astype(float).sum()) if not df_v_sem.empty else 0.0

    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_g_sem = pd.DataFrame(res_g_sem.data) if res_g_sem.data else pd.DataFrame()
    gastos_semana = float(df_g_sem["monto"].astype(float).sum()) if not df_g_sem.empty else 0.0

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

    total_ingresos_tabla = 0.0
    total_gastos_tabla = 0.0
    total_neto_tabla = 0.0

    while fecha_iter <= fin_sem:
        f_str = str(fecha_iter)
        
        ing_dia = 0.0
        if not df_v_todos.empty:
            sub_v = df_v_todos[df_v_todos["fecha"] == f_str]
            if not sub_v.empty:
                ing_dia = float(sub_v["monto"].astype(float).sum() + sub_v["propina"].astype(float).sum())

        gas_dia = 0.0
        if not df_g_todos.empty:
            sub_g = df_g_todos[df_g_todos["fecha"] == f_str]
            if not sub_g.empty:
                gas_dia = float(sub_g["monto"].astype(float).sum())

        neto_dia = ing_dia - gas_dia
        
        total_ingresos_tabla += ing_dia
        total_gastos_tabla += gas_dia
        total_neto_tabla += neto_dia

        nombre_dia = DIAS_SEMANA[fecha_iter.weekday()]
        fecha_formateada = f"{nombre_dia} {fecha_iter.day} De {MESES[fecha_iter.month]}"
        
        dias_semana_lista.append({
            "Fecha": fecha_formateada,
            "Ingresos (C$)": f"{ing_dia:.0f}",
            "Gastos Operativos (C$)": f"{gas_dia:.0f}",
            "Ganancia Neta (C$)": f"{neto_dia:.0f}"
        })
        fecha_iter += datetime.timedelta(days=1)

    dias_semana_lista.append({
        "Fecha": "TOTAL",
        "Ingresos (C$)": f"{total_ingresos_tabla:.0f}",
        "Gastos Operativos (C$)": f"{total_gastos_tabla:.0f}",
        "Ganancia Neta (C$)": f"{total_neto_tabla:.0f}"
    })

    df_dias_semana = pd.DataFrame(dias_semana_lista)
    st.table(df_dias_semana)

# ------------------------------------------------------------------------------
# PESTAÑA 3: DISTRIBUCIÓN DE GANANCIAS (LÓGICA DIARIA)
# ------------------------------------------------------------------------------
with tab3:
    st.header("💰 Distribución De Ganancias")
    
    hoy = obtener_fecha_hoy()

    # 1. Ganancia Neta de HOY
    res_v_hoy = supabase.table("viajes").select("monto, propina").eq("fecha", str(hoy)).execute()
    df_v_h = pd.DataFrame(res_v_hoy.data) if res_v_hoy.data else pd.DataFrame()
    ing_hoy = float(df_v_h["monto"].astype(float).sum() + df_v_h["propina"].astype(float).sum()) if not df_v_h.empty else 0.0

    res_g_hoy = supabase.table("gastos").select("monto").eq("fecha", str(hoy)).execute()
    df_g_h = pd.DataFrame(res_g_hoy.data) if res_g_hoy.data else pd.DataFrame()
    gas_hoy = float(df_g_h["monto"].astype(float).sum()) if not df_g_h.empty else 0.0

    ganancia_hoy = max(0.0, ing_hoy - gas_hoy)

    st.write(f"**Ganancia Neta De Hoy ({hoy.strftime('%d/%m/%Y')}):** `C$ {ganancia_hoy:.2f}`")

    # 2. Cargar Fondos limpios desde Supabase
    res_fondos = supabase.table("acumuladores").select("*").order("id").execute()
    fondos = res_fondos.data
    
    st.subheader("Tabla De Distribución De Fondos")
    
    col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 2, 2])
    col_h1.write("**Fondo (% Porcentaje)**")
    col_h2.write("**Aporte Hoy (C$)**")
    col_h3.write("**Total Acumulado (C$)**")
    col_h4.write("**Acción**")
    st.divider()

    # Diccionario para guardar el total acumulado de cada fondo y usarlo en la calculadora
    totales_acumulados_fondos = {}

    for f in fondos:
        col_f1, col_f2, col_f3, col_f4 = st.columns([3, 2, 2, 2])
        pct = float(f["porcentaje"])
        nombre_fondo = f["nombre"]
        
        # Saldo base previo acumulado
        saldo_base = float(f.get("saldo", 0.0))
        
        # Aporte únicamente del día de hoy
        aporte_hoy = ganancia_hoy * (pct / 100.0)
        
        # Total acumulado = Saldo previo + Aporte de hoy
        total_acumulado = saldo_base + aporte_hoy
        
        # Guardar en diccionario para la calculadora
        totales_acumulados_fondos[nombre_fondo] = total_acumulado
        
        col_f1.write(f"**{nombre_fondo}** ({pct:.0f}%)")
        col_f2.write(f"C$ {aporte_hoy:.2f}")
        col_f3.write(f"**C$ {total_acumulado:.2f}**")
        
        if col_f4.button("Retirar", key=f"btn_retirar_{f['id']}"):
            confirmar_retirar_fondo(f["id"], nombre_fondo)

    # --------------------------------------------------------------------------
    # CALCULADORA DE SUMA DE FONDOS
    # --------------------------------------------------------------------------
    st.divider()
    st.subheader("🧮 Calculadora De Suma De Fondos Acumulados")
    st.caption("Selecciona los ítems o fondos que deseas sumar para conocer el total acumulado entre ellos.")

    opciones_fondos = list(totales_acumulados_fondos.keys())
    
    fondos_seleccionados = st.multiselect(
        "Selecciona los fondos a sumar:",
        options=opciones_fondos,
        default=[]
    )

    if fondos_seleccionados:
        suma_total = sum(totales_acumulados_fondos[f] for f in fondos_seleccionados)
        st.metric(
            label=f"Suma Total de {len(fondos_seleccionados)} fondo(s) seleccionado(s)",
            value=f"C$ {suma_total:.2f}"
        )
        
        # Mostrar detalle de los seleccionados
        detalle_str = " + ".join([f"{f} (C$ {totales_acumulados_fondos[f]:.2f})" for f in fondos_seleccionados])
        st.caption(f"Desglose: {detalle_str}")
    else:
        st.info("Selecciona al menos un fondo arriba para ver la suma total.")

# ------------------------------------------------------------------------------
# PESTAÑA 4: REPORTES OPERATIVOS Y FINANCIEROS
# ------------------------------------------------------------------------------
with tab4:
    st.header("📈 Reportes Operativos Y Financieros")
    
    tipo_reporte = st.selectbox("Filtro De Reporte", ["Diario", "Semanal", "Mensual"])
    
    hoy = obtener_fecha_hoy()
    if tipo_reporte == "Diario":
        f_rep = st.date_input("Seleccionar Día De Reporte", hoy)
        inicio_f, fin_f = f_rep, f_rep
    elif tipo_reporte == "Semanal":
        f_ref = st.date_input("Seleccionar Fecha De La Semana", hoy)
        inicio_f, fin_f = obtener_rango_semanal(f_ref)
        st.caption(f"Rango Seleccionado: Del {inicio_f.strftime('%d/%m/%Y')} Al {fin_f.strftime('%d/%m/%Y')}")
    else:
        mes_sel = st.selectbox("Seleccionar Mes", list(MESES.values()), index=hoy.month - 1)
        num_mes = list(MESES.keys())[list(MESES.values()).index(mes_sel)]
        anio_sel = st.number_input("Año", min_value=2024, max_value=2030, value=hoy.year)
        inicio_f = datetime.date(anio_sel, num_mes, 1)
        if num_mes == 12:
            fin_f = datetime.date(anio_sel, 12, 31)
        else:
            fin_f = datetime.date(anio_sel, num_mes + 1, 1) - datetime.timedelta(days=1)

    st.divider()

    # Obtención de datos del período
    res_v_rep = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_v_r = pd.DataFrame(res_v_rep.data) if res_v_rep.data else pd.DataFrame()
    
    ing_bruto = float(df_v_r["monto"].astype(float).sum()) if not df_v_r.empty and "monto" in df_v_r else 0.0
    propinas = float(df_v_r["propina"].astype(float).sum()) if not df_v_r.empty and "propina" in df_v_r else 0.0
    total_ingresos = ing_bruto + propinas

    res_g_rep = supabase.table("gastos").select("categoria, monto").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_g_r = pd.DataFrame(res_g_rep.data) if res_g_rep.data else pd.DataFrame()
    total_gastos = float(df_g_r["monto"].astype(float).sum()) if not df_g_r.empty and "monto" in df_g_r else 0.0

    ganancia_real = total_ingresos - total_gastos

    # 1. REPORTE DE INGRESOS
    st.subheader("1. 💵 Reporte De Ingresos")
    col_i1, col_i2, col_i3 = st.columns(3)
    col_i1.metric("Ingresos Por Viajes", f"C$ {ing_bruto:.2f}")
    col_i2.metric("Propinas Recibidas", f"C$ {propinas:.2f}")
    col_i3.metric("Total Ingresos", f"C$ {total_ingresos:.2f}")

    st.divider()

    # 2. REPORTE DE GASTOS OPERATIVOS DESGLOSADO
    st.subheader("2. ⛽ Reporte De Gastos Operativos (Desglosado)")
    
    desglose_gastos = []
    for cat in CATEGORIAS_GASTOS:
        monto_cat = 0.0
        if not df_g_r.empty and "categoria" in df_g_r and "monto" in df_g_r:
            sub_cat = df_g_r[df_g_r["categoria"] == cat]
            if not sub_cat.empty:
                monto_cat = float(sub_cat["monto"].astype(float).sum())
        desglose_gastos.append({
            "Categoría De Gasto": cat,
            "Total Gastado (C$)": f"C$ {monto_cat:.2f}"
        })
    
    df_desglose = pd.DataFrame(desglose_gastos)
    st.table(df_desglose)
    st.markdown(f"**Total Gastos Operativos Del Período:** `C$ {total_gastos:.2f}`")

    st.divider()

    # 3. BALANCE REAL
    st.subheader("3. ⚖️ Reporte Real De Ganancias Netas")
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Total Ingresos (+)", f"C$ {total_ingresos:.2f}")
    col_r2.metric("Total Gastos Operativos (-)", f"C$ {total_gastos:.2f}")
    col_r3.metric("Ganancia Real (=)", f"C$ {ganancia_real:.2f}")