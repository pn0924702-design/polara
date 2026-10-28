const $ = (id) => document.getElementById(id);
const results = $("results");
const translations = {
 ru:{home:"Главная",featuresNav:"Возможности",about:"О нас",contacts:"Контакты",tagline:"Поиск, который всегда рядом",popular:"Популярные запросы:",tashkent:"Ташкент",universities:"Университеты",work:"Работа",weather:"Погода",fast:"Быстрые<br>результаты",reliable:"Надёжные<br>источники",bilingual:"На двух языках",uzbekistan:"Создан для<br>Узбекистана",placeholder:"Найди всё, что тебе нужно...",count:"В индексе страниц: "},
 uz:{home:"Bosh sahifa",featuresNav:"Imkoniyatlar",about:"Biz haqimizda",contacts:"Aloqa",tagline:"Har doim yoningizdagi qidiruv",popular:"Ommabop so‘rovlar:",tashkent:"Toshkent",universities:"Universitetlar",work:"Ish",weather:"Ob-havo",fast:"Tezkor<br>natijalar",reliable:"Ishonchli<br>manbalar",bilingual:"Ikki tilda",uzbekistan:"O‘zbekiston uchun<br>yaratilgan",placeholder:"Kerakli ma’lumotni qidiring...",count:"Indekslangan sahifalar: "}
};
async function refreshCount(){
 try{const r=await fetch("/api/status");const d=await r.json();$("count").textContent=(translations[document.documentElement.lang]||translations.ru).count+(d.total_indexed??0);}
 catch{$("count").textContent="Сервер не отвечает";}
}
function renderResults(items,query){
 $("results-title").textContent=query?`Результаты: «${query}»`:"Результаты поиска";$("result-count").textContent=`${items.length} найдено`;
 if(!items.length){results.innerHTML='<div class="empty">Ничего не найдено. Возможно, сайт ещё не добавлен в индекс.</div>';return;}
 results.replaceChildren();
 for(const item of items){const article=document.createElement("article");article.className="result";const a=document.createElement("a");a.href=item.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent=item.title||item.url;const url=document.createElement("div");url.className="url";url.textContent=item.url;const snippet=document.createElement("div");snippet.className="snippet";snippet.textContent=item.snippet||"";article.append(a,url,snippet);results.append(article);}
}
$("search-form").addEventListener("submit",async e=>{
 e.preventDefault();const q=$("query").value.trim();if(!q)return;
 results.innerHTML='<div class="empty">Ищем в индексе POLARA…</div>';document.querySelector(".results-section").scrollIntoView({behavior:"smooth",block:"start"});
 try{const response=await fetch("/api/search?q="+encodeURIComponent(q));const data=await response.json();renderResults(data.results||[],q);}
 catch{results.innerHTML='<div class="empty">Не удалось связаться с сервером POLARA. Попробуй ещё раз позже.</div>';}
});
document.querySelectorAll("[data-query]").forEach(btn=>btn.addEventListener("click",()=>{$("query").value=btn.dataset.query;$("search-form").requestSubmit();}));

function setLanguage(lang){
 const dict=translations[lang]||translations.ru;document.documentElement.lang=lang;
 document.querySelectorAll("[data-i18n]").forEach(el=>{const key=el.dataset.i18n;if(dict[key])el.innerHTML=dict[key];});
 $("query").placeholder=dict.placeholder;
 document.querySelectorAll(".lang").forEach(b=>b.classList.toggle("active",b.dataset.lang===lang));
 refreshCount();
}
document.querySelectorAll(".lang").forEach(b=>b.addEventListener("click",()=>setLanguage(b.dataset.lang)));
$("theme-toggle").addEventListener("click",()=>{document.body.classList.toggle("theme-dark");$("theme-toggle").setAttribute("aria-pressed",document.body.classList.contains("theme-dark")?"true":"false");});
setLanguage("ru");refreshCount();
