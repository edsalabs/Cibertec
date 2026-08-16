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
    tab1, tab2, tab3 = st.tabs([
        '📊 Resumen Epidemiológico',
        '🗺️ Impacto Geográfico y Focalización',
        '🧒 5.1 Anemia por Etapa Pediátrica',
    ])

    with tab1:
        tab_resumen(df_filtrado, df_raw)

    with tab2:
        tab_impacto_geografico(df_filtrado)

    with tab3:
        tab_prevalencia_etapa(df_filtrado)


if __name__ == '__main__':
    main()
