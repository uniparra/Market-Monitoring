# Market-Monitoring


Se ha diseñado un sistema RAG para responder preguntas de usuarios sobre acción de precio de ciertas compañías energéticas. Aunque no fuera el objetivo de la práctica dado que estoy realizando un curso de FLINK he visto la posibilidad de poner los nuevos conocimientos en práctica. El diagrama del servicio es el siguiente, 


<img width="866" height="618" alt="Diagrama_de_Arquitectura_Completa" src="https://github.com/user-attachments/assets/87af1d47-c6c9-4c43-8ccf-c4ffddced738" />

En resumen, 

1. Se ingestan noticias financieras desde un par de RSS Feeds y se obtienen datos tecnicos sobre precio de las compañías energéticas, 
2. Éstas se enriquecen con flink para poder obtener ciertas métricas simples, usadas para análisis técnico.
3. Un consumer que guarda los datos tecnicos enriquecidos y los fundamentales en el vector store weaviate, elegido por su capacidad de generar objetos con varias capas, el vector, los filtros y las búsquedas de palabras clave. De esta forma se pueden diseñar fácilmente estrategias de búsqueda hibrida que mejoran la performace del retrieve. Por otro lado, dado que los datos técnicos no tienen gran semántica se han usado dos estrategias de indexación,

    1. Inverse Index para los datos técnicos estos no se vectorizan ya que es suficiente con filtrar symbolos, rangos de fechas y buscar eventos determinados.
    2. Indexación hibrida para los datos fundamentales, se vectoriza la noticia y se disponibilizan ciertos campos, como source, symbol o publishedTimestamp como filtros estructurados. Esto permite combinar búsquedas por similitud semántica con filtrados específicos, equilibrando recuperación contextual y precisión en la selección.

4. Como modelo de embedding se ha usado, sentence-transformers/all-MiniLM-L6-v2 de huggingface, por estar optimizada para representación semántica eficiente de texto, y ofrece una excelente relación entre rendimiento y coste computacional, lo que resulta clave en un sistema RAG que se actualiza en tiempo real. En lo académico, también por explorar otras opcio 
    1. En determinados casos sí realizaría fine-tuning con el objetivo de enseñar al modelo a relacionar noticias geopolíticas con variaciones en el precio de los activos, utilizando pares de frases como “Sube el precio del Brent por tensiones geopolíticas” y “El crudo se encarece tras el conflicto en Oriente Medio”.nes fuera de las opciones comerciales más conocidas.

5. El retriever usa gemini. Esencialmente porque ofrece un buen balance entre calidad de respuestas, capacidad gratuita e integración con langchain. Esto se integra en el mismo servicio que el backend. Donde además de disponibilizar el post query también se da una opción de pregutnar sobre empresas en concreto a partir de su symbolo.

6. Se ha creado también un pequeño front con streamlit.



## Cómo ejecutar
Para ejecutar el código es suficiente con compilar el componente de flink, situandonos en el directorio raíz del microservicio, (/services/flink) con (version de sbt, 1.9.7) 
```
sbt assembly
```
Mientras tanto configurar el .env ir añadiendo lo siguiente, 
```
TWELVE_DATA_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
GOOGLE_PROJECT_ID=
HUGGINGFACE_APIKEY=

KAFKA_BOOTSTRAP_SERVER=kafka:29092
WEAVIATE_URL=weaviate:8080
BACKEND_URL=http://rag-api:8000

FUNDAMENTAL_TOPIC="raw_market_data_fundamental"
TECHNICAL_TOPIC="raw_market_data_technical"
PROCESSED_TECHNICAL_TOPIC="processed_market_signals"
```
Finalmente montar el docker compose. Tras ello abrimos, http://localhost:8501/ que es donde estará el front para interactuar con el rag.



## Cosas a mejorar:
1. Gestionar la eliminación de los índices. Ya que es un proceso, que en el caso de que estuviera en producción sería un proceso de streaming habría que gestionar bien la eliminación de índices. Los datos técnicos se podrían borrar con un criterio de tiempo, según volumetría eliminar aquellos que tienen más de X tiempo. Tal vez añadir un proceso que los compactifique. Es decir, que vaya guardando sólo ciertos datos técnicos con relevancia a futuro y eliminar los demás. En cuanto a las noticias sin valor de presente simplemente se podrían guardar en un data storage etiquetandolos según relevancia que ya hayan tenido en precio de acción para un futuro entrenamiento y eliminarlas del vector store al cabo de X tiempo.
2. Las RSS Feeds no me daban información sobre el articulo en cuestion, solo una url, al no haber encontrado mejores fuentes he acudido a un agente de ia para que se inventara, a partir de los titulares, un resumen de noticia que es lo que he usado como noticia. Por lo que un web scrapper sería ideal en este punto.
3. El diseño funcional seguramente sea muy mejorable, desde las señales técnicas calculadas hasta las fuentes de las noticias son mejorables.
4. Creo que podría ser interesante dejar la compilación del componente de scala (de flink) como tarea dentro del contenedor. Para evitar al usuario tener que compilar.
5. Hay una colección de variables que en lugar de ir en el .env deberían de ir en un .conf.
