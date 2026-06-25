"""Preços do Steam Community Market para a página Mercado.

Estratégia: UM sweep em lote do mercado inteiro (endpoint search/render) com
`country=BR` — que é o único jeito de vir tudo em BRL de forma confiável (sem
country a moeda oscila entre R$ e US$ na mesma resposta; o priceoverview por
item é confiável mas toma 429 com dezenas de itens). O sweep roda em background,
salva incrementalmente em disco e NUNCA descarta um preço já conhecido (falha
parcial/429 mantém o que já tem). TTL 15min. Sem dependências externas.

Casamento item -> preço:
- material/gem/soulstone/coin: nome inglês exato ("Twilight Amethyst").
- gear: nome de mercado é "Base (Grade) Sufixo" (ex.: "Dimensional Boots
  (Legendary) A"); casa por prefixo "Base (Grade)" e pega o de menor preço.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STEAM_APPID = 3678970
CURRENCY_BRL = 7
COUNTRY_BR = "BR"                # força BRL consistente no render
STEAM_FEE = 0.30                 # taxa da Steam (definido pelo usuário)
TRADESHIP_COOLDOWN_HOURS = 8     # cooldown do tradeship (definido pelo usuário)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def normalize_name(s):
    return " ".join((s or "").strip().lower().split())


def parse_render_page(obj):
    """[{hash_name, sell_price(centavos|None), sell_price_text}], total_count."""
    out = []
    for r in (obj or {}).get("results") or []:
        name = r.get("hash_name") or r.get("name")
        if not name:
            continue
        out.append({
            "hash_name": name,
            "sell_price": r.get("sell_price"),
            "sell_price_text": r.get("sell_price_text"),
        })
    return out, (obj or {}).get("total_count") or 0


def _fetch_page(appid, currency, start, count, country=COUNTRY_BR):
    qs = urllib.parse.urlencode({"appid": appid, "norender": 1,
                                 "start": start, "count": count,
                                 "currency": currency, "country": country})
    url = "https://steamcommunity.com/market/search/render/?" + qs
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


class MarketCache:
    """Mapa normalized_hash_name -> {hash_name, cents, text}, alimentado por um
    sweep em background do mercado inteiro. Persistido em disco; nunca descarta
    preço conhecido."""

    def __init__(self, path, appid=STEAM_APPID, currency=CURRENCY_BRL,
                 country=COUNTRY_BR, ttl=3 * 60, interval=1.0, count=100,
                 fetch=_fetch_page, now=time.time):
        self.path = Path(path)
        self.appid = appid
        self.currency = currency
        self.country = country
        self.ttl = ttl
        self.interval = interval
        self.count = count
        self._fetch = fetch
        self._now = now
        self._lock = threading.Lock()
        self._prices, self._updated = self._load()
        self._sweeping = False
        self._progress = (0, 0)         # (baixados, total) do sweep atual
        self._worker = None

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d.get("prices") or {}, d.get("updatedAt", 0)
        except (FileNotFoundError, ValueError):
            return {}, 0

    def _save(self):
        try:
            self.path.write_text(json.dumps({
                "updatedAt": self._updated, "prices": self._prices,
            }), encoding="utf-8")
        except OSError:
            pass

    def _fresh(self):
        return bool(self._prices) and (self._now() - self._updated) < self.ttl

    def prices(self):
        with self._lock:
            return dict(self._prices)

    def loading(self):
        with self._lock:
            return self._sweeping

    def meta(self):
        with self._lock:
            return {"updatedAt": self._updated, "have": len(self._prices),
                    "loading": self._sweeping, "progress": self._progress,
                    "stale": not self._fresh()}

    def ensure(self):
        """Dispara um sweep em background se estiver vencido e nenhum em curso."""
        with self._lock:
            if self._sweeping or self._fresh():
                return
            self._sweeping = True
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        start, total, retries = 0, 0, 0
        try:
            while True:
                try:
                    page = self._fetch(self.appid, self.currency, start,
                                       self.count, self.country)
                except urllib.error.HTTPError as e:
                    if e.code == 429 and retries < 8:
                        retries += 1
                        time.sleep(30)        # 429: recua e re-tenta a mesma página
                        continue
                    break                     # outro erro/desiste: mantém o que tem
                except Exception:
                    break
                retries = 0
                rows, total = parse_render_page(page)
                if not rows:
                    break
                with self._lock:
                    for e in rows:
                        text = e.get("sell_price_text") or ""
                        if text.strip().startswith("$"):
                            continue          # defensivo: ignora linha em USD
                        self._prices[normalize_name(e["hash_name"])] = {
                            "hash_name": e["hash_name"],
                            "cents": e.get("sell_price"),
                            "text": text,
                        }
                    self._progress = (start + len(rows), total)
                    self._save()              # incremental: progresso aparece já
                start += len(rows)
                if total and start >= total:
                    break
                if self.interval:
                    time.sleep(self.interval)
        finally:
            with self._lock:
                self._updated = self._now()
                self._sweeping = False
                self._save()


def find_price(prices, item, en):
    """Preço de um item no mapa do mercado. Exato pelo nome inglês; pra GEAR
    casa por prefixo "Base (Grade)" (sufixo A/B/…) pegando o de menor preço."""
    if not en:
        return None
    p = prices.get(normalize_name(en))
    if p:
        return p
    grade = item.get("grade")
    if grade and item.get("gear"):
        pref = normalize_name(f"{en} ({grade})") + " "
        cands = [v for k, v in prices.items() if k.startswith(pref)]
        if cands:
            return min(cands, key=lambda v: v["cents"]
                       if v.get("cents") is not None else float("inf"))
    return None


def _en_name(item):
    n = item.get("name") or {}
    return n.get("en-US") or next(iter(n.values()), None)


def _disp_name(item, lang_code):
    n = item.get("name") or {}
    return n.get(lang_code) or n.get("en-US") or next(iter(n.values()), None)


def _iter_owned(gd, save):
    """Itera os itens do inventário/stash/trading (ordem nativa, igual cubo),
    rendendo (uid, item, en_name, marketable)."""
    by_uid = {it.get("UniqueId"): it for it in save.get("itemSaveDatas") or []}
    for key in ("inventorySaveDatas", "stashSaveDatas", "tradingStashSaveDatas"):
        for s in save.get(key) or []:
            uid = s.get("ItemUniqueId")
            it = by_uid.get(uid)
            item = gd.items.get(it.get("ItemKey")) if it else None
            if not item:
                continue
            yield uid, item, _en_name(item), bool(item.get("marketable"))


def market_panel(gd, save, cache, lang="en"):
    """Itens do inventário/stash/trading com valor de Steam (BRL)."""
    lang_code = {"pt": "pt-BR", "en": "en-US"}.get(lang, "en-US")
    keep = 1 - STEAM_FEE
    cache.ensure()                       # garante o sweep em background
    prices = cache.prices()
    loading = cache.loading()

    def entry(uid, item, en, mk):
        p = find_price(prices, item, en) if mk else None
        listed = p.get("cents") if p else None
        priced = listed is not None
        return {
            "uid": str(uid),
            "key": item["id"],
            "name": _disp_name(item, lang_code),
            "hashName": p.get("hash_name") if p else None,
            "grade": item.get("grade"),
            "type": item.get("type"),
            "gear": item.get("gear"),
            "level": item.get("level"),
            "marketable": mk,
            "listed": listed,
            "listedText": p.get("text") if priced else None,
            "receive": round(listed * keep) if priced else None,
            "matched": priced,
            "pending": bool(mk and not priced and loading),  # ainda carregando o mercado
        }

    rows = {uid: entry(uid, item, en, mk) for uid, item, en, mk in _iter_owned(gd, save)}
    containers = []
    for cid, label, key in (("inventory", "Inventário", "inventorySaveDatas"),
                            ("stash", "Stash", "stashSaveDatas"),
                            ("trading", "Stash de troca", "tradingStashSaveDatas")):
        slots = [rows.get(s.get("ItemUniqueId")) for s in (save.get(key) or [])]
        items = [e for e in slots if e]
        containers.append({
            "id": cid, "label": label, "slots": slots,
            "filled": len(items),
            "tradable": sum(1 for e in items if e["marketable"]),
            "matched": sum(1 for e in items if e["matched"]),
            "pending": sum(1 for e in items if e["pending"]),
            "sumReceive": sum(e["receive"] or 0 for e in items),
        })
    return {
        "appid": STEAM_APPID,
        "feePct": round(STEAM_FEE * 100),
        "cooldownHours": TRADESHIP_COOLDOWN_HOURS,
        "loading": loading,
        "containers": containers,
    }
