from selenium.webdriver.chrome.options import Options
from config import DISCORD_TOKEN, OPENAI_API_KEY
from discord.ext import commands, tasks
from dataclasses import dataclass
from selenium import webdriver
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import asyncio
import discord
import time


try:
    from openai import AsyncOpenAI
    OPENAI_SDK_AVAILABLE = True
except Exception:
    OPENAI_SDK_AVAILABLE = False


# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

# Bot initialization
bot = commands.Bot(command_prefix="!", intents=intents)

# OpenAI client initialization
client = None
if OPENAI_SDK_AVAILABLE and OPENAI_API_KEY:
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI Async client initialized.")
    except Exception as e:
        logger.critical(f"Falha ao inicializar OpenAI: {e}")
        client = None
else:
    logger.critical("OpenAI API key ausente ou SDK indisponível. Funcionalidades de IA desativadas.")

@dataclass
class News:
    title: str
    url: str
    comments: int = 0
    img: str = ""

# Synchronous function that initializes a headless Chrome WebDriver
# Opens a given URL, waits for the page to load, and returns its HTML source
def fetch_page_source(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)
    try:
        logger.info(f"Opening headless browser para URL: {url}")
        driver.get(url)
        time.sleep(2)
        logger.info("Página carregada com sucesso.")
        return driver.page_source
    finally:
        driver.quit()
        logger.info("WebDriver finalizado.")


# Asynchronous function that uses OpenAI API to summarize a Counter-Strike news article
# It ensures the summary is in Brazilian Portuguese, concise, and respects specific rules
async def summarize_news(content, client):
    logger.info("Iniciando resumo de notícia.")
    if not content:
        logger.info("Conteúdo de entrada vazio para resumo.")
        return ""

    try:
        response = await client.responses.create(
            model="gpt-5-nano",
            input=content,
            instructions="""
                        You are an expert in summarizing Counter-Strike news articles. Your task is to process an English article about the Counter-Strike competitive scene (CS2 or CS:GO) and produce a summary in Portuguese (Brazil) with the following rules:

                        Instructions:
                        1. If the article is longer than 800 characters, summarize it in up to 800 characters, focusing on key points (e.g., match results, player transfers, tournament updates).
                        2. Structure the summary in 1-2 short paragraphs for readability.
                        3. Use a journalistic and objective tone, avoiding opinions or speculation.
                        4. Preserve Counter-Strike terminology (e.g., "AWP", "clutch", "Major") in English, but ensure the text is clear to a Portuguese-speaking audience.
                        5. If the article contains irrelevant details (e.g., ads, unrelated topics), exclude them from the summary.

                        Example:
                        Input: Article about Team X winning a tournament...
                        Output: A Team X venceu o torneio Y em [data], derrotando a Team Z na final por 2-1. O jogador W foi destaque, com um clutch decisivo na Dust2. O torneio marcou a estreia do novo elenco da Team X.
                        """
        )
        output = response.output_text
        logger.info("Resumo gerado (tamanho %d chars).", len(output or ""))
        return output
    except Exception:
        logger.exception("Erro na API OpenAI (resumo)")
        raise


# Asynchronous function that uses OpenAI API to translate text into Brazilian Portuguese
# Specifically designed for Counter-Strike news headlines, keeping proper names and terms intact
async def translate(text, client):
    logger.info("Iniciando tradução para Português (Brasil).")
    if not text:
        logger.info("Conteúdo de entrada vazio para tradução.")
        return ""

    try:
        response = await client.responses.create(
            model="gpt-5-nano",
            input=text,
            instructions="""
                        Translate the provided message into Brazilian Portuguese. Do not include any explanation, comment, or additional content.
                        These messages are Counter-Strike news headlines, so the AI must keep the proper names and original terms.
                        Preserve the original meaning and tone, and provide only the translated text.
                        """
        )
        output = response.output_text
        logger.info("Resumo gerado (tamanho %d chars).", len(output or ""))
        return output
    except Exception:
        logger.exception("Erro na API OpenAI (resumo)")
        raise


