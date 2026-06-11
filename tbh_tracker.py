#!/usr/bin/env python3
"""
TBH: Task Bar Hero - Live Save Tracker
=======================================

Monitora o SaveFile_Live.es3 do jogo, decripta uma COPIA do arquivo
(nunca o original), parseia o estado atual e mostra, em tempo (quase) real:

  - estado do time (heroi, nivel, exp)
  - gold atual e taxa de gold/hora medida entre saves
  - exp/hora por heroi medida entre saves
  - ranking de estagios por gold/HP e exp/HP (dado do jogo)

Tudo 100% local e passivo: o script SO LE o save. O jogo nunca sabe
que ele existe, e o arquivo original jamais e aberto em modo escrita.
Zero risco de ban (jogo single-player, sem anticheat de qualquer forma).

Abordagem comprovada: o projeto open-source 'tbh-copilot' faz o mesmo
(le o save ao vivo no navegador).

Uso:
    python tbh_tracker.py                 # auto-detecta o caminho padrao do save
    python tbh_tracker.py --save C:\\caminho\\SaveFile_Live.es3
    python tbh_tracker.py --once          # le uma vez e sai (sem ficar vigiando)
    python tbh_tracker.py --interval 2    # checa mtime a cada 2s (padrao 3s)

Requer:  pip install cryptography
         (watchdog e opcional; sem ele, usa polling de mtime)
"""

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ---------------------------------------------------------------------------
# Constantes do formato Easy Save 3 usado pelo TBH
# ---------------------------------------------------------------------------
# A senha e fixa no jogo. Recuperada do bundle do tbh-copilot, onde o save e
# decriptado no navegador com Web Crypto (PBKDF2-SHA1, 100 iters, AES-128-CBC).
ES3_PASSWORD = b"emuMqG3bLYJ938ZDCfieWJ"
PBKDF2_ITERS = 100
KEY_LEN = 16  # AES-128

GOLD_CURRENCY_KEY = 100001  # chave da moeda 'gold' em currenySaveDatas
TICKS_PER_HOUR = 3.6e10     # .NET ticks (100 ns) numa hora

# Caminho padrao do save no Windows
DEFAULT_SAVE = Path(
    os.path.expandvars(
        r"%USERPROFILE%\AppData\LocalLow\TesseractStudio\TaskbarHero\SaveFile_Live.es3"
    )
)

# ---------------------------------------------------------------------------
# Decriptacao
# ---------------------------------------------------------------------------
def decrypt_es3(raw: bytes) -> bytes:
    """Decripta os bytes de um arquivo .es3 e retorna o JSON em bytes.

    Layout: [IV de 16 bytes][ciphertext AES-128-CBC]. A chave vem de
    PBKDF2(senha, salt=IV, 100 iters, SHA1). Depois remove padding PKCS7;
    se o resultado comecar com o magic GZip (1f 8b), descomprime.
    """
    iv, ct = raw[:16], raw[16:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=KEY_LEN, salt=iv,
                     iterations=PBKDF2_ITERS)
    key = kdf.derive(ES3_PASSWORD)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    pt = decryptor.update(ct) + decryptor.finalize()

    # remove padding PKCS7
    pad = pt[-1]
    if not (1 <= pad <= 16) or pt[-pad:] != bytes([pad]) * pad:
        raise ValueError("padding PKCS7 invalido - arquivo truncado ou senha errada")
    pt = pt[:-pad]

    if pt[:2] == b"\x1f\x8b":  # magic GZip
        pt = gzip.decompress(pt)
    return pt


