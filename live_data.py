# This file is part of the Stark split-up package. It continues on from
# system_tools.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from system_tools import *

# ---------- Live system stats: CPU / RAM / SWAP / network ----------
NET_HISTORY_LEN = 40

psutil.cpu_percent(percpu=True)
psutil.cpu_percent()


def get_uptime_string():
    s = int(time.time() - psutil.boot_time())
    return f"{s // 3600}h {s % 3600 // 60}m"


def stats_refresher():
    last_net = psutil.net_io_counters()
    last_time = time.time()
    down_hist, up_hist = [], []

    while True:
        time.sleep(1)
        cpu_total = psutil.cpu_percent(interval=None)
        cores = psutil.cpu_percent(interval=None, percpu=True)
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()

        now_net = psutil.net_io_counters()
        now_time = time.time()
        dt = max(now_time - last_time, 0.001)
        down_kbps = max((now_net.bytes_recv - last_net.bytes_recv) / dt / 1024, 0)
        up_kbps = max((now_net.bytes_sent - last_net.bytes_sent) / dt / 1024, 0)
        last_net, last_time = now_net, now_time

        down_hist.append(round(down_kbps, 1))
        up_hist.append(round(up_kbps, 1))
        del down_hist[:-NET_HISTORY_LEN]
        del up_hist[:-NET_HISTORY_LEN]

        update_state(
            cpu_percent=cpu_total,
            cpu_cores=cores,
            ram={
                "percent": vm.percent,
                "used_gb": round(vm.used / 1e9, 1),
                "total_gb": round(vm.total / 1e9, 1),
                "free_gb": round(vm.available / 1e9, 1),
            },
            swap={
                "percent": sm.percent,
                "used_gb": round(sm.used / 1e9, 1),
                "total_gb": round(sm.total / 1e9, 1),
                "free_gb": round(sm.free / 1e9, 1),
            },
            net={
                "down_kbps": round(down_kbps, 1),
                "up_kbps": round(up_kbps, 1),
                "down_history": list(down_hist),
                "up_history": list(up_hist),
            },
            uptime=get_uptime_string(),
        )


# ---------- News / Stocks / Weather (free, no-API-key sources) ----------
EXTRA_LOCK = threading.Lock()
extra_state = {
    "news": [],
    "stocks": [],
    "weather": None,
    "stocks_error": None,
}

WEATHER_CODES = {
    0: ("Clear sky", "\u2600\ufe0f"), 1: ("Mainly clear", "\U0001F324\ufe0f"), 2: ("Partly cloudy", "\u26c5"),
    3: ("Overcast", "\u2601\ufe0f"), 45: ("Fog", "\U0001F32B\ufe0f"), 48: ("Fog", "\U0001F32B\ufe0f"),
    51: ("Light drizzle", "\U0001F326\ufe0f"), 53: ("Drizzle", "\U0001F326\ufe0f"), 55: ("Heavy drizzle", "\U0001F327\ufe0f"),
    61: ("Light rain", "\U0001F326\ufe0f"), 63: ("Rain", "\U0001F327\ufe0f"), 65: ("Heavy rain", "\U0001F327\ufe0f"),
    71: ("Light snow", "\U0001F328\ufe0f"), 73: ("Snow", "\U0001F328\ufe0f"), 75: ("Heavy snow", "\u2744\ufe0f"),
    80: ("Rain showers", "\U0001F326\ufe0f"), 81: ("Rain showers", "\U0001F327\ufe0f"), 82: ("Violent showers", "\u26c8\ufe0f"),
    95: ("Thunderstorm", "\u26c8\ufe0f"), 96: ("Thunderstorm w/ hail", "\u26c8\ufe0f"), 99: ("Severe thunderstorm", "\u26c8\ufe0f"),
}

STOCK_WATCHLIST = [
    {"symbol": "AAPL", "domain": "apple.com"},
    {"symbol": "GOOGL", "domain": "google.com"},
    {"symbol": "MSFT", "domain": "microsoft.com"},
    {"symbol": "TSLA", "domain": "tesla.com"},
    {"symbol": "AMZN", "domain": "amazon.com"},
]

