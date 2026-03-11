import os
import tkinter as tk 
from tkinter import scrolledtext
import threading
import winsound
import datetime
import json
import urllib.request
import xml.etree.ElementTree as ET
import openai
from connectors import MassiveConnector, DTNConnector
CONFIG_FILE = "C:\\Users\\Trader\\Desktop\\terminal_config.json"

def save_config():
    config = {
        "massive_key": api_key_entry.get().strip(),
        "openai_key": openai_key_entry.get().strip()
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get("massive_key", ""), config.get("openai_key", "")
    except:
        return "", ""

# API KEYS
POLYGON_API_KEY = "ceF7rXmSTIpGsQDR6m8uVmeFBAomMQ3n"
OPENAI_API_KEY = ""

# ORDER FLOW STATE
current_bid = 0
current_ask = 0
buy_count = 0
sell_count = 0
total_volume = 0
active_connector = [None]
ticker_stats = {}

def play_beep(frequency=440, duration=150):
    try:
        winsound.Beep(frequency, duration)
    except Exception:
        pass

def on_quote(bid, ask):
    global current_bid, current_ask
    current_bid = bid
    current_ask = ask
    root.after(0, update_bid_ask)

def on_trade(price, size, ticker=""):
    global buy_count, sell_count, total_volume, ticker_stats
    if size < 100:
        return
    if current_ask > 0 and price >= current_ask:
        side = "ASK"
        tag = "ask"
        buy_count += 1
        total_volume += size
        if ticker:
            ticker_stats.setdefault(ticker, {'buys': 0, 'sells': 0})
            ticker_stats[ticker]['buys'] += 1
        threading.Thread(target=play_beep, args=(880, 150), daemon=True).start()
    elif current_bid > 0 and price <= current_bid:
        side = "BID"
        tag = "bid"
        sell_count += 1
        total_volume += size
        if ticker:
            ticker_stats.setdefault(ticker, {'buys': 0, 'sells': 0})
            ticker_stats[ticker]['sells'] += 1
        threading.Thread(target=play_beep, args=(220, 150), daemon=True).start()
    else:
        return
    text = f"{ticker+' ' if ticker else ''}{side}  ${price:.2f}  x  {size:,} shares"
    if size >= 1000:
        text += "  ⚡ LARGE"
        root.after(0, add_large_trade, text, side)
    root.after(0, add_trade, text, tag)
    root.after(0, update_counters)

def update_bid_ask():
    bid_label.config(text=f"BID: ${current_bid:.2f}")
    ask_label.config(text=f"ASK: ${current_ask:.2f}")

def update_ratio_bar():
    total = buy_count + sell_count
    if total == 0:
        buy_bar.delete("all")
        return
    width = buy_bar.winfo_width()
    buy_ratio = buy_count / total
    sell_ratio = sell_count / total
    buy_width = int(width * buy_ratio)
    sell_width = int(width * sell_ratio)
    buy_bar.delete("all")
    buy_bar.create_rectangle(0, 0, buy_width, 20, fill="lime", outline="")
    buy_bar.create_rectangle(buy_width, 0, buy_width + sell_width, 20, fill="#ff4444", outline="")
    buy_pct = int(buy_ratio * 100)
    sell_pct = int(sell_ratio * 100)
    buy_bar.create_text(10, 10, text=f"BUY {buy_pct}%", fill="black", font=("Arial", 9, "bold"), anchor="w")
    buy_bar.create_text(width - 10, 10, text=f"SELL {sell_pct}%", fill="white", font=("Arial", 9, "bold"), anchor="e")

def update_counters():
    buy_label.config(text=f"BUYS: {buy_count}")
    sell_label.config(text=f"SELLS: {sell_count}")
    volume_label.config(text=f"VOLUME: {total_volume:,}")
    update_ratio_bar()
    stats_text = ""
    for sym, stats in ticker_stats.items():
        stats_text += f"{sym}: {stats['buys']}B / {stats['sells']}S   "
    ticker_stats_label.config(text=stats_text if stats_text else "")

def add_trade(text, tag):
    trade_feed.insert(tk.END, text + "\n", tag)
    trade_feed.see(tk.END)

def add_large_trade(text, side):
    large_feed.tag_config("large_ask", foreground="lime")
    large_feed.tag_config("large_bid", foreground="#ff4444")
    tag = "large_ask" if side == "ASK" else "large_bid"
    large_feed.insert(tk.END, text + "\n", tag)
    large_feed.see(tk.END)

def save_session():
    now = datetime.datetime.now()
    filename = f"C:\\Users\\Trader\\Desktop\\session_{now.strftime('%Y%m%d')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"ORDER FLOW SESSION - {now.strftime('%Y-%m-%d')}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"SUMMARY\n")
        f.write(f"Total Buys: {buy_count}\n")
        f.write(f"Total Sells: {sell_count}\n")
        f.write(f"Total Volume: {total_volume:,}\n\n")
        f.write("PER TICKER STATS\n")
        for sym, stats in ticker_stats.items():
            f.write(f"{sym}: {stats['buys']} buys / {stats['sells']} sells\n")
        f.write("\nTRADE LOG\n")
        f.write("-" * 50 + "\n")
        trades = trade_feed.get(1.0, tk.END)
        f.write(trades)
        f.write("\nLARGE TRADES\n")
        f.write("-" * 50 + "\n")
        large = large_feed.get(1.0, tk.END)
        f.write(large)
    add_trade(f"💾 Session saved!", "mid")

