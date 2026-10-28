

def search_web(query):
    """Search SearXNG. Return (results, error); errors are exposed for diagnostics."""
    if not SEARCH_URL:
        return [], "POLARA_SEARCH_URL не задан"
    params = urlencode({"q": query, "format": "json", "language": "all"})
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request = Request(f"{SEARCH_URL}/search?{params}", headers=headers)
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(2_000_000).decode("utf-8", errors="replace")
        data = json.loads(raw)
        results = []
        for item in data.get("results", [])[:20]:
            url = item.get("url", "")
            if url.startswith(("https://", "http://")):
                results.append({"title": item.get("title") or url, "url": url, "snippet": re.sub(r"\s+", " ", item.get("content") or "")[:260], "score": 0})
        if results:
            return results, None
        return [], "SearXNG ответил JSON, но не вернул результатов"
    except Exception as exc:
        json_error = f"JSON API: {type(exc).__name__}: {exc}"

    # If JSON is blocked, try the regular HTML search page.
    try:
        html_params = urlencode({"q": query, "language": "all"})
        request = Request(f"{SEARCH_URL}/search?{html_params}", headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urlopen(request, timeout=12) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")
        parser = SearchHTMLParser()
        parser.feed(html)
        if parser.results:
            return parser.results[:20], None
        return [], json_error + "; HTML: страница открылась, но результаты не удалось разобрать"
    except Exception as exc:
        return [], json_error + f"; HTML: {type(exc).__name__}: {exc}"


def search_local(query):
    words = [w.lower() for w in re.findall(r"\w+", query, flags=re.UNICODE) if len(w) > 1]
    if not words:
        return []
    scored = []
    for item in load_index():
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("заголовок") or "").lower()
        content = str(item.get("text") or item.get("текст") or item.get("snippet") or "").lower()
        url = str(item.get("url") or "")
        searchable = title + " " + content + " " + url.lower()
        score = sum(title.count(w) * 5 + content.count(w) + url.lower().count(w) * 2 for w in words)
        for word in words:
            if re.search(r"\b" + re.escape(word) + r"\b", searchable, flags=re.UNICODE):
                score += 2
        if score:
            scored.append((score, title, content, url))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{"title": title or url, "url": url, "snippet": content[:260] + ("…" if len(content) > 260 else ""), "score": score} for score, title, content, url in scored[:20]]


def search_index(query):
    query = query.strip()
    if not query:
        return [], None
    web_results, web_error = search_web(query)
    if web_results:
        return web_results, None
    return search_local(query), web_error


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0]
            results, web_error = search_index(query)
            self.send_json({"results": results[:20], "total_indexed": len(load_index()), "web_search": not bool(web_error), "web_search_error": web_error})
            return
        if parsed.path == "/api/status":
            self.send_json({"total_indexed": len(load_index()), "search_url_configured": bool(SEARCH_URL)})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/crawl":
            self.send_json({"error": "Неизвестный адрес API"}, 404)
            return
        if not PUBLIC_CRAWL:
            self.send_json({"error": "Индексирование отключено на публичном демо-сервере. Это сделано для защиты сервиса."}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10000:
                self.send_json({"error": "Слишком большой запрос"}, 413)
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = crawl(str(body.get("url", "")))
            self.send_json({"ok": True, **result})
        except Exception as exc:
            self.send_json({"error": str(exc) or "Не удалось проиндексировать сайт"}, 400)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print("=" * 52)
    print("POLARA — веб-демо")
    print(f"Сервер слушает порт: {PORT}")
    print(f"SearXNG: {SEARCH_URL}")
    print("Для остановки нажми Ctrl+C.")
    print("=" * 52)
    try:
