#!/usr/bin/env python3
"""
Validacoes de funcionamento do TBH Copilot (sem framework, so asserts).

    python validate.py            # roda tudo
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

import tbh_tracker as core
from simulator import (GameData, StatBag, simulate, fit_clear_model,
                       fit_factor, make_clear_sample, mitigation, offline_info,
                       project_levels, rune_stats, _crit_factor,
                       _rune_to_hero_stat, T_FIXED, T_WAVE)

ROOT = Path(__file__).parent
PASS, FAIL = 0, []


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"[ok]   {name}")
    else:
        FAIL.append(name)
        print(f"[FAIL] {name}  {detail}")


# ---------------------------------------------------------------- formulas
def t_stacking():
    bag = StatBag()
    bag.put("X", "FLAT", 100)
    bag.put("X", "ADDITIVE", 200)          # +20%
    bag.put("X", "MULTIPLICATIVE", 100)    # x1.1
    out = bag.final()
    check("stacking flat*(1+add/1000)*mult", abs(out["X"] - 100 * 1.2 * 1.1) < 1e-6,
          f"got {out['X']}")


def t_crit():
    f = _crit_factor({"CriticalChance": 500, "CriticalDamage": 2000})
    check("crit 50% chance, 2.0x dano -> 1.5", abs(f - 1.5) < 1e-9, f"got {f}")
    f2 = _crit_factor({"CriticalChance": 5000, "CriticalDamage": 3000})
    check("crit chance clampa em 100%", abs(f2 - 3.0) < 1e-9, f"got {f2}")


def t_mitigation():
    # armadura = limiar (14*lvl+12) com hit 0 -> exatamente 50%
    lvl = 10
    thr = 14 * lvl + 12
    check("armadura no limiar = 50%", abs(mitigation(thr, lvl, 0) - 0.5) < 1e-9)
    check("armadura capa em 75%", mitigation(1e9, 1, 0) == 0.75)
    check("hit grande fura armadura",
          mitigation(200, 10, 10000) < mitigation(200, 10, 0))


def t_rune_mapping():
    check("AllHeroAttackSpeed -> ADDITIVE",
          _rune_to_hero_stat("AllHeroAttackSpeed") == ("AttackSpeed", "ADDITIVE"))
    check("AllHeroAttackDamage -> FLAT",
          _rune_to_hero_stat("AllHeroAttackDamage") == ("AttackDamage", "FLAT"))
    check("AllHeroAttackDamagePercent -> ADDITIVE",
          _rune_to_hero_stat("AllHeroAttackDamagePercent") == ("AttackDamage", "ADDITIVE"))


# ---------------------------------------------------------------- regressao
def t_fit_recovery():
    # gera amostras sinteticas com tWave=4.0 e c=0.8 e confere a recuperacao
    import random
    rng = random.Random(42)
    true_twave, true_c = 4.0, 0.8
    now = time.time()
    samples = []
    for i in range(20):
        dps = 1500 + i * 120
        waves = 8 + (i % 12)
        hp = 30000 + i * 25000
        clear = T_FIXED + true_twave * waves + hp / (true_c * dps)
        clear *= 1 + rng.uniform(-0.05, 0.05)  # 5% de ruido
        samples.append({"ts": now - i * 3600, "stage": 1100 + i, "lvl": 1,
                        "clearSec": clear, "hp": hp, "waves": waves,
                        "partyDps": dps})
    fit = fit_clear_model(samples, now)
    check("regressao recupera tWave (±25%)",
          fit and abs(fit["tWave"] - true_twave) / true_twave < 0.25,
          f"got {fit}")
    check("regressao recupera c (±10%)",
          fit and abs(fit["c"] - true_c) / true_c < 0.10, f"got {fit}")
    check("regressao recupera tFixed (±5s)",
          fit and abs(fit["tFixed"] - T_FIXED) < 5, f"got {fit}")
    check("regressao exige 3+ amostras", fit_clear_model(samples[:2], now) is None)


def t_fit_manual_weight():
    # auto consistente com c=1.0; manual (peso alto) consistente com c=0.5.
    # o c ajustado deve pender forte para o manual.
    now = time.time()

    def gen(c, source, n, stage0):
        out = []
        for i in range(n):
            dps = 1000 + i * 200
            waves = 6 + (i % 8)
            hp = 40000 + i * 30000
            s = {"ts": now, "stage": stage0 + i,
                 "clearSec": T_FIXED + 4.0 * waves + hp / (c * dps),
                 "hp": hp, "waves": waves, "partyDps": dps}
            if source:
                s["source"] = source
            out.append(s)
        return out

    auto = gen(1.0, None, 6, 1100)
    manual = gen(0.5, "manual", 6, 1200)
    fit = fit_clear_model(auto + manual, now)
    check("manual domina: c puxa forte pro manual (<0.65)",
          fit and fit["c"] < 0.65, f"got {fit}")
    check("manual contado no fit", fit and fit.get("manual") == 6, f"got {fit}")
    fit_auto = fit_clear_model(auto, now)
    check("so auto: c ~1.0", fit_auto and abs(fit_auto["c"] - 1.0) < 0.15,
          f"got {fit_auto}")


def t_fit_single_manual():
    # um unico tempo manual ja ancora o c (tWave/T_fixo ficam no default)
    now = time.time()
    dps, waves, hp, c = 2000.0, 10, 200000.0, 0.7
    clear = T_FIXED + T_WAVE * waves + hp / (c * dps)
    s = {"ts": now, "stage": 2109, "clearSec": clear, "hp": hp,
         "waves": waves, "partyDps": dps, "source": "manual"}
    fit = fit_clear_model([s], now)
    check("1 tempo manual ancora c", fit and abs(fit["c"] - c) < 0.02, f"got {fit}")
    check("1 manual: tWave/tFixo nos defaults",
          fit and fit["tWave"] == T_WAVE and fit["tFixed"] == T_FIXED, f"got {fit}")
    s_auto = {k: v for k, v in s.items() if k != "source"}
    check("1 amostra auto nao ancora (deixa gold/h)",
          fit_clear_model([s_auto], now) is None)


# ---------------------------------------------------------------- jogo real
def t_real_save(gd):
    save = core.safe_copy_and_decrypt(core.DEFAULT_SAVE)
    r = simulate(gd, save, measured={"goldPerSec": 200})
    check("simulate: herois > 0", len(r["heroes"]) > 0)
    check("simulate: statusDps > 0 em todos",
          all(h["statusDps"] > 0 for h in r["heroes"]))
    check("simulate: farm tem linhas", len(r["farm"]["rows"]) > 10)
    check("simulate: bestGold nao e ACTBOSS",
          r["farm"]["bestGold"]["type"] != "ACTBOSS")
    check("simulate: recomendacao so em fase LIMPA (nao a seguinte/travada)",
          r["farm"]["bestGold"]["cleared"] and r["farm"]["bestExp"]["cleared"])
    check("simulate: push so se 'seguro' (ou None)",
          r["farm"]["push"] is None or r["farm"]["push"]["rating"] == "seguro")
    bb = r["farm"]["bestBossBox"]
    check("simulate: rota de bau = fase LIMPA com bau de nivel mais alto",
          bb and bb["cleared"] and bb["bossBoxLvl"] > 0 and bb["bossBox"] and
          bb["bossBoxLvl"] == max(x["bossBoxLvl"] for x in r["farm"]["rows"]
                                  if x["cleared"] and x["type"] != "ACTBOSS"))
    rt = r["runes"]
    check("runas: arvore completa (197 nos)", len(rt["nodes"]) == 197,
          f"got {len(rt['nodes'])}")
    levels = {x["RuneKey"]: x.get("Level") or 0 for x in save["RuneSaveData"]}
    parent = {}
    for rn in gd.runes.values():
        for c in str(rn.get("NextRuneKey") or "").split():
            parent[int(c)] = rn["RuneKey"]
    bad = [n["key"] for n in rt["nodes"]
           if n["unlocked"] and parent.get(n["key"]) is not None
           and levels.get(parent[n["key"]], 0) < n["req"]]
    check("runas: unlock respeita nivel do pai", not bad, f"violacoes: {bad}")
    allrec = rt["recommendations"]["combate"] + rt["recommendations"]["farm"]
    check("runas: recomendacoes com custo e ganho positivos",
          all(x["cost"] > 0 and x["pct"] > 0 for x in allrec))
    check("simulate: coach tem texto", len(r["coach"]) >= 3)
    check("simulate: offline park so em fase limpa",
          r["offline"]["park"] is None or any(
              row["key"] == r["offline"]["park"]["key"] and (row["cleared"] or row["current"])
              for row in r["farm"]["rows"]))
    ups = [s for g in r["gear"] for s in g["slots"] if s["upgrade"]]
    check("gear advisor: estrutura ok",
          all(s["upgrade"]["dPower"] > 0 for s in ups))
    return save


def t_sample_derivation(gd, save):
    econ = gd.stage_econ(2109)
    runes = rune_stats(gd, save)
    from simulator import _gold_per_clear
    gpc = _gold_per_clear(gd, runes, econ)
    # fallback por gold (saves sem contador)
    anchor = {"currentStage": 2109, "lastSavedTime": 0, "gold": 0}
    cur = {"currentStage": 2109, "lastSavedTime": int(120 * 1e7),
           "gold": gpc * 2}  # 2 clears em 120s
    s, _, _ = make_clear_sample(gd, save, anchor, cur, party_dps=2000)
    check("amostra(gold): clearSec = 60s para 2 clears em 120s",
          s and abs(s["clearSec"] - 60) < 0.5 and s["method"] == "gold", f"got {s}")
    s2, keep2, _ = make_clear_sample(gd, save, anchor, dict(cur, gold=-5), 2000)
    check("amostra(gold): gold gasto -> janela invalida (re-ancora)",
          s2 is None and keep2 is False)

    # metodo exato pelo contador de clears + validacao por kills
    kills = econ["kills"]
    anchor3 = dict(anchor, totalClears=100, totalKills=50000)
    cur3 = dict(cur, gold=0, totalClears=103,
                totalKills=50000 + round(3 * kills))
    s3, _, _ = make_clear_sample(gd, save, anchor3, cur3, 2000)
    check("amostra(contador): 3 clears em 120s -> 40s, metodo exato",
          s3 and abs(s3["clearSec"] - 40) < 0.5 and s3["method"] == "clears",
          f"got {s3}")
    # run longa: nenhum clear entre saves -> janela ACUMULA (keep_anchor)
    cur_acc = dict(cur, gold=0, totalClears=100,
                   totalKills=50000 + round(0.4 * kills))
    s_acc, keep_acc, _ = make_clear_sample(gd, save, anchor3, cur_acc, 2000)
    check("amostra(contador): run mais longa que o intervalo de save -> acumula",
          s_acc is None and keep_acc is True)
    # janela acumulada de 300s fecha quando o clear completa
    cur_close = dict(cur, lastSavedTime=int(300 * 1e7), gold=0,
                     totalClears=101, totalKills=50000 + round(1.3 * kills))
    s_close, _, _ = make_clear_sample(gd, save, anchor3, cur_close, 2000)
    check("amostra(contador): janela de 300s com 1 clear -> 300s/run",
          s_close and abs(s_close["clearSec"] - 300) < 0.5, f"got {s_close}")
    # kills/run observados vao para o info (alimentam o aprendizado por fase)
    s7, _, info7 = make_clear_sample(gd, save, anchor3, cur3, 2000)
    check("amostra(contador): killsPorRun registrado no info",
          s7 and abs(info7["killsPorRun"] - kills) < 1, f"got {info7}")
    # janela curta (<60s) mesmo com clear -> segue acumulando
    cur8 = dict(cur, lastSavedTime=int(40 * 1e7), gold=0, totalClears=101,
                totalKills=50000 + round(kills))
    s8, keep8, _ = make_clear_sample(gd, save, anchor3, cur8, 2000)
    check("amostra(contador): janela <60s com clear -> acumula",
          s8 is None and keep8 is True)
    anchor5 = dict(anchor3, currentStage=2108)
    s5, keep5, _ = make_clear_sample(gd, save, anchor5, cur3, 2000)
    check("amostra: estagio diferente -> re-ancora",
          s5 is None and keep5 is False)
    # relogio por playTime: 90s de playTime / 3 clears = 30s (lastSavedTime nao muda)
    a_pt = dict(anchor3, playTime=1000, lastSavedTime=0)
    c_pt = dict(cur, playTime=1090, lastSavedTime=0, gold=0, totalClears=103,
                totalKills=50000 + round(3 * kills))
    s_pt, _, _ = make_clear_sample(gd, save, a_pt, c_pt, 2000)
    check("amostra: dt usa playTime (90s/3 = 30s)",
          s_pt and abs(s_pt["clearSec"] - 30) < 0.5, f"got {s_pt}")


def t_econ_scale(gd, save):
    # econScale REMOVIDO: usa reward dataminado cru (igual a wiki), ignora kpc
    econ = gd.stage_econ(2109)
    r = simulate(gd, save, stage_stats={"2109": {"kpc": econ["kills"] / 2, "n": 3}})
    row = next((x for x in r["farm"]["rows"] if x["key"] == 2109), None)
    check("econ: sem correcao por kills (scale=1.0)",
          row and abs(row["econScale"] - 1.0) < 1e-9, f"got {row and row['econScale']}")
    check("econ: global = 1.0 (reward cru)",
          abs(r["econScale"]["global"] - 1.0) < 1e-9, f"got {r.get('econScale')}")


def t_fit_factor():
    # curva real medida no jogo (heroi Lv41), delta = nivel_da_fase - nivel_do_heroi:
    # plato 100% em delta [-2,+6]; queda forte abaixo (out-level); queda leve acima.
    check("fit: plato 100% no nivel da fase", abs(fit_factor(41, 41) - 1.0) < 1e-9)
    check("fit: plato cobre ate +6 acima", abs(fit_factor(41, 47) - 1.0) < 1e-9)
    check("fit: ~88% a -5 (fase 5 abaixo)", abs(fit_factor(41, 36) - 0.88) < 0.02)
    check("fit: ~50% a -8", abs(fit_factor(48, 40) - 0.50) < 0.02)
    check("fit: ~16% a -12", abs(fit_factor(41, 29) - 0.16) < 0.02)
    check("fit: ~5% a -16", abs(fit_factor(41, 25) - 0.05) < 0.02)
    check("fit: pune lado alto, ~85% a +10", abs(fit_factor(41, 51) - 0.85) < 0.02)


def t_projection(gd):
    # eps que da exatamente o exp do nivel 50 em 1h
    need = gd.levels[50]
    p = project_levels(gd, 50, 0, need / 3600)
    check("projecao: sobe ~1 nivel na 1a hora",
          p and abs(p["horizons"]["1"] - 51) < 0.05, f"got {p and p['horizons']}")
    # com penalidade: parado numa fase lvl 50 ja estando lvl 56, o ritmo cai
    p2 = project_levels(gd, 56, 0, need / 3600, stage_lvl=50)
    p3 = project_levels(gd, 56, 0, need / 3600)
    check("projecao: penalidade desacelera na mesma fase",
          p2 and p3 and p2["horizons"]["24"] < p3["horizons"]["24"],
          f"com={p2 and p2['horizons']}, sem={p3 and p3['horizons']}")


def t_offline(gd):
    rows = [{"key": 1, "label": "1-1", "tag": "N", "name": "x", "lvl": 40,
             "cleared": True, "current": False}]
    off = offline_info(gd, {"UnlockOfflineReward": 1,
                            "OfflineRewardGoldPercent": 600}, 40, rows)
    # lvl 40: BaseGold 98 * KillCount 2730 * 1.6
    check("offline: gold lvl40 com +60%",
          abs(off["current"]["gold"] - round(98 * 2730 * 1.6)) <= 1,
          f"got {off['current']}")
    check("offline: park escolhido", off["park"] and off["park"]["lvl"] == 40)


# ---------------------------------------------------------------- API viva
def t_api():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8423/api/snapshot",
                                    timeout=5) as r:
            d = json.loads(r.read())
        check("API viva: snapshot completo",
              all(k in d for k in ("status", "state", "sim", "history", "samples")))
        with urllib.request.urlopen("http://127.0.0.1:8423/", timeout=5) as r:
            html = r.read().decode()
        check("API viva: serve o frontend React", "/assets/index" in html)
    except Exception as e:
        check("API viva", False, str(e))


if __name__ == "__main__":
    t_stacking()
    t_crit()
    t_mitigation()
    t_rune_mapping()
    t_fit_recovery()
    t_fit_manual_weight()
    t_fit_single_manual()
    t_fit_factor()
    gd = GameData(ROOT / "gamedata")
    save = t_real_save(gd)
    t_sample_derivation(gd, save)
    t_econ_scale(gd, save)
    t_projection(gd)
    t_offline(gd)
    t_api()
    print(f"\n{PASS} ok, {len(FAIL)} falhas" + (f": {FAIL}" if FAIL else ""))
    sys.exit(1 if FAIL else 0)
