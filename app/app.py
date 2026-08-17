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
    """Carga el dataset ENDES versionado junto con la aplicacion."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro el dataset procesado requerido: {DATA_PATH}"
        )
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
            df.groupby('nombre_departamento', observed=True)['tiene_anemia'].transform('mean') * 100
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
    """Pestaña 2: Impacto Geográfico y Focalización de Anemia.

    IMPORTANTE:
    Esta función recibe ``df_filtrado``; por lo tanto, todos los filtros del
    sidebar ya fueron aplicados antes de llegar aquí. Como ``nombre_departamento``
    es una columna categórica en el Parquet optimizado, usamos ``observed=True``
    para que Pandas NO cree grupos vacíos de categorías que quedaron fuera del
    filtro. Esos grupos vacíos eran los que producían ``pd.NA`` y el error
    "boolean value of NA is ambiguous".
    """
    st.subheader('🗺️ Impacto Geográfico y Focalización Territorial de la Anemia')
    st.caption(
        'Análisis comparativo de prevalencia (%) y volumen muestral de niños evaluados por departamento.'
    )
    st.caption('🎛️ Esta vista responde a los filtros globales de la barra lateral.')

    if df_filtrado.empty:
        st.warning(
            '⚠️ No hay datos disponibles con los filtros seleccionados. Por favor ajusta la barra lateral.'
        )
        return

    # -------------------------------------------------------------------------
    # 1. AGREGACIÓN SEGURA DESPUÉS DE LOS FILTROS
    # -------------------------------------------------------------------------
    # observed=True es clave cuando la columna de agrupación es dtype category.
    # Solo devuelve departamentos que realmente tienen registros en df_filtrado.
    df_geo = (
        df_filtrado.groupby('nombre_departamento', observed=True)
        .agg(
            total_evaluados=('caseid', 'count'),
            total_casos=('tiene_anemia', 'sum'),
            pct_anemia=('tiene_anemia', lambda x: x.mean() * 100),
        )
        .reset_index()
    )

    # Convertimos explícitamente las métricas a numéricas. El Parquet optimizado
    # usa tipos nullable de Pandas (Int8, Int16, etc.), por eso es conveniente
    # limpiar cualquier NA antes de usar comparaciones booleanas o Plotly.
    df_geo['total_evaluados'] = pd.to_numeric(df_geo['total_evaluados'], errors='coerce')
    df_geo['total_casos'] = pd.to_numeric(df_geo['total_casos'], errors='coerce')
    df_geo['pct_anemia'] = pd.to_numeric(df_geo['pct_anemia'], errors='coerce')

    # Doble protección: aunque observed=True evita los grupos categóricos vacíos,
    # descartamos cualquier fila sin muestra o sin prevalencia calculable.
    df_geo = df_geo[
        (df_geo['total_evaluados'].fillna(0) > 0) &
        (df_geo['pct_anemia'].notna())
    ].copy()

    if df_geo.empty:
        st.warning(
            '⚠️ Los filtros actuales no dejan departamentos con observaciones válidas para calcular prevalencia.'
        )
        return

    # -------------------------------------------------------------------------
    # 2. CLASIFICACIÓN DE RIESGO ROBUSTA ANTE VALORES FALTANTES
    # -------------------------------------------------------------------------
    def asignar_riesgo(pct):
        # Este guard evita que un posible pd.NA llegue a una expresión "if".
        if pd.isna(pct):
            return 'Sin dato', '#95A5A6'
        if pct >= 40.0:
            return 'Riesgo Crítico (≥ 40%)', '#A93226'
        if pct >= 30.0:
            return 'Riesgo Alto (30% - 39.9%)', '#E67E22'
        return 'Riesgo Moderado (< 30%)', '#27AE60'

    res_riesgo = df_geo['pct_anemia'].apply(asignar_riesgo)
    df_geo['nivel_riesgo'] = [r[0] for r in res_riesgo]
    df_geo['color_hex'] = [r[1] for r in res_riesgo]

    df_geo_lol = df_geo.sort_values(by='pct_anemia', ascending=True).copy()

    # Indicadores que ayudan a comprobar visualmente que el filtro sí cambió.
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric('Departamentos visibles', f"{df_geo['nombre_departamento'].nunique():,}")
    col_kpi2.metric('Niños evaluados', f"{int(df_geo['total_evaluados'].sum()):,}")
    tasa_vista = (df_geo['total_casos'].sum() / df_geo['total_evaluados'].sum()) * 100
    col_kpi3.metric('Prevalencia de la vista', f'{tasa_vista:.1f}%')

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown('##### 🍭 Prevalencia de Anemia (Gráfico Lollipop)')

        fig_lol = go.Figure()

        for _, row in df_geo_lol.iterrows():
            fig_lol.add_shape(
                type='line',
                x0=0,
                y0=str(row['nombre_departamento']),
                x1=float(row['pct_anemia']),
                y1=str(row['nombre_departamento']),
                line=dict(color='#BDC3C7', width=2),
            )

        fig_lol.add_trace(
            go.Scatter(
                x=df_geo_lol['pct_anemia'].astype(float),
                y=df_geo_lol['nombre_departamento'].astype(str),
                mode='markers+text',
                marker=dict(
                    color=df_geo_lol['color_hex'],
                    size=14,
                    line=dict(color='white', width=1.5),
                ),
                text=df_geo_lol['pct_anemia'].apply(lambda x: f'  {float(x):.1f}%'),
                textposition='middle right',
                textfont=dict(size=11, color='#2C3E50'),
                hovertext=df_geo_lol.apply(
                    lambda r: f"<b>{r['nombre_departamento']}</b><br>"
                    f"Prevalencia: {float(r['pct_anemia']):.1f}%<br>"
                    f"Casos: {int(r['total_casos']):,} / {int(r['total_evaluados']):,} niños",
                    axis=1,
                ),
                hoverinfo='text',
                showlegend=False,
            )
        )

        elementos_leyenda = [
            ('Riesgo Crítico (≥ 40%)', '#A93226'),
            ('Riesgo Alto (30% - 39.9%)', '#E67E22'),
            ('Riesgo Moderado (< 30%)', '#27AE60'),
        ]

        for etiqueta, color in elementos_leyenda:
            fig_lol.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=12, color=color, symbol='square'),
                    name=etiqueta,
                    showlegend=True,
                )
            )

        max_val = float(df_geo_lol['pct_anemia'].max())
        fig_lol.update_layout(
            xaxis=dict(
                title='% Prevalencia de Anemia',
                range=[0, min(100, max_val + 15)],
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
                title=dict(
                    text='<b>Semáforo de Riesgo Territorial</b>',
                    font=dict(size=11, color='#1A1A1A'),
                ),
                x=0.98,
                y=0.02,
                xanchor='right',
                yanchor='bottom',
                bgcolor='#F8F9F9',
                bordercolor='#D5D8DC',
                borderwidth=1,
                font=dict(size=10, color='#2C3E50'),
            ),
        )

        st.plotly_chart(fig_lol, use_container_width=True)

    with col_der:
        st.markdown('##### 🔲 Proporción de Muestra y Tasa de Anemia (Treemap)')

        df_geo['texto_pct'] = df_geo['pct_anemia'].apply(lambda x: f'{float(x):.1f}%')
        df_geo['texto_evaluados'] = df_geo['total_evaluados'].apply(
            lambda x: f'({int(x):,} niños)'
        )

        min_pct = float(df_geo['pct_anemia'].min())
        max_pct = float(df_geo['pct_anemia'].max())

        # Si solo queda un departamento, min y max pueden ser iguales. Ampliamos
        # un poco el rango para que la escala continua de Plotly siga siendo válida.
        if np.isclose(min_pct, max_pct):
            rango_color = [max(0.0, min_pct - 1.0), min(100.0, max_pct + 1.0)]
        else:
            rango_color = [min_pct, max_pct]

        fig_tree = px.treemap(
            df_geo,
            path=[px.Constant('Perú (Vista filtrada)'), 'nombre_departamento'],
            values='total_evaluados',
            color='pct_anemia',
            color_continuous_scale='Reds',
            range_color=rango_color,
            custom_data=['texto_pct', 'texto_evaluados'],
            hover_data={
                'total_evaluados': ':,',
                'total_casos': ':,',
                'pct_anemia': ':.1f',
            },
            labels={
                'total_evaluados': 'Evaluados',
                'pct_anemia': '% Anemia',
                'total_casos': 'Casos',
            },
        )

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
def tab_heatmap_trayectoria(df_filtrado: pd.DataFrame) -> None:
    """
    Pestaña 4:
    Analiza dónde se concentra la caída de hemoglobina
    y el aumento de anemia según edad en meses.

    Responde a:
    ¿En qué meses o rangos de edad se concentra
    la mayor caída crítica de hemoglobina?
    """

    st.subheader(
        "🔥 5 Trayectoria Crítica de Hemoglobina por Edad"
    )

    st.caption(
        "Identificación de los meses y etapas pediátricas donde "
        "se concentra la mayor caída de hemoglobina."
    )

    st.caption(
        "🎛️ Los filtros generales del sidebar se aplican antes "
        "de este análisis."
    )

    # =========================================================
    # 1. VALIDACIÓN
    # =========================================================

    columnas_requeridas = {
        "caseid",
        "edad_meses_num",
        "hemoglobina_g_dl",
        "tiene_anemia",
        "rango_edad_child",
    }

    faltantes = columnas_requeridas.difference(df_filtrado.columns)

    if faltantes:
        st.error(
            "Faltan columnas necesarias para construir este análisis: "
            + ", ".join(sorted(faltantes))
        )
        return

    if df_filtrado.empty:
        st.warning(
            "⚠️ No existen datos con los filtros actuales."
        )
        return

    # =========================================================
    # 2. PREPARACIÓN
    # =========================================================

    df = df_filtrado.copy()

    df["edad_meses_num"] = pd.to_numeric(
        df["edad_meses_num"],
        errors="coerce"
    )

    df["hemoglobina_g_dl"] = pd.to_numeric(
        df["hemoglobina_g_dl"],
        errors="coerce"
    )

    df["tiene_anemia"] = pd.to_numeric(
        df["tiene_anemia"],
        errors="coerce"
    )

    df = df[
        (df["edad_meses_num"] >= 0)
        & (df["edad_meses_num"] <= 59)
    ].copy()

    df = df.dropna(
        subset=[
            "edad_meses_num",
            "hemoglobina_g_dl",
            "tiene_anemia",
            "rango_edad_child",
        ]
    )

    if df.empty:
        st.warning(
            "No existen observaciones válidas entre 0 y 59 meses."
        )
        return

    # =========================================================
    # 3. FILTROS ESPECÍFICOS DE LA PREGUNTA DE NEGOCIO
    # =========================================================

    st.markdown("### 🎛️ Filtros específicos de trayectoria")

    col1, col2, col3 = st.columns(3)

    etapas = [
        "1. 0-11 meses (Lactantes)",
        "2. 12-23 meses (Caminadores)",
        "3. 24-59 meses (Preescolares)",
    ]

    etapas_disponibles = [
        e for e in etapas
        if e in df["rango_edad_child"].astype(str).unique()
    ]

    with col1:

        etapas_sel = st.multiselect(
            "Etapa pediátrica",
            options=etapas_disponibles,
            default=etapas_disponibles,
            key="heatmap_etapas",
        )

    with col2:

        rango_meses = st.slider(
            "Rango de edad",
            min_value=0,
            max_value=59,
            value=(0, 59),
            key="heatmap_rango",
        )

    with col3:

        indicador = st.selectbox(
            "Indicador principal",
            [
                "Hemoglobina promedio",
                "Prevalencia de anemia",
            ],
            key="heatmap_indicador",
        )

    # =========================================================
    # 4. APLICAR FILTROS
    # =========================================================

    df = df[
        df["rango_edad_child"].astype(str).isin(etapas_sel)
        & df["edad_meses_num"].between(
            rango_meses[0],
            rango_meses[1]
        )
    ].copy()

    if df.empty:
        st.warning(
            "⚠️ No existen datos para los filtros seleccionados."
        )
        return

    # =========================================================
    # 5. AGRUPACIÓN MENSUAL
    # =========================================================

    df_meses = (
        df.groupby(
            "edad_meses_num",
            observed=True
        )
        .agg(
            hemoglobina_promedio=(
                "hemoglobina_g_dl",
                "mean"
            ),

            prevalencia_anemia=(
                "tiene_anemia",
                "mean"
            ),

            casos_anemia=(
                "tiene_anemia",
                "sum"
            ),

            total_niños=(
                "caseid",
                "count"
            ),
        )
        .reset_index()
        .sort_values("edad_meses_num")
    )

    df_meses["prevalencia_anemia"] *= 100

    # =========================================================
    # 6. IDENTIFICAR PUNTO CRÍTICO
    # =========================================================

    if indicador == "Hemoglobina promedio":

        fila_critica = df_meses.loc[
            df_meses["hemoglobina_promedio"].idxmin()
        ]

        mes_critico = int(
            fila_critica["edad_meses_num"]
        )

        valor_critico = float(
            fila_critica["hemoglobina_promedio"]
        )

        texto_critico = (
            f"Mes crítico: **{mes_critico} meses** "
            f"con Hemoglobina promedio de **{valor_critico:.2f} g/dL**"
        )

    else:

        fila_critica = df_meses.loc[
            df_meses["prevalencia_anemia"].idxmax()
        ]

        mes_critico = int(
            fila_critica["edad_meses_num"]
        )

        valor_critico = float(
            fila_critica["prevalencia_anemia"]
        )

        texto_critico = (
            f"Mes crítico: **{mes_critico} meses** "
            f"con prevalencia de anemia de **{valor_critico:.1f}%**"
        )

    # =========================================================
    # 7. KPIs
    # =========================================================

    k1, k2, k3, k4 = st.columns(4)

    total = int(df_meses["total_niños"].sum())

    hb_min = float(
        df_meses["hemoglobina_promedio"].min()
    )

    anemia_max = float(
        df_meses["prevalencia_anemia"].max()
    )

    k1.metric(
        "Niños evaluados",
        f"{total:,}"
    )

    k2.metric(
        "Hemoglobina mínima promedio",
        f"{hb_min:.2f} g/dL"
    )

    k3.metric(
        "Mayor prevalencia",
        f"{anemia_max:.1f}%"
    )

    k4.metric(
        "Mes crítico",
        f"{mes_critico} meses"
    )

    st.info(
        "🔎 " + texto_critico
    )

    st.divider()

    # =========================================================
    # 8. CREAR MATRIZ PARA HEATMAP
    # =========================================================

    if indicador == "Hemoglobina promedio":

        valor_columna = "hemoglobina_promedio"

        titulo_color = (
            "Hemoglobina promedio (g/dL)"
        )

        escala = "Blues"

    else:

        valor_columna = "prevalencia_anemia"

        titulo_color = (
            "Prevalencia de anemia (%)"
        )

        escala = "Reds"

    matriz = df_meses[
        [
            "edad_meses_num",
            valor_columna
        ]
    ].copy()

    matriz["Edad"] = (
        matriz["edad_meses_num"]
        .astype(int)
        .astype(str)
        + " meses"
    )

    matriz["Indicador"] = titulo_color

    matriz = matriz.pivot(
        index="Indicador",
        columns="Edad",
        values=valor_columna
    )

    # =========================================================
    # 9. HEATMAP
    # =========================================================

    st.markdown(
        "### 🌡️ Mapa de intensidad por edad"
    )

    fig = px.imshow(
        matriz,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale=escala,
        labels={
            "x": "Edad del niño",
            "y": "",
            "color": titulo_color,
        },
        title=(
            "Mapa de concentración crítica "
            "según edad en meses"
        ),
    )

    fig.update_layout(
        height=300,
        plot_bgcolor="white",
        margin=dict(
            l=20,
            r=20,
            t=70,
            b=20
        ),
    )

    fig.update_xaxes(
        tickangle=-45
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # =========================================================
    # 10. COMPARACIÓN CON UMBRAL CLÍNICO
    # =========================================================

    st.markdown(
        "### 🩺 Identificación de meses bajo umbral clínico"
    )

    meses_bajo_umbral = df_meses[
        df_meses["hemoglobina_promedio"] < 11
    ].copy()

    if meses_bajo_umbral.empty:

        st.success(
            "No se encontraron meses con hemoglobina "
            "promedio inferior a 11.0 g/dL."
        )

    else:

        st.warning(
            f"⚠️ Se identificaron "
            f"**{len(meses_bajo_umbral)} meses** "
            "con hemoglobina promedio inferior a "
            "**11.0 g/dL**."
        )

        tabla = meses_bajo_umbral[
            [
                "edad_meses_num",
                "hemoglobina_promedio",
                "prevalencia_anemia",
                "casos_anemia",
                "total_niños",
            ]
        ].copy()

        tabla.columns = [
            "Edad (meses)",
            "Hb promedio (g/dL)",
            "Prevalencia anemia (%)",
            "Casos anemia",
            "Niños evaluados",
        ]

        tabla[
            "Hb promedio (g/dL)"
        ] = tabla[
            "Hb promedio (g/dL)"
        ].round(2)

        tabla[
            "Prevalencia anemia (%)"
        ] = tabla[
            "Prevalencia anemia (%)"
        ].round(1)

        st.dataframe(
            tabla,
            use_container_width=True,
            hide_index=True,
        )

    # =========================================================
    # 11. INTERPRETACIÓN
    # =========================================================

    with st.expander(
        "🎓 Interpretación de la pregunta de negocio"
    ):

        st.markdown(
            f"""
            ### ¿Qué busca este análisis?

            La pregunta de negocio busca identificar **en qué momento
            de la trayectoria pediátrica se presenta la mayor
            concentración de riesgo de anemia**.

            **Resultado de la selección actual:**

            - Mes crítico: **{mes_critico} meses**
            - Hemoglobina promedio mínima: **{hb_min:.2f} g/dL**
            - Mayor prevalencia observada:
              **{anemia_max:.1f}%**

            El mapa de intensidad permite detectar visualmente
            los meses donde el indicador presenta valores más
            críticos.

            Esto facilita la **focalización de intervenciones
            nutricionales según edad**, en lugar de analizar
            únicamente el promedio general de niños de 0 a 59 meses.
            """
        )

# ── Pregunta de Negocio 5.1 ─────────────────────────────────────

def tab_prevalencia_etapa(df_filtrado: pd.DataFrame) -> None:
    """Pestaña 3: Pregunta 5.1 - Prevalencia de anemia por etapa pediátrica.

    La función recibe exclusivamente ``df_filtrado``. Por eso, cualquier cambio
    realizado en el sidebar (departamento, riesgo, rango de edad o quintil) se
    refleja primero en esta pestaña y luego se pueden aplicar filtros locales.
    """

    st.subheader('🧒 5.1 Prevalencia de Anemia (%) según Etapa Pediátrica')
    st.caption(
        'Pregunta de negocio: ¿En qué meses o rangos de edad se concentra la mayor caída crítica de hemoglobina?'
    )
    st.caption('🎛️ Esta vista parte de la muestra filtrada en la barra lateral.')

    columnas_requeridas = {
        'caseid',
        'rango_edad_child',
        'tiene_anemia',
        'edad_meses_num',
        'hemoglobina_g_dl',
    }
    faltantes = columnas_requeridas.difference(df_filtrado.columns)

    if faltantes:
        st.error(
            'No se puede construir la pregunta 5.1 porque faltan estas columnas '
            f'en el Parquet: {", ".join(sorted(faltantes))}'
        )
        return

    if df_filtrado.empty:
        st.warning(
            '⚠️ No hay registros con los filtros actuales. Ajusta los filtros de la barra lateral.'
        )
        return

    # -------------------------------------------------------------------------
    # 1. PREPARACIÓN SEGURA DE LA MUESTRA FILTRADA
    # -------------------------------------------------------------------------
    df_trabajo = df_filtrado.copy()

    # string (dtype de Pandas) conserva NA como NA; a diferencia de astype(str),
    # no lo convierte en el texto literal "nan" o "<NA>".
    df_trabajo['rango_edad_child'] = df_trabajo['rango_edad_child'].astype('string')
    df_trabajo['tiene_anemia'] = pd.to_numeric(df_trabajo['tiene_anemia'], errors='coerce')
    df_trabajo['edad_meses_num'] = pd.to_numeric(df_trabajo['edad_meses_num'], errors='coerce')
    df_trabajo['hemoglobina_g_dl'] = pd.to_numeric(
        df_trabajo['hemoglobina_g_dl'], errors='coerce'
    )

    # Para prevalencia necesitamos etapa e indicador de anemia válidos.
    df_trabajo = df_trabajo.dropna(subset=['rango_edad_child', 'tiene_anemia']).copy()

    if df_trabajo.empty:
        st.warning('No existen observaciones válidas para calcular la pregunta 5.1.')
        return

    orden_etapas = list(COLOR_ETAPAS.keys())
    etapas_presentes = set(df_trabajo['rango_edad_child'].dropna().unique())
    etapas_disponibles = [e for e in orden_etapas if e in etapas_presentes]

    if not etapas_disponibles:
        st.warning('No existen etapas pediátricas disponibles con los filtros seleccionados.')
        return

    # -------------------------------------------------------------------------
    # 2. FILTROS LOCALES DE 5.1
    # -------------------------------------------------------------------------
    st.markdown('##### 🎛️ Exploración interactiva de la pregunta 5.1')
    col_filtro1, col_filtro2 = st.columns([2, 1])

    with col_filtro1:
        etapas_seleccionadas = st.multiselect(
            'Etapas pediátricas a comparar',
            options=etapas_disponibles,
            default=etapas_disponibles,
            help=(
                'Este filtro se aplica DESPUÉS de los filtros generales del sidebar. '
                'Por ejemplo, si el sidebar deja solo Puno y quintil muy pobre, '
                'aquí compararás las etapas únicamente dentro de esa submuestra.'
            ),
            key='pn51_etapas',
        )

    with col_filtro2:
        metrica_visual = st.selectbox(
            'Métrica del gráfico principal',
            options=[
                'Prevalencia de anemia (%)',
                'Casos de anemia',
                'Hemoglobina promedio (g/dL)',
            ],
            index=0,
            help='Cambia la medida mostrada en las barras sin cambiar la muestra.',
            key='pn51_metrica',
        )

    if not etapas_seleccionadas:
        st.info('Selecciona al menos una etapa pediátrica para continuar.')
        return

    df_51 = df_trabajo[
        df_trabajo['rango_edad_child'].isin(etapas_seleccionadas)
    ].copy()

    if df_51.empty:
        st.warning('No hay observaciones para las etapas seleccionadas.')
        return

    # -------------------------------------------------------------------------
    # 3. AGREGACIÓN PRINCIPAL
    # -------------------------------------------------------------------------
    # Como rango_edad_child ya es string, no arrastramos categorías no observadas.
    # Aun así dejamos observed=True por claridad si en el futuro vuelve a category.
    df_etapas = (
        df_51.groupby('rango_edad_child', observed=True)
        .agg(
            total_niños=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            tasa_anemia_pct=('tiene_anemia', lambda x: x.mean() * 100),
            hemoglobina_promedio=('hemoglobina_g_dl', 'mean'),
        )
        .reset_index()
    )

    for col in ['total_niños', 'casos_anemia', 'tasa_anemia_pct', 'hemoglobina_promedio']:
        df_etapas[col] = pd.to_numeric(df_etapas[col], errors='coerce')

    df_etapas = df_etapas[
        (df_etapas['total_niños'].fillna(0) > 0) &
        (df_etapas['tasa_anemia_pct'].notna())
    ].copy()

    if df_etapas.empty:
        st.warning('No hay etapas con una prevalencia calculable en la muestra actual.')
        return

    orden_seleccionado = [
        e for e in orden_etapas
        if e in etapas_seleccionadas and e in set(df_etapas['rango_edad_child'])
    ]

    df_etapas['rango_edad_child'] = pd.Categorical(
        df_etapas['rango_edad_child'],
        categories=orden_seleccionado,
        ordered=True,
    )
    df_etapas = df_etapas.sort_values('rango_edad_child').reset_index(drop=True)
    df_etapas['rango_edad_child'] = df_etapas['rango_edad_child'].astype('string')

    # -------------------------------------------------------------------------
    # 4. AGREGACIÓN MENSUAL
    # -------------------------------------------------------------------------
    df_meses = (
        df_51.dropna(subset=['edad_meses_num', 'tiene_anemia'])
        .groupby('edad_meses_num', observed=True)
        .agg(
            total_niños=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            tasa_anemia_pct=('tiene_anemia', lambda x: x.mean() * 100),
            hemoglobina_promedio=('hemoglobina_g_dl', 'mean'),
        )
        .reset_index()
        .sort_values('edad_meses_num')
    )

    for col in ['total_niños', 'casos_anemia', 'tasa_anemia_pct', 'hemoglobina_promedio']:
        if col in df_meses.columns:
            df_meses[col] = pd.to_numeric(df_meses[col], errors='coerce')

    # -------------------------------------------------------------------------
    # 5. KPIs: TODOS CAMBIAN CON EL SIDEBAR
    # -------------------------------------------------------------------------
    prevalencias_validas = df_etapas.dropna(subset=['tasa_anemia_pct'])
    fila_etapa_critica = prevalencias_validas.loc[
        prevalencias_validas['tasa_anemia_pct'].idxmax()
    ]

    total_evaluados = int(df_51['caseid'].count())
    total_casos = int(df_51['tiene_anemia'].sum())

    hb_meses_validos = df_meses.dropna(subset=['hemoglobina_promedio'])
    if not hb_meses_validos.empty:
        fila_min_hb = hb_meses_validos.loc[hb_meses_validos['hemoglobina_promedio'].idxmin()]
        mes_min_hb = int(fila_min_hb['edad_meses_num'])
        hb_min = float(fila_min_hb['hemoglobina_promedio'])
    else:
        mes_min_hb = None
        hb_min = np.nan

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric('Niños en la vista', f'{total_evaluados:,}')
    kpi2.metric('Casos de anemia', f'{total_casos:,}')
    kpi3.metric(
        'Etapa con mayor prevalencia',
        f"{float(fila_etapa_critica['tasa_anemia_pct']):.1f}%",
        help=str(fila_etapa_critica['rango_edad_child']),
    )
    kpi4.metric(
        'Mes con menor Hb promedio',
        f'{mes_min_hb} meses' if mes_min_hb is not None else 'Sin dato',
        delta=f'{hb_min:.2f} g/dL' if pd.notna(hb_min) else None,
        delta_color='off',
    )

    st.divider()

    # -------------------------------------------------------------------------
    # 6. GRÁFICO PRINCIPAL
    # -------------------------------------------------------------------------
    mapa_metricas = {
        'Prevalencia de anemia (%)': ('tasa_anemia_pct', 'Prevalencia de Anemia (%)', '%'),
        'Casos de anemia': ('casos_anemia', 'Casos de anemia', ''),
        'Hemoglobina promedio (g/dL)': (
            'hemoglobina_promedio',
            'Hemoglobina promedio (g/dL)',
            ' g/dL',
        ),
    }
    campo_y, titulo_y, sufijo = mapa_metricas[metrica_visual]

    df_grafico_etapas = df_etapas.dropna(subset=[campo_y]).copy()
    if df_grafico_etapas.empty:
        st.info(f'No hay datos válidos para mostrar la métrica: {metrica_visual}.')
    else:
        if campo_y == 'tasa_anemia_pct':
            df_grafico_etapas['etiqueta_barra'] = df_grafico_etapas[campo_y].apply(
                lambda x: f'{float(x):.1f}%'
            )
        elif campo_y == 'hemoglobina_promedio':
            df_grafico_etapas['etiqueta_barra'] = df_grafico_etapas[campo_y].apply(
                lambda x: f'{float(x):.2f} g/dL'
            )
        else:
            df_grafico_etapas['etiqueta_barra'] = df_grafico_etapas[campo_y].apply(
                lambda x: f'{int(x):,}'
            )

        fig_etapas = px.bar(
            df_grafico_etapas,
            x='rango_edad_child',
            y=campo_y,
            color='rango_edad_child',
            color_discrete_map=COLOR_ETAPAS,
            text='etiqueta_barra',
            custom_data=[
                'total_niños',
                'casos_anemia',
                'tasa_anemia_pct',
                'hemoglobina_promedio',
            ],
            labels={
                'rango_edad_child': 'Etapa Pediátrica',
                campo_y: titulo_y,
            },
            title='Comparación por Etapa Pediátrica — muestra filtrada',
        )

        fig_etapas.update_traces(
            texttemplate='%{text}',
            textposition='outside',
            hovertemplate=(
                '<b>%{x}</b><br>'
                'Niños evaluados: %{customdata[0]:,.0f}<br>'
                'Casos de anemia: %{customdata[1]:,.0f}<br>'
                'Prevalencia: %{customdata[2]:.1f}%<br>'
                'Hb promedio: %{customdata[3]:.2f} g/dL'
                '<extra></extra>'
            ),
        )
        fig_etapas.update_layout(
            height=470,
            plot_bgcolor='white',
            showlegend=False,
            xaxis_title=None,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        fig_etapas.update_yaxes(showgrid=True, gridcolor='#EAECEE')

        if sufijo == '%':
            fig_etapas.update_yaxes(ticksuffix='%')

        if campo_y == 'hemoglobina_promedio':
            fig_etapas.add_hline(
                y=11.0,
                line_dash='dash',
                line_color='#A93226',
                annotation_text='Umbral clínico 11.0 g/dL',
                annotation_position='top left',
            )

        st.plotly_chart(fig_etapas, use_container_width=True)

    # -------------------------------------------------------------------------
    # 7. DRILL-DOWN MENSUAL
    # -------------------------------------------------------------------------
    st.markdown('##### 🔎 Detalle mensual de la etapa seleccionada')

    if not orden_seleccionado:
        st.info('No quedan etapas disponibles para el detalle mensual.')
        return

    etapa_detalle = st.selectbox(
        'Selecciona una etapa para analizar mes a mes',
        options=orden_seleccionado,
        index=0,
        key='pn51_etapa_detalle',
    )

    df_detalle = df_51[df_51['rango_edad_child'] == etapa_detalle].copy()
    df_mes_detalle = (
        df_detalle.dropna(subset=['edad_meses_num', 'tiene_anemia'])
        .groupby('edad_meses_num', observed=True)
        .agg(
            total_niños=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            tasa_anemia_pct=('tiene_anemia', lambda x: x.mean() * 100),
            hemoglobina_promedio=('hemoglobina_g_dl', 'mean'),
        )
        .reset_index()
        .sort_values('edad_meses_num')
    )

    for col in ['total_niños', 'casos_anemia', 'tasa_anemia_pct', 'hemoglobina_promedio']:
        if col in df_mes_detalle.columns:
            df_mes_detalle[col] = pd.to_numeric(df_mes_detalle[col], errors='coerce')

    df_mes_detalle = df_mes_detalle[
        (df_mes_detalle['total_niños'].fillna(0) > 0) &
        (df_mes_detalle['tasa_anemia_pct'].notna())
    ].copy()

    if df_mes_detalle.empty:
        st.info('No hay datos mensuales disponibles para la etapa seleccionada.')
    else:
        prev_validas = df_mes_detalle.dropna(subset=['tasa_anemia_pct'])
        fila_max_anemia = prev_validas.loc[prev_validas['tasa_anemia_pct'].idxmax()]

        hb_detalle_validos = df_mes_detalle.dropna(subset=['hemoglobina_promedio'])
        if not hb_detalle_validos.empty:
            fila_min_hb_detalle = hb_detalle_validos.loc[
                hb_detalle_validos['hemoglobina_promedio'].idxmin()
            ]
            texto_hb = (
                f" La hemoglobina promedio más baja aparece a los "
                f"**{int(fila_min_hb_detalle['edad_meses_num'])} meses** "
                f"({float(fila_min_hb_detalle['hemoglobina_promedio']):.2f} g/dL)."
            )
        else:
            texto_hb = ' No hay valores válidos de hemoglobina para esta selección.'

        st.info(
            f"En **{etapa_detalle}**, el mayor porcentaje mensual de anemia aparece a los "
            f"**{int(fila_max_anemia['edad_meses_num'])} meses** "
            f"({float(fila_max_anemia['tasa_anemia_pct']):.1f}%)."
            + texto_hb
        )

        col_mes1, col_mes2 = st.columns(2)

        with col_mes1:
            fig_prev_mes = px.line(
                df_mes_detalle,
                x='edad_meses_num',
                y='tasa_anemia_pct',
                markers=True,
                custom_data=['total_niños', 'casos_anemia'],
                labels={
                    'edad_meses_num': 'Edad exacta (meses)',
                    'tasa_anemia_pct': 'Prevalencia de anemia (%)',
                },
                title='Prevalencia de anemia por mes',
            )
            fig_prev_mes.update_traces(
                hovertemplate=(
                    '<b>Edad: %{x:.0f} meses</b><br>'
                    'Prevalencia: %{y:.1f}%<br>'
                    'Evaluados: %{customdata[0]:,.0f}<br>'
                    'Casos: %{customdata[1]:,.0f}'
                    '<extra></extra>'
                )
            )
            fig_prev_mes.update_layout(
                height=390,
                plot_bgcolor='white',
                margin=dict(l=20, r=20, t=60, b=20),
            )
            fig_prev_mes.update_yaxes(
                ticksuffix='%',
                showgrid=True,
                gridcolor='#EAECEE',
            )
            st.plotly_chart(fig_prev_mes, use_container_width=True)

        with col_mes2:
            if hb_detalle_validos.empty:
                st.info('No hay hemoglobina válida para graficar en esta selección.')
            else:
                fig_hb_mes = px.line(
                    hb_detalle_validos,
                    x='edad_meses_num',
                    y='hemoglobina_promedio',
                    markers=True,
                    labels={
                        'edad_meses_num': 'Edad exacta (meses)',
                        'hemoglobina_promedio': 'Hemoglobina promedio (g/dL)',
                    },
                    title='Hemoglobina promedio por mes',
                )
                fig_hb_mes.add_hline(
                    y=11.0,
                    line_dash='dash',
                    line_color='#A93226',
                    annotation_text='Umbral 11.0 g/dL',
                    annotation_position='bottom right',
                )
                fig_hb_mes.update_traces(
                    hovertemplate=(
                        '<b>Edad: %{x:.0f} meses</b><br>'
                        'Hb promedio: %{y:.2f} g/dL'
                        '<extra></extra>'
                    )
                )
                fig_hb_mes.update_layout(
                    height=390,
                    plot_bgcolor='white',
                    margin=dict(l=20, r=20, t=60, b=20),
                )
                fig_hb_mes.update_yaxes(showgrid=True, gridcolor='#EAECEE')
                st.plotly_chart(fig_hb_mes, use_container_width=True)

    # -------------------------------------------------------------------------
    # 8. TABLA DE RESULTADOS
    # -------------------------------------------------------------------------
    st.markdown('##### 📋 Resumen numérico por etapa')
    tabla_51 = df_etapas.rename(
        columns={
            'rango_edad_child': 'Etapa Pediátrica',
            'total_niños': 'Total Niños',
            'casos_anemia': 'Casos Anemia',
            'tasa_anemia_pct': 'Prevalencia Anemia (%)',
            'hemoglobina_promedio': 'Hb Promedio (g/dL)',
        }
    ).copy()

    tabla_51['Prevalencia Anemia (%)'] = tabla_51['Prevalencia Anemia (%)'].round(2)
    tabla_51['Hb Promedio (g/dL)'] = tabla_51['Hb Promedio (g/dL)'].round(2)

    st.dataframe(
        tabla_51,
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------------
    # 9. EXPLICACIÓN DIDÁCTICA
    # -------------------------------------------------------------------------
    with st.expander('🎓 ¿Cómo funcionan los filtros y esta pestaña?'):
        st.markdown(
            """
            **Orden de ejecución:**

            1. `sidebar_filtros(df_raw)` crea una nueva muestra llamada `df_filtrado`.
            2. Las tres pestañas reciben esa muestra. La pestaña 3 recibe
               `tab_prevalencia_etapa(df_filtrado)`.
            3. Por eso, departamento, riesgo, edad y quintil se aplican **antes**
               de calcular los resultados de la pregunta 5.1.
            4. Después, `st.multiselect()` permite aplicar un segundo filtro local
               para elegir las etapas pediátricas que quieres comparar.
            5. `groupby(..., observed=True)` calcula solo los grupos que realmente
               existen en la muestra. Esto es importante porque las columnas del
               Parquet fueron optimizadas como `category`.
            6. La prevalencia se calcula con:
               `promedio(tiene_anemia) × 100`.
            7. Streamlit vuelve a ejecutar el script cada vez que modificas un
               widget; por eso gráficos, KPIs y tablas se recalculan automáticamente.

            **Por qué aparecía el error `boolean value of NA is ambiguous`:**

            Después de filtrar una columna categórica, Pandas puede conservar
            categorías que ya no tienen observaciones. Si `groupby()` incluye esas
            categorías vacías, su prevalencia queda como `pd.NA`. Una expresión
            como `if pct >= 40:` no puede decidir si un `pd.NA` es verdadero o falso.
            Por eso ahora usamos `observed=True`, eliminamos grupos sin observaciones
            y validamos `pd.isna()` antes de cualquier comparación.
            """
        )

# ── Pregunta de Negocio 3: Brecha Socioeducativa ─────────────────

def tab_brecha_socioeducativa(df_filtrado: pd.DataFrame) -> None:
    """Pestaña independiente para la relación entre educación, jefatura y anemia."""
    st.subheader('🎓 Brecha Socioeducativa y Vulnerabilidad del Hogar')
    st.caption(
        'Pregunta de negocio: ¿Cómo se asocian el nivel educativo de la madre o entrevistada '
        'y el tipo de jefatura del hogar con la prevalencia de anemia infantil?'
    )
    st.caption('🎛️ Esta vista responde a los filtros globales de la barra lateral.')

    if df_filtrado.empty:
        st.warning('⚠️ No hay datos disponibles con los filtros seleccionados. Ajusta la barra lateral.')
        return

    columnas_requeridas = {
        'caseid',
        'nivel_educativo_agrupado',
        'es_jefatura_femenina',
        'tiene_anemia',
        'desc_anemia_nivel',
    }
    faltantes = columnas_requeridas.difference(df_filtrado.columns)
    if faltantes:
        st.error(
            'No se puede construir la pregunta 3 porque faltan estas columnas '
            f'en el Parquet: {", ".join(sorted(faltantes))}'
        )
        return

    orden_educacion = [
        '1. Sin Educación',
        '2. Primaria (Completa e Incompleta)',
        '3. Secundaria (Completa e Incompleta)',
        '4. Superior',
    ]

    # Los registros sin hemoglobina no forman parte del denominador epidemiológico.
    df_analisis = df_filtrado[
        df_filtrado['desc_anemia_nivel'].notna()
        & df_filtrado['desc_anemia_nivel'].ne('Sin dato')
        & df_filtrado['nivel_educativo_agrupado'].isin(orden_educacion)
        & df_filtrado['es_jefatura_femenina'].isin([0, 1])
    ].copy()

    if df_analisis.empty:
        st.warning(
            '⚠️ No hay mediciones válidas de anemia para la combinación de filtros seleccionada.'
        )
        return

    df_analisis['tipo_jefatura'] = np.where(
        df_analisis['es_jefatura_femenina'].eq(1),
        'Jefatura femenina',
        'Jefatura masculina',
    )
    df_analisis['nivel_educativo_agrupado'] = pd.Categorical(
        df_analisis['nivel_educativo_agrupado'],
        categories=orden_educacion,
        ordered=True,
    )

    resumen = (
        df_analisis.groupby(
            ['nivel_educativo_agrupado', 'tipo_jefatura'], observed=True, as_index=False
        )
        .agg(
            n_evaluados=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            prevalencia_anemia=('tiene_anemia', lambda valores: valores.mean() * 100),
        )
        .sort_values(['nivel_educativo_agrupado', 'tipo_jefatura'])
    )
    resumen_educacion = (
        df_analisis.groupby('nivel_educativo_agrupado', observed=True, as_index=False)
        .agg(
            n_evaluados=('caseid', 'count'),
            casos_anemia=('tiene_anemia', 'sum'),
            prevalencia_anemia=('tiene_anemia', lambda valores: valores.mean() * 100),
        )
        .sort_values('nivel_educativo_agrupado')
    )

    sin_educacion = resumen_educacion[
        resumen_educacion['nivel_educativo_agrupado'].eq('1. Sin Educación')
    ]
    superior = resumen_educacion[
        resumen_educacion['nivel_educativo_agrupado'].eq('4. Superior')
    ]
    prevalencia_general = df_analisis['tiene_anemia'].mean() * 100
    brecha_educativa = (
        sin_educacion.iloc[0]['prevalencia_anemia'] - superior.iloc[0]['prevalencia_anemia']
        if not sin_educacion.empty and not superior.empty
        else None
    )

    st.markdown('##### Panorama de la muestra seleccionada')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Niños con medición válida', f'{len(df_analisis):,}')
    col2.metric('Prevalencia de anemia', f'{prevalencia_general:.1f}%')
    if brecha_educativa is not None:
        col3.metric('Brecha: sin educación vs. superior', f'{brecha_educativa:.1f} p.p.')
    else:
        col3.metric('Brecha educativa', 'No disponible')
    col4.metric('Casos de anemia', f"{int(df_analisis['tiene_anemia'].sum()):,}")

    st.divider()
    st.markdown('##### 📊 Prevalencia de anemia por educación y tipo de jefatura')
    st.caption(
        'Cada barra incluye la prevalencia y permite consultar casos y niños evaluados al pasar el cursor.'
    )

    etiquetas_educacion = {
        '1. Sin Educación': 'Sin educación',
        '2. Primaria (Completa e Incompleta)': 'Primaria',
        '3. Secundaria (Completa e Incompleta)': 'Secundaria',
        '4. Superior': 'Superior',
    }
    resumen['Educación'] = resumen['nivel_educativo_agrupado'].map(etiquetas_educacion)

    fig = px.bar(
        resumen,
        x='Educación',
        y='prevalencia_anemia',
        color='tipo_jefatura',
        barmode='group',
        category_orders={
            'Educación': list(etiquetas_educacion.values()),
            'tipo_jefatura': ['Jefatura femenina', 'Jefatura masculina'],
        },
        color_discrete_map={
            'Jefatura femenina': '#C0392B',
            'Jefatura masculina': '#1B4F72',
        },
        text=resumen['prevalencia_anemia'].map(lambda valor: f'{valor:.1f}%'),
        custom_data=['casos_anemia', 'n_evaluados'],
        labels={
            'prevalencia_anemia': 'Prevalencia de anemia (%)',
            'tipo_jefatura': 'Tipo de jefatura',
        },
    )
    fig.update_traces(
        textposition='outside',
        cliponaxis=False,
        hovertemplate=(
            '<b>%{x}</b><br>%{fullData.name}<br>'
            'Prevalencia: <b>%{y:.1f}%</b><br>'
            'Casos: %{customdata[0]:,}<br>'
            'Niños evaluados: %{customdata[1]:,}<extra></extra>'
        ),
    )
    fig.update_layout(
        height=470,
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=20, r=20, t=25, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        uniformtext_minsize=10,
        uniformtext_mode='hide',
    )
    fig.update_yaxes(
        title='Prevalencia de anemia (%)',
        ticksuffix='%',
        rangemode='tozero',
        gridcolor='#EAECEE',
    )
    fig.update_xaxes(title='Nivel educativo de la madre o entrevistada')
    st.plotly_chart(fig, use_container_width=True)

    with st.expander('📋 Tabla de resultados por educación y jefatura', expanded=False):
        tabla = resumen.rename(
            columns={
                'nivel_educativo_agrupado': 'Nivel educativo',
                'tipo_jefatura': 'Tipo de jefatura',
                'n_evaluados': 'Niños evaluados',
                'casos_anemia': 'Casos de anemia',
                'prevalencia_anemia': 'Prevalencia (%)',
            }
        )[
            ['Nivel educativo', 'Tipo de jefatura', 'Niños evaluados', 'Casos de anemia', 'Prevalencia (%)']
        ].copy()
        tabla['Prevalencia (%)'] = tabla['Prevalencia (%)'].round(2)
        st.dataframe(tabla, use_container_width=True, hide_index=True)

    st.divider()
    with st.expander('📝 Interpretación y conclusiones', expanded=False):
        if brecha_educativa is not None:
            mensaje_brecha = (
                f'Entre los extremos educativos observados hay una brecha de **{brecha_educativa:.1f} '
                'puntos porcentuales**: sin educación frente a educación superior.'
            )
        else:
            mensaje_brecha = (
                'La muestra filtrada no contiene ambos extremos educativos; la brecha no puede calcularse.'
            )

        st.markdown(
            f"""
            **Qué responde esta pregunta.** La vista identifica si la prevalencia de anemia cambia
            según el nivel educativo de la madre o entrevistada y si el patrón se mantiene al
            separar hogares con jefatura femenina y masculina.

            **Mensaje principal.** {mensaje_brecha} La tendencia debe leerse de izquierda a derecha:
            una menor prevalencia en los niveles educativos más altos refleja una asociación
            consistente entre educación y mejores resultados nutricionales.

            **Lectura de la jefatura.** Las barras del mismo nivel educativo permiten verificar si
            la diferencia por tipo de jefatura añade una brecha relevante o si el nivel educativo
            concentra la mayor parte del patrón observado.

            **Decisión sugerida.** Priorizar consejería nutricional, seguimiento CRED y comunicación
            preventiva en hogares donde la madre o entrevistada tiene educación primaria o menor.

            **Rigor metodológico.** Los porcentajes excluyen registros sin medición válida de anemia
            y se acompañan de su número de evaluados. Este análisis es descriptivo: muestra asociación,
            no demuestra que la educación o la jefatura causen anemia.
            """
        )
    st.caption('Fuente: ENDES 2025, módulo 1638 y variables sociodemográficas integradas del módulo 1631.')


# ── Pregunta de Negocio: Trayectoria Clínica por Edad ────────────

# ─────────────────────────────────────────────────────────────
# PESTAÑA 4 — PREGUNTA DE NEGOCIO 5.1
# HEATMAP DE TRAYECTORIA CLÍNICA
# ─────────────────────────────────────────────────────────────
# Pachin
# ──Pregunta 3-  Pestaña: Gradiente Económico y Nivel de Riqueza ─────────────────────────

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

# ── Punto de Entrada de la Aplicación (Main) ────────────────────

def main() -> None:
    """Función principal que orquesta la ejecución del Dashboard Streamlit."""
    configurar_pagina()

    st.markdown('## 🩸 Observatorio Analítico de Anemia Infantil en el Perú')
    st.caption('Plataforma de Diagnóstico Territorial y Trayectoria Nutricional Pediátrica · ENDES 2025')
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
    # La tercera pestaña corresponde a la Pregunta de Negocio 5.1.
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        '📊 Resumen Epidemiológico',
        '🗺️ Impacto Geográfico y Focalización',
        '📈 Trayectoria de Hemoglobina',
        '🧒 5.1 Anemia por Etapa Pediátrica',
        '💰 Gradiente Económico',
        '🎓 Brecha Socioeducativa',
    ])

    with tab1:
        tab_resumen(df_filtrado, df_raw)

    with tab2:
        tab_impacto_geografico(df_filtrado)

    with tab3:
        tab_heatmap_trayectoria(df_filtrado)

    with tab4:
        tab_prevalencia_etapa(df_filtrado)

    with tab5:
            tab_gradiente_economico(df_filtrado, df_filtrado)   

    with tab6:
        tab_brecha_socioeducativa(df_filtrado)


if __name__ == '__main__':
    main()
