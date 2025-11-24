# Market Monitoring

Sistema RAG (Retrieval-Augmented Generation) en tiempo real diseñado para responder preguntas sobre la acción de precio y movimientos del mercado de compañías del sector energético, aprovechando Apache Flink para procesamiento de streams y capacidades de búsqueda híbrida.

## Arquitectura General

<img width="866" height="618" alt="Diagrama_de_Arquitectura_Completa" src="https://github.com/user-attachments/assets/87af1d47-c6c9-4c43-8ccf-c4ffddced738" />

## Componentes del Sistema

### 1. Ingesta de Datos
El sistema ingesta datos de múltiples fuentes:
- Noticias financieras a través de feeds RSS
- Datos técnicos de precio para compañías del sector energético

### 2. Procesamiento de Streams con Apache Flink
Pipeline de enriquecimiento de datos en tiempo real que calcula métricas e indicadores de análisis técnico comúnmente utilizados en análisis financiero.

### 3. Estrategia de Indexación Híbrida
Los datos se almacenan en **Weaviate**, una base de datos vectorial elegida por su estructura de objetos multicapa que soporta vectores, filtros y búsquedas por palabras clave. El sistema emplea dos estrategias de indexación distintas:

#### Datos Técnicos (Índice Invertido)
Los datos técnicos de precio se almacenan mediante indexación invertida sin vectorización. Este enfoque permite filtrado eficiente por:
- Símbolos bursátiles
- Rangos de fechas
- Eventos técnicos específicos

#### Datos Fundamentales (Índice Híbrido)
Las noticias se indexan mediante un enfoque híbrido:
- **Vectorización semántica** del contenido de artículos para búsqueda por similitud
- **Filtros estructurados** para metadatos (fuente, símbolo, timestamp de publicación)
- Esta combinación balancea recuperación contextual con filtrado de precisión

### 4. Modelo de Embeddings
El sistema utiliza **sentence-transformers/all-MiniLM-L6-v2** de Hugging Face, seleccionado por:
- Representación semántica optimizada de texto
- Excelente relación rendimiento-coste
- Idoneidad para sistemas RAG en tiempo real

**Mejora Potencial**: Realizar fine-tuning del modelo con pares específicos del dominio (ej. "Sube el precio del Brent por tensiones geopolíticas" → "El crudo se encarece tras el conflicto en Oriente Medio") podría mejorar la correlación entre noticias geopolíticas y movimientos de precio de activos.

### 5. Recuperación y Generación
El retriever utiliza **Google Gemini** por:
- Generación de respuestas de calidad
- Operación rentable dentro de los límites del tier gratuito
- Integración nativa con LangChain

El servicio backend proporciona:
- Consultas generales de mercado
- Análisis específico de compañías por símbolo

### 6. Interfaz de Usuario
Un frontend basado en Streamlit proporciona una interfaz intuitiva para la interacción con el sistema.

## Primeros Pasos

### Requisitos Previos
Crea un archivo `.env` con las siguientes claves API:

```env
TWELVE_DATA_API_KEY=tu_clave_aqui
OPENAI_API_KEY=tu_clave_aqui
GOOGLE_API_KEY=tu_clave_aqui
GOOGLE_PROJECT_ID=tu_id_de_proyecto
HUGGINGFACE_APIKEY=tu_clave_aqui
```

### Instalación

1. Configura tu archivo `.env` con las claves API requeridas
2. Inicia los servicios usando Docker Compose:
   ```bash
   docker-compose up
   ```
3. Accede al frontend en `http://localhost:8501`

## Mejoras Futuras

### Gestión de Índices
Para un despliegue en producción, implementar gestión del ciclo de vida para datos en streaming:
- **Datos técnicos**: Políticas de retención basadas en tiempo, estrategias de compactación de datos y archivo selectivo de indicadores históricos relevantes
- **Datos de noticias**: Archivar artículos según su impacto histórico en la acción de precio para futuros entrenamientos del modelo, con eliminación automática del vector store después de un período definido

### Fuentes de Datos Mejoradas
Reemplazar la implementación actual de feeds RSS con un web scraper robusto para extraer el contenido completo de los artículos en lugar de depender de resúmenes generados por IA a partir de titulares.

### Calidad de Señales
Refinar los indicadores técnicos calculados por el pipeline de Flink y diversificar las fuentes de noticias para mejorar la calidad de las señales y la cobertura.

### Mejoras Adicionales
Se planean mejoras continuas en la fiabilidad del sistema, rendimiento y capacidades analíticas.

## Stack Tecnológico

- **Procesamiento de Streams**: Apache Flink
- **Base de Datos Vectorial**: Weaviate
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **LLM**: Google Gemini
- **Frontend**: Streamlit
- **Orquestación**: Docker Compose
