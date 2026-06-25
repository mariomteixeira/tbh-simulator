"""Preços do Steam Community Market para a página Mercado.

Puxa TODOS os itens negociáveis do TBH (appid 3678970) em lote pelo endpoint
market/search/render (paginado), cacheia em disco com TTL e casa com os itens
do save por nome inglês normalizado. Sem dependências externas (urllib stdlib).
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

STEAM_APPID = 3678970
CURRENCY_BRL = 7
COUNTRY_BR = "BR"                # força localização BRL consistente no render
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


def fetch_all_prices(appid=STEAM_APPID, currency=CURRENCY_BRL,
                     country=COUNTRY_BR, fetch=None):
    """Pagina o render até cobrir total_count. normalized_name -> entry."""
    if fetch is None:
        fetch = lambda a, c, s, n: _fetch_page(a, c, s, n, country)
    prices, start, total = {}, 0, None
    while True:
        rows, total = parse_render_page(fetch(appid, currency, start, 100))
        if not rows:
            break
        for e in rows:
            prices[normalize_name(e["hash_name"])] = e
        start += len(rows)
        if (total and start >= total) or start > 5000:
            break
    return prices


class SteamMarketCache:
    """Cache em disco dos preços, com TTL e fallback stale em falha de rede."""

    def __init__(self, path, ttl=3600, currency=CURRENCY_BRL,
                 fetch=fetch_all_prices, now=time.time):
        self.path = Path(path)
        self.ttl = ttl
        self.currency = currency
        self._fetch = fetch
        self._now = now
        self._prices = None
        self._updated = 0
        self._load_disk()

    def _load_disk(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self._prices = d.get("prices")
            self._updated = d.get("updatedAt", 0)
            self.currency = d.get("currency", self.currency)
        except (FileNotFoundError, ValueError):
            self._prices = None

    def _save_disk(self):
        try:
            self.path.write_text(json.dumps({
                "updatedAt": self._updated, "currency": self.currency,
                "prices": self._prices,
            }), encoding="utf-8")
        except OSError:
            pass

    def _fresh(self):
        return self._prices is not None and (self._now() - self._updated) < self.ttl

    def prices(self):
        if not self._fresh():
            try:
                self._prices = self._fetch(currency=self.currency)
                self._updated = self._now()
                self._save_disk()
            except Exception:
                pass   # mantém o último cache (stale) ou {}
        return self._prices or {}

    def meta(self):
        return {"updatedAt": self._updated, "currency": self.currency,
                "stale": not self._fresh()}


def _disp_name(item, lang_code):
    n = item.get("name") or {}
    return n.get(lang_code) or n.get("en-US") or next(iter(n.values()), None)


def _en_name(item):
    n = item.get("name") or {}
    return n.get("en-US") or next(iter(n.values()), None)


def market_panel(gd, save, cache, lang="en"):
    """Itens marketáveis do inventário/stash/trading com valor de Steam."""
    lang_code = {"pt": "pt-BR", "en": "en-US"}.get(lang, "en-US")
    prices = cache.prices()
    keep = 1 - STEAM_FEE
    by_uid = {it.get("UniqueId"): it for it in save.get("itemSaveDatas") or []}

    def entry(uid):
        if not uid:
            return None
        it = by_uid.get(uid)
        if not it:
            return None
        item = gd.items.get(it.get("ItemKey"))
        if not item or not item.get("marketable"):
            return None
        en = _en_name(item)
        p = prices.get(normalize_name(en)) if en else None
        listed = p.get("sell_price") if p else None
        return {
            "uid": str(uid),
            "key": item["id"],
            "name": _disp_name(item, lang_code),
            "hashName": en,
            "grade": item.get("grade"),
            "type": item.get("type"),
            "gear": item.get("gear"),
            "level": item.get("level"),
            "listed": listed,
            "listedText": p.get("sell_price_text") if p else None,
            "receive": round(listed * keep) if listed else None,
            "matched": p is not None,
        }

    containers = []
    for cid, label, key in (("inventory", "Inventário", "inventorySaveDatas"),
                            ("stash", "Stash", "stashSaveDatas"),
                            ("trading", "Stash de troca", "tradingStashSaveDatas")):
        slots = [entry(s.get("ItemUniqueId")) for s in (save.get(key) or [])]
        mk = [e for e in slots if e]
        containers.append({
            "id": cid, "label": label, "slots": slots,
            "filled": len(mk),
            "matched": sum(1 for e in mk if e["matched"]),
            "sumReceive": sum(e["receive"] or 0 for e in mk),
        })
    return {
        "appid": STEAM_APPID,
        "feePct": round(STEAM_FEE * 100),
        "cooldownHours": TRADESHIP_COOLDOWN_HOURS,
        "containers": containers,
        **cache.meta(),
    }