COUNTRY_STOCK_INDEX = {
    "united states": "^spx", "united states of america": "^spx", "usa": "^spx",
    "united kingdom": "^ftm", "uk": "^ftm",
    "germany": "^dax", "france": "^cac", "japan": "^nkx", "china": "^shc",
    "india": "^bsesn", "canada": "^tsx", "australia": "^aor", "brazil": "^bvsp",
    "italy": "^mib", "spain": "^ibex", "south korea": "^kospi", "korea": "^kospi",
    "hong kong": "^hsi", "russia": "^rts", "mexico": "^mxx", "netherlands": "^aex",
    "switzerland": "^ssmi",
}

# Maps every country name used in the world map to a Yahoo Finance ticker,
# so the fallback quote source works even when Stooq is blocked/rate-limited.
YAHOO_INDEX_SYMBOLS = {
    "^spx": "^GSPC", "^ftm": "^FTSE", "^dax": "^GDAXI", "^cac": "^FCHI",
    "^nkx": "^N225", "^shc": "000001.SS", "^bsesn": "^BSESN", "^tsx": "^GSPTSE",
    "^aor": "^AXJO", "^bvsp": "^BVSP", "^mib": "FTSEMIB.MI", "^ibex": "^IBEX",
    "^kospi": "^KS11", "^hsi": "^HSI", "^rts": "IMOEX.ME", "^mxx": "^MXX",
    "^aex": "^AEX", "^ssmi": "^SSMI",
}


def fetch_news(query="technology", max_results=6):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        articles = []
        for r in results:
            articles.append({
                "title": r.get("title"),
                "source": r.get("source"),
                "url": r.get("url"),
                "image": r.get("image"),
                "date": r.get("date"),
            })
        return articles
    except Exception as e:
        print("News fetch error:", e)
        return []


_LAST_STOCK_ERROR = {"stooq": None, "stooq_light": None, "yahoo": None, "yahoo2": None}

FINANCE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_stooq(symbol, index=False):
    """Raw close-price history from Stooq's historical CSV endpoint. Sends a
    real browser User-Agent, since Stooq silently returns 'N/D' (no data) or a
    bot-check HTML page for the default python-requests UA."""
    try:
        sym = symbol.lower() if index else f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        r = requests.get(url, headers=FINANCE_HEADERS, timeout=8)
        text = r.text.strip()
        if not text or text.startswith("N/D") or "<html" in text.lower():
            _LAST_STOCK_ERROR["stooq"] = f"Stooq (HTTP {r.status_code}) returned no data for {symbol} - likely blocked/rate-limited on your network."
            return None
        lines = text.splitlines()
        if len(lines) < 2:
            _LAST_STOCK_ERROR["stooq"] = f"Stooq returned an empty series for {symbol}."
            return None
        closes = []
        for line in lines[1:][-30:]:
            parts = line.split(",")
            if len(parts) >= 5:
                try:
                    closes.append(float(parts[4]))
                except ValueError:
                    pass
        if not closes:
            _LAST_STOCK_ERROR["stooq"] = f"Stooq response for {symbol} had no parseable close prices."
            return None
        _LAST_STOCK_ERROR["stooq"] = None
        return closes
    except Exception as e:
        _LAST_STOCK_ERROR["stooq"] = f"Stooq request failed for {symbol}: {e}"
        print("Stooq fetch error:", symbol, e)
        return None