def start_monitoring():
    save_config()
    global buy_count, sell_count, total_volume, active_connector, ticker_stats
    TICKER = ticker_entry.get().upper()
    buy_count = 0
    sell_count = 0
    total_volume = 0
    ticker_stats.clear()
    update_counters()
    trade_feed.delete(1.0, tk.END)
    large_feed.delete(1.0, tk.END)
    if active_connector[0]:
        active_connector[0].disconnect()
    provider = provider_var.get()
    if provider == "Massive":
        active_connector[0] = MassiveConnector(
            api_key=api_key_entry.get(),
            ticker=TICKER,
            on_trade=on_trade,
            on_quote=on_quote
        )
    elif provider == "DTN":
        active_connector[0] = DTNConnector(
            ticker=TICKER,
            on_trade=on_trade,
            on_quote=on_quote
        )
    active_connector[0].connect()
    root.after(0, add_trade, f"✅ Connected via {provider}! Monitoring {TICKER}", "mid")

def stop_monitoring():
    if active_connector[0]:
        active_connector[0].disconnect()
        active_connector[0] = None
        root.after(0, add_trade, "⏹ Monitoring stopped", "bid")

# SENTIMENT FUNCTIONS
def get_news_sentiment(ticker):
    def run():
        try:
            sent_feed.delete(1.0, tk.END)
            sent_feed.insert(tk.END, f"Analyzing {ticker}...\n", "info")
            url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&limit=5&apiKey={POLYGON_API_KEY}"
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            data = json.loads(response.read().decode())
            articles = data.get('results', [])
            if not articles:
                sent_feed.insert(tk.END, "No news found\n", "info")
                return
            client = openai.OpenAI(api_key=openai_key_entry.get())
            total = 0
            count = 0
            for article in articles:
                title = article.get('title', '')
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": f"Score sentiment 0-100 (0=very negative, 100=very positive). Reply with just number and one sentence. Title: {title}"}]
                )
                sentiment = response.choices[0].message.content
                try:
                    score = int(''.join(filter(str.isdigit, sentiment.split('.')[0][:3])))
                except:
                    score = 50
                total += score
                count += 1
                if score >= 70:
                    tag = "positive"
                elif score <= 40:
                    tag = "negative"
                else:
                    tag = "neutral"
                root.after(0, sent_feed.insert, tk.END, f"{score}/100 {title[:50]}\n", tag)
            if count > 0:
                avg = total // count
                if avg >= 70:
                    tag = "positive"
                elif avg <= 40:
                    tag = "negative"
                else:
                    tag = "neutral"
                root.after(0, sent_feed.insert, tk.END, f"\nNEWS SCORE: {avg}/100\n", tag)
            get_reddit_sentiment(ticker, client, total, count)
        except Exception as e:
            root.after(0, sent_feed.insert, tk.END, f"Error: {str(e)[:50]}\n", "negative")
    threading.Thread(target=run, daemon=True).start()

