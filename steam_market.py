"""Preços do Steam Community Market para a página Mercado.

Fonte do preço = endpoint **priceoverview** (atual, bate com a página). NÃO o
search/render, cujo `sell_price` vem de um índice de busca defasado em horas
(causava valores errados/baixos). priceoverview tem limite ~20 req/min, então:

- busca SÓ os itens que o jogador tem (não os ~742 do mercado);
- um worker em background respeita um teto de ~10 req/min (1 a cada 6s);
- cada item revalida a cada ~20min (3x/hora) — folga grande no limite;
- NUNCA descarta um preço bom: 429/erro de rede não apaga o valor já conhecido;
- persiste em disco (sobrevive a restart).

currency=7 já devolve BRL no texto ("R$ 2,26"); parse_price_brl converte em
centavos. Nome de mercado: material = nome inglês; gear = "Base (Grade) A".
Sem dependências externas (urllib stdlib).
"""
import json
import queue
import threading
import time
import urllib.error
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
    """Nome de mercado (market_hash_name). Gear = "Base (Grade) A"; resto = nome."""
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
        "median_cents": parse_price_brl(d.get("median_price")),
        "volume": d.get("volume"),
    }


class PriceCache:
    """Cache em disco de preços por market_hash_name (fonte=priceoverview).

    Um worker busca 1 item por vez, respeitando `interval` (teto de req/min).
    NUNCA descarta um preço bom: só um novo sucesso substitui o valor; 429/erro
    de rede deixam o valor anterior intacto."""

    def __init__(self, path, appid=STEAM_APPID, currency=CURRENCY_BRL,
                 ttl=20 * 60, fail_ttl=20 * 60, interval=6.0, backoff=60,
                 max_429=5, cooldown=15 * 60, max_cooldown=60 * 60,
                 fetch=_fetch_priceoverview, now=time.time):
        self.path = Path(path)
        self.appid = appid
        self.currency = currency
        self.ttl = ttl              # revalida preço bom a cada 20min (3x/hora)
        self.fail_ttl = fail_ttl    # re-tenta "sem listagem" a cada 20min
        self.interval = interval    # 6s -> teto ~10 req/min
        self.backoff = backoff      # pausa após 429
        self.max_429 = max_429      # 429s seguidos antes de pausar tudo
        self.cooldown = cooldown    # pausa base do circuit breaker
        self.max_cooldown = max_cooldown  # teto da pausa (recuo progressivo)
        self._fetch = fetch
        self._now = now
        self._lock = threading.Lock()
        self._data = self._load()        # {hash_name: {success, cents, ts, ...}}
        self._queued = set()
        self._q = queue.Queue()
        self._worker = None
        self._pause_until = 0            # circuit breaker: não busca enquanto > now
        self._breaker_trips = 0          # pausas seguidas (recuo progressivo)
        self._activity = []              # log das últimas buscas (p/ debug na UI)

    def _record(self, name, status, cents=None):
        self._activity.append({"name": name, "status": status,
                               "cents": cents, "ts": self._now()})
        if len(self._activity) > 30:
            self._activity = self._activity[-30:]

    def status(self):
        """Estado p/ o painel de debug: log de buscas, fila e pausa."""
        with self._lock:
            return {
                "activity": list(self._activity),
                "queued": len(self._queued),
                "pausedSecs": max(0, round(self._pause_until - self._now())),
                "cached": len(self._data),
            }

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("prices"), dict):
                return {}                # formato antigo (sweep) — começa limpo
            return d if isinstance(d, dict) else {}
        except (FileNotFoundError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except OSError:
            pass

    def _needs_refresh(self, name):
        e = self._data.get(name)
        if not e:
            return True
        ttl = self.ttl if e.get("success") else self.fail_ttl
        return (self._now() - e.get("ts", 0)) >= ttl

    def get(self, name):
        """Valor armazenado p/ exibir (mesmo defasado — nunca some)."""
        with self._lock:
            e = self._data.get(name)
            return dict(e) if e else None

    def request(self, names):
        """Enfileira os nomes que precisam buscar/revalidar."""
        start = False
        with self._lock:
            if self._now() < self._pause_until:   # circuit breaker ativo: não bate na Steam
                return
            for n in names:
                if not n or n in self._queued or not self._needs_refresh(n):
                    continue
                self._queued.add(n)
                self._q.put(n)
            if self._queued and (self._worker is None or not self._worker.is_alive()):
                self._worker = threading.Thread(target=self._run, daemon=True)
                start = True
        if start:
            self._worker.start()

    def _run(self):
        consec_429 = 0
        while True:
            try:
                name = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                res = self._fetch(name, self.appid, self.currency)
            except Exception as e:
                # 429/rede: NÃO descarta o valor bom; tira da fila e recua.
                # _needs_refresh continua True, então o próximo request() re-tenta.
                is_429 = getattr(e, "code", None) == 429
                with self._lock:
                    self._queued.discard(name)
                    self._record(name, "429" if is_429 else "error")
                if is_429:
                    consec_429 += 1
                    if consec_429 >= self.max_429:
                        # circuit breaker: para tudo e pausa. Recuo progressivo —
                        # se o IP segue bloqueado, cada pausa dobra (até o teto),
                        # pra não insistir de 15 em 15min num IP punido por horas.
                        with self._lock:
                            pause = min(self.cooldown * (2 ** self._breaker_trips),
                                        self.max_cooldown)
                            self._pause_until = self._now() + pause
                            self._breaker_trips += 1
                        return
                    time.sleep(self.backoff)
                else:
                    time.sleep(self.interval)
                continue
            consec_429 = 0
            with self._lock:
                self._breaker_trips = 0   # respondeu (IP ok) -> zera o recuo
                if res.get("success") and res.get("cents") is not None:
                    self._data[name] = {**res, "ts": self._now()}      # preço bom
                    self._record(name, "ok", res.get("cents"))
                elif name not in self._data:
                    self._data[name] = {"success": False, "ts": self._now()}
                    self._record(name, "no_listing")
                else:
                    self._data[name]["ts"] = self._now()               # mantém valor, adia
                    self._record(name, "no_listing")
                self._queued.discard(name)
                self._save()
            time.sleep(self.interval)


def _iter_owned(gd, save):
    """Itens do inventário/stash/trading (ordem nativa, igual cubo) ->
    (uid, item, en_name, hash_name, marketable). hash_name só nos negociáveis."""
    by_uid = {it.get("UniqueId"): it for it in save.get("itemSaveDatas") or []}
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
            yield uid, item, en, hn, mk


def owned_market_names(gd, save):
    """Nomes de mercado dos negociáveis que o jogador tem (p/ aquecer o cache)."""
    return [hn for _, _, _, hn, mk in _iter_owned(gd, save) if hn]


def market_panel(gd, save, cache, lang="en"):
    """Itens do inventário/stash/trading com valor de Steam (BRL)."""
    lang_code = {"pt": "pt-BR", "en": "en-US"}.get(lang, "en-US")
    keep = 1 - STEAM_FEE
    owned = list(_iter_owned(gd, save))
    cache.request([hn for _, _, _, hn, _ in owned if hn])   # dispara buscas que faltam
    pending_any = any(hn and cache.get(hn) is None for _, _, _, hn, mk in owned if mk)

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
            "receive": round(listed * keep) if priced else None,
            "matched": priced,
            "pending": bool(mk and p is None),    # ainda não buscado
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
    result = {
        "appid": STEAM_APPID,
        "feePct": round(STEAM_FEE * 100),
        "cooldownHours": TRADESHIP_COOLDOWN_HOURS,
        "loading": pending_any,
        "containers": containers,
    }
    status_fn = getattr(cache, "status", None)
    if callable(status_fn):
        result["debug"] = status_fn()
    return result