def _fetch_stooq_light(symbol, index=False):
    """Fallback: Stooq's single-line 'light' quote endpoint (today + previous
    close only, no full history). Different URL shape than the CSV-download
    endpoint above, so it sometimes gets through when that one is blocked."""
    try:
        sym = symbol.lower() if index else f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlc&h&e=csv"
        r = requests.get(url, headers=FINANCE_HEADERS, timeout=8)
        text = r.text.strip()
        lines = text.splitlines()
        if len(lines) < 2:
            _LAST_STOCK_ERROR["stooq_light"] = f"Stooq light quote (HTTP {r.status_code}) had no data for {symbol}."
            return None
        parts = lines[1].split(",")
        if len(parts) < 7 or parts[6] in ("N/D", ""):
            _LAST_STOCK_ERROR["stooq_light"] = f"Stooq light quote for {symbol} came back empty."
            return None
        close = float(parts[6])
        _LAST_STOCK_ERROR["stooq_light"] = None
        return [close, close]  # only one data point available - flat sparkline, still shows a live price
    except Exception as e:
        _LAST_STOCK_ERROR["stooq_light"] = f"Stooq light quote failed for {symbol}: {e}"
        print("Stooq light fetch error:", symbol, e)
        return None


def _fetch_yahoo(symbol, host="query1"):
    """No-key fallback used whenever Stooq comes back empty (blocked, rate-limited,
    unrecognized symbol, etc). Yahoo's public chart endpoint needs no API key.
    Tries query1 then query2 - Yahoo load-balances across hosts and one is
    occasionally reachable when the other is rate-limiting your IP."""
    key = "yahoo" if host == "query1" else "yahoo2"
    try:
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, headers=FINANCE_HEADERS, params={"range": "1mo", "interval": "1d"}, timeout=8)
        if r.status_code != 200:
            _LAST_STOCK_ERROR[key] = f"Yahoo ({host}) returned HTTP {r.status_code} for {symbol} - likely rate-limited or blocked by your network/firewall/antivirus."
            return None
        result = (r.json().get("chart", {}).get("result") or [None])[0]
        if not result:
            _LAST_STOCK_ERROR[key] = f"Yahoo ({host}) returned no chart data for {symbol}."
            return None
        closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
        if not closes:
            _LAST_STOCK_ERROR[key] = f"Yahoo ({host}) response for {symbol} had no close prices."
            return None
        _LAST_STOCK_ERROR[key] = None
        return closes
    except Exception as e:
        _LAST_STOCK_ERROR[key] = f"Yahoo ({host}) request failed for {symbol}: {e}. This usually means the domain is blocked by a firewall/antivirus/VPN/DNS filter."
        print(f"Yahoo ({host}) fetch error:", symbol, e)
        return None


def _build_quote(symbol, closes):
    latest = closes[-1]
    prev = closes[-2] if len(closes) > 1 else latest
    change = latest - prev
    pct = (change / prev * 100) if prev else 0
    return {
        "symbol": symbol.upper(),
        "price": round(latest, 2),
        "change": round(change, 2),
        "pct": round(pct, 2),
        "history": closes,
    }


def fetch_stock(symbol):
    closes = _fetch_stooq(symbol) or _fetch_stooq_light(symbol) or _fetch_yahoo(symbol, "query1") or _fetch_yahoo(symbol, "query2")
    return _build_quote(symbol, closes) if closes else None


def fetch_index(symbol):
    yahoo_sym = YAHOO_INDEX_SYMBOLS.get(symbol.lower(), symbol)
    closes = (_fetch_stooq(symbol, index=True) or _fetch_stooq_light(symbol, index=True)
              or _fetch_yahoo(yahoo_sym, "query1") or _fetch_yahoo(yahoo_sym, "query2"))
    return _build_quote(symbol, closes) if closes else None


def fetch_all_stocks():
    out = []
    for item in STOCK_WATCHLIST:
        data = fetch_stock(item["symbol"])
        if data:
            data["logo"] = f"https://logo.clearbit.com/{item['domain']}"
            out.append(data)
    if not out:
        reason = (_LAST_STOCK_ERROR.get("yahoo") or _LAST_STOCK_ERROR.get("yahoo2")
                  or _LAST_STOCK_ERROR.get("stooq") or _LAST_STOCK_ERROR.get("stooq_light")
                  or "Unknown error - check your network/firewall.")
        with EXTRA_LOCK:
            extra_state["stocks_error"] = reason
    else:
        with EXTRA_LOCK:
            extra_state["stocks_error"] = None
    return out


