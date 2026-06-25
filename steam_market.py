"""Preços do Steam Community Market para a página Mercado.

Estratégia: buscar o preço só dos itens que o jogador TEM (não os ~741 do
mercado), via endpoint priceoverview por item (que respeita currency=7 → BRL de
forma confiável, sem o fallback pra USD do search/render). Um worker em
background espaça as requisições (~3s) pra não tomar 429, e o resultado é
cacheado em disco. Sem dependências externas (urllib stdlib).

Nome de mercado:
- materiais/gems/soulstones/coins: o próprio nome inglês ("Twilight Amethyst").
- gear: "Base (Grade) Sufixo" — ex.: "Dimensional Boots (Legendary) A". O sufixo
  atual é sempre "A" (único tier negociável); construímos esse nome.
"""
import json
import queue
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

STEAM_APPID = 3678970
CURRENCY_BRL = 7
STEAM_FEE = 0.30                 # taxa da Steam (definido pelo usuário)
TRADESHIP_COOLDOWN_HOURS = 8     # cooldown do tradeship (definido pelo usuário)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def normalize_name(s):
    return " ".join((s or "").strip().lower().split())


def parse_price_brl(text):
    """'R$ 1.234,56' -> 123456 (centavos). None se não der pra ler."""
    if not text:
        return None
    s = (text.replace("R$", "").replace("\xa0", "").strip()
         .replace(".", "").replace(",", "."))
    try:
        return round(float(s) * 100)
    except ValueError:
        return None


def _en_name(item):
    n = item.get("name") or {}
    return n.get("en-US") or next(iter(n.values()), None)


def _disp_name(item, lang_code):
    n = item.get("name") or {}
    return n.get(lang_code) or n.get("en-US") or next(iter(n.values()), None)


def market_hash_name(item, en=None):
    """Nome de mercado do item (market_hash_name). Gear leva (Grade) + sufixo A."""
    en = en or _en_name(item)
    if not en:
        return None
    grade = item.get("grade")
    if item.get("gear") and grade:
        return f"{en} ({grade.title()}) A"
    return en


def _fetch_priceoverview(hash_name, appid=STEAM_APPID, currency=CURRENCY_BRL):
    qs = urllib.parse.urlencode({"appid": appid, "currency": currency,
                                 "market_hash_name": hash_name})
    url = "https://steamcommunity.com/market/priceoverview/?" + qs
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
    if not d.get("success"):
        return {"success": False}
    return {
        "success": True,
        "cents": parse_price_brl(d.get("lowest_price")),
        "text": d.get("lowest_price"),
        "median_cents": parse_price_brl(d.get("median_price")),
        "volume": d.get("volume"),
    }


class PriceCache:
    """Cache em disco de preços por market_hash_name, alimentado por um worker
    em background que busca um item por vez (espaçado) pra não tomar 429."""

    def __init__(self, path, appid=STEAM_APPID, currency=CURRENCY_BRL,
                 ttl=6 * 3600, fail_ttl=120, interval=3.0,
                 fetch=_fetch_priceoverview, now=time.time):
        self.path = Path(path)
        self.appid = appid
        self.currency = currency
        self.ttl = ttl
        self.fail_ttl = fail_ttl
        self.interval = interval
        self._fetch = fetch
        self._now = now
        self._lock = threading.Lock()
        self._data = self._load()        # {hash_name: {success, cents, ..., ts}}
        self._queued = set()
        self._q = queue.Queue()
        self._worker = None

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except OSError:
            pass

    def _fresh(self, e):
        if not e:
            return False
        ttl = self.ttl if e.get("success") else self.fail_ttl
        return (self._now() - e.get("ts", 0)) < ttl

    def get(self, name):
        """Entry fresca (ou None se ausente/vencida/ainda na fila)."""
        with self._lock:
            e = self._data.get(name)
            return dict(e) if self._fresh(e) else None

    def request(self, names):
        """Enfileira pra buscar os nomes ainda não frescos."""
        start = False
        with self._lock:
            for n in names:
                if not n or n in self._queued or self._fresh(self._data.get(n)):
                    continue
                self._queued.add(n)
                self._q.put(n)
            if self._queued and (self._worker is None or not self._worker.is_alive()):
                self._worker = threading.Thread(target=self._run, daemon=True)
                start = True
        if start:
            self._worker.start()

    def _run(self):
        while True:
            try:
                name = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                res = self._fetch(name, self.appid, self.currency)
            except Exception:
                res = {"success": False}
            with self._lock:
                self._data[name] = {**res, "ts": self._now()}
                self._queued.discard(name)
                self._save()
            if self.interval:
                time.sleep(self.interval)


def market_panel(gd, save, cache, lang="en"):
    """Itens marketáveis do inventário/stash/trading com valor de Steam."""
    lang_code = {"pt": "pt-BR", "en": "en-US"}.get(lang, "en-US")
    keep = 1 - STEAM_FEE
    by_uid = {it.get("UniqueId"): it for it in save.get("itemSaveDatas") or []}

    # 1ª passada: todos os itens (na ordem nativa, igual cubo) + nomes de mercado
    # só dos negociáveis (esses é que vão pra busca de preço)
    owned = []   # (uid, item, en, hash_name, marketable)
    names = []
    for key in ("inventorySaveDatas", "stashSaveDatas", "tradingStashSaveDatas"):
        for s in save.get(key) or []:
            uid = s.get("ItemUniqueId")
            it = by_uid.get(uid)
            item = gd.items.get(it.get("ItemKey")) if it else None
            if not item:
                continue
            mk = bool(item.get("marketable"))
            en = _en_name(item)
            hn = market_hash_name(item, en) if mk else None
            owned.append((uid, item, en, hn, mk))
            if hn:
                names.append(hn)
    cache.request(names)   # dispara as buscas que faltam

    def entry(uid, item, en, hn, mk):
        p = cache.get(hn) if hn else None
        priced = bool(p and p.get("success") and p.get("cents") is not None)
        listed = p.get("cents") if priced else None
        return {
            "uid": str(uid),
            "key": item["id"],
            "name": _disp_name(item, lang_code),
            "hashName": hn,
            "grade": item.get("grade"),
            "type": item.get("type"),
            "gear": item.get("gear"),
            "level": item.get("level"),
            "marketable": mk,
            "listed": listed,
            "listedText": p.get("text") if priced else None,
            "receive": round(listed * keep) if listed else None,
            "matched": priced,
            "pending": bool(mk and p is None),    # buscando o preço (só negociável)
        }

    rows = {uid: entry(uid, item, en, hn, mk) for uid, item, en, hn, mk in owned}
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
        "containers": containers,
    }
