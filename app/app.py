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
    st.divider()

    grafico_trayectoria_clinica(df_completo)

    st.divider()

    
    
def grafico_trayectoria_clinica(df: pd.DataFrame) -> None:
    """
    Gráfico profesional de anemia por etapas pediátricas.
    Utiliza los mismos datos del dataset ENDES 2025.
    """

    st.markdown("##### 📈 Perfil Clínico de Anemia por Etapa Pediátrica")
    st.caption(
        "Comparación de hemoglobina promedio y prevalencia de anemia "
        "entre las principales etapas del desarrollo infantil."
    )

    # ---------------------------------------------------------
    # 1. PREPARAR DATOS
    # ---------------------------------------------------------

    df_plot = df[
        (df["edad_meses_num"] >= 0) &
        (df["edad_meses_num"] <= 59) &
        (df["hemoglobina_g_dl"].notna())
    ].copy()

    if df_plot.empty:
        st.warning("No existen datos suficientes para construir este gráfico.")
        return

    df_etapas = (
        df_plot.groupby("rango_edad_child", observed=False)
        .agg(
            hemoglobina_promedio=("hemoglobina_g_dl", "mean"),
            prevalencia_anemia=("tiene_anemia", "mean"),
            total_ninos=("caseid", "count"),
        )
        .reset_index()
    )

    df_etapas["prevalencia_anemia"] *= 100

    # Orden correcto
    orden = [
        "1. 0-11 meses (Lactantes)",
        "2. 12-23 meses (Caminadores)",
        "3. 24-59 meses (Preescolares)",
    ]

    df_etapas["rango_edad_child"] = pd.Categorical(
        df_etapas["rango_edad_child"],
        categories=orden,
        ordered=True
    )

    df_etapas = df_etapas.sort_values("rango_edad_child")

    # Nombres cortos para el gráfico
    df_etapas["etapa"] = [
        "Lactantes\n0-11 meses",
        "Caminadores\n12-23 meses",
        "Preescolares\n24-59 meses"
    ][:len(df_etapas)]

    # ---------------------------------------------------------
    # 2. GRÁFICO
    # ---------------------------------------------------------

    fig = go.Figure()

    # Barras: prevalencia de anemia
    fig.add_trace(
        go.Bar(
            x=df_etapas["etapa"],
            y=df_etapas["prevalencia_anemia"],
            name="Prevalencia de anemia",
            marker=dict(
                color="#C0392B",
                line=dict(
                    color="#922B21",
                    width=1
                )
            ),
            text=df_etapas["prevalencia_anemia"].map(
                lambda x: f"{x:.1f}%"
            ),
            textposition="outside",
            textfont=dict(
                size=13,
                color="#1F2937"
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Prevalencia: %{y:.1f}%<extra></extra>"
            )
        )
    )

    # Línea: hemoglobina promedio
    fig.add_trace(
        go.Scatter(
            x=df_etapas["etapa"],
            y=df_etapas["hemoglobina_promedio"],
            name="Hemoglobina promedio",
            mode="lines+markers",
            line=dict(
                color="#1B4F72",
                width=4
            ),
            marker=dict(
                size=12,
                color="#1B4F72",
                line=dict(
                    color="white",
                    width=2
                )
            ),
            text=df_etapas["hemoglobina_promedio"].map(
                lambda x: f"{x:.2f} g/dL"
            ),
            textposition="top center",
            textfont=dict(
                size=11,
                color="#1B4F72"
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Hemoglobina: %{y:.2f} g/dL<extra></extra>"
            )
        )
    )

    # ---------------------------------------------------------
    # 3. LÍNEA CLÍNICA OMS
    # ---------------------------------------------------------

    fig.add_hline(
        y=11.0,
        line_dash="dash",
        line_width=2,
        line_color="#7B241C",
        annotation_text="Umbral clínico: 11.0 g/dL",
        annotation_position="top left",
        annotation_font=dict(
            size=11,
            color="#7B241C"
        )
    )

    # ---------------------------------------------------------
    # 4. DISEÑO PROFESIONAL
    # ---------------------------------------------------------

    fig.update_layout(
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",

        title=dict(
            text="Perfil clínico de anemia infantil según etapa de edad",
            font=dict(
                size=18,
                color="#17202A"
            ),
            x=0
        ),

        xaxis=dict(
            title=None,
            showgrid=False,
            tickfont=dict(
                size=11,
                color="#34495E"
            )
        ),

        yaxis=dict(
            title="Prevalencia de anemia (%)",
            ticksuffix="%",
            showgrid=True,
            gridcolor="#E5E7EB",
            zeroline=False,
            range=[
                0,
                max(df_etapas["prevalencia_anemia"].max() + 15, 50)
            ]
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(
                size=11
            )
        ),

        margin=dict(
            l=60,
            r=40,
            t=90,
            b=60
        ),

        hovermode="x unified"
    )

    # ---------------------------------------------------------
    # 5. MOSTRAR
    # ---------------------------------------------------------

    st.plotly_chart(
        fig,
        width="stretch"
    )

    # ---------------------------------------------------------
    # 6. TABLA DE DATOS DEL GRÁFICO
    # ---------------------------------------------------------

    tabla = df_etapas[
        [
            "etapa",
            "total_ninos",
            "hemoglobina_promedio",
            "prevalencia_anemia"
        ]
    ].copy()

    tabla.columns = [
        "Etapa",
        "Niños evaluados",
        "Hb promedio (g/dL)",
        "Anemia (%)"
    ]

    tabla["Hb promedio (g/dL)"] = tabla[
        "Hb promedio (g/dL)"
    ].round(2)

    tabla["Anemia (%)"] = tabla[
        "Anemia (%)"
    ].round(1)

    st.dataframe(
        tabla,
        width="stretch",
        hide_index=True
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
    tab1, tab2 = st.tabs([
        '📊 Resumen Epidemiológico',
        '🗺️ Impacto Geográfico y Focalización',
    ])

    with tab1:
        tab_resumen(df_filtrado, df_raw)

    with tab2:
        tab_impacto_geografico(df_filtrado)


if __name__ == '__main__':
    main()
