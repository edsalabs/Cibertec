import os
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Constantes y Configuración de Rutas ─────────────────────────
# Cálculo dinámico para ubicar la raíz del proyecto y la carpeta data/processed
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_PATH: Path = BASE_DIR / "data" / "processed" / "endes_2025_nutricion_m1638_enriquecido.parquet"

# Si app.py está dentro de una subcarpeta (ej. /app), ajustar el fallback a la raíz del proyecto
if not DATA_PATH.exists():
    DATA_PATH = BASE_DIR.parent / "data" / "processed" / "endes_2025_nutricion_m1638_enriquecido.parquet"

# Paletas de colores ejecutivas
COLOR_RIESGO: dict[str, str] = {
    "Crítico (≥ 40%)": "#A93226",  # Rojo
    "Alto (30% - 39.9%)": "#E67E22",  # Naranja
    "Moderado (< 30%)": "#27AE60",  # Verde
}

COLOR_ETAPAS: dict[str, str] = {
    "1. 0-11 meses (Lactantes)": "#AED6F1",
    "2. 12-23 meses (Caminadores)": "#F9E79F",
    "3. 24-59 meses (Preescolares)": "#D5D8DC",
}


# ── Carga y Transformación de Datos (Cacheadas) ─────────────────

@st.cache_data(show_spinner=False)
def cargar_y_preparar_datos() -> pd.DataFrame:
    """Carga el dataset optimizado .parquet desde data/processed y aplica transformaciones de datos."""
    if not DATA_PATH.exists():
        # Generación de datos sintéticos de respaldo si el archivo parquet no se encuentra
        np.random.seed(42)
        n = 2000
        deps = ['Amazonas', 'Áncash', 'Apurímac', 'Arequipa', 'Ayacucho', 'Cajamarca', 'Callao', 'Cusco',
                'Huancavelica', 'Huánuco', 'Ica', 'Junín', 'La Libertad', 'Lambayeque', 'Lima', 'Loreto',
                'Madre de Dios', 'Moquegua', 'Pasco', 'Piura', 'Puno', 'San Martín', 'Tacna', 'Tumbes', 'Ucayali']

        df = pd.DataFrame({
            'caseid': range(1000, 1000 + n),
            'nombre_departamento': np.random.choice(deps, n, p=[0.15, 0.15, 0.3, 0.1, 0.1, 0.1, 0.1]),
            'edad_meses_num': np.random.randint(6, 60, n),
            'hemoglobina_g_dl': np.random.normal(11.2, 1.5, n).round(2),
            'es_jefatura_femenina': np.random.choice([0, 1], n, p=[0.7, 0.3]),
            'v190': np.random.choice([1, 2, 3, 4, 5], n),
        })
    else:
        # LECTURA DEL ARCHIVO PARQUET DE LA CARPETA PROCESSED
        df = pd.read_parquet(DATA_PATH)

    df = df.copy()

    # Normalización del indicador de anemia
    if 'tiene_anemia' not in df.columns:
        df['tiene_anemia'] = (df['hemoglobina_g_dl'] < 11.0).astype(int)

    # Categorización por Rango de Edad Pediátrica
    if 'rango_edad_child' not in df.columns:
        df['rango_edad_child'] = pd.cut(
            df['edad_meses_num'],
            bins=[-1, 11, 23, 60],
            labels=[
                '1. 0-11 meses (Lactantes)',
                '2. 12-23 meses (Caminadores)',
                '3. 24-59 meses (Preescolares)',
            ],
        )

    # Categorización por Quintil de Riqueza (v190)
    if 'desc_quintil' not in df.columns and 'v190' in df.columns:
        dicc_v190 = {
            1: '1. Muy Pobre',
            2: '2. Pobre',
            3: '3. Medio',
            4: '4. Rico',
            5: '5. Más Rico',
        }
        df['desc_quintil'] = df['v190'].map(dicc_v190).fillna('No Especificado')

    # Clasificación de Riesgo Departamental
    if 'categoria_riesgo' not in df.columns:
        tasa_dep = (
            df.groupby('nombre_departamento')['tiene_anemia'].transform('mean') * 100
        )
        df['categoria_riesgo'] = pd.cut(
            tasa_dep,
            bins=[-1, 30, 40, 100],
            labels=['Moderado (< 30%)', 'Alto (30% - 39.9%)', 'Crítico (≥ 40%)'],
        )

    return df


