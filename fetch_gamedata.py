#!/usr/bin/env python3
"""
Baixa as tabelas de dados do jogo de taskbarhero.wiki para gamedata/.

A wiki expoe o banco de dados completo do jogo como JSON estatico em
https://taskbarhero.wiki/data/t/<tabela>.json (indice em /data/catalog.json).
Baixamos so as tabelas que o simulador usa, uma vez, e guardamos local.

Uso:
    python fetch_gamedata.py            # baixa o que falta
    python fetch_gamedata.py --force    # rebaixa tudo (apos update do jogo)
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://taskbarhero.wiki/data/t/{}.json"
OUT_DIR = Path(__file__).parent / "gamedata"

# Tabelas que o simulador precisa (de /data/catalog.json)
TABLES = [
    # combate
    "heroes", "monsters", "skills", "skill_levels",
    "passive_skills", "attributes", "attribute_groups",
    "buffs", "buff_groups", "status_effects",
    # itens
    "gear", "gear_types", "grades", "stat_mods",
    "item_level_scales", "item_type_scales", "gear_type_scales",
    # progressao
    "runes", "rune_levels", "stages", "stage_levels",
    "levels", "offline_rewards",
    # cubo / alquimia (curva de nivel do cubo)
    "cube_levels",
    # colecao
    "pets", "pet_stats",
]

# Tabelas que vivem fora de /data/t/ (URLs completas)
EXTRA = {
    "items": "https://taskbarhero.wiki/data/items.json",
    "items_detail": "https://taskbarhero.wiki/data/items_detail.json",
    "stat_strings": "https://taskbarhero.wiki/data/stat_strings.json",
}

# Icones das runas (PNG da wiki, fan-made/comunidade) -> gamedata/icons/runes/
RUNE_ICON_URL = "https://taskbarhero.wiki/game/runes/{}.png"
RUNES_PAGE_URL = "https://taskbarhero.wiki/runes"


def fetch_rune_layout(out_dir: Path, force: bool = False):
    """Extrai as posicoes (x,y) da arvore de runas da pagina /runes da wiki.

    A pagina embute um JSON com {key, x, y, ...} por runa — o MESMO layout do
    mapa interativo do site, pra nossa arvore ficar identica.
    """
    import re
    dest = out_dir / "rune_layout.json"
    if dest.exists() and not force:
        return
    html = fetch(RUNES_PAGE_URL).decode("utf-8", "replace").replace('\\"', '"')
    pairs = re.findall(r'\{"key": (\d+), "x": (-?[\d.]+), "y": (-?[\d.]+)', html)
    if len(pairs) < 100:
        raise RuntimeError(f"layout de runas suspeito ({len(pairs)} nos)")
    m = re.search(r'"bounds": \{"minX": (-?[\d.]+), "maxX": (-?[\d.]+), '
                  r'"minY": (-?[\d.]+), "maxY": (-?[\d.]+)\}', html)
    out = {
        "source": RUNES_PAGE_URL,
        "bounds": (dict(zip(("minX", "maxX", "minY", "maxY"),
                            map(float, m.groups()))) if m else None),
        "positions": {k: {"x": float(x), "y": float(y)} for k, x, y in pairs},
    }
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok]   rune_layout: {len(pairs)} posicoes extraidas da wiki")


def fetch_rune_icons(out_dir: Path, force: bool = False):
    """Baixa o icone de cada runa (39 IconPaths distintos)."""
    runes_file = out_dir / "runes.json"
    if not runes_file.exists():
        print("[aviso] runes.json ainda nao baixado; pulando icones", file=sys.stderr)
        return 0, []
    icons_dir = out_dir / "icons" / "runes"
    icons_dir.mkdir(parents=True, exist_ok=True)
    runes = json.loads(runes_file.read_text(encoding="utf-8-sig"))
    paths = sorted({r.get("IconPath") for r in runes if r.get("IconPath")})
    ok, failed = 0, []
    for p in paths:
        dest = icons_dir / f"{p}.png"
        if dest.exists() and not force:
            continue
        try:
            dest.write_bytes(fetch(RUNE_ICON_URL.format(p)))
            ok += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"[erro] icone {p}: {e}", file=sys.stderr)
            failed.append(p)
    if ok:
        print(f"[ok]   icones de runas: {ok} baixados em {icons_dir}")
    return ok, failed

# O site bloqueia user-agents nao-navegador (403)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="rebaixa mesmo se ja existir")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    ok, skipped, failed = 0, 0, []
    downloads = [(t, BASE.format(t)) for t in TABLES] + list(EXTRA.items())
    for table, url in downloads:
        dest = OUT_DIR / f"{table}.json"
        if dest.exists() and not args.force:
            skipped += 1
            continue
        try:
            raw = fetch(url)
            json.loads(raw.decode("utf-8-sig"))  # valida antes de gravar
            dest.write_bytes(raw)
            print(f"[ok]   {table:<22} {len(raw)/1024:8.1f} kB")
            ok += 1
            time.sleep(0.3)  # educacao com o servidor
        except Exception as e:
            print(f"[erro] {table}: {e}", file=sys.stderr)
            failed.append(table)

    _, icon_failed = fetch_rune_icons(OUT_DIR, force=args.force)
    failed += icon_failed
    try:
        fetch_rune_layout(OUT_DIR, force=args.force)
    except Exception as e:
        print(f"[erro] rune_layout: {e}", file=sys.stderr)
        failed.append("rune_layout")

    print(f"\n{ok} baixadas, {skipped} ja existiam, {len(failed)} falharam")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
