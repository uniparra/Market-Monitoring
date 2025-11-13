import streamlit as st
import requests
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="RAG Financial Predictor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# URL de la API (configurable desde variables de entorno)
import os
API_URL = os.getenv("BACKEND_URL")

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-healthy {
        color: green;
        font-weight: bold;
    }
    .status-unhealthy {
        color: red;
        font-weight: bold;
    }
    .prediction-box {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">📈 RAG Financial Predictor</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")

    # Health check
    st.subheader("Estado del Sistema")
    if st.button("🔍 Verificar Estado"):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    st.markdown('<p class="status-healthy">✅ Sistema Operativo</p>', unsafe_allow_html=True)
                    st.json(data)
                else:
                    st.markdown('<p class="status-unhealthy">❌ Sistema No Disponible</p>', unsafe_allow_html=True)
                    st.json(data)
            else:
                st.error(f"Error: {response.status_code}")
        except Exception as e:
            st.error(f"No se puede conectar a la API: {e}")

    st.markdown("---")

    # Información
    st.subheader("ℹ️ Información")
    st.info("""
    **¿Cómo funciona?**
    
    1. Ingresa tu consulta sobre un símbolo bursátil
    2. El sistema analiza señales técnicas y noticias
    3. Obtén una predicción fundamentada
    
    **Ejemplos de consultas:**
    - ¿Qué predicción hay para SLB?
    - Analiza AAPL con noticias recientes
    - ¿Es buen momento para comprar TSLA?
    """)

    st.markdown("---")
    st.caption(f"API URL: {API_URL}")
    st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("💬 Consulta Personalizada")

    # Formulario de consulta libre
    with st.form("query_form"):
        question = st.text_area(
            "Escribe tu consulta:",
            height=100,
            placeholder="Ejemplo: ¿Cuál es la predicción para SLB basada en las últimas señales técnicas y noticias del sector energético?",
            help="Puedes preguntar sobre cualquier símbolo bursátil"
        )

        submitted = st.form_submit_button("🔮 Obtener Predicción", use_container_width=True)

        if submitted and question:
            with st.spinner("🤖 Analizando señales técnicas y noticias..."):
                try:
                    response = requests.post(
                        f"{API_URL}/query",
                        json={"question": question},
                        timeout=30
                    )

                    if response.status_code == 200:
                        data = response.json()

                        if "error" in data:
                            st.error(f"❌ Error: {data['error']}")
                        else:
                            st.success("✅ Análisis completado")

                            # Mostrar respuesta
                            st.markdown('<div class="prediction-box">', unsafe_allow_html=True)
                            st.markdown("### 📊 Predicción y Análisis")
                            st.markdown(data.get("answer", "No hay respuesta disponible"))
                            st.markdown('</div>', unsafe_allow_html=True)

                            # Información adicional
                            with st.expander("🔍 Ver detalles técnicos"):
                                st.json(data)
                    else:
                        st.error(f"Error HTTP: {response.status_code}")

                except requests.exceptions.Timeout:
                    st.error("⏱️ La consulta excedió el tiempo de espera. Intenta de nuevo.")
                except Exception as e:
                    st.error(f"❌ Error de conexión: {e}")

with col2:
    st.header("🎯 Análisis Rápido")

    # Análisis por símbolo específico
    st.subheader("Por Símbolo")

    # Lista de símbolos comunes
    common_symbols = ["SLB", "XOM", "CVX", "NEE"]

    # Selectbox para símbolos comunes
    symbol_select = st.selectbox(
        "Selecciona un símbolo:",
        options=["Personalizado"] + common_symbols,
        help="Selecciona un símbolo de la lista o escribe uno personalizado"
    )

    # Input para símbolo personalizado
    if symbol_select == "Personalizado":
        symbol = st.text_input(
            "Símbolo personalizado:",
            placeholder="Ej: AAPL",
            max_chars=5
        ).upper()
    else:
        symbol = symbol_select

    if st.button("📈 Analizar Símbolo", use_container_width=True, disabled=not symbol):
        with st.spinner(f"🔍 Analizando {symbol}..."):
            try:
                response = requests.post(
                    f"{API_URL}/analyze-symbol",
                    params={"symbol": symbol},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()

                    if "error" in data:
                        st.error(f"❌ {data['error']}")
                    else:
                        st.success(f"✅ Análisis de {symbol}")

                        st.markdown('<div class="prediction-box">', unsafe_allow_html=True)
                        st.markdown(f"### 📊 {symbol}")
                        st.markdown(data.get("answer", "No hay datos disponibles"))
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error(f"Error: {response.status_code}")

            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    # Sección de ejemplos
    st.subheader("💡 Ejemplos de Consultas")

    example_queries = [
        "¿Qué predicción hay para SLB considerando las noticias del sector energético?",
        "Analiza AAPL: ¿hay señales de compra o venta?",
        "¿Es buen momento para invertir en TSLA según el análisis técnico?",
        "Compara las señales técnicas de MSFT con las noticias recientes"
    ]

    for i, example in enumerate(example_queries, 1):
        if st.button(f"📝 Ejemplo {i}", key=f"example_{i}", use_container_width=True):
            st.session_state.example_query = example
            st.rerun()

# Si hay una consulta de ejemplo seleccionada, mostrarla
if "example_query" in st.session_state:
    with col1:
        st.info(f"📝 Consulta de ejemplo cargada: {st.session_state.example_query}")
        st.session_state.pop("example_query")

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🤖 Powered by LangChain, Weaviate & Google Gemini | 
        📊 Análisis Técnico + Fundamental</p>
    </div>
""", unsafe_allow_html=True)