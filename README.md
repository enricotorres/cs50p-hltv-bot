# CS2 News Bot

## Video Demo
https://youtu.be/1j23mjnRkVk

## Description

### Overview
The **CS2 News Bot** is a Discord bot that automatically fetches the latest news from **HLTV.org**, translates the headlines into Portuguese, and generates short, objective summaries. It was designed to help the Portuguese-speaking Counter-Strike community stay up to date with the competitive scene without having to visit HLTV directly or read long articles in English.  

News is posted in Discord using **embeds**, which include the translated headline, summary in Portuguese, an image, and a link to the original article. This makes the bot a practical tool for servers of teams, fan communities, and groups of friends who follow the competitive scene.  

### How It Works
The bot works in three main steps. First, it uses **Selenium** to open the HLTV homepage in a headless browser. Then, with the help of **BeautifulSoup**, it parses the HTML and extracts data such as headline, link, comment count, and image.  
Second, the collected content is processed by the **OpenAI API**. The headline is translated into Portuguese, keeping the original game terms (such as “AWP,” “clutch,” or “Major”), while the article’s body is summarized into up to 800 characters in an objective, journalistic tone.  
Finally, the bot posts the results into a Discord channel using the **discord.py** library. Messages are sent as **embeds**, displaying the translated headline, summary, image, and link in a clean and organized way.  

### Commands
The bot provides **slash commands** in Discord:  

1. **`/daily_news <hour> <timezone> [delay]`**  
   - Sets the current channel to receive daily news at a fixed time.  
   - `hour` must follow `HH:MM` format (e.g., `23:50`).  
   - `timezone` must follow the format `Etc/UTC` or `Etc/GMT+X` (e.g., `Etc/GMT-3`).  
   - `delay` is optional and defines the interval (in seconds) between sending each news item.  

   **Example:**  
   ```
   /daily_news 23:50 Etc/GMT-3 1.5
   ```  
   This will schedule the bot to post news every day at 11:50 PM in Brasília time, with 1.5 seconds between each message.  

2. **`/news`**  
   - Immediately fetches and posts the latest HLTV news.  
   - Useful if you don’t want to wait for the scheduled time.  

3. **`/help`**  
   - Displays the list of available commands and quick usage instructions.  

---

### Technologies
- **Python** as the main language.  
- **discord.py** for Discord integration.  
- **Selenium + BeautifulSoup** for scraping and parsing HLTV.  
- **OpenAI API** for translation and summarization.  
- **asyncio + pytz** for scheduling.  
- **pytest** and `unittest.mock` for automated testing.  

### Limitations
The bot depends on the HLTV website structure. If the HTML changes, scraping selectors may need updates.  
The OpenAI API requires a valid key, which may generate costs.  
Currently, the bot only supports one channel per server for scheduled posts.  

---

## Files
- `project.py` — Main bot logic (scraping, translation, summarization, Discord integration).  
- `test_project.py` — Automated tests to verify functionality.  
- `.env` — Environment variables file (not included). It must contain:  
  ```
  DISCORD_TOKEN=your_token_here
  OPENAI_API_KEY=your_key_here
  ```

---

## How to Run
1. Clone the repository.  
2. Create and activate a virtual environment:  
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Linux/Mac
   .venv\Scripts\activate      # Windows
   ```
3. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file with `DISCORD_TOKEN` and `OPENAI_API_KEY`.  
5. Run the bot:  
   ```bash
   python project.py
   ```

---

## How to Test
The tests use `pytest` and mocks. They verify:  
- Time and timezone format validation.  
- Fetching of recent HLTV news.  
- Extraction of article content and image.  
- Translation and summarization via OpenAI (mocked).  

Run the tests with:  
```bash
pytest test_project.py -v
```
---

## Notes
This project was developed for **educational purposes** as part of the CS50P course.  
It is not intended for production use, and there is **no need to fork or reuse this project**.  

