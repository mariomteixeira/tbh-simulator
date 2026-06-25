import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steam_market as sm

N = sm.normalize_name


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
    assert rows[1]["hash_name"] == "Soulstone - Torment"   # cai pro name
    assert rows[0]["sell_price"] == 24


def test_find_price_exact_and_gear_prefix():
    prices = {
        N("Twilight Amethyst"): {"hash_name": "Twilight Amethyst", "cents": 782, "text": "R$ 7,82"},
        N("Dimensional Boots (Legendary) A"): {"hash_name": "Dimensional Boots (Legendary) A", "cents": 57, "text": "R$ 0,57"},
        N("Dimensional Boots (Legendary) B"): {"hash_name": "Dimensional Boots (Legendary) B", "cents": 40, "text": "R$ 0,40"},
        N("Dimensional Boots (Arcana) A"): {"hash_name": "Dimensional Boots (Arcana) A", "cents": 999, "text": "R$ 9,99"},
    }
    mat = {"name": {"en-US": "Twilight Amethyst"}, "grade": "RARE", "gear": None}
    assert sm.find_price(prices, mat, "Twilight Amethyst")["cents"] == 782
    gear = {"name": {"en-US": "Dimensional Boots"}, "grade": "LEGENDARY", "gear": "BOOTS"}
    assert sm.find_price(prices, gear, "Dimensional Boots")["cents"] == 40   # menor sufixo do grade certo
    none = {"name": {"en-US": "Unknown Thing"}, "grade": "RARE", "gear": None}
    assert sm.find_price(prices, none, "Unknown Thing") is None


def test_market_cache_sweeps_persists_never_discards():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        clock = [1000.0]
        # sweep 1: A,B (página 0) + C (página 2) + linha em USD ignorada
        def fetch1(appid, currency, start, count, country):
            if start == 0:
                return {"total_count": 4, "results": [
                    {"hash_name": "A", "sell_price": 10, "sell_price_text": "R$ 0,10"},
                    {"hash_name": "B", "sell_price": 20, "sell_price_text": "R$ 0,20"},
                    {"hash_name": "Junk", "sell_price": 4, "sell_price_text": "$0.04"}]}
            if start == 3:
                return {"total_count": 4, "results": [
                    {"hash_name": "C", "sell_price": 30, "sell_price_text": "R$ 0,30"}]}
            return {"total_count": 4, "results": []}

        c = sm.MarketCache(path, ttl=100, interval=0, fetch=fetch1, now=lambda: clock[0])
        c.ensure(); c._worker.join(timeout=5)
        p = c.prices()
        assert p[N("A")]["cents"] == 10 and p[N("C")]["cents"] == 30
        assert N("Junk") not in p                  # linha USD ignorada
        assert path.exists()
        assert c._fresh() and not c.loading()

        # sweep 2 (vencido): retorna só A atualizado; B e C NÃO podem sumir
        clock[0] = 1200.0
        def fetch2(appid, currency, start, count, country):
            if start == 0:
                return {"total_count": 1, "results": [
                    {"hash_name": "A", "sell_price": 99, "sell_price_text": "R$ 0,99"}]}
            return {"total_count": 1, "results": []}
        c._fetch = fetch2
        c.ensure(); c._worker.join(timeout=5)
        p = c.prices()
        assert p[N("A")]["cents"] == 99            # atualizado
        assert N("B") in p and N("C") in p         # preço conhecido nunca some


def test_market_cache_fresh_skips_sweep():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        calls = [0]
        def fetch(appid, currency, start, count, country):
            calls[0] += 1
            return {"total_count": 1, "results": [
                {"hash_name": "A", "sell_price": 1, "sell_price_text": "R$ 0,01"}]} if start == 0 else {"results": []}
        c = sm.MarketCache(path, ttl=1000, interval=0, fetch=fetch, now=lambda: 5000.0)
        c.ensure(); c._worker.join(timeout=5)
        n = calls[0]
        c.ensure()                                  # fresco -> não re-busca
        assert c._worker is None or not c._worker.is_alive()
        assert calls[0] == n


class _FakeGD:
    def __init__(self, items): self.items = items


class _FakeCache:
    def __init__(self, prices, loading=False):
        self._p = {N(k): v for k, v in prices.items()}
        self._loading = loading
        self.ensured = False
    def ensure(self): self.ensured = True
    def prices(self): return self._p
    def loading(self): return self._loading


def test_market_panel():
    gd = _FakeGD({
        110001: {"id": 110001, "name": {"en-US": "Minor Ruby", "pt-BR": "Rubi Menor"},
                 "grade": "COMMON", "type": "MATERIAL", "gear": None, "level": None, "marketable": True},
        533171: {"id": 533171, "name": {"en-US": "Dimensional Boots"},
                 "grade": "LEGENDARY", "type": "GEAR", "gear": "BOOTS", "level": 80, "marketable": True},
        110002: {"id": 110002, "name": {"en-US": "Bound"}, "marketable": False},
    })
    save = {
        "itemSaveDatas": [{"UniqueId": "u1", "ItemKey": 110001},
                          {"UniqueId": "g1", "ItemKey": 533171},
                          {"UniqueId": "u2", "ItemKey": 110002}],
        "stashSaveDatas": [{"ItemUniqueId": "u1"}, {"ItemUniqueId": "g1"}, {"ItemUniqueId": "u2"}],
        "inventorySaveDatas": [], "tradingStashSaveDatas": [],
    }
    # Minor Ruby achado; Dimensional Boots ainda não (mercado carregando)
    cache = _FakeCache({"Minor Ruby": {"hash_name": "Minor Ruby", "cents": 90, "text": "R$ 0,90"}},
                       loading=True)
    panel = sm.market_panel(gd, save, cache, lang="pt")

    assert cache.ensured is True
    assert panel["feePct"] == 30 and panel["cooldownHours"] == 8
    stash = next(c for c in panel["containers"] if c["id"] == "stash")
    items = {e["key"]: e for e in stash["slots"] if e}
    assert len(items) == 3                          # todos aparecem (ordem nativa)

    ruby = items[110001]
    assert ruby["name"] == "Rubi Menor" and ruby["marketable"] is True
    assert ruby["listed"] == 90 and ruby["receive"] == 63
    assert ruby["matched"] is True and ruby["pending"] is False

    boots = items[533171]
    assert boots["matched"] is False and boots["pending"] is True   # carregando

    bound = items[110002]
    assert bound["marketable"] is False
    assert bound["matched"] is False and bound["pending"] is False and bound["listed"] is None

    assert stash["filled"] == 3 and stash["tradable"] == 2
    assert stash["matched"] == 1 and stash["pending"] == 1 and stash["sumReceive"] == 63


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("ALL PASS")