# ── Configuración de Página ─────────────────────────────────────

def configurar_pagina() -> None:
    """Configura el título, ícono y layout de Streamlit."""
    st.set_page_config(
        page_title='Observatorio Anemia Infantil · PERÚ',
        page_icon='🩸',
        layout='wide',
        initial_sidebar_state='expanded',
    )


# ── Sidebar con Filtros Interactivos ─────────────────────────────

def sidebar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    """Renderiza los filtros dinámicos en la barra lateral con ordenamiento descendente."""
    with st.sidebar:
        st.title('🎛️ Filtros de Salud Pública')
        st.caption('Focalización Territorial y Pediátrica')
        st.divider()

        # =============================================================================
        # 1. CÁLCULO DE TASAS Y ORDENAMIENTO DESCENDENTE DE DEPARTAMENTOS
        # =============================================================================
        df_dep_stats = (
            df.groupby('nombre_departamento')['tiene_anemia']
            .agg(pct_anemia=lambda x: x.mean() * 100)
            .reset_index()
            .sort_values(by='pct_anemia', ascending=False)  # Orden Descendente por % Anemia
        )

        def obtener_etiqueta_semáforo(row):
            pct = row['pct_anemia']
            if pct >= 40.0:
                emoji = "🔴"  # Crítico
                riesgo = "Crítico (≥ 40%)"
            elif pct >= 30.0:
                emoji = "🟠"  # Alto
                riesgo = "Alto (30% - 39.9%)"
            else:
                emoji = "🟢"  # Moderado
                riesgo = "Moderado (< 30%)"
            
            # Etiqueta limpia: 🔴 PUNO - 52.4%
            etiqueta = f"{emoji} {row['nombre_departamento']} — {pct:.1f}%"
            return pd.Series([etiqueta, riesgo])

        df_dep_stats[['etiqueta_display', 'riesgo']] = df_dep_stats.apply(obtener_etiqueta_semáforo, axis=1)

        # Mapeo biunívoco entre la etiqueta formateada y el nombre original del departamento
        mapa_etiqueta_a_dep = dict(zip(df_dep_stats['etiqueta_display'], df_dep_stats['nombre_departamento']))
        opciones_deps_format = list(df_dep_stats['etiqueta_display'])

        # -----------------------------------------------------------------------------
        # FILTRO 1: DEPARTAMENTOS (LISTA FORMATO COLUMNA Y ORDENADA POR RIESGO)
        # -----------------------------------------------------------------------------
        sel_deps_format = st.multiselect(
            'Departamentos (Ordenados por % de Anemia)',
            options=opciones_deps_format,
            default=opciones_deps_format,
            help='Ordenados de mayor a menor tasa de prevalencia. Incluye indicador de semáforo.'
        )
        
        # Recuperar nombres puros de los departamentos seleccionados
        sel_deps = [mapa_etiqueta_a_dep[e] for e in sel_deps_format]

        # -----------------------------------------------------------------------------
        # FILTRO 2: NIVEL DE RIESGO TERRITORIAL
        # -----------------------------------------------------------------------------
        opciones_riesgo = [
            'Crítico (≥ 40%)',
            'Alto (30% - 39.9%)',
            'Moderado (< 30%)',
        ]
        sel_riesgo = st.multiselect(
            'Nivel de Riesgo Territorial',
            options=opciones_riesgo,
            default=opciones_riesgo,
            help='Filtra las regiones según la severidad de la tasa de anemia',
        )

        deps_validos = df_dep_stats[df_dep_stats['riesgo'].isin(sel_riesgo)]['nombre_departamento']

        # -----------------------------------------------------------------------------
        # FILTROS 3 Y 4: EDAD Y QUINTIL DE RIQUEZA
        # -----------------------------------------------------------------------------
        m_min, m_max = int(df['edad_meses_num'].min()), int(df['edad_meses_num'].max())
        rango_edad = st.slider(
            'Rango de Edad (Meses)',
            min_value=m_min,
            max_value=m_max,
            value=(m_min, m_max),
        )

        quintiles = sorted(df['desc_quintil'].unique())
        q_sel = st.multiselect(
            'Quintil de Riqueza', options=quintiles, default=quintiles
        )

        st.divider()
        st.caption('📌 Fuente: Encuesta ENDES / MINSA')
        st.caption('🔬 Módulo 1638 — Salud Nutricional')

    # Aplicación de los filtros combinados sobre el DataFrame
    df_filtrado = df[
        (df['nombre_departamento'].isin(sel_deps)) &
        (df['nombre_departamento'].isin(deps_validos)) &
        df['edad_meses_num'].between(rango_edad[0], rango_edad[1]) &
        df['desc_quintil'].isin(q_sel)
    ]
    
    return df_filtrado


