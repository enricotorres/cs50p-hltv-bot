from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from config import DISCORD_TOKEN, OPENAI_API_KEY
from discord.ext import commands
from dataclasses import dataclass
from selenium import webdriver
from bs4 import BeautifulSoup
import datetime
import logging
import asyncio
import discord
import pytz
import re

try:
    from openai import AsyncOpenAI
    OPENAI_SDK_AVAILABLE = True
except Exception:
    OPENAI_SDK_AVAILABLE = False


@dataclass
class News:
    title: str
    url: str
    comments: int = 0
    img: str = ""


# Configurable runtime schedules
HOUR: int = 23
MINUTES: int = 50
TIMEZONE: str = "Etc/GMT"
NEWS_CHANNEL_ID: int | None = None
NEWS_SEND_DELAY: float = 1

# Internal scheduler
_scheduler_task = None

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
        logger.critical(f"Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.critical("OpenAI API key missing or SDK unavailable. AI functionalities disabled.")


# Initializes a headless Chrome WebDriver, opens a URL, waits for the page to load, and returns its HTML source
async def fetch_page_source(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)
    try:
        logger.info(f"Opening headless browser for URL: {url}")
        driver.get(url)
        # Dynamically wait until a specific element is present (up to 10 seconds)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.newsline.article, div.newstext-con"))
        )
        logger.info("Page loaded successfully.")
        return driver.page_source
    except Exception as e:
        logger.error(f"Failed to fetch page source from {url}: {e}")
        raise
    finally:
        driver.quit()
        logger.info("WebDriver closed.")


# Summarizes a Counter-Strike news article using the OpenAI API, producing a concise summary in Brazilian Portuguese
async def summarize_news(content, client):
    if client is None:
        return content
    logger.info("Starting news summarization.")
    if not content:
        logger.info("Empty input content for summarization.")
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
        logger.info("Summary generated (length %d characters).", len(output or ""))
        return output
    except Exception as e:
        logger.exception(f"Error in OpenAI API (summarization): {e}")
        raise


# Translates text into Brazilian Portuguese using the OpenAI API, designed for Counter-Strike news headlines
async def translate(text, client):
    logger.info("Starting translation to Brazilian Portuguese.")
    if not text:
        logger.info("Empty input content for translation.")
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
        logger.info("Translation generated (length %d characters).", len(output or ""))
        return output
    except Exception as e:
        logger.exception(f"Error in OpenAI API (translation): {e}")
        raise


# Fetches the HLTV homepage, extracts recent news headlines, URLs, and comment counts, filtering for recent news
async def fetch_daily_news():
    homepage_url = "https://www.hltv.org"
    all_news = []

    try:
        logger.info("Starting fetch of daily news from HLTV.")
        page_source = await fetch_page_source(homepage_url)

        soup = BeautifulSoup(page_source, "html.parser")
        news_list = soup.select("a.newsline.article")

        logger.info(f"Total items found in HTML: {len(news_list)}")

        for news_item in news_list:
            published_time_tag = news_item.find("div", class_="newsrecent")
            published_time = published_time_tag.get_text(strip=True) if published_time_tag else ""

            if any(unit in published_time for unit in ["hours", "hour", "minutes", "minute", "seconds", "second"]):
                title_tag = news_item.find("div", class_="newstext")
                if not title_tag:
                    logger.debug("News item without title; skipping.")
                    continue
                title = title_tag.get_text(strip=True)
                link = news_item.get("href")
                if not link:
                    logger.debug("News item without link; skipping.")
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

        logger.info(f"News collected: {len(all_news)}")
        return all_news if all_news else None

    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        return None


# Fetches the full content of a news article, extracts main text and image, and summarizes it using OpenAI
async def fetch_news_content(news):
    try:
        page_source = await fetch_page_source(news.url)

        soup = BeautifulSoup(page_source, "html.parser")

        news_container = soup.find("div", class_="newstext-con")

        img_tag = soup.find("img", class_="image")
        img = img_tag.get("src") if img_tag else ""
        news.img = img

        if news_container:
            news_text = news_container.get_text(strip=True)
            logger.info("Content successfully fetched for: %s", news.url)
            return news_text
        else:
            logger.error(f"Failed to find news content at {news.url}")
            return None

    except Exception as e:
        logger.error(f"Failed to access {news.url}: {e}")
        return None


# Validates the hour format (HH:MM) using regex
async def verify_hour(hour):
    pattern = r"^(?:[01]?\d|2[0-3]):[0-5]\d$"
    if re.match(pattern, hour, flags=re.IGNORECASE):
        return True
    else:
        return False


# Validates the timezone format (Etc/UTC or Etc/GMT[+-][0-14]) using regex
async def verify_timezone(timezone):
    pattern = r"^Etc/(UTC|GMT([+-](?:[0-9]|1[0-4])))$"
    if re.match(pattern, timezone, flags=re.IGNORECASE):
        return True
    else:
        return False


# --- BOT FUNCTIONS ---


