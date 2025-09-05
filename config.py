import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN não foi encontrado. Verifique o arquivo .env.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY não foi encontrado. Verifique o arquivo .env.")
