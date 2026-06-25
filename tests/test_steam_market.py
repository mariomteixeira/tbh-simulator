import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steam_market as sm


def test_normalize_name():
    assert sm.normalize_name("  Soulstone -  Torment ") == "soulstone - torment"
    assert sm.normalize_name(None) == ""


def test_parse_price_brl():
    assert sm.parse_price_brl("R$ 0,87") == 87
    assert sm.parse_price_brl("R$ 1.234,56") == 123456
    assert sm.parse_price_brl(None) is None
    assert sm.parse_price_brl("--") is None


def test_market_hash_name():
    gear = {"name": {"en-US": "Dimensional Boots"}, "grade": "LEGENDARY", "gear": "BOOTS"}
    assert sm.market_hash_name(gear) == "Dimensional Boots (Legendary) A"
    arcana = {"name": {"en-US": "Knight Boots"}, "grade": "ARCANA", "gear": "BOOTS"}
    assert sm.market_hash_name(arcana) == "Knight Boots (Arcana) A"
    mat = {"name": {"en-US": "Twilight Amethyst"}, "grade": "RARE", "gear": None}
    assert sm.market_hash_name(mat) == "Twilight Amethyst"


def test_price_cache_fetches_and_caches():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "prices.json"
        calls = []

        def fake_fetch(name, appid, currency):
            calls.append(name)
            return {"success": True, "cents": 87, "text": "R$ 0,87",
                    "median_cents": 71, "volume": "41"}

        c = sm.PriceCache(path, ttl=100, interval=0, fetch=fake_fetch, now=lambda: 1000.0)
        assert c.get("X") is None                 # nada ainda
        c.request(["X"])
        c._worker.join(timeout=5)                 # espera o worker drenar a fila
        e = c.get("X")
        assert e and e["cents"] == 87
        assert calls == ["X"]
        assert path.exists()
        c.request(["X"])                          # fresco -> não re-busca
        if c._worker and c._worker.is_alive():
            c._worker.join(timeout=5)
        assert calls == ["X"]


def test_price_cache_failure_short_ttl():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "prices.json"
        clock = [1000.0]

        def fail(name, appid, currency):
            raise OSError("429")

        c = sm.PriceCache(path, ttl=100, fail_ttl=10, interval=0,
                          fetch=fail, now=lambda: clock[0])
        c.request(["X"]); c._worker.join(timeout=5)
        e = c.get("X")
        assert e is not None and e.get("success") is False   # falha registrada (fresca)
        clock[0] = 1005.0                          # dentro do fail_ttl -> não re-busca
        c.request(["X"])
        assert c._worker is None or not c._worker.is_alive()
        clock[0] = 1020.0                          # passou fail_ttl -> vencida
        assert c.get("X") is None


class _FakeCache:
    def __init__(self, data): self._d = data; self.requested = []
    def request(self, names): self.requested += list(names)
    def get(self, name):
        e = self._d.get(name)
        return dict(e) if e else None


class _FakeGD:
    def __init__(self, items): self.items = items


def test_market_panel_priced_and_pending():
    gd = _FakeGD({
        110001: {"id": 110001, "name": {"en-US": "Minor Ruby", "pt-BR": "Rubi Menor"},
                 "grade": "COMMON", "type": "MATERIAL", "gear": None,
                 "level": None, "marketable": True},
        533171: {"id": 533171, "name": {"en-US": "Dimensional Boots"},
                 "grade": "LEGENDARY", "type": "GEAR", "gear": "BOOTS",
                 "level": 80, "marketable": True},
        110002: {"id": 110002, "name": {"en-US": "Bound"}, "marketable": False},
    })
    save = {
        "itemSaveDatas": [
            {"UniqueId": "u1", "ItemKey": 110001},
            {"UniqueId": "g1", "ItemKey": 533171},
            {"UniqueId": "u2", "ItemKey": 110002},
        ],
        "stashSaveDatas": [{"ItemUniqueId": "u1"}, {"ItemUniqueId": "g1"}, {"ItemUniqueId": "u2"}],
        "inventorySaveDatas": [], "tradingStashSaveDatas": [],
    }
    cache = _FakeCache({"Minor Ruby": {"success": True, "cents": 90, "text": "R$ 0,90"}})
    panel = sm.market_panel(gd, save, cache, lang="pt")

    assert panel["feePct"] == 30 and panel["cooldownHours"] == 8
    assert "Dimensional Boots (Legendary) A" in cache.requested
    assert "Minor Ruby" in cache.requested
    stash = next(c for c in panel["containers"] if c["id"] == "stash")
    items = {e["key"]: e for e in stash["slots"] if e}
    assert len(items) == 2                         # non-marketable excluded

    ruby = items[110001]
    assert ruby["name"] == "Rubi Menor"            # display name em pt
    assert ruby["listed"] == 90 and ruby["receive"] == 63
    assert ruby["matched"] is True and ruby["pending"] is False

    boots = items[533171]
    assert boots["hashName"] == "Dimensional Boots (Legendary) A"
    assert boots["matched"] is False and boots["pending"] is True

    assert stash["matched"] == 1 and stash["pending"] == 1 and stash["sumReceive"] == 63


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("ALL PASS")
