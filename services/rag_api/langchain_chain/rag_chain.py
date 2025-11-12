from langchain_weaviate import WeaviateVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.runnables import RunnableParallel, RunnableLambda
import weaviate
from weaviate.client import WeaviateClient
from operator import itemgetter
from typing import List, Dict, Any
import os

from .prompt import RAG_PROMPT
from .llm import SMALL_LLM as LLM

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")

try:
    weaviate_client = weaviate.connect_to_local(
        host=WEAVIATE_URL.split(":")[0],
        port=int(WEAVIATE_URL.split(":")[-1])
    )
    print("[INIT] Conexión a Weaviate exitosa.")
except Exception as e:
    print(f"[INIT] ERROR al conectar a Weaviate: {e}")
    weaviate_client = None


def format_fundamental_news(docs: List[Any]) -> str:
    """
    Formatea las noticias fundamentales en texto estructurado para el LLM.
    """
    if not docs:
        return "No se encontraron noticias fundamentales relevantes."

    news_items = []
    for doc in docs:
        metadata = doc.metadata
        news = (
            f"Título: {metadata.get('title', 'Sin título')}\n"
            f"Fuente: {metadata.get('source', 'Fuente desconocida')}\n"
            f"Resumen: {doc.page_content}\n"
            f"Link: {metadata.get('link', 'N/A')}"
        )
        news_items.append(news)

    return "\n\n---\n\n".join(news_items)


def get_technical_signals(client: WeaviateClient, symbols: List[str] = None, limit: int = 10) -> List[Dict]:
    """
    Recupera señales técnicas usando búsqueda por filtros (no vectorial).
    Opcionalmente filtra por símbolos específicos.
    """
    if not client:
        return []

    try:
        collection = client.collections.get("TechnicalSignal")

        # Si hay símbolos específicos, filtrar por ellos
        if symbols and len(symbols) > 0:
            # Crear filtro para múltiples símbolos
            from weaviate.classes.query import Filter

            if len(symbols) == 1:
                query_result = collection.query.fetch_objects(
                    filters=Filter.by_property("symbol").equal(symbols[0]),
                    limit=limit
                )
            else:
                symbol_filters = [Filter.by_property("symbol").equal(s) for s in symbols]
                combined_filter = symbol_filters[0]
                for f in symbol_filters[1:]:
                    combined_filter = combined_filter | f

                query_result = collection.query.fetch_objects(
                    filters=combined_filter,
                    limit=limit
                )
        else:
            # Sin filtro, obtener las más recientes
            query_result = collection.query.fetch_objects(
                limit=limit,
                sort=collection.query.Sort.by_property("timestamp", ascending=False)
            )

        # Convertir a formato compatible
        results = []
        for obj in query_result.objects:
            results.append({
                "metadata": obj.properties,
                "page_content": obj.properties.get("details", "")
            })

        return results

    except Exception as e:
        print(f"[ERROR] Error al recuperar señales técnicas: {e}")
        return []


def get_news_retriever(client: WeaviateClient):
    if not client:
        return None

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectorstore = WeaviateVectorStore(
        client=client,
        index_name="FinancialNews",
        text_key="summary",
        embedding=embeddings
    )

    # Usar hybrid search en lugar de solo similarity search
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )


news_retriever = get_news_retriever(weaviate_client)


def create_rag_chain():
    """
    Crea la cadena RAG con estrategia híbrida:
    - TechnicalSignal: búsqueda por filtros (inverse index)
    - FinancialNews: búsqueda semántica (vectorial)
    """
    if not news_retriever or not weaviate_client:
        return None

    def extract_symbols_from_query(question: str) -> List[str]:
        """
        Extrae símbolos bursátiles de la pregunta.
        Formato típico: 3-5 letras mayúsculas.
        """
        import re

        symbols = re.findall(r'\b[A-Z]{2,5}\b', question)
        return list(set(symbols))

    def retrieve_technical_signals(question: str) -> str:
        """
        Recupera señales técnicas relevantes.
        Si hay símbolos en la pregunta, filtra por ellos.
        """
        symbols = extract_symbols_from_query(question)

        signals = get_technical_signals(weaviate_client, symbols=symbols if symbols else None, limit=10)

        if not signals:
            return "No se encontraron señales técnicas relevantes."

        formatted = []
        for signal in signals:
            metadata = signal["metadata"]
            text = (
                f"Símbolo: {metadata.get('symbol', 'N/A')}\n"
                f"Tipo de Evento: {metadata.get('eventType', 'unknown')}\n"
                f"Detalles: {metadata.get('details', signal['page_content'])}\n"
                f"Precio Mín: {metadata.get('minPrice', 'N/A')}\n"
                f"Precio Máx: {metadata.get('maxPrice', 'N/A')}\n"
                f"Timestamp: {metadata.get('timestamp', 'N/A')}"
            )
            formatted.append(text)

        return "\n\n---\n\n".join(formatted)

    retrieval_chain = RunnableParallel(
        technical_context=itemgetter("question") | RunnableLambda(retrieve_technical_signals),
        fundamental_context=itemgetter("question") | news_retriever | RunnableLambda(format_fundamental_news),
        question=itemgetter("question")
    )

    return retrieval_chain | RAG_PROMPT | LLM


rag_chain = create_rag_chain()