# Handles bot connection and starts the dynamic scheduler
@bot.event
async def on_ready():
    logger.info(f"Bot connected as {bot.user} (ID={getattr(bot.user, 'id', 'unknown')})")
    await bot.tree.sync()
    start_scheduler()


@bot.tree.command(name="help")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    help_text = """
**📌 Lista de Comandos do Bot CS:GO News**

1️⃣ `/daily_news <hour> <timezone> [delay]`
Define o canal atual para receber notícias diárias do HLTV.
Exemplo: `/daily_news 23:50 Etc/GMT-3 1.5`

2️⃣ `/news`
Envia manualmente as notícias do dia no canal atual.

**⚠️ Observações**
- Use `/daily_news` para definir o canal antes de receber notícias.
- O bot traduz títulos e resume automaticamente em português.
"""

    await interaction.followup.send(help_text, ephemeral=True)


# Sets the news channel, schedule, and optional delay for daily news delivery
@bot.tree.command(name="daily_news")
async def set_news_channel(interaction: discord.Interaction, hour:str, timezone:str, delay: float = 1.0):
    if await verify_hour(hour) and await verify_timezone(timezone):
        global NEWS_CHANNEL_ID, TIMEZONE, HOUR, MINUTES, NEWS_SEND_DELAY
        NEWS_CHANNEL_ID = interaction.channel.id
        TIMEZONE = timezone
        HOUR, MINUTES = map(int, hour.split(":"))
        NEWS_SEND_DELAY = max(0.1, delay)

        start_scheduler()

        await interaction.response.send_message(f"Channel set for receiving daily news at {hour} {timezone}.")
        return
    else:
        logger.error("Invalid hour or timezone format")
        await interaction.response.send_message(
            "Invalid hour or timezone format. Use HH:MM (e.g., 22:20) and a valid timezone (e.g., Etc/UTC, Etc/GMT+3). "
            "Valid timezone formats are Etc/UTC or Etc/GMT[+-][0-14]. Optional delay (in seconds) can be provided (e.g., !daily_news 22:20 Etc/UTC 2.5)."
        )
        return


# Manually fetches and sends HLTV news to the specified channel
@bot.tree.command(name="news")
async def manual_news(interaction: discord.Interaction):
    logger.info("Command 'news' received from %s", interaction.user)
    channel = interaction.channel
    await interaction.response.send_message("Enviando as noticias")
    await news_task(channel)


# Runs a dynamic scheduler for daily news delivery
async def daily_news_scheduler():
    global _scheduler_task
    while True:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.datetime.now(tz)
        target = now.replace(hour=HOUR, minute=MINUTES, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        wait = (target - now).total_seconds()
        if wait < 0:
            wait = 0
        logger.info(f"Scheduler sleeping for {wait:.0f} seconds until {target.isoformat()}")
        await asyncio.sleep(wait)

        if NEWS_CHANNEL_ID is not None:
            channel = bot.get_channel(NEWS_CHANNEL_ID)
            if channel is not None:
                await news_task(channel)
            else:
                logger.error("Channel not found. Set the channel with !daily_news.")
        else:
            logger.info("NEWS_CHANNEL_ID not set yet.")


# Starts the dynamic scheduler, canceling any existing task
def start_scheduler():
    global _scheduler_task
    if _scheduler_task is not None:
        try:
            _scheduler_task.cancel()
        except Exception:
            pass
    _scheduler_task = asyncio.create_task(daily_news_scheduler())


# Fetches news, translates titles, summarizes content, and posts to the target Discord channel
async def news_task(channel):
    if channel is None:
        logger.error("Channel not found. Use !set_news_channel to set the channel.")
        return

    logger.info("Starting daily news delivery...")
    news_list = await fetch_daily_news()
    if news_list:
        for news in news_list:
            content_to_send = await fetch_news_content(news)
            if content_to_send:
                try:
                    title_translated, summarized_content = await asyncio.gather(
                    translate(news.title, client),
                    summarize_news(content_to_send, client),
                    return_exceptions=True
                    )
                    if isinstance(title_translated, Exception):
                        logger.error(f"Failed to translate title for {news.title}: {title_translated}")
                        title_translated = news.title
                    if isinstance(summarized_content, Exception):
                        logger.error(f"Failed to summarize content for {news.title}: {summarized_content}")
                        summarized_content = ""

                    embed = discord.Embed(
                        title=title_translated,
                        description=summarized_content,
                        color=0x0099ff
                    )
                    embed.add_field(
                        name="🔗 Source",
                        value=f"[Visit HLTV for more details]({news.url})",
                        inline=False
                    )
                    if news.img:
                        embed.set_image(url=news.img)
                    await channel.send(embed=embed)
                    logger.info("News sent successfully: %s", news.title)

                except Exception as e:
                    logger.error(f"Failed to send news: {e}")
            else:
                logger.info("Processed content not available for: %s", news.title)

            await asyncio.sleep(NEWS_SEND_DELAY)
    else:
        logger.info("No valid news found to send today.")


# Runs the bot with the provided Discord token
def main():
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN not set.")
        raise SystemExit("DISCORD_TOKEN is required.")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}")


if __name__ == "__main__":
    main()
