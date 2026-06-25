import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steam_market as sm


def test_normalize_name():
    assert sm.normalize_name("  Soulstone -  Torment ") == "soulstone - torment"
    assert sm.normalize_name(None) == ""


def test_parse_render_page():
    obj = {"total_count": 2, "results": [
        {"hash_name": "Minor Ruby", "sell_price": 24, "sell_price_text": "R$ 0,24"},
        {"name": "Soulstone - Torment", "sell_price": 90, "sell_price_text": "R$ 0,90"},
    ]}
    rows, total = sm.parse_render_page(obj)
    assert total == 2
    assert rows[0]["hash_name"] == "Minor Ruby"
    assert rows[1]["hash_name"] == "Soulstone - Torment"  # falls back to name
    assert rows[0]["sell_price"] == 24


def test_fetch_all_prices_paginates():
    pages = [
        {"total_count": 3, "results": [
            {"hash_name": "A", "sell_price": 10, "sell_price_text": "R$ 0,10"},
            {"hash_name": "B", "sell_price": 20, "sell_price_text": "R$ 0,20"},
        ]},
        {"total_count": 3, "results": [
            {"hash_name": "C", "sell_price": 30, "sell_price_text": "R$ 0,30"},
        ]},
    ]
    calls = []

    def fake_fetch(appid, currency, start, count):
        calls.append(start)
        return pages[0] if start == 0 else pages[1]

    prices = sm.fetch_all_prices(fetch=fake_fetch)
    assert set(prices.keys()) == {"a", "b", "c"}
    assert prices["c"]["sell_price"] == 30
    assert calls == [0, 2]  # second page starts after 2 rows


def test_cache_ttl_and_stale_fallback():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cache.json"
        clock = [1000.0]
        fetch_count = [0]

        def fake_fetch(appid=sm.STEAM_APPID, currency=sm.CURRENCY_BRL):
            fetch_count[0] += 1
            return {"x": {"hash_name": "X", "sell_price": 5, "sell_price_text": "R$ 0,05"}}

        c = sm.SteamMarketCache(path, ttl=100, fetch=fake_fetch, now=lambda: clock[0])
        assert c.prices()["x"]["sell_price"] == 5      # first fetch
        assert fetch_count[0] == 1
        c.prices()                                      # still fresh -> no refetch
        assert fetch_count[0] == 1
        assert c.meta()["stale"] is False
        assert path.exists()                            # persisted to disk

        clock[0] = 1200.0                               # TTL expired
        def failing_fetch(appid=sm.STEAM_APPID, currency=sm.CURRENCY_BRL):
            raise OSError("steam down")
        c._fetch = failing_fetch
        assert c.prices()["x"]["sell_price"] == 5       # keeps stale cache
        assert c.meta()["stale"] is True


class _FakeCache:
    def __init__(self, prices): self._p = prices
    def prices(self): return self._p
    def meta(self): return {"updatedAt": 1, "currency": 7, "stale": False}


class _FakeGD:
    def __init__(self, items): self.items = items


def test_market_panel():
    gd = _FakeGD({
        110001: {"id": 110001, "name": {"en-US": "Minor Ruby", "pt-BR": "Rubi Menor"},
                 "grade": "COMMON", "type": "MATERIAL", "gear": None,
                 "level": None, "marketable": True},
        110002: {"id": 110002, "name": {"en-US": "Bound Trinket"},
                 "grade": "COMMON", "type": "MATERIAL", "marketable": False},
    })
    save = {
        "itemSaveDatas": [
            {"UniqueId": "u1", "ItemKey": 110001},
            {"UniqueId": "u2", "ItemKey": 110002},
        ],
        "stashSaveDatas": [{"ItemUniqueId": "u1"}, {"ItemUniqueId": "u2"}],
        "inventorySaveDatas": [],
        "tradingStashSaveDatas": [],
    }
    cache = _FakeCache({"minor ruby": {"hash_name": "Minor Ruby",
                                       "sell_price": 90, "sell_price_text": "R$ 0,90"}})

    panel = sm.market_panel(gd, save, cache, lang="pt")
    assert panel["appid"] == 3678970
    assert panel["feePct"] == 30
    assert panel["cooldownHours"] == 8
    stash = next(c for c in panel["containers"] if c["id"] == "stash")
    items = [e for e in stash["slots"] if e]
    assert len(items) == 1                       # non-marketable item excluded
    ruby = items[0]
    assert ruby["name"] == "Rubi Menor"          # display name uses lang=pt
    assert ruby["hashName"] == "Minor Ruby"      # match uses English
    assert ruby["listed"] == 90
    assert ruby["receive"] == 63                 # round(90 * 0.70)
    assert ruby["matched"] is True
    assert stash["sumReceive"] == 63
    assert stash["matched"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("ALL PASS")