def fetch_weather():
    try:
        loc = requests.get("http://ip-api.com/json/", timeout=6).json()
        lat, lon = loc.get("lat"), loc.get("lon")
        city = loc.get("city", "Unknown")
        if lat is None or lon is None:
            return None
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon, "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
            },
            timeout=8,
        ).json()
        current = w.get("current_weather", {}) or {}
        daily = w.get("daily", {}) or {}
        code = current.get("weathercode")
        desc, icon = WEATHER_CODES.get(code, ("Unknown", "\U0001F321\ufe0f"))
        return {
            "city": city,
            "temp": current.get("temperature"),
            "windspeed": current.get("windspeed"),
            "desc": desc,
            "icon": icon,
            "high": (daily.get("temperature_2m_max") or [None])[0],
            "low": (daily.get("temperature_2m_min") or [None])[0],
        }
    except Exception as e:
        print("Weather fetch error:", e)
        return None


def geocode_place(name):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        ).json()
        results = r.get("results") or []
        if not results:
            return None
        top = results[0]
        label = top.get("name") or name
        country = top.get("country")
        if country and country.lower() != label.lower():
            label = f"{label}, {country}"
        return {"lat": top.get("latitude"), "lon": top.get("longitude"), "label": label}
    except Exception as e:
        print("Geocode error:", name, e)
        return None


def fetch_weather_for_place(lat, lon, label):
    try:
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon, "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
            },
            timeout=8,
        ).json()
        current = w.get("current_weather", {}) or {}
        daily = w.get("daily", {}) or {}
        code = current.get("weathercode")
        desc, icon = WEATHER_CODES.get(code, ("Unknown", "\U0001F321\ufe0f"))
        return {
            "city": label,
            "temp": current.get("temperature"),
            "windspeed": current.get("windspeed"),
            "desc": desc,
            "icon": icon,
            "high": (daily.get("temperature_2m_max") or [None])[0],
            "low": (daily.get("temperature_2m_min") or [None])[0],
        }
    except Exception as e:
        print("Weather-for-place fetch error:", e)
        return None


def fetch_place_image(name):
    """No-key image lookup for a place. Tries restcountries.com first (fast,
    reliable, gives an actual flag plus capital/region/population for real
    countries), then falls back to a general DuckDuckGo image search so cities
    and non-country locations still get a picture."""
    try:
        r = requests.get(
            f"https://restcountries.com/v3.1/name/{requests.utils.quote(name)}",
            params={"fields": "flags,capital,region,population,name"},
            timeout=6,
        )
        if r.status_code == 200:
            data = r.json()
            top = data[0] if isinstance(data, list) and data else None
            if top:
                flags = top.get("flags") or {}
                return {
                    "image": flags.get("png") or flags.get("svg"),
                    "capital": (top.get("capital") or [None])[0],
                    "region": top.get("region"),
                    "population": top.get("population"),
                }
    except Exception as e:
        print("restcountries fetch error:", name, e)

    image = search_web_image(f"{name} landmark") or search_google_image(f"{name} landmark")
    return {"image": image, "capital": None, "region": None, "population": None}