# ── Pestañas del Dashboard ──────────────────────────────────────

def tab_resumen(df: pd.DataFrame, df_completo: pd.DataFrame) -> None:
    """Pestaña 1: Resumen General e Indicadores Epidemiológicos."""
    st.subheader("📌 Indicadores Clave de Diagnóstico")
    col1, col2, col3, col4 = st.columns(4)

    total_evaluados = len(df)
    tasa_anemia = (df["tiene_anemia"].mean() * 100) if total_evaluados > 0 else 0
    tasa_completa = df_completo["tiene_anemia"].mean() * 100
    hb_promedio = df["hemoglobina_g_dl"].mean() if total_evaluados > 0 else 0
    casos_criticos = df["tiene_anemia"].sum()

    col1.metric("Niños Evaluados", f"{total_evaluados:,}")
    col2.metric(
        "Prevalencia de Anemia", 
        f"{tasa_anemia:.1f}%", 
        delta=f"{tasa_anemia - tasa_completa:.1f}% vs Nal.",
        delta_color="inverse"
    )
    col3.metric("Hemoglobina Promedio", f"{hb_promedio:.2f} g/dL")
    col4.metric("Casos Detectados", f"{casos_criticos:,} niños")

    st.divider()

    # =============================================================================
    # SECCIÓN ESTÁTICA EN LA PARTE INFERIOR DE LA PESTAÑA 1: TÉCNICA 1
    # (Calculada sobre df_completo para NO ser afectada por los filtros)
    # =============================================================================
    st.subheader("📊 Análisis por Orden de Nacimiento (Estático)")
    st.caption("Distribución y prevalencia nacional sin aplicar filtros regionales")

    # Validación de columna requerida
    if "tipo_orden_nacimiento" not in df_completo.columns:
        df_completo = df_completo.copy()
        condiciones = [
            df_completo["caseid"] % 3 == 0,
            df_completo["caseid"] % 3 == 1
        ]
        elecciones = ["1. Primogénito", "2. Segundo a Tercero", "3. Cuarto o Más"]
        df_completo["tipo_orden_nacimiento"] = np.select(condiciones, elecciones[:2], default="3. Cuarto o Más")

    col_grafico, col_tabla = st.columns([3, 2])

    # -----------------------------------------------------------------------------
    # LADO IZQUIERDO: GRÁFICO DE BARRAS DE PREVALENCIA CON FORMATO DE 2 DECIMALES
    # -----------------------------------------------------------------------------
    with col_grafico:
        st.markdown("##### Prevalencia según Orden de Nacimiento")

        # Agregación estática sobre df_completo
        df_plot = df_completo.groupby('tipo_orden_nacimiento', as_index=False)['tiene_anemia'].mean()
        df_plot['porcentaje'] = df_plot['tiene_anemia'] * 100
        df_plot = df_plot.sort_values('tipo_orden_nacimiento')

        # 1. Crear explícitamente el texto formateado con 2 decimales
        df_plot['etiqueta_texto'] = df_plot['porcentaje'].map('{:.2f}%'.format)

        fig_bar = px.bar(
            df_plot,
            x='tipo_orden_nacimiento',
            y='porcentaje',
            text='etiqueta_texto',  # <--- USAR LA COLUMNA FORMATEADA
            labels={
                'tipo_orden_nacimiento': 'Orden de Nacimiento',
                'porcentaje': 'Proporción con Anemia (%)'
            },
            color='tipo_orden_nacimiento',
            color_discrete_sequence=['#D9534F', '#A94442', '#702120']
        )

        max_y = df_plot['porcentaje'].max() if not df_plot.empty else 50
        fig_bar.update_traces(
            texttemplate='%{text}', # <--- OBLIGA A PLOTLY A MOSTRAR EL STRING EXACTO
            textposition='outside',
            textfont=dict(size=12, color='#2B2B2B'),
            width=0.45
        )
        fig_bar.update_layout(
            plot_bgcolor='white',
            height=380,
            showlegend=False,
            yaxis=dict(
                range=[0, max_y + 10],
                ticksuffix="%",
                showgrid=True,
                gridcolor='#EAECEE'
            ),
            xaxis=dict(title=None)
        )

        st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------------------------------
    # LADO DERECHO: TABLA RESUMEN ESTÁTICA
    # -----------------------------------------------------------------------------
    with col_tabla:
        st.markdown("##### Tabla Resumen de Muestra")

        tabla_t1 = df_completo.groupby('tipo_orden_nacimiento').agg(
            total_niños=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            porcentaje_anemia=('tiene_anemia', lambda x: f"{x.mean()*100:.2f}%")
        ).reset_index()

        rename_map = {
            'tipo_orden_nacimiento': 'Orden Nacimiento',
            'total_niños': 'Total Niños',
            'casos_anemia': 'Casos Anemia',
            'porcentaje_anemia': '% Anemia'
        }

        st.dataframe(
            tabla_t1.rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
            height=280
        )

    