def get_reddit_sentiment(ticker, client, news_total, news_count):
    try:
        url = "https://www.reddit.com/r/wallstreetbets/search.rss?q=" + ticker + "&sort=top&t=week&restrict_sr=1"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SentimentBot/1.0 (personal project)',
            'Accept': 'application/rss+xml'
        })
        response = urllib.request.urlopen(req)
        tree = ET.parse(response)
        root_xml = tree.getroot()
        items = list(root_xml.iter('{http://www.w3.org/2005/Atom}entry'))
        titles = []
        for item in items[:5]:
            title = item.find('{http://www.w3.org/2005/Atom}title')
            if title is not None:
                titles.append(title.text)
        if not titles:
            return
        reddit_total = 0
        reddit_count = 0
        for title in titles:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Score sentiment 0-100. Reply with just number. Title: {title}"}]
            )
            sentiment = response.choices[0].message.content
            try:
                score = int(''.join(filter(str.isdigit, sentiment.split('.')[0][:3])))
            except:
                score = 50
            reddit_total += score
            reddit_count += 1
        if reddit_count > 0:
            reddit_avg = reddit_total // reddit_count
            if reddit_avg >= 70:
                tag = "positive"
            elif reddit_avg <= 40:
                tag = "negative"
            else:
                tag = "neutral"
            root.after(0, sent_feed.insert, tk.END, f"REDDIT SCORE: {reddit_avg}/100\n", tag)
            combined = (news_total + reddit_total) // (news_count + reddit_count)
            if combined >= 70:
                tag = "positive"
            elif combined <= 40:
                tag = "negative"
            else:
                tag = "neutral"
            root.after(0, sent_feed.insert, tk.END, f"\n⭐ OVERALL: {combined}/100\n", tag)
            root.after(0, overall_score_label.config, {"text": f"SCORE: {combined}/100",
                "fg": "lime" if combined >= 70 else "red" if combined <= 40 else "yellow"})
    except Exception as e:
        root.after(0, sent_feed.insert, tk.END, f"Reddit error: {str(e)[:50]}\n", "negative")

def analyze_sentiment():
    ticker = sent_ticker_entry.get().upper()
    if ticker:
        get_news_sentiment(ticker)

def sync_ticker():
    ticker = ticker_entry.get().upper()
    sent_ticker_entry.delete(0, tk.END)
    sent_ticker_entry.insert(0, ticker)
    analyze_sentiment()

# BUILD THE GUI
root = tk.Tk()
root.title("⚡ Trading Terminal")
root.geometry("1300x780")
root.configure(bg="#0a0f2c")

# MAIN TITLE
tk.Label(root, text="⚡ TRADING TERMINAL ⚡",
    font=("Arial", 20, "bold"), bg="#0a0f2c", fg="#00aaff").pack(pady=8)

# MAIN FRAME - LEFT AND RIGHT
main_frame = tk.Frame(root, bg="#0a0f2c")
main_frame.pack(fill=tk.BOTH, expand=True, padx=10)

# LEFT PANEL - ORDER FLOW
left_panel = tk.Frame(main_frame, bg="#0a0f2c", width=650)
left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
left_panel.pack_propagate(False)

tk.Label(left_panel, text="ORDER FLOW",
    font=("Arial", 13, "bold"), bg="#0a0f2c", fg="#00aaff").pack(pady=5)

# PROVIDER DROPDOWN
provider_frame = tk.Frame(left_panel, bg="#0a0f2c")
provider_frame.pack()
tk.Label(provider_frame, text="Provider:", bg="#0a0f2c", fg="white",
    font=("Arial", 10)).pack(side=tk.LEFT)
provider_var = tk.StringVar(value="Massive")
provider_dropdown = tk.OptionMenu(provider_frame, provider_var, "Massive", "DTN")
provider_dropdown.config(font=("Arial", 10), bg="#1a2a5a", fg="white",
    activebackground="#2a3a6a", activeforeground="white", width=8)
provider_dropdown.pack(side=tk.LEFT, padx=5)

# API KEY
api_frame = tk.Frame(left_panel, bg="#0a0f2c")
api_frame.pack(pady=2)
tk.Label(api_frame, text="API Key:", bg="#0a0f2c", fg="white",
    font=("Arial", 10)).pack(side=tk.LEFT)
