import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steam_market as sm


def test_normalize_name():
    assert sm.normalize_name("  Soulstone -  Torment ") == "soulstone - torment"
    assert sm.normalize_name(None) == ""


def test_parse_price_brl():
    assert sm.parse_price_brl("R$ 0,87") == 87
    assert sm.parse_price_brl("R$ 2,26") == 226
    assert sm.parse_price_brl("R$ 1.234,56") == 123456
    assert sm.parse_price_brl(None) is None
    assert sm.parse_price_brl("--") is None


def test_market_hash_name():
    gear = {"name": {"en-US": "Dimensional Shield"}, "grade": "ARCANA", "gear": "SHIELD"}
    assert sm.market_hash_name(gear) == "Dimensional Shield (Arcana) A"
    legendary = {"name": {"en-US": "Dimensional Boots"}, "grade": "LEGENDARY", "gear": "BOOTS"}
    assert sm.market_hash_name(legendary) == "Dimensional Boots (Legendary) A"
    mat = {"name": {"en-US": "Twilight Amethyst"}, "grade": "RARE", "gear": None}
    assert sm.market_hash_name(mat) == "Twilight Amethyst"


def test_price_cache_fetches_and_persists():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        calls = []
        def fetch(name, appid, currency):
            calls.append(name)
            return {"success": True, "cents": 226, "median_cents": 210, "volume": "9"}
        c = sm.PriceCache(path, ttl=100, interval=0, fetch=fetch, now=lambda: 1000.0)
        assert c.get("X") is None
        c.request(["X"]); c._worker.join(timeout=5)
        e = c.get("X")
        assert e and e["cents"] == 226
        assert calls == ["X"] and path.exists()
        c.request(["X"])                              # fresco -> não re-busca
        if c._worker and c._worker.is_alive():
            c._worker.join(timeout=5)
        assert calls == ["X"]


def test_price_cache_never_discards_on_429():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        clock = [1000.0]
        def good(name, appid, currency):
            return {"success": True, "cents": 226, "median_cents": 210, "volume": "9"}
        c = sm.PriceCache(path, ttl=100, interval=0, backoff=0, fetch=good, now=lambda: clock[0])
        c.request(["X"]); c._worker.join(timeout=5)
        assert c.get("X")["cents"] == 226

        # vence e a próxima busca toma 429 -> valor bom NÃO pode sumir
        clock[0] = 2000.0
        class _429(Exception):
            code = 429
        def boom(name, appid, currency):
            raise _429("429")
        c._fetch = boom
        c.request(["X"]);
        if c._worker:
            c._worker.join(timeout=5)
        assert c.get("X")["cents"] == 226            # preço bom preservado


def test_price_cache_circuit_breaker_pauses_on_repeated_429():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        clock = [1000.0]
        class _429(Exception):
            code = 429
        def boom(name, appid, currency):
            raise _429("429")
        c = sm.PriceCache(path, interval=0, backoff=0, max_429=3, cooldown=500,
                          fetch=boom, now=lambda: clock[0])
        c.request(["A", "B", "C", "D", "E"])
        if c._worker:
            c._worker.join(timeout=5)
        assert c._pause_until == 1000.0 + 500          # pausou após 3 429s seguidos
        prev = c._worker
        c.request(["A"])                                # durante a pausa: não bate na Steam
        assert c._worker is prev

        clock[0] = 1000.0 + 600                         # passou o cooldown
        c._fetch = lambda n, a, cur: {"success": True, "cents": 50}
        c.request(["A"]); c._worker.join(timeout=5)
        assert c.get("A")["cents"] == 50               # volta a funcionar sozinho


def test_price_cache_no_listing_recorded():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        def nolist(name, appid, currency):
            return {"success": False}
        c = sm.PriceCache(path, ttl=100, interval=0, fetch=nolist, now=lambda: 1000.0)
        c.request(["X"]); c._worker.join(timeout=5)
        e = c.get("X")
        assert e is not None and e.get("success") is False