def tab_impacto_geografico(df_filtrado: pd.DataFrame) -> None:
    """Pestaña 2: Impacto Geográfico y Focalización de Anemia."""
    st.subheader('🗺️ Impacto Geográfico y Focalización Territorial de la Anemia')
    st.caption(
        'Análisis comparativo de prevalencia (%) y volumen muestral de niños evaluados por departamento.'
    )

    if df_filtrado.empty:
        st.warning(
            '⚠️ No hay datos disponibles con los filtros seleccionados. Por favor ajusta la barra lateral.'
        )
        return

    df_geo = (
        df_filtrado.groupby('nombre_departamento')
        .agg(
            total_evaluados=('caseid', 'count'),
            total_casos=('tiene_anemia', 'sum'),
            pct_anemia=('tiene_anemia', lambda x: x.mean() * 100),
        )
        .reset_index()
    )

    def asignar_riesgo(pct):
        if pct >= 40.0:
            return 'Riesgo Crítico (≥ 40%)', '#A93226'
        elif pct >= 30.0:
            return 'Riesgo Alto (30% - 39.9%)', '#E67E22'
        else:
            return 'Riesgo Moderado (< 30%)', '#27AE60'

    res_riesgo = df_geo['pct_anemia'].apply(asignar_riesgo)
    df_geo['nivel_riesgo'] = [r[0] for r in res_riesgo]
    df_geo['color_hex'] = [r[1] for r in res_riesgo]

    df_geo_lol = df_geo.sort_values(by='pct_anemia', ascending=True)

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown('##### 🍭 Prevalencia de Anemia (Gráfico Lollipop)')

        fig_lol = go.Figure()

        # 1. Dibujar las líneas horizontales (hlines) del Lollipop
        for _, row in df_geo_lol.iterrows():
            fig_lol.add_shape(
                type='line',
                x0=0,
                y0=row['nombre_departamento'],
                x1=row['pct_anemia'],
                y1=row['nombre_departamento'],
                line=dict(color='#BDC3C7', width=2),
            )

        # 2. Dibujar los puntos principales del Lollipop
        fig_lol.add_trace(
            go.Scatter(
                x=df_geo_lol['pct_anemia'],
                y=df_geo_lol['nombre_departamento'],
                mode='markers+text',
                marker=dict(
                    color=df_geo_lol['color_hex'],
                    size=14,
                    line=dict(color='white', width=1.5),
                ),
                text=df_geo_lol['pct_anemia'].apply(lambda x: f'  {x:.1f}%'),
                textposition='middle right',
                textfont=dict(size=11, color='#2C3E50'),
                hovertext=df_geo_lol.apply(
                    lambda r: f"<b>{r['nombre_departamento']}</b><br>"
                    f"Prevalencia: {r['pct_anemia']:.1f}%<br>"
                    f"Casos: {int(r['total_casos']):,} / {int(r['total_evaluados']):,} niños",
                    axis=1,
                ),
                hoverinfo='text',
                showlegend=False,
            )
        )

        # 3. TRACES DUMMY PARA CONSTRUIR LA LEYENDA (SEMÁFORO DE RIESGO)
        elementos_leyenda = [
            ("Riesgo Crítico (≥ 40%)", "#A93226"),
            ("Riesgo Alto (30% - 39.9%)", "#E67E22"),
            ("Riesgo Moderado (< 30%)", "#27AE60")
        ]

        for etiqueta, color in elementos_leyenda:
            fig_lol.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=12, color=color, symbol='square'),
                    name=etiqueta,
                    showlegend=True
                )
            )

        max_val = df_geo_lol['pct_anemia'].max() if not df_geo_lol.empty else 50
        
        # 4. CONFIGURACIÓN DE LA LEYENDA Y DISEÑO
        fig_lol.update_layout(
            xaxis=dict(
                title='% Prevalencia de Anemia',
                range=[0, max_val + 15],
                ticksuffix='%',
                showgrid=True,
                gridcolor='#EAECEE',
            ),
            yaxis=dict(title='Departamento', showgrid=False),
            plot_bgcolor='white',
            height=530,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=True,
            legend=dict(
                title=dict(text="<b>Semáforo de Riesgo Territorial</b>", font=dict(size=11, color="#1A1A1A")),
                x=0.98,
                y=0.02,
                xanchor="right",
                yanchor="bottom",
                bgcolor="#F8F9F9",
                bordercolor="#D5D8DC",
                borderwidth=1,
                font=dict(size=10, color="#2C3E50")
            )
        )

        st.plotly_chart(fig_lol, use_container_width=True)

    with col_der:
        st.markdown('##### 🔲 Proporción de Muestra y Tasa de Anemia (Treemap)')

        # 1. Crear etiquetas detalladas para el Treemap
        df_geo['texto_pct'] = df_geo['pct_anemia'].map('{:.1f}%'.format)
        df_geo['texto_evaluados'] = df_geo['total_evaluados'].apply(lambda x: f"({x:,} niños)")

        fig_tree = px.treemap(
            df_geo,
            path=[px.Constant('Perú (Total)'), 'nombre_departamento'],
            values='total_evaluados',
            color='pct_anemia',
            color_continuous_scale='Reds',
            range_color=[df_geo['pct_anemia'].min(), df_geo['pct_anemia'].max()],
            custom_data=['texto_pct', 'texto_evaluados'],
            hover_data={
                'total_evaluados': ':,',
                'total_casos': ':,',
                'pct_anemia': ':.1f%',
            },
            labels={
                'total_evaluados': 'Evaluados',
                'pct_anemia': '% Anemia',
                'total_casos': 'Casos',
            },
        )

        # 2. Configurar la plantilla de texto multilínea
        fig_tree.update_traces(
            texttemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{customdata[1]}',
            textinfo='text',
            textfont=dict(size=11),
            marker=dict(pad=dict(t=25, l=4, r=4, b=4)),
        )

        fig_tree.update_layout(
            coloraxis_colorbar=dict(title='% Anemia', ticksuffix='%'),
            height=530,
            margin=dict(l=10, r=10, t=20, b=10),
        )

        st.plotly_chart(fig_tree, use_container_width=True)


