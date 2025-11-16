from datetime import datetime
import os
import time
import json
import requests
import feedparser
import logging
from confluent_kafka import Producer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()  # Solo consola
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
KAFKA_BROKER = os.environ.get('KAFKA_BOOTSTRAP_SERVER', 'kafka:9092')
TWELVE_DATA_API_KEY = os.environ.get('TWELVE_DATA_API_KEY')

TICKERS_ENERGIA = ["XOM", "CVX", "SLB", "NEE"]  # ExxonMobil, Chevron, Schlumberger, NextEra Energy
KEY_ENERGY_WORDS = ["gas", "oil", "chevron", "exxonmobil", "nextera", "schlumberger"]


POLLING_INTERVAL_TECHNICAL = 15 * 60 # 15 minutos para no sobrepasar limites gratuitos API Twelve Data y la aplicación pueda estar funcionando 24 horas.
POLLING_INTERVAL_FUNDAMENTAL = 10 * 60
LAST_RUN_TECHNICAL = 0
LAST_RUN_FUNDAMENTAL = 0

TOPIC_TECHNICAL = 'raw_market_data_technical'
TOPIC_FUNDAMENTAL = 'raw_market_data_fundamental'

# --- PRODUCTOR KAFKA (Confluent) ---
def delivery_report(err, msg):
    """Callback que confirma la entrega de mensajes o muestra error."""
    if err is not None:
        logger.error(f"Entrega fallida: {err}")
    else:
        logger.info(f"Mensaje entregado a {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

try:
    producer_config = {
        'bootstrap.servers': KAFKA_BROKER,
        'client.id': 'market-data-producer',
        'acks': '1'
    }
    producer = Producer(producer_config)
except Exception as e:
    logger.error(f"Error al conectar a Kafka: {e}")
    exit(1)


# --- FUNCIONES DE POLLING ---
def get_technical_data():
    """Recupera datos técnicos de Twelve Data."""
    logger.info("--- Polling: Datos Técnicos ---")

    for ticker in TICKERS_ENERGIA:
        url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=15min&apikey={TWELVE_DATA_API_KEY}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            message = response.json()

            producer.produce(
                topic=TOPIC_TECHNICAL,
                key=ticker.encode('utf-8'),
                value=json.dumps(message).encode('utf-8'),
                callback=delivery_report
            )
            producer.poll(0)
            logger.info(f"Enviado dato técnico para {ticker}")

        except Exception as e:
            logger.error(f"Falló la API o envío a Kafka: {e}")


def get_fundamental_data():
    """Recupera noticias financieras de Bloomberg y Reuters (RSS)."""
    logger.info("--- Polling: Datos Fundamentales (RSS) ---")

    sources = {
        "bloomberg": "bloomberg.com",
        "reuters": "reuters.com"
    }

    for keyword in KEY_ENERGY_WORDS:
        for name, domain in sources.items():
            feed_url = f"https://news.google.com/rss/search?q=allinurl:{domain}+{keyword}&hl=en-US&gl=US&ceid=US:en"
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    message = {
                        "title": entry.get("title"),
                        "link": entry.get("link"),
                        "source": entry.get("source", {}).get("title", name),
                        "id": entry.get("id"),
                        "published_timestamp": datetime.fromtimestamp(
                            time.mktime(entry.published_parsed)
                        ).isoformat() if entry.get("published_parsed") else None
                    }
                    producer.produce(
                        topic=TOPIC_FUNDAMENTAL,
                        value=json.dumps(message).encode("utf-8"),
                        callback=delivery_report
                    )
            except Exception as e:
                logger.error(f"Falló el procesamiento del feed {feed_url}: {e}")

# --- BUCLE PRINCIPAL ---
if __name__ == "__main__":
    time.sleep(15)  # Espera inicial para asegurar que Kafka esté listo

    while True:
        current_time = time.time()

        if current_time - LAST_RUN_TECHNICAL >= POLLING_INTERVAL_TECHNICAL:
            get_technical_data()
            LAST_RUN_TECHNICAL = current_time

        if current_time - LAST_RUN_FUNDAMENTAL >= POLLING_INTERVAL_FUNDAMENTAL:
            get_fundamental_data()
            LAST_RUN_FUNDAMENTAL = current_time

        producer.flush()  # Asegura envío completo de los mensajes pendientes
        time.sleep(60*5)
