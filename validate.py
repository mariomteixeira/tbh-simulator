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
                       fit_factor, mitigation, offline_info, hero_damage,
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
    # o datamine tem valores string com espaco ("190 "): coage; lixo e ignorado
    bag2 = StatBag()
    bag2.put("Y", "FLAT", "190 ")
    bag2.put("Y", "FLAT", "abc")
    check("stacking: string numerica do datamine vira numero",
          abs(bag2.final()["Y"] - 190) < 1e-9, f"got {bag2.final()}")


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
    check("levelEta: nivel-alvo = atual + 1 (sem off-by-one)",
          all(e["level"] == e["fromLevel"] + 1 for e in r.get("levelEta", [])),
          f'{[(e["fromLevel"], e["level"]) for e in r.get("levelEta", [])]}')
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
    # teto (ceiling): nada acima dele em recomendacao
    ceil = 2102  # NM 1-2, bem abaixo do max do save
    rc = simulate(gd, save, ceiling=ceil)
    order = gd.stage_order
    ci = order.index(ceil)
    f = rc["farm"]
    above = [x for x in (f["bestGold"], f["bestExp"], f["push"],
                         f["bestBossBox"], f["bestNormalBox"])
             if x and order.index(x["key"]) > ci]
    check("ceiling: nenhuma recomendacao acima do teto", not above,
          f"acima: {[x['label'] for x in above]}")
    check("ceiling: linhas acima marcadas beyondCeiling",
          all(x["beyondCeiling"] == (order.index(x["key"]) > ci)
              for x in f["rows"]))

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
    # lvl 40: BaseGold 98 * KillCount 2730 * 1.6 = recompensa POR HORA
    per_h = round(98 * 2730 * 1.6)
    check("offline: gold/h lvl40 com +60%",
          abs(off["current"]["goldPerHour"] - per_h) <= 1,
          f"got {off['current']}")
    check("offline: total 8h = por-hora x cap (x8)",
          abs(off["current"]["gold"] - per_h * off["capHours"]) <= 1,
          f"got {off['current']}")
    check("offline: park escolhido", off["park"] and off["park"]["lvl"] == 40)


# ---------------------------------------------------------------- API viva
def t_api():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8423/api/snapshot",
                                    timeout=5) as r:
            d = json.loads(r.read())
        check("API viva: snapshot completo",
              all(k in d for k in ("status", "state", "sim", "history",
                                   "manualSamples")))
        with urllib.request.urlopen("http://127.0.0.1:8423/", timeout=5) as r:
            html = r.read().decode()
        check("API viva: serve o frontend React", "/assets/index" in html)
    except Exception as e:
        check("API viva", False, str(e))


def t_util_not_damage(gd):
    """Skills de cura/revive/escudo NÃO podem aparecer como dano (Heal, etc.)."""
    from simulator import _is_damage_skill, GameData
    # Heal=40101 (cura, deliv None), Resurrection=40601, Sanctuary=40401 (regen AOE),
    # Aegis Field=10401 (escudo AOE) -> nenhum dá dano
    for sk in (40101, 40601, 40401, 10401):
        row = gd.skills.get(sk)
        check(f"skill {sk} classificada como NÃO-dano", not _is_damage_skill(row),
              f"{(row.get('SkillNameKey_i18n') or {}).get('en-US')}")
    # e um de dano de verdade segue como dano
    check("skill de dano (Fireball 30101) segue dano", _is_damage_skill(gd.skills.get(30101)))
    check("skill de dano (Shield Charge 10201, tem 'shield') segue dano",
          _is_damage_skill(gd.skills.get(10201)))


