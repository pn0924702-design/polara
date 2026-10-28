from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urljoin, urlencode
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser
import json
import os
import re
import socket
import ipaddress
import time

SEARCH_URL = os.environ.get(
    "POLARA_SEARCH_URL", "https://searx.tiekoetter.com"
).strip().rstrip("/")
ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(ROOT, "index.json")
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8765"))
PUBLIC_CRAWL = os.environ.get("POLARA_ENABLE_CRAWL", "0") == "1"
MAX_PAGES = 20
MAX_BYTES = 1_500_000
USER_AGENT = "POLARA-Prototype/1.0 (educational search service)"


def load_index():
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_index(items):
    with open(INDEX_FILE, "w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.text = []
        self.links = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        if tag in ("script", "style", "noscript", "svg"):
            self.skip_depth += 1
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        if tag in ("script", "style", "noscript", "svg") and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        clean = " ".join(data.split())
        if not clean:
            return
        if self.in_title:
            self.title.append(clean)
        if not self.skip_depth:
            self.text.append(clean)


def public_http_url(url):
    try:
        parsed = urlparse(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password):
            return False
        infos = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        return bool(infos) and all(
            ipaddress.ip_address(info[4][0]).is_global for info in infos
        )
    except Exception:
        return False


def fetch_page(url):
    if not public_http_url(url):
        raise ValueError("Адрес должен быть публичным сайтом с http:// или https://")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=10) as response:
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            return None, []
        raw = response.read(MAX_BYTES + 1)[:MAX_BYTES]
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    parser = PageParser()
    parser.feed(html)
    title = " ".join(parser.title).strip() or final_url
    text = re.sub(r"\s+", " ", " ".join(parser.text)).strip()
    item = {
        "url": final_url,
        "title": title[:300],
        "text": text[:30000],
        "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return item, parser.links


def crawl(start_url):
    start_url = start_url.strip()
    if not start_url:
        raise ValueError("Введи адрес сайта.")
    if not urlparse(start_url).scheme:
        start_url = "https://" + start_url
    if not public_http_url(start_url):
        raise ValueError("Не удалось проверить адрес. Используй публичный сайт, например https://example.com/")

    domain = urlparse(start_url).hostname
    queue = [start_url]
    seen = set()
    found = []
    robots = RobotFileParser()
    robots_url = f"{urlparse(start_url).scheme}://{domain}/robots.txt"
    try:
        robots.set_url(robots_url)
        robots.read()
        robots_ok = True
    except Exception:
        robots_ok = False

    while queue and len(found) < MAX_PAGES:
        url = queue.pop(0)
        parsed = urlparse(url)
        normalized = parsed._replace(fragment="", query="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)
        if parsed.hostname != domain or parsed.scheme not in ("http", "https"):
            continue
        if robots_ok and not robots.can_fetch(USER_AGENT, normalized):
            continue
        try:
            result, links = fetch_page(normalized)
            if result:
                found.append(result)
            for link in links:
                absolute = urljoin(normalized, link)
                link_parsed = urlparse(absolute)
                absolute = link_parsed._replace(fragment="", query="").geturl()
                if (link_parsed.hostname == domain
                        and link_parsed.scheme in ("http", "https")
                        and absolute not in seen and absolute not in queue):
                    queue.append(absolute)
        except Exception as exc:
            print(f"Crawler error for {normalized}: {exc}")
        time.sleep(1)

    current = load_index()
    by_url = {item.get("url"): item for item in current if isinstance(item, dict)}
    for item in found:
        by_url[item["url"]] = item
    combined = list(by_url.values())
    save_index(combined)
    return {"added": len(found), "total": len(combined), "domain": domain}


def search_index(query):
    query = query.strip()
    if not query:
        return [], "empty query", "none"

    # Try the external metasearch service first.
    if SEARCH_URL:
        try:
            params = urlencode({"q": query, "format": "json", "language": "all"})
            request = Request(
                f"{SEARCH_URL}/search?{params}",
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urlopen(request, timeout=12) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8"))
            web_results = []
            for item in data.get("results", [])[:20]:
                result_url = item.get("url", "")
                if not result_url.startswith(("http://", "https://")):
                    continue
                web_results.append({
                    "title": item.get("title") or result_url,
                    "url": result_url,
                    "snippet": re.sub(r"\s+", " ", item.get("content") or "")[:260],
                    "score": 0,
                })
            if web_results:
                return web_results, "", "web"
            web_error = "SearXNG вернул пустой список результатов"
        except Exception as exc:
            web_error = f"{type(exc).__name__}: {exc}"
            print(f"SearXNG search error: {web_error}")
    else:
        web_error = "POLARA_SEARCH_URL не задан"

    # If the external service fails, search the local index.
    words = [word.lower() for word in re.findall(r"\w+", query, flags=re.UNICODE) if len(word) > 1]
    scored = []
    for item in load_index():
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("заголовок") or "")
        content = str(item.get("text") or item.get("текст") or item.get("snippet") or "")
        result_url = str(item.get("url") or "")
        searchable = (title + " " + content + " " + result_url).lower()
        score = sum(title.lower().count(word) * 5 + content.lower().count(word)
                    + result_url.lower().count(word) * 2 for word in words)
        for word in words:
            if re.search(r"\b" + re.escape(word) + r"\b", searchable, flags=re.UNICODE):
                score += 2
        if score:
            scored.append((score, title, content, result_url))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    local_results = [{
        "title": title or result_url,
        "url": result_url,
        "snippet": content[:260] + ("…" if len(content) > 260 else ""),
        "score": score,
    } for score, title, content, result_url in scored[:20]]
    return local_results, web_error, "local" if local_results else "none"


class Handler(SimpleHTTPRequestHandler):
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
            results, web_error, source = search_index(query)
            self.send_json({
                "results": results,
                "total_indexed": len(load_index()),
                "search_source": source,
                "web_search_error": web_error,
            })
            return
        if parsed.path == "/api/status":
            self.send_json({"total_indexed": len(load_index())})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

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
    print("Для остановки нажми Ctrl+C.")
    print("=" * 52)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