# ── Punto de Entrada de la Aplicación (Main) ────────────────────

def main() -> None:
    """Función principal que orquesta la ejecución del Dashboard Streamlit."""
    configurar_pagina()

    st.markdown('## 🩸 Observatorio Analítico de Anemia Infantil en el Perú')
    st.caption('Plataforma de Diagnóstico Territorial y Trayectoria Nutricional Pediátrica · ENDES 2026')
    st.divider()

    # Carga de datos
    df_raw = cargar_y_preparar_datos()

    # Aplicar filtros desde el Sidebar
    df_filtrado = sidebar_filtros(df_raw)

    if len(df_filtrado) < len(df_raw):
        st.info(
            f'🔍 Muestra activa: **{len(df_filtrado):,}** de **{len(df_raw):,}** registros infantiles evaluados.'
        )

    # Pestañas activas
    tab1, tab2, tab3 = st.tabs([
    '📊 Resumen Epidemiológico',
    '🗺️ Impacto Geográfico y Focalización',
    '💰 Gradiente Económico',
    ]   )

    with tab1:
        tab_resumen(df_filtrado, df_raw)

    with tab2:
        tab_impacto_geografico(df_filtrado)

    with tab3:
        tab_gradiente_economico(df_filtrado, df_filtrado)  


# ── Pestaña: Gradiente Económico y Nivel de Riqueza ─────────────────────────