def t_buff_dps(gd):
    """Skill de BUFF (Surto Veloz = +Vel.Ataque) NÃO pode virar dano direto;
    deve escalar o DPS do ataque básico. Regressão do bug 'X de dano por uso'."""
    hero_save = {"heroKey": 201, "equippedSKillKey": [20401]}  # Ranger + Surto Veloz
    stats = {"AttackDamage": 1000.0, "AttackSpeed": 100.0,
             "CriticalChance": 0.0, "CriticalDamage": 1000.0}
    dmg = hero_damage(gd, {"attributeSaveDatas": []}, hero_save, stats)
    sk_keys = [s["key"] for s in dmg["breakdown"]["skills"]]
    check("buff: nao contado como skill de dano", 20401 not in sk_keys)
    check("buff: skillDps zero (so buff equipado)", dmg["skillDps"] == 0)
    buffs = dmg["breakdown"]["buffs"]
    check("buff: listado em breakdown.buffs", len(buffs) == 1)
    if buffs:
        b = buffs[0]
        check("buff: stat = AttackSpeed", b["statType"] == "AttackSpeed")
        # lv1 = +50% AS -> ataque ativo = 1.5x do base
        check("buff: DPS com buff ativo = base x (1+frac)",
              abs(b["dpsActive"] - dmg["autoDps"] * 1.5) < 1.0,
              f"active {b['dpsActive']} vs {dmg['autoDps']*1.5}")
        check("buff: dpsBuffed inclui a media estimada",
              dmg["dpsBuffed"] >= dmg["dps"])


def t_chaos_resist():
    """AllElementalResistance cobre fogo/gelo/raio, NÃO chaos. Chaos só por
    ChaosResistance. Regressão do bug de resistência."""
    from simulator import hero_ehp
    base = {"MaxHp": 1000.0, "Armor": 0.0}
    fire0 = hero_ehp(base, 1, 0, ["Fire"])
    fire_all = hero_ehp({**base, "AllElementalResistance": 50}, 1, 0, ["Fire"])
    check("AllElementalResistance reduz fogo (EHP sobe)", fire_all > fire0 + 1)
    chaos0 = hero_ehp(base, 1, 0, ["Chaos"])
    chaos_all = hero_ehp({**base, "AllElementalResistance": 50}, 1, 0, ["Chaos"])
    check("AllElementalResistance NÃO cobre chaos", abs(chaos_all - chaos0) < 1e-6)
    chaos_res = hero_ehp({**base, "ChaosResistance": 50}, 1, 0, ["Chaos"])
    check("ChaosResistance reduz chaos (EHP sobe)", chaos_res > chaos0 + 1)


def t_role_power():
    """Peso por papel: tank valoriza +EHP, DPS valoriza +DPS. w=0.5 = sqrt."""
    from simulator import _power, ROLE_WDPS
    d = e = 1000.0
    check("_power(0.5) = sqrt(dps*ehp)", abs(_power(d, e, 0.5) - (d * e) ** 0.5) < 1e-6)
    bt = _power(d, e, ROLE_WDPS["tank"])
    check("tank: +EHP vale mais que +DPS",
          (_power(d, e * 1.2, ROLE_WDPS["tank"]) - bt) >
          (_power(d * 1.2, e, ROLE_WDPS["tank"]) - bt))
    bp = _power(d, e, ROLE_WDPS["dps"])
    check("dps: +DPS vale mais que +EHP",
          (_power(d * 1.2, e, ROLE_WDPS["dps"]) - bp) >
          (_power(d, e * 1.2, ROLE_WDPS["dps"]) - bp))


if __name__ == "__main__":
    t_stacking()
    t_crit()
    t_chaos_resist()
    t_role_power()
    t_mitigation()
    t_rune_mapping()
    t_fit_recovery()
    t_fit_manual_weight()
    t_fit_single_manual()
    t_fit_factor()
    gd = GameData(ROOT / "gamedata")
    t_util_not_damage(gd)
    t_buff_dps(gd)
    save = t_real_save(gd)
    t_econ_scale(gd, save)
    t_projection(gd)
    t_offline(gd)
    t_api()
    print(f"\n{PASS} ok, {len(FAIL)} falhas" + (f": {FAIL}" if FAIL else ""))
    sys.exit(1 if FAIL else 0)