# Asynchronous function that fetches the HLTV homepage
# Extracts recent news headlines, their URLs, and comment counts
# Filters news published today, yesterday, or in the last hours/minutes
async def fetch_daily_news():
    today = datetime.now().date().isoformat()
    loop = asyncio.get_running_loop()
    homepage_url = "https://www.hltv.org"
    all_news = []

    try:
        # Run sync function in executor
        logger.info("Iniciando fetch de notícias diárias de HLTV.")
        page_source = await loop.run_in_executor(None, fetch_page_source, homepage_url)

        # Process page with BeautifulSoup
        soup = BeautifulSoup(page_source, "html.parser")
        news_list = soup.select("a.newsline.article")

        logger.info(f"Total de itens encontrados no HTML: {len(news_list)}")

        for news_item in news_list:
            published_time_tag = news_item.find("div", class_="newsrecent")
            published_time = published_time_tag.get_text(strip=True) if published_time_tag else ""

            if any(unit in published_time for unit in ["hours", "hour", "minutes", "minute", "seconds", "second"]):
                title_tag = news_item.find("div", class_="newstext")
                if not title_tag:
                    logger.debug("Notícia sem título; pulando.")
                    continue
                title = title_tag.get_text(strip=True)
                link = news_item.get("href")
                if not link:
                    logger.debug("Notícia sem link; pulando.")
                    continue
                full_link = f"https://www.hltv.org{link.strip()}"

                section = news_item.find("div", class_="newstc")
                if section:
                    divs = section.find_all("div", recursive=False)
                    for div in divs:
                        if "comments" in div.text.lower():
                            text = div.text.strip()
                            digits = "".join(filter(str.isdigit, text))
                            if digits:
                                comments = int(digits)
                            break

                news = News(
                    title=title,
                    url=full_link,
                    comments=comments,
                )
                all_news.append(news)

        logger.info(f"Notícias coletadas: {len(all_news)}")
        return all_news if all_news else None

    except Exception as e:
        logger.error(f"Erro ao buscar notícias: {e}")
        return None


# Asynchronous function that fetches the full content of a news article
# Extracts the main text and image, then summarizes it using OpenAI
async def fetch_news_content(news):
    loop = asyncio.get_running_loop()

    try:
        page_source = await loop.run_in_executor(None, fetch_page_source, news.url)

        soup = BeautifulSoup(page_source, "html.parser")

        news_container = soup.find("div", class_="newstext-con")

        img_tag = soup.find("img", class_="image")
        img = img_tag.get("src")
        news.img = img

        if news_container:
            news_text = news_container.get_text(strip=True)
            summarized_news = await summarize_news(news_text, client)
            logger.info("Conteúdo longo resumido com sucesso.")
            return summarized_news
        else:
            logger.error(f"Couldn't find the news content at {news.url}")
            return None



    except Exception as e:
        logger.error(f"Erro ao acessar {news.url}: {e}")
        return None


# --- BOT FUNCTIONS ---


# Event handler triggered when the bot is connected and ready
# Starts the scheduled daily news delivery task
@bot.event
async def on_ready():
    logger.info(f"Bot conectado como {bot.user} (ID={getattr(bot.user, 'id', 'unknown')})")
    daily_news_task.start()


# Manual bot command: "!news"
# Fetches and sends HLTV news to the channel where the command was issued
@bot.command(name="news")
async def manual_news(ctx):
    logger.info("Comando 'news' recebido por %s", ctx.author)
    await news_task(ctx.channel)


# Scheduled task that runs every 24 hours
# Fetches HLTV news and posts them into a fixed Discord channel
@tasks.loop(hours=24)
async def daily_news_task():
    channel = bot.get_channel(1413349029189910660)
    if channel is None:
        logger.error("Canal não encontrado. Verifique permissões e existência.")
        return
    await news_task(channel)


# Core function that fetches news, translates titles, summarizes content
# Builds a Discord embed and posts each news article into the target channel
async def news_task(channel):
    if channel is None:
        logger.error("Canal não encontrado; abortando task de notícias.")
        return

    logger.info("Iniciando entrega diária de notícias...")
    news_list = await fetch_daily_news()
    if news_list:
        for news in news_list:
            content_to_send = await fetch_news_content(news)
            title_translated = await translate(news.title, client)
            if content_to_send:
                try:
                    embed = discord.Embed(
                        title=title_translated,
                        description=content_to_send,
                        color=0x0099ff
                    )
                    embed.add_field(
                            name="🔗 Fonte",
                            value=f"[Visite HLTV para mais detalhes]({news.url})",
                            inline=False
                    )
                    embed.set_image(url=news.img)
                    await channel.send(embed=embed)
                    logger.info("Notícia enviada com sucesso: %s", news.title)

                except Exception as e:
                    logger.error(f"Falha ao enviar notícia: {e}")
            else:
                logger.info("Conteúdo processado não disponível para: %s", news.title)

            await asyncio.sleep(1)
    else:
        logger.info("Nenhuma notícia válida encontrada para enviar hoje.")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN não definido.")
        raise SystemExit("DISCORD_TOKEN é obrigatório.")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Erro ao iniciar o bot: {e}")