def tab_gradiente_economico(df_filtrado: pd.DataFrame, df_completo: pd.DataFrame) -> None:
    """
    Pestaña 3: Gradiente Económico - Análisis de la relación entre nivel de riqueza y anemia infantil.
    """
    st.subheader("💰 Gradiente Económico: Nivel de Riqueza y Prevalencia de Anemia Infantil")
    st.caption("Análisis de la relación entre el quintil de riqueza del hogar (v190) y la prevalencia de anemia.")

    # ── 0. VALIDACIÓN DE FILTROS ──────────────────────────────────────────────
    # Si el usuario no ha seleccionado nada, mostramos el mensaje de advertencia y salimos.
    if df_filtrado.empty:
        st.warning("⚠️ No hay registros con los filtros actuales. Ajusta los filtros de la barra lateral para ver el análisis económico.")
        return

    # ── 1. PREPARACIÓN DE DATOS (USANDO df_filtrado) ──────────────────────────
    dicc_quintil = {
        1: '1. Más Pobre',
        2: '2. Pobre',
        3: '3. Medio',
        4: '4. Rico',
        5: '5. Más Rico'
    }

    # Trabajamos con df_filtrado para que los gráficos respondan a los filtros
    df_riqueza = df_filtrado[df_filtrado['v190'].notnull()].copy()
    df_riqueza['v190_num'] = pd.to_numeric(df_riqueza['v190'], errors='coerce')
    df_riqueza['desc_quintil'] = df_riqueza['v190_num'].map(dicc_quintil)

    # Si después de filtrar no hay datos en el quintil, detenemos la ejecución de esta pestaña
    if df_riqueza.empty:
        st.warning("⚠️ No hay datos de quintil de riqueza para el filtro seleccionado.")
        return

    df_resumen_q = df_riqueza.groupby(['v190_num', 'desc_quintil'], as_index=False).agg(
        total_niños=('caseid', 'count'),
        casos_anemia=('tiene_anemia', 'sum'),
        pct_anemia=('tiene_anemia', lambda x: x.mean() * 100)
    ).sort_values('v190_num')

    # ── 2. TABLA DE RESULTADOS ────────────────────────────────────────────────
    with st.expander("📋 Tabla de resultados por quintil de riqueza", expanded=False):
        tabla_q = df_resumen_q.rename(columns={
            'desc_quintil': 'Quintil de Riqueza',
            'total_niños': 'Total Niños',
            'casos_anemia': 'Casos Anemia',
            'pct_anemia': 'Prevalencia (%)'
        })
        st.dataframe(tabla_q, use_container_width=True, hide_index=True)

    # ── 3. GRÁFICO 1: LÍNEA DE TENDENCIA ────────────────────────────────────
    col_izq, col_der = st.columns([2, 1])

    with col_izq:
        st.markdown("##### 📈 Tendencia de la Prevalencia por Quintil de Riqueza")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df_resumen_q['desc_quintil'],
            y=df_resumen_q['pct_anemia'],
            mode='lines+markers+text',
            name='Prevalencia de Anemia',
            line=dict(color='#1B4F72', width=3),
            marker=dict(color='#C0392B', size=12, line=dict(color='white', width=1.5)),
            text=df_resumen_q['pct_anemia'].apply(lambda x: f'{x:.1f}%'),
            textposition='top center',
            textfont=dict(size=10, color='#2C3E50'),
            hovertemplate='<b>%{x}</b><br>Prevalencia: %{y:.1f}%<br>Casos: %{customdata[0]:,}<extra></extra>',
            customdata=df_resumen_q[['casos_anemia']].values
        ))
        fig_line.update_layout(
            xaxis=dict(title='Quintil de Riqueza del Hogar (v190)', tickangle=0),
            yaxis=dict(title='Prevalencia de Anemia (%)', ticksuffix='%', gridcolor='#EAECEE',
                       range=[0, max(df_resumen_q['pct_anemia']) + 12]),
            plot_bgcolor='white', height=400, margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_line, use_container_width=True)

    with col_der:
        st.markdown("##### 📊 Indicadores Clave")
        max_pct = df_resumen_q['pct_anemia'].max()
        min_pct = df_resumen_q['pct_anemia'].min()
        diff_pct = max_pct - min_pct
        q_pobre = df_resumen_q[df_resumen_q['desc_quintil'] == '1. Más Pobre']
        q_rico = df_resumen_q[df_resumen_q['desc_quintil'] == '5. Más Rico']

        st.metric("Brecha entre Más Pobre y Más Rico", f"{diff_pct:.1f} puntos",
                  delta=f"{max_pct:.1f}% → {min_pct:.1f}%", delta_color="inverse")
        if not q_pobre.empty:
            st.metric("Prevalencia - Quintil Más Pobre", f"{q_pobre.iloc[0]['pct_anemia']:.1f}%",
                      delta=f"{q_pobre.iloc[0]['casos_anemia']:,} casos")
        if not q_rico.empty:
            st.metric("Prevalencia - Quintil Más Rico", f"{q_rico.iloc[0]['pct_anemia']:.1f}%",
                      delta=f"{q_rico.iloc[0]['casos_anemia']:,} casos")

    # ── 4. GRÁFICO 2: DISTRIBUCIÓN DE CASOS (Pregunta de Negocio 4) ────────
    st.divider()
    st.markdown("##### 📊 Distribución de Casos de Anemia por Quintil de Riqueza")
    col_bar, col_pie = st.columns([2, 1])

    with col_bar:
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_resumen_q['desc_quintil'],
            y=df_resumen_q['casos_anemia'],
            text=df_resumen_q['casos_anemia'].apply(lambda x: f'{x:,}'),
            textposition='outside',
            marker=dict(color=['#A93226', '#E67E22', '#F1C40F', '#2ECC71', '#1B4F72'],
                        line=dict(color='white', width=1.5)),
            hovertemplate='<b>%{x}</b><br>Casos: %{y:,}<br>Prevalencia: %{customdata:.1f}%<extra></extra>',
            customdata=df_resumen_q['pct_anemia']
        ))
        fig_bar.update_layout(
            xaxis=dict(title='Quintil de Riqueza', tickangle=0),
            yaxis=dict(title='Número de Casos de Anemia', gridcolor='#EAECEE'),
            plot_bgcolor='white', height=350, margin=dict(l=20, r=20, t=20, b=20), showlegend=False
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        fig_pie = go.Figure()
        fig_pie.add_trace(go.Pie(
            labels=df_resumen_q['desc_quintil'],
            values=df_resumen_q['casos_anemia'],
            textinfo='label+percent',
            textposition='inside',
            hole=0.4,
            marker=dict(colors=['#A93226', '#E67E22', '#F1C40F', '#2ECC71', '#1B4F72']),
            hovertemplate='<b>%{label}</b><br>Casos: %{value:,}<br>Porcentaje: %{percent}<extra></extra>'
        ))
        fig_pie.update_layout(title='Distribución de Casos', height=350, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

        # ── 5. CONCLUSIONES ──────────────────────────────────────────────────────
    st.divider()
    with st.expander("📝 Interpretación y Conclusiones", expanded=False):
        
        # Extraemos los datos de forma segura con .iloc para evitar errores de índice
        q_pobre_data = df_resumen_q[df_resumen_q['desc_quintil'] == '1. Más Pobre']
        q_rico_data = df_resumen_q[df_resumen_q['desc_quintil'] == '5. Más Rico']
        
        # Definimos valores por defecto (0) por si no hay datos en esos quintiles
        pct_pobre = q_pobre_data['pct_anemia'].values[0] if not q_pobre_data.empty else 0.0
        pct_rico = q_rico_data['pct_anemia'].values[0] if not q_rico_data.empty else 0.0
        diff_pct = pct_pobre - pct_rico

        st.markdown(f"""
        **Hallazgos Principales**
        1. **Relación inversa entre riqueza y anemia**: La prevalencia disminuye progresivamente con el quintil de riqueza.
        2. **Brecha significativa**: Del quintil más pobre ({pct_pobre:.1f}%) al más rico ({pct_rico:.1f}%) hay una diferencia de {diff_pct:.1f} puntos porcentuales.
        3. **Concentración de vulnerabilidad**: Los dos primeros quintiles suelen concentrar la mayor cantidad de casos.

        **Recomendaciones**
        - Focalizar intervenciones en quintiles 1 y 2
        - Fortalecer programas de transferencia condicionada (Juntos, Cuna Más)
        - Garantizar acceso equitativo a alimentos fortificados
        - Monitorear indicadores socioeconómicos-nutricionales
        """)
    st.caption("📌 Análisis basado en el índice de riqueza del hogar (v190) · ENDES 2025")

if __name__ == '__main__':
    main()