def fetch_country_info(country_name):
    country_name = (country_name or "").strip()
    if not country_name:
        return {"country": country_name, "weather": None, "news": [], "stock": None,
                "image": None, "capital": None, "region": None, "population": None}

    geo = geocode_place(country_name)
    weather = None
    if geo and geo.get("lat") is not None and geo.get("lon") is not None:
        weather = fetch_weather_for_place(geo["lat"], geo["lon"], geo.get("label") or country_name)

    # 8 articles instead of 5 so the "show more" expander in the UI has something
    # to expand into.
    news = fetch_news(f"{country_name} news", max_results=8)

    stock = None
    index_symbol = COUNTRY_STOCK_INDEX.get(country_name.strip().lower())
    if index_symbol:
        stock = fetch_index(index_symbol)
        if stock:
            stock["label"] = f"{country_name} ({index_symbol.upper()})"

    place_extra = fetch_place_image(country_name)

    # A handful of extra photos (landmarks/cities) so the map panel isn't
    # limited to a single hero image, plus a dedicated political/outline map
    # image (separate from the flag/landmark photo above) and a short list of
    # relevant videos - all shown whenever a country is clicked on the map.
    gallery = search_web_images_multi(f"{country_name} landmarks cities", max_results=6)
    map_image = (search_web_image(f"{country_name} political map") or
                 search_web_image(f"{country_name} country map"))
    videos = search_web_videos(f"{country_name} travel guide", max_results=4)

    return {
        "country": country_name,
        "weather": weather,
        "news": news,
        "stock": stock,
        "image": place_extra.get("image"),
        "capital": place_extra.get("capital"),
        "region": place_extra.get("region"),
        "population": place_extra.get("population"),
        "gallery": gallery,
        "map_image": map_image,
        "videos": videos,
    }


def news_refresher():
    while True:
        articles = fetch_news()
        with EXTRA_LOCK:
            extra_state["news"] = articles
        time.sleep(600)


def stocks_refresher():
    while True:
        stocks = fetch_all_stocks()
        with EXTRA_LOCK:
            extra_state["stocks"] = stocks
        time.sleep(300)


def weather_refresher():
    while True:
        w = fetch_weather()
        with EXTRA_LOCK:
            extra_state["weather"] = w
        time.sleep(900)


def auto_learn_refresher():
    time.sleep(30)
    while True:
        try:
            with EXTRA_LOCK:
                articles = list(extra_state.get("news") or [])
            random.shuffle(articles)
            for article in articles:
                title = (article.get("title") or "").strip()
                if not title:
                    continue
                topic_guess = re.sub(r"[:\-\u2013].*$", "", title).strip()
                if not topic_guess or len(topic_guess) < 4:
                    continue
                try:
                    summary = wikipedia.summary(topic_guess, sentences=2)
                except Exception:
                    summary = None
                fact_text = summary or title
                if add_auto_fact(topic_guess, fact_text):
                    break
        except Exception as e:
            print("Auto-learn error:", e)
        time.sleep(1800)


def diagnose_stock_sources():
    """Runs once at startup: hits each finance data source directly and prints
    a pass/fail line for each, so a blocked domain is obvious immediately
    instead of buried behind a generic 'unavailable' message in the UI."""
    print("(Checking stock data sources...)")
    checks = [
        ("Stooq (CSV)", lambda: _fetch_stooq("AAPL")),
        ("Stooq (light quote)", lambda: _fetch_stooq_light("AAPL")),
        ("Yahoo query1", lambda: _fetch_yahoo("AAPL", "query1")),
        ("Yahoo query2", lambda: _fetch_yahoo("AAPL", "query2")),
    ]
    any_ok = False
    for name, fn in checks:
        try:
            result = fn()
            if result:
                print(f"  [OK]   {name} - reachable.")
                any_ok = True
            else:
                key = {"Stooq (CSV)": "stooq", "Stooq (light quote)": "stooq_light",
                       "Yahoo query1": "yahoo", "Yahoo query2": "yahoo2"}[name]
                print(f"  [FAIL] {name} - {_LAST_STOCK_ERROR.get(key)}")
        except Exception as e:
            print(f"  [FAIL] {name} - unexpected error: {e}")
    if not any_ok:
        print("(All stock sources failed. This almost always means your firewall, antivirus, VPN, or ISP "
              "is blocking stooq.com and finance.yahoo.com specifically - news/weather use different domains "
              "so they can work fine while stocks don't. Try temporarily disabling your firewall/antivirus, "
              "or add stooq.com and query1/query2.finance.yahoo.com to its allowed list, then restart Stark.)")
    return any_ok