def safe_copy_and_decrypt(save_path: Path) -> dict:
    """Copia o save para um temp (leitura compartilhada), decripta e parseia.

    Nunca abre o original em modo escrita. Se a copia pegar o arquivo no meio
    de uma gravacao do jogo, a decriptacao levanta ValueError e o chamador
    deve simplesmente tentar de novo mais tarde.
    """
    with tempfile.NamedTemporaryFile(suffix=".es3", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        # shutil.copy abre o original em modo leitura compartilhada
        shutil.copy2(save_path, tmp_path)
        raw = tmp_path.read_bytes()
        plain = decrypt_es3(raw)
        outer = json.loads(plain.decode("utf-8-sig"))
        inner = json.loads(outer["PlayerSaveData"]["value"])
        return inner
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Parsing do estado
# ---------------------------------------------------------------------------
HERO_NAMES = {
    101: "Knight", 201: "Ranger", 301: "Sorcerer",
    401: "Priest", 501: "Hunter", 601: "Slayer",
}


def parse_state(inner: dict) -> dict:
    cs = inner["commonSaveData"]
    gold = 0
    for cur in inner.get("currenySaveDatas", []):
        if cur.get("Key") == GOLD_CURRENCY_KEY:
            gold = cur.get("Quantity", 0)
            break

    heroes = []
    for h in inner["heroSaveDatas"]:
        if not h.get("IsUnLock"):
            continue
        heroes.append({
            "key": h["heroKey"],
            "name": HERO_NAMES.get(h["heroKey"], str(h["heroKey"])),
            "level": h["HeroLevel"],
            "exp": h["HeroExp"],
            "allocated": h["AllocatedHeroAbilityPoint"],
            "unspent": h["HeroLevel"] - h["AllocatedHeroAbilityPoint"],
        })

    # contadores agregados: Type 15/SubKey 0 = total de clears de estagio,
    # Type 0/SubKey 0 = total de monstros mortos (usados para medir o tempo
    # exato por run entre dois saves)
    agg = {(a.get("Type"), a.get("SubKey")): a.get("Value")
           for a in inner.get("aggregateSaveDatas") or []}

    return {
        "version": cs["version"],
        "lastSavedTime": cs["lastSavedTime"],   # .NET ticks
        "playTime": cs["playTime"],             # segundos
        "gold": gold,
        "currentStage": cs["currentStageKey"],
        "maxStage": cs["maxCompletedStage"],
        "arranged": cs["arrangedHeroKey"],
        "heroes": heroes,
        "totalClears": agg.get((15, 0)),
        "totalKills": agg.get((0, 0)),
    }


# ---------------------------------------------------------------------------
# Calculo de taxas (entre dois snapshots)
# ---------------------------------------------------------------------------
def compute_rates(prev: dict, cur: dict) -> dict:
    """Gold/hora e exp/hora medidos entre dois snapshots reais do save.

    Usa lastSavedTime (ticks) como relogio. Trata os casos:
      - gold caiu  -> voce gastou; ignora (rate None)
      - exp caiu   -> heroi upou (exp reseta); ignora aquele heroi
    """
    dt_hours = (cur["lastSavedTime"] - prev["lastSavedTime"]) / TICKS_PER_HOUR
    if dt_hours <= 0:
        return {"dt_hours": 0, "gold_per_hour": None, "exp_per_hour": {}}

    dg = cur["gold"] - prev["gold"]
    gold_rate = dg / dt_hours if dg >= 0 else None  # negativo = gastou

    exp_rate = {}
    prev_heroes = {h["key"]: h for h in prev["heroes"]}
    for h in cur["heroes"]:
        ph = prev_heroes.get(h["key"])
        if not ph:
            continue
        de = h["exp"] - ph["exp"]
        if de >= 0:  # se negativo, upou de nivel; pula
            exp_rate[h["name"]] = de / dt_hours

    return {"dt_hours": dt_hours, "gold_per_hour": gold_rate, "exp_per_hour": exp_rate}


# ---------------------------------------------------------------------------
# Ranking de estagios (a partir do gamedata exportado)
# ---------------------------------------------------------------------------
def load_gamedata(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rank_stages(gamedata: dict, max_stage: int, top: int = 8):
    """Ranqueia estagios DESBLOQUEADOS por gold/HP e exp/HP.

    IMPORTANTE sobre desbloqueio: as chaves dos estagios codificam a
    dificuldade no primeiro digito (1xxx=Normal, 2xxx=Nightmare,
    3xxx=Hell, 4xxx=Torment). Por isso NAO da pra filtrar com
    'int(chave) <= maxCompletedStage' - isso misturaria dificuldades.
    A ordem real de progressao esta em gamedata['stageOrder']; um estagio
    esta desbloqueado se aparece nessa lista ate (inclusive) o maxStage.

    gold/HP e exp/HP sao independentes do seu DPS (quanto rende por ponto de
    vida do inimigo). Para gold/HORA real, multiplique pelo seu DPS efetivo
    (DPS * goldPerHP = gold/seg). O DPS sai do engine; aqui ficamos no
    indicador puro de eficiencia do mapa.
    """
    order = gamedata.get("stageOrder") or []
    if order:
        try:
            cutoff = order.index(max_stage)
        except ValueError:
            cutoff = len(order) - 1
        unlocked_keys = {str(k) for k in order[:cutoff + 1]}
    else:
        unlocked_keys = set(gamedata["stages"].keys())

    unlocked = []
    for k, s in gamedata["stages"].items():
        if k in unlocked_keys and s.get("goldPerHP") is not None:
            unlocked.append((k, s))

    by_gold = sorted(unlocked, key=lambda kv: kv[1]["goldPerHP"], reverse=True)[:top]
    by_exp = sorted(unlocked, key=lambda kv: kv[1]["expPerHP"], reverse=True)[:top]
    return by_gold, by_exp


# ---------------------------------------------------------------------------
# Apresentacao
# ---------------------------------------------------------------------------
def fmt(n):
    if n is None:
        return "-"
    n = round(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def render(state, rates, gamedata):
    lines = []
    lines.append("=" * 60)
    lines.append(f"TBH Tracker  |  v{state['version']}  |  playtime {state['playTime']/3600:.1f}h")
    lines.append(f"Gold: {fmt(state['gold'])}   Estagio atual: {state['currentStage']}   Max: {state['maxStage']}")
    lines.append("-" * 60)
    lines.append("Time:")
    for h in state["heroes"]:
        flag = "  <-- arrumado" if h["key"] in state["arranged"] else ""
        unspent = f"  [{h['unspent']} ponto(s) livre!]" if h["unspent"] > 0 else ""
        lines.append(f"  {h['name']:<9} Lv {h['level']:<3} exp {fmt(h['exp'])}{unspent}{flag}")

    if rates and rates["dt_hours"] > 0:
        lines.append("-" * 60)
        lines.append(f"Taxas (medidas em {rates['dt_hours']:.2f}h reais entre saves):")
        lines.append(f"  Gold/hora: {fmt(rates['gold_per_hour'])}")
        for name, r in rates["exp_per_hour"].items():
            lines.append(f"  Exp/hora {name}: {fmt(r)}")

    if gamedata:
        by_gold, by_exp = rank_stages(gamedata, state["maxStage"])
        lines.append("-" * 60)
        lines.append("Melhores estagios desbloqueados (gold/HP):")
        for k, s in by_gold:
            lines.append(f"  {s['label']:<5} {s['diff'][:4]:<4} {s['name'][:16]:<16} gold/HP {s['goldPerHP']:.4f}  (lvl {s['lvl']})")
        lines.append("Melhores estagios desbloqueados (exp/HP):")
        for k, s in by_exp:
            lines.append(f"  {s['label']:<5} {s['diff'][:4]:<4} {s['name'][:16]:<16} exp/HP {s['expPerHP']:.4f}  (lvl {s['lvl']})")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="TBH live save tracker (somente leitura)")
    ap.add_argument("--save", type=Path, default=DEFAULT_SAVE,
                    help="caminho do SaveFile_Live.es3")
    ap.add_argument("--gamedata", type=Path,
                    default=Path(__file__).with_name("tbh_gamedata.json"),
                    help="caminho do tbh_gamedata.json")
    ap.add_argument("--interval", type=float, default=3.0,
                    help="segundos entre checagens de mtime")
    ap.add_argument("--debounce", type=float, default=1.0,
                    help="segundos a esperar apos detectar mudanca (evita ler save no meio da gravacao)")
    ap.add_argument("--once", action="store_true", help="le uma vez e sai")
    args = ap.parse_args()

    if not args.save.exists():
        print(f"[erro] save nao encontrado: {args.save}", file=sys.stderr)
        print("       passe o caminho com --save", file=sys.stderr)
        sys.exit(1)
    gamedata = None
    if args.gamedata.exists():
        gamedata = load_gamedata(args.gamedata)
    else:
        print(f"[aviso] gamedata nao encontrado ({args.gamedata}); "
              "ranking de estagios desativado", file=sys.stderr)

    def read_once(prev_state):
        try:
            inner = safe_copy_and_decrypt(args.save)
        except (ValueError, OSError) as e:
            # arquivo truncado (gravacao em andamento) ou lock momentaneo: tenta depois
            print(f"[aviso] leitura falhou ({e}); tentando de novo no proximo ciclo")
            return prev_state
        state = parse_state(inner)
        rates = compute_rates(prev_state, state) if prev_state else None
        print(render(state, rates, gamedata))
        return state

    state = read_once(None)
    if args.once:
        return

    last_mtime = args.save.stat().st_mtime
    print(f"\n[vigiando] {args.save}  (Ctrl+C para sair)\n")
    try:
        while True:
            time.sleep(args.interval)
            try:
                m = args.save.stat().st_mtime
            except OSError:
                continue
            if m != last_mtime:
                last_mtime = m
                time.sleep(args.debounce)  # deixa o jogo terminar de gravar
                state = read_once(state)
    except KeyboardInterrupt:
        print("\n[saindo]")


if __name__ == "__main__":
    main()