class _FakeGD:
    def __init__(self, items): self.items = items


class _FakeCache:
    def __init__(self, data):
        self._d = data
        self.requested = []
    def request(self, names): self.requested += list(names)
    def get(self, name):
        e = self._d.get(name)
        return dict(e) if e else None


def test_market_panel():
    gd = _FakeGD({
        110001: {"id": 110001, "name": {"en-US": "Minor Ruby", "pt-BR": "Rubi Menor"},
                 "grade": "COMMON", "type": "MATERIAL", "gear": None, "level": None, "marketable": True},
        533171: {"id": 533171, "name": {"en-US": "Dimensional Shield"},
                 "grade": "ARCANA", "type": "GEAR", "gear": "SHIELD", "level": 80, "marketable": True},
        110002: {"id": 110002, "name": {"en-US": "Bound"}, "marketable": False},
    })
    save = {
        "itemSaveDatas": [{"UniqueId": "u1", "ItemKey": 110001},
                          {"UniqueId": "g1", "ItemKey": 533171},
                          {"UniqueId": "u2", "ItemKey": 110002}],
        "stashSaveDatas": [{"ItemUniqueId": "u1"}, {"ItemUniqueId": "g1"}, {"ItemUniqueId": "u2"}],
        "inventorySaveDatas": [], "tradingStashSaveDatas": [],
    }
    # Minor Ruby precificado; Dimensional Shield ainda não (pending)
    cache = _FakeCache({"Minor Ruby": {"success": True, "cents": 90}})
    panel = sm.market_panel(gd, save, cache, lang="pt")

    assert "Dimensional Shield (Arcana) A" in cache.requested
    assert "Minor Ruby" in cache.requested
    assert "Bound" not in cache.requested
    assert panel["feePct"] == 30 and panel["cooldownHours"] == 8
    stash = next(c for c in panel["containers"] if c["id"] == "stash")
    items = {e["key"]: e for e in stash["slots"] if e}
    assert len(items) == 3

    ruby = items[110001]
    assert ruby["name"] == "Rubi Menor" and ruby["marketable"] is True
    assert ruby["listed"] == 90 and ruby["receive"] == 63
    assert ruby["matched"] is True and ruby["pending"] is False

    shield = items[533171]
    assert shield["hashName"] == "Dimensional Shield (Arcana) A"
    assert shield["matched"] is False and shield["pending"] is True

    bound = items[110002]
    assert bound["marketable"] is False
    assert bound["matched"] is False and bound["pending"] is False and bound["listed"] is None

    assert stash["filled"] == 3 and stash["tradable"] == 2
    assert stash["matched"] == 1 and stash["pending"] == 1 and stash["sumReceive"] == 63


def test_owned_market_names():
    gd = _FakeGD({
        110001: {"id": 110001, "name": {"en-US": "Minor Ruby"}, "grade": "COMMON",
                 "type": "MATERIAL", "gear": None, "marketable": True},
        533171: {"id": 533171, "name": {"en-US": "Dimensional Shield"}, "grade": "ARCANA",
                 "type": "GEAR", "gear": "SHIELD", "level": 80, "marketable": True},
        110002: {"id": 110002, "name": {"en-US": "Bound"}, "marketable": False},
    })
    save = {
        "itemSaveDatas": [{"UniqueId": "u1", "ItemKey": 110001},
                          {"UniqueId": "g1", "ItemKey": 533171},
                          {"UniqueId": "u2", "ItemKey": 110002}],
        "stashSaveDatas": [{"ItemUniqueId": "u1"}, {"ItemUniqueId": "g1"}, {"ItemUniqueId": "u2"}],
        "inventorySaveDatas": [], "tradingStashSaveDatas": [],
    }
    names = sm.owned_market_names(gd, save)
    assert "Minor Ruby" in names
    assert "Dimensional Shield (Arcana) A" in names
    assert "Bound" not in names
    assert len(names) == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("ALL PASS")
