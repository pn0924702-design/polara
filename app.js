const $ = (id) => document.getElementById(id);
const results = $("results");
async function refreshCount() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();
    $("count").textContent = `В индексе страниц: ${d.total_indexed}`;
  } catch {
    $("count").textContent = "Сервер не отвечает";
  }
}
function renderResults(items, query) {
  $("results-title").textContent = query ? `Результаты: «${query}»` : "Результаты поиска";
  $("result-count").textContent = `${items.length} найдено`;
  if (!items.length) {
    results.innerHTML = '<div class="empty">Ничего не найдено. Возможно, сайт ещё не добавлен в индекс.</div>';
    return;
  }
  results.replaceChildren();
  for (const item of items) {
    const article = document.createElement("article");
    article.className = "result";
    const a = document.createElement("a");
    a.href = item.url; a.target = "_blank"; a.rel = "noopener noreferrer";
    a.textContent = item.title || item.url;
    const url = document.createElement("div"); url.className = "url"; url.textContent = item.url;
    const snippet = document.createElement("div"); snippet.className = "snippet"; snippet.textContent = item.snippet || "";
    article.append(a, url, snippet); results.append(article);
  }
}
$("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("query").value.trim();
  if (!q) return;
  results.innerHTML = '<div class="empty">Ищем в локальном индексе…</div>';
  try {
    const response = await fetch("/api/search?q=" + encodeURIComponent(q));
    const data = await response.json();
    renderResults(data.results || [], q);
  } catch {
    results.innerHTML = '<div class="empty">Не удалось связаться с POLARA. Проверь, что окно start.bat открыто.</div>';
  }
});
$("crawl-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("crawl-button");
  const status = $("crawl-status");
  button.disabled = true; button.textContent = "Идёт работа…";
  status.textContent = "Подключаемся к сайту. Это может занять несколько минут.";
  try {
    const response = await fetch("/api/crawl", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({url: $("site-url").value.trim()})
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "Не удалось добавить сайт");
    status.textContent = `Готово! Добавлено страниц: ${data.added}. Всего в индексе: ${data.total}. Теперь можно искать по их тексту.`;
    await refreshCount();
  } catch (err) {
    status.textContent = "Ошибка: " + err.message;
  } finally {
    button.disabled = false; button.textContent = "Индексировать";
  }
});
refreshCount();