api_key_entry = tk.Entry(api_frame, font=("Arial", 10), width=38,
    bg="#1a2a5a", fg="white", insertbackground="white", show="*")
api_key_entry.insert(0, POLYGON_API_KEY)
api_key_entry.pack(side=tk.LEFT, padx=5)

# BID ASK
ba_frame = tk.Frame(left_panel, bg="#0a0f2c")
ba_frame.pack(pady=3)
bid_label = tk.Label(ba_frame, text="BID: $0.00",
    font=("Arial", 12, "bold"), bg="#0a0f2c", fg="red", width=14)
bid_label.pack(side=tk.LEFT, padx=15)
ask_label = tk.Label(ba_frame, text="ASK: $0.00",
    font=("Arial", 12, "bold"), bg="#0a0f2c", fg="lime", width=14)
ask_label.pack(side=tk.LEFT, padx=15)

# COUNTERS
counter_frame = tk.Frame(left_panel, bg="#0a0f2c")
counter_frame.pack(pady=3)
buy_label = tk.Label(counter_frame, text="BUYS: 0",
    font=("Arial", 11, "bold"), bg="#0a0f2c", fg="lime", width=10)
buy_label.pack(side=tk.LEFT, padx=8)
sell_label = tk.Label(counter_frame, text="SELLS: 0",
    font=("Arial", 11, "bold"), bg="#0a0f2c", fg="red", width=10)
sell_label.pack(side=tk.LEFT, padx=8)
volume_label = tk.Label(counter_frame, text="VOLUME: 0",
    font=("Arial", 11, "bold"), bg="#0a0f2c", fg="#00aaff", width=16)
volume_label.pack(side=tk.LEFT, padx=8)

# PER TICKER STATS
ticker_stats_label = tk.Label(left_panel, text="",
    font=("Arial", 10, "bold"), bg="#0a0f2c", fg="yellow")
ticker_stats_label.pack(pady=1)

# RATIO BAR
ratio_frame = tk.Frame(left_panel, bg="#0a0f2c")
ratio_frame.pack(fill=tk.X, padx=10, pady=2)
buy_bar = tk.Canvas(ratio_frame, height=18, bg="#0a0f2c", highlightthickness=0)
buy_bar.pack(fill=tk.X)

# TICKER AND SIZE
control_frame = tk.Frame(left_panel, bg="#0a0f2c")
control_frame.pack(pady=3)
tk.Label(control_frame, text="Ticker:", bg="#0a0f2c", fg="white",
    font=("Arial", 10)).pack(side=tk.LEFT)
ticker_entry = tk.Entry(control_frame, font=("Arial", 11), width=18,
    bg="#1a2a5a", fg="white", insertbackground="white")
ticker_entry.insert(0, "AAPL")
ticker_entry.pack(side=tk.LEFT, padx=5)
tk.Label(control_frame, text="Min Size:", bg="#0a0f2c", fg="white",
    font=("Arial", 10)).pack(side=tk.LEFT, padx=(10,0))
size_slider = tk.Scale(control_frame, from_=100, to=2000,
    orient=tk.HORIZONTAL, bg="#0a0f2c", fg="white",
    highlightthickness=0, length=120)
size_slider.set(100)
size_slider.pack(side=tk.LEFT, padx=5)

# TRADE FEED
trade_feed = scrolledtext.ScrolledText(left_panel, width=60, height=12,
    bg="#050d1f", fg="white", font=("Courier", 10),
    insertbackground="white")
trade_feed.pack(pady=5, padx=10, fill=tk.BOTH)
trade_feed.tag_config("ask", foreground="lime")
trade_feed.tag_config("bid", foreground="#ff4444")
trade_feed.tag_config("mid", foreground="#00aaff")
trade_feed.tag_config("large", foreground="white")

# LARGE TRADE LOG
tk.Label(left_panel, text="⚡ LARGE TRADES (1000+ shares)",
    font=("Arial", 9, "bold"), bg="#0a0f2c", fg="yellow").pack()
large_feed = scrolledtext.ScrolledText(left_panel, width=60, height=4,
    bg="#0a0500", fg="yellow", font=("Courier", 10),
    insertbackground="white")
large_feed.pack(pady=2, padx=10, fill=tk.BOTH)

