from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEndpoint

GEMINI_MODEL = "gemini-2.5-flash"
HUGGINGIGFACE_REPO_ID = "meta-llama/Llama-3.1-8B-Instruct"

LLM = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0.2
)

SMALL_LLM = HuggingFaceEndpoint(
    repo_id=HUGGINGIGFACE_REPO_ID
)