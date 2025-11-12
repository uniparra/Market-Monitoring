import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from langchain_chain.rag_chain import rag_chain, weaviate_client
from langchain_chain.llm import GEMINI_MODEL

app = FastAPI(
    title="RAG Financial Predictor",
    description="Sistema de predicción de precio basado en análisis técnico y fundamental"
)


class Query(BaseModel):
    question: str

    class Config:
        json_schema_extra = {
            "example": {
                "question": "¿Cuál es la predicción para SLB basada en las últimas señales técnicas y noticias del sector energético?"
            }
        }


@app.get("/")
async def root():
    return {
        "message": "RAG Financial Predictor API",
        "endpoints": {
            "/query": "POST - Realiza una consulta de predicción",
            "/health": "GET - Verifica el estado del sistema"
        }
    }


@app.get("/health")
async def health_check():
    """Verifica el estado de conexión con Weaviate."""
    if not weaviate_client:
        return {"status": "unhealthy", "weaviate": "disconnected"}
    return {"status": "healthy", "weaviate": "connected"}


@app.post("/query")
async def process_query(query: Query):
    """
    Endpoint principal para predicción de precio basada en análisis RAG.
    """
    if not rag_chain:
        return {
            "error": "Sistema RAG no inicializado. Verifica la conexión con Weaviate."
        }

    try:
        input_data = {"question": query.question}
        response = rag_chain.invoke(input_data)

        return {
            "answer": response.content,
            "model": GEMINI_MODEL
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {
            "error": f"Error al procesar la consulta: {str(e)}"
        }


@app.post("/analyze-symbol")
async def analyze_symbol(symbol: str):
    """
    Endpoint específico para analizar un símbolo concreto.
    """
    query = Query(
        question=f"Analiza las señales técnicas y noticias recientes para {symbol}. Proporciona una predicción de precio con nivel de confianza."
    )
    return await process_query(query)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6800)