# DIVIDER
tk.Frame(main_frame, bg="#00aaff", width=2).pack(side=tk.LEFT, fill=tk.Y, padx=5)

# RIGHT PANEL - SENTIMENT
right_panel = tk.Frame(main_frame, bg="#0a0f2c", width=580)
right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
right_panel.pack_propagate(False)

tk.Label(right_panel, text="SENTIMENT ANALYSIS",
    font=("Arial", 13, "bold"), bg="#0a0f2c", fg="#00aaff").pack(pady=5)
# OPENAI KEY INPUT
oai_frame = tk.Frame(right_panel, bg="#0a0f2c")
oai_frame.pack(pady=2)
tk.Label(oai_frame, text="OpenAI Key:", bg="#0a0f2c", fg="white",
    font=("Arial", 10)).pack(side=tk.LEFT)
openai_key_entry = tk.Entry(oai_frame, font=("Arial", 10), width=38,
    bg="#1a2a5a", fg="white", insertbackground="white", show="*")
openai_key_entry.insert(0, OPENAI_API_KEY)
openai_key_entry.pack(side=tk.LEFT, padx=5)

# SENTIMENT TICKER INPUT
sent_control = tk.Frame(right_panel, bg="#0a0f2c")
sent_control.pack(pady=5)
tk.Label(sent_control, text="Ticker:", bg="#0a0f2c", fg="white",
    font=("Arial", 11)).pack(side=tk.LEFT)
sent_ticker_entry = tk.Entry(sent_control, font=("Arial", 12), width=12,
    bg="#1a2a5a", fg="white", insertbackground="white")
sent_ticker_entry.insert(0, "AAPL")
sent_ticker_entry.pack(side=tk.LEFT, padx=5)
tk.Button(sent_control, text="🔍 ANALYZE",
    font=("Arial", 11, "bold"), bg="#00aaff", fg="black",
    command=analyze_sentiment, padx=10).pack(side=tk.LEFT, padx=5)
tk.Button(sent_control, text="🔗 SYNC",
    font=("Arial", 11, "bold"), bg="#555555", fg="white",
    command=sync_ticker, padx=10).pack(side=tk.LEFT, padx=5)

# OVERALL SCORE
overall_score_label = tk.Label(right_panel, text="SCORE: --",
    font=("Arial", 22, "bold"), bg="#0a0f2c", fg="yellow")
overall_score_label.pack(pady=5)

# SENTIMENT FEED
sent_feed = scrolledtext.ScrolledText(right_panel, width=55, height=30,
    bg="#050d1f", fg="white", font=("Courier", 10),
    insertbackground="white")
sent_feed.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
sent_feed.tag_config("positive", foreground="lime")
sent_feed.tag_config("negative", foreground="#ff4444")
sent_feed.tag_config("neutral", foreground="yellow")
sent_feed.tag_config("info", foreground="#00aaff")

# BOTTOM BUTTONS
button_frame = tk.Frame(root, bg="#0a0f2c")
button_frame.pack(pady=5)
tk.Button(button_frame, text="▶  START",
    font=("Arial", 12, "bold"), bg="#00aaff", fg="black",
    command=start_monitoring, padx=15, pady=4).pack(side=tk.LEFT, padx=8)
tk.Button(button_frame, text="⏹  STOP",
    font=("Arial", 12, "bold"), bg="#ff4444", fg="white",
    command=stop_monitoring, padx=15, pady=4).pack(side=tk.LEFT, padx=8)
tk.Button(button_frame, text="💾  SAVE",
    font=("Arial", 12, "bold"), bg="#00aa44", fg="white",
    command=save_session, padx=15, pady=4).pack(side=tk.LEFT, padx=8)
tk.Button(button_frame, text="🗑  CLEAR",
    font=("Arial", 12, "bold"), bg="#555555", fg="white",
    command=lambda: [trade_feed.delete(1.0, tk.END), large_feed.delete(1.0, tk.END)],
    padx=15, pady=4).pack(side=tk.LEFT, padx=8)
# LOAD SAVED KEYS
massive_key, openai_key = load_config()
if not api_key_entry.get():
    api_key_entry.insert(0, massive_key)
openai_key_entry.insert(0, openai_key)
root.mainloop()