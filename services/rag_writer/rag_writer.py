import os
import json
import time
import logging
from confluent_kafka import Consumer
import weaviate
import google.genai as genai

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Config
KAFKA_BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVER")
TOPIC_FUNDAMENTAL = os.getenv("FUNDAMENTAL_TOPIC")
TOPIC_TECHNICAL = os.getenv("PROCESSED_TECHNICAL_TOPIC")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
huggingface_key = os.getenv("HUGGINGFACE_APIKEY")

# Kafka consumer
consumer_conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "group.id": os.getenv("KAFKA_GROUP", "rag-writer-group"),
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False
}

consumer = Consumer(consumer_conf)
consumer.subscribe([TOPIC_FUNDAMENTAL, TOPIC_TECHNICAL])

client = weaviate.connect_to_local(
    host=WEAVIATE_URL.split(":")[0],
    port=int(WEAVIATE_URL.split(":")[1]),
    headers={"X-HuggingFace-Api-Key": huggingface_key}
)

with open("./weaviate_config/schema.json", "r") as f:
    schema = json.load(f)

for collection_def in schema.get("classes", []):
    name = collection_def.get("class")

    if client.collections.exists(name):
        logger.info(f"[Weaviate] Collection '{name}' already exists.")
    else:
        client.collections.create_from_dict(collection_def)
        logger.info(f"[Weaviate] Created collection '{name}' from schema.")

news_collection = client.collections.get("FinancialNews")
signals_collection = client.collections.get("TechnicalSignal")

gemini_client = None
try:
    gemini_client = genai.Client()
except Exception as e:
    pass

def generate_new(title):
    """
    Genera un resumen de noticia utilizando el SDK de Gemini.
    """
    if gemini_client is None:
        return "Error: Cliente Gemini no inicializado (clave GEMINI_API_KEY no válida)."

    try:
        system_instruction = (
            "Eres un periodista financiero. Redacta noticias breves, claras e imparciales. "
            "El tono es informativo, no más de 100 palabras."
        )

        prompt = (
            f"Redacta una noticia breve a partir del siguiente titular:\n"
            f"Titular: \"{title}\""
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.7
            }
        )
        new = response.text.strip()

        logger.info("Resumen de noticia generado.")
        return new

    except Exception as e:
        return f"Error al generar la noticia con Gemini: {e}"


def insert_fundamental(payload):
    data = {
        "title": payload.get("title"),
        "summary": generate_new(payload.get("title")),
        "link": payload.get("link"),
        "source": payload.get("source"),
        "sourceId": payload.get("id"),
        "symbol": payload.get("symbol"),
        "publishedTimestamp": payload.get("publishedTimestamp")
    }
    news_collection.data.insert(data)
    logger.info(f"[Weaviate] Inserted FinancialNews: {payload.get('id')}")


def insert_technical(payload):
    data = {
        "symbol": payload.get("symbol"),
        "timestamp": payload.get("timestamp"),
        "eventType": payload.get("eventType"),
        "details": payload.get("details"),
        "minPrice": payload.get("minPrice"),
        "maxPrice": payload.get("maxPrice"),
        "sma20": payload.get("sma20"),
        "sma50": payload.get("sma50")
    }
    signals_collection.data.insert(data)
    logger.info(f"[Weaviate] Inserted TechnicalSignal for {payload.get('symbol')}")


def run():
    logger.info("rag-writer started, consuming from:", TOPIC_FUNDAMENTAL, TOPIC_TECHNICAL)
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                logger.error("Kafka error:", msg.error())
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception as e:
                logger.error("Invalid JSON:", e)
                consumer.commit(message=msg)
                continue

            topic = msg.topic()
            try:
                if topic == TOPIC_FUNDAMENTAL:
                    insert_fundamental(payload)
                elif topic == TOPIC_TECHNICAL:
                    insert_technical(payload)
                else:
                    logger.error("Unknown topic:", topic)
                consumer.commit(message=msg)
            except Exception as e:
                logger.error("Error inserting into Weaviate:", e)
            time.sleep(3)

    except KeyboardInterrupt:
        logger.error("Stopping consumer...")
    finally:
        consumer.close()
        client.close()
        print("rag-writer stopped cleanly.")


if __name__ == "__main__":
    run()
