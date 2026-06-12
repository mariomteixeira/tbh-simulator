#!/usr/bin/env python3
"""
Simulador de combate e economia do TBH: Task Bar Hero
=====================================================

Implementacao propria, em Python, baseada em duas fontes:

  1. Dados do jogo: tabelas JSON baixadas de taskbarhero.wiki/data/
     (rode `python fetch_gamedata.py` uma vez). Sao os dados datamineados
     do jogo que a wiki publica: herois, monstros, estagios, gear, runas etc.

  2. Formulas: documentadas em taskbarhero.wiki/mechanics (recuperadas do
     codigo decompilado do jogo e verificadas no binario, segundo a wiki):

       stacking:   final = (base + somaFLAT) * (1 + somaADDITIVE/1000)
                           * prod(1 + MULTIPLICATIVE/1000)
       DPS:        AttackSpeed * AttackDamage * (1 + CritChance*(CritDamage-1))
       armadura:   Red = Armor^2 / (Armor^2 + (14*StageLevel+12)*(Armor+0.4*Dano))
                   cap 75%; so dano fisico
       resistencia: linear, dano * (1 - res/100); sem cap embutido

Unidades (verificadas nas tabelas):
  - AttackSpeed 100 = 1 ataque/seg
  - CriticalChance 25 = 2,5%  (escala /1000)
  - CriticalDamage 1400 = 1,40x (escala /1000)
  - multiplicadores de stage_levels: 100 = 1x (escala /100)
  - multiplicadores de boss nas stages: 1000 = 1x (escala /1000)
  - cooldown de skill: ActivationValue em segundos
  - dano de skill: skill_levels.Value /1000 = multiplicador de AttackDamage

O que e estimativa nossa (nao vem do datamine) esta marcado com [estimativa]
e e absorvido pela calibracao com as taxas medidas entre saves.
"""

import json
import math
import time
from pathlib import Path

PCT = 1000.0          # divisor per-mille usado pelo jogo
STAGE_MULT_DIV = 1000.0   # multiplicadores de nivel da fase sao per-mille (NAO /100):
                          # validado contra o expectedGold/HP/EXP da wiki (era 10x off)

# Multiplicador do ataque basico. Validado empiricamente contra o painel de
# Status do jogo: AD * AS * critF * 1.9 reproduziu o DPS exibido com erro
# zero (Ranger 727.3, Sorcerer 216.8 no save de referencia, 2026-06-11).
BASIC_ATTACK_MULT = 1.9

# [estimativa] modelo de tempo de clear: overhead fixo + overhead por wave
# (andar ate os inimigos) + tempo de matar (HP total / DPS). A calibracao
# com o gold/h medido substitui a escala absoluta quando ha dados.
T_FIXED = 1.0
T_WAVE = 5.0
W_MANUAL = 20.0       # peso de uma amostra manual (cronometrada) na regressao;
                      # ~4x uma janela automatica perfeita (clears saturado em 5)
# [estimativa] quantos monstros batem em voce ao mesmo tempo, para o
# calculo de perigo (uma wave pode ter 13 monstros, mas nem todos alcancam)
MAX_CONCURRENT = 4

DIFF_TAG = {"NORMAL": "N", "NIGHTMARE": "NM", "HELL": "H", "TORMENT": "T"}


def _load(gd_dir: Path, name: str):
    return json.loads((gd_dir / f"{name}.json").read_text(encoding="utf-8-sig"))


def _name(i18n, lang="pt-BR"):
    if not i18n:
        return None
    return i18n.get(lang) or i18n.get("en-US") or next(iter(i18n.values()), None)


class GameData:
    """Indexa as tabelas baixadas da wiki para consulta rapida."""

    def __init__(self, gd_dir: Path):
        self.heroes = {h["HeroKey"]: h for h in _load(gd_dir, "heroes")}
        self.monsters = {m["MonsterKey"]: m for m in _load(gd_dir, "monsters")}
        self.stages = {s["StageKey"]: s for s in _load(gd_dir, "stages")}
        self.stage_mult = {r["StageLevel"]: r for r in _load(gd_dir, "stage_levels")}
        self.levels = {r["Level"]: r["ExpForLevelUp"] for r in _load(gd_dir, "levels")}
        self.attributes = {a["AttributeKey"]: a for a in _load(gd_dir, "attributes")}
        self.attr_groups = {g["AttributeGroupKey"]: g["RequiredAllocatedPoint"]
                            for g in _load(gd_dir, "attribute_groups")}
        self.passives = {p["PassiveSkillKey"]: p for p in _load(gd_dir, "passive_skills")}
        self.skills = {s["SkillKey"]: s for s in _load(gd_dir, "skills")}

        self.skill_levels = {}
        for r in _load(gd_dir, "skill_levels"):
            self.skill_levels.setdefault(r["SkillLevelKey"], {})[r["Level"]] = r["Value"]

        self.items = {i["id"]: i for i in _load(gd_dir, "items")}
        self.gear = {g["GearKey"]: g for g in _load(gd_dir, "gear")}
        self.gear_types = {g["GearType"]: g for g in _load(gd_dir, "gear_types")}
        self.stat_mods = {(m["StatModKey"], m["Tier"]): m
                          for m in _load(gd_dir, "stat_mods")}

        self.runes = {r["RuneKey"]: r for r in _load(gd_dir, "runes")}
        self.rune_levels = {}
        for r in _load(gd_dir, "rune_levels"):
            self.rune_levels.setdefault(r["LevelKey"], {})[r["Level"]] = r

        self.offline_rewards = _load(gd_dir, "offline_rewards")
        self.pets = {p["PetKey"]: p for p in _load(gd_dir, "pets")}
        self.pet_stats = {}
        for r in _load(gd_dir, "pet_stats"):
            self.pet_stats.setdefault(r["PetStatKey"], []).append(r)

        # monstros por estagio: a wiki ja calculou spawnPct e perClear
        self.stage_monsters = {}
        for m in self.monsters.values():
            for e in m.get("stages") or []:
                self.stage_monsters.setdefault(e["key"], []).append((m, e))

        self.stage_order = self._build_stage_order()
        self._econ_cache = {}

    # -- progressao dos estagios -------------------------------------------
    def _build_stage_order(self):
        """Ordem real de progressao seguindo NextStageKey a partir do 1101."""
        nxt = {k: s.get("NextStageKey") for k, s in self.stages.items()}
        targets = {v for v in nxt.values() if v}
        starts = [k for k in self.stages if k not in targets]
        order, seen = [], set()
        for start in sorted(starts):
            k = start
            while k and k in self.stages and k not in seen:
                order.append(k)
                seen.add(k)
                k = nxt.get(k)
        for k in sorted(self.stages):       # sobras fora da cadeia
            if k not in seen:
                order.append(k)
        return order

    def unlocked_stages(self, max_completed: int):
        """Desbloqueados = ate o max concluido + o proximo da cadeia."""
        try:
            cutoff = self.stage_order.index(max_completed) + 1
        except ValueError:
            cutoff = len(self.stage_order) - 1
        return self.stage_order[:cutoff + 1]

    # -- economia de um estagio --------------------------------------------
    def stage_econ(self, key: int):
        """HP, gold, exp e kills totais de um clear completo do estagio."""
        if key in self._econ_cache:
            return self._econ_cache[key]
        s = self.stages.get(key)
        if not s:
            return None
        mult = self.stage_mult.get(s["StageLevel"]) or {}
        mh = mult.get("MonsterHpMultiplier", 100) / STAGE_MULT_DIV
        mg = mult.get("MonsterGoldMultiplier", 100) / STAGE_MULT_DIV
        me = mult.get("MonsterExpMultiplier", 100) / STAGE_MULT_DIV
        ma = mult.get("MonsterAtkDmgMultiplier", 100) / STAGE_MULT_DIV

        hp = gold = exp = kills = 0.0
        n_normal = n_stage_boss = n_act_boss = 0.0
        in_dps = 0.0          # dps medio de UM monstro (ponderado por presenca)
        biggest_hit = 0.0
        elems = set()
        weight = 0.0
        for mon, e in self.stage_monsters.get(key, []):
            n = e.get("perClear") or 0
            if n <= 0:
                continue
            boss = e.get("boss")
            if not boss:
                n_normal += n
            elif s.get("STAGETYPE") == "ACTBOSS":
                n_act_boss += n
            else:
                n_stage_boss += n
            bh = (s.get("BossHpMultiplier") or PCT) / PCT if boss else 1.0
            bg = (s.get("BossGoldMultiplier") or PCT) / PCT if boss else 1.0
            be = (s.get("BossExpMultiplier") or PCT) / PCT if boss else 1.0
            bd = (s.get("BossDamageMultiplier") or PCT) / PCT if boss else 1.0
            hp += (mon.get("MaxLife") or 0) * mh * bh * n
            gold += (mon.get("RewardGold") or 0) * mg * bg * n
            exp += (mon.get("RewardExp") or 0) * me * be * n
            kills += n
            hit = (mon.get("AttackDamage") or 0) * ma * bd
            mdps = hit * (mon.get("AttackSpeed") or 0) / 100.0
            in_dps += mdps * n
            weight += n
            biggest_hit = max(biggest_hit, hit)
            elems.update(mon.get("attackElements") or [])

        econ = {
            "key": key,
            "label": f"{s['Act']}-{s['StageNo']}",
            "type": s.get("STAGETYPE"),
            "diff": s["STAGEDIFFICULITY"],
            "tag": DIFF_TAG.get(s["STAGEDIFFICULITY"], "?"),
            "name": _name(s.get("StageNameKey_i18n")),
            "lvl": s["StageLevel"] or 1,
            "waves": s["WaveAmount"] or 0,
            "hp": hp, "gold": gold, "exp": exp, "kills": kills,
            "nNormal": n_normal, "nStageBoss": n_stage_boss, "nActBoss": n_act_boss,
            "monsterDps": (in_dps / weight) if weight else 0.0,
            "biggestHit": biggest_hit,
            "elements": sorted(elems),
        }
        self._econ_cache[key] = econ
        return econ


# ---------------------------------------------------------------------------
# Coleta e agregacao de stats de heroi
# ---------------------------------------------------------------------------
BASE_STATS = ["AttackDamage", "AttackSpeed", "CastSpeed", "CriticalChance",
              "CriticalDamage", "MaxHp", "Armor", "CooldownReduction",
              "MovementSpeed"]

# stats de runa que afetam o time inteiro -> stat de heroi correspondente.
# AttackSpeed e MoveSpeed sao ADDITIVE mesmo sem sufixo "Percent" (validado:
# com a runa AllHeroAttackSpeed aditiva, o DPS bate exato com o painel de
# Status do jogo; como flat, nao bate).
_RUNE_FLAT = {"AttackDamage", "Armor"}

def _rune_to_hero_stat(stat_type: str):
    if not stat_type.startswith("AllHero"):
        return None
    rest = stat_type[len("AllHero"):]
    if rest.endswith("Percent"):
        return rest[:-len("Percent")], "ADDITIVE"
    if rest == "MoveSpeed":
        rest = "MovementSpeed"
    return rest, "FLAT" if rest in _RUNE_FLAT else "ADDITIVE"


class StatBag:
    """Acumula modificadores e aplica a formula de stacking documentada."""

    def __init__(self):
        self.flat = {}
        self.add = {}
        self.mult = {}

    def put(self, stat, mod, value):
        if not stat or stat == "NONE" or not value:
            return
        if mod == "FLAT":
            self.flat[stat] = self.flat.get(stat, 0.0) + value
        elif mod == "ADDITIVE":
            self.add[stat] = self.add.get(stat, 0.0) + value
        elif mod == "MULTIPLICATIVE":
            self.mult[stat] = self.mult.get(stat, 1.0) * (1 + value / PCT)

    def final(self):
        out = {}
        for stat in set(self.flat) | set(self.add) | set(self.mult):
            base = self.flat.get(stat, 0.0)
            out[stat] = (base * (1 + self.add.get(stat, 0.0) / PCT)
                         * self.mult.get(stat, 1.0))
        return out


def rune_stats(gd: GameData, save: dict):
    """Soma o valor de todos os niveis comprados de cada runa."""
    total = {}
    for rs in save.get("RuneSaveData") or []:
        lv = rs.get("Level") or 0
        if lv <= 0:
            continue
        rune = gd.runes.get(rs.get("RuneKey"))
        if not rune:
            continue
        rows = gd.rune_levels.get(rune["LevelDataKey"]) or {}
        for L in range(1, lv + 1):
            row = rows.get(L)
            if row:
                st = row["STATTYPE"]
                total[st] = total.get(st, 0.0) + (row["Value"] or 0)
    return total


def collect_hero(gd: GameData, save: dict, hero_save: dict, runes: dict,
                 equip_override: list | None = None):
    """Junta base + gear + encantos + passivas + runas num StatBag.

    equip_override: lista de UniqueIds para simular trocas de equipamento
    (usada pelo comparador de gear) sem mexer no save.
    """
    bag = StatBag()
    hero = gd.heroes.get(hero_save["heroKey"]) or {}
    for st in BASE_STATS:
        bag.put(st, "FLAT", hero.get(st) or 0)

    # gear equipado
    item_by_uid = {it["UniqueId"]: it for it in save.get("itemSaveDatas") or []}
    equipped = (equip_override if equip_override is not None
                else hero_save.get("equippedItemIds") or [])
    for uid in equipped:
        if not uid:
            continue
        it = item_by_uid.get(uid)
        if not it:
            continue
        gear = gd.gear.get(it["ItemKey"])
        item = gd.items.get(it["ItemKey"])
        if gear and item:
            gt = gd.gear_types.get(item.get("gear"))
            if gt:
                bag.put(gt.get("BaseStat1_STATTYPE"), gt.get("BaseStat1_MODTYPE"),
                        gear.get("BaseStat1_Value") or 0)
                bag.put(gt.get("BaseStat2_STATTYPE"), gt.get("BaseStat2_MODTYPE"),
                        gear.get("BaseStat2_Value") or 0)
            for i in (1, 2, 3):
                bag.put(gear.get(f"InherentStat{i}_STATTYPE"),
                        gear.get(f"InherentStat{i}_MODTYPE"),
                        gear.get(f"InherentStat{i}_Value") or 0)
        # encantos: o save guarda o valor rolado; tipo vem de stat_mods
        for e in it.get("EnchantData") or []:
            if not e or not e.get("StatModKey"):
                continue
            sm = gd.stat_mods.get((e["StatModKey"], e.get("Tier")))
            if sm:
                bag.put(sm["STATTYPE"], sm["MODTYPE"], e.get("Value") or 0)

    # arvore de atributos (passivas)
    for a in save.get("attributeSaveDatas") or []:
        lv = a.get("Level") or 0
        if lv <= 0:
            continue
        node = gd.attributes.get(a.get("Key"))
        if not node or node["HeroKey"] != hero_save["heroKey"]:
            continue
        if node["ATTRIBUTETYPE"] != "PASSIVESKILL":
            continue
        p = gd.passives.get(node["Value"])
        if p:
            bag.put(p["STATTYPE"], p["MODTYPE"], (p["Value"] or 0) * lv)

    # runas que dao stat para todos os herois
    for st, val in runes.items():
        mapped = _rune_to_hero_stat(st)
        if mapped:
            bag.put(mapped[0], mapped[1], val)

    return bag.final()


# ---------------------------------------------------------------------------
# DPS, mitigacao, EHP
# ---------------------------------------------------------------------------
INC_BY_DELIVERY = {"Melee": "IncreaseMeleeDamage", "Projectile": "IncreaseProjectileDamage",
                   "AOE": "IncreaseAreaOfEffectDamage", "Summon": "IncreaseSummonDamage"}
PCT_BY_ELEMENT = {"Physical": "PhysicalDamagePercent", "Fire": "FireDamagePercent",
                  "Cold": "ColdDamagePercent", "Lightning": "LightningDamagePercent",
                  "Chaos": "ChaosDamagePercent"}


def _crit_factor(stats):
    cc = min((stats.get("CriticalChance") or 0) / PCT, 1.0)
    cd = (stats.get("CriticalDamage") or 0) / PCT
    return 1 + cc * (max(cd, 1.0) - 1)


def _dmg_bonus(stats, delivery, element):
    inc = (stats.get(INC_BY_DELIVERY.get(delivery, ""), 0) or 0) / PCT
    elem = (stats.get(PCT_BY_ELEMENT.get(element, ""), 0) or 0) / PCT
    return (1 + inc) * (1 + elem)


def _skill_level(gd: GameData, save: dict, hero_key: int, skill_key: int):
    lvl = 1
    for a in save.get("attributeSaveDatas") or []:
        node = gd.attributes.get(a.get("Key"))
        if (node and node["HeroKey"] == hero_key
                and node["ATTRIBUTETYPE"] == "ACTIVESKILL"
                and node["Value"] == skill_key):
            lvl += a.get("Level") or 0
    return lvl


def hero_damage(gd: GameData, save: dict, hero_save: dict, stats: dict):
    """DPS de ataque basico + skills de cooldown equipadas."""
    hero = gd.heroes.get(hero_save["heroKey"]) or {}
    ad = stats.get("AttackDamage") or 0
    crit = _crit_factor(stats)
    aps = (stats.get("AttackSpeed") or 0) / 100.0

    base_skill = gd.skills.get(hero.get("SkillKey")) or {}
    delivery = base_skill.get("DamageDeliveryType") or "Melee"
    element = base_skill.get("DamageType") or "Physical"
    base_mult = (base_skill.get("Value") or PCT) / PCT
    # statusDps = o que o painel de Status do jogo mostra (validado exato);
    # o DPS efetivo aplica por cima os bonus de delivery/elemento, que o
    # painel do jogo nao inclui [estimativa: divisor /1000 desses bonus]
    status_dps = ad * aps * crit * base_mult * BASIC_ATTACK_MULT
    auto_bonus = _dmg_bonus(stats, delivery, element)
    auto = status_dps * auto_bonus

    skill = 0.0
    skills_detail = []
    cast = max((stats.get("CastSpeed") or 100) / 100.0, 0.1)
    cdr = min((stats.get("CooldownReduction") or 0) / PCT, 0.75)
    for sk in hero_save.get("equippedSKillKey") or []:
        row = gd.skills.get(sk)
        if not row or row.get("ACTIVATIONTYPE") != "COOLDOWN":
            continue
        cd = row.get("ActivationValue") or 0
        lvl_rows = gd.skill_levels.get(row.get("SkillLevelKey"))
        if not lvl_rows or cd <= 0:
            continue
        lvl = _skill_level(gd, save, hero_save["heroKey"], sk)
        val = lvl_rows.get(lvl) or lvl_rows.get(max(lvl_rows)) or 0
        # delivery pode vir composto ("Projectile, AOE"): usa o primeiro
        sdel = (row.get("DamageDeliveryType") or "").split(",")[0].strip()
        if not sdel or sdel == "None":
            sdel = delivery
        selem = row.get("DamageType") or element
        per_cast = ad * (val / PCT) * crit * _dmg_bonus(stats, sdel, selem)
        # cooldown recarrega mais rapido com Cast Speed (wiki/mechanics);
        # CooldownReduction aplicado por cima [estimativa do cap]
        cd_eff = cd * (1 - cdr) / cast
        dps_i = per_cast / cd_eff
        skill += dps_i
        skills_detail.append({
            "key": sk,
            "name": _name(row.get("SkillNameKey_i18n")) or f"Skill {sk}",
            "level": lvl, "perCast": round(per_cast, 1),
            "cooldownBase": cd, "cooldown": round(cd_eff, 2),
            "dps": round(dps_i, 1), "element": selem, "delivery": sdel,
        })

    return {"statusDps": status_dps, "autoDps": auto, "skillDps": skill,
            "dps": auto + skill, "delivery": delivery, "element": element,
            "breakdown": {
                "auto": {"statusDps": round(status_dps, 1),
                         "bonusMult": round(auto_bonus, 3),
                         "dps": round(auto, 1), "element": element,
                         "delivery": delivery},
                "skills": skills_detail,
            }}


def mitigation(armor: float, stage_level: int, damage: float):
    """Formula exata de armadura da wiki, com pierce de hits grandes."""
    a = max(armor, 0.0)
    thr = 14.0 * max(stage_level, 1) + 12.0
    denom = a * a + thr * (a + 0.4 * max(damage, 0.0))
    red = (a * a) / denom if denom > 0 else 0.0
    return min(red, 0.75)


def hero_ehp(stats: dict, stage_level: int, hit: float, elements):
    """EHP contra um estagio: HP / fracao de dano que passa."""
    hp = stats.get("MaxHp") or 0
    # fisico passa pela armadura; elemental por resistencia linear
    phys_taken = 1 - mitigation(stats.get("Armor") or 0, stage_level, hit)
    takens = []
    for el in elements or ["Physical"]:
        if el == "Physical":
            takens.append(phys_taken)
        else:
            res = (stats.get(f"{el}Resistance") or 0) + (stats.get("AllElementalResistance") or 0)
            takens.append(max(1 - res / 100.0, 0.0) if res >= 0 else 1 + abs(res) / 100.0)
    avg_taken = sum(takens) / len(takens)
    dr = min((stats.get("DamageReduction") or 0) / PCT, 0.9)
    avg_taken *= (1 - dr)
    return hp / max(avg_taken, 0.01)


# ---------------------------------------------------------------------------
# Amostras de clear e calibracao por regressao
# ---------------------------------------------------------------------------
def _gold_per_clear(gd: GameData, runes: dict, econ: dict):
    gold_mult = 1 + runes.get("IncreaseGoldAmount", 0) / PCT
    flat = (runes.get("AdditionalGold", 0) * econ["kills"]
            + runes.get("AdditionalGoldNormalMonster", 0) * econ["nNormal"]
            + runes.get("AdditionalGoldStageBoss", 0) * econ["nStageBoss"]
            + runes.get("AdditionalGoldActBoss", 0) * econ["nActBoss"])
    return econ["gold"] * gold_mult + flat


def make_clear_sample(gd: GameData, save: dict, anchor_state: dict,
                      state: dict, party_dps: float):
    """Deriva uma observacao de tempo de clear de uma JANELA de saves.

    O jogo grava o save com frequencia (~30s) e uma run pode durar varios
    minutos, entao a medicao usa uma janela acumulada: 'anchor' e o save em
    que a janela abriu (entrada no mapa ou ultima amostra emitida) e 'state'
    e o save atual. A janela so fecha quando o contador agregado de clears
    do save (Type 15) avanca - o delta e o numero EXATO de runs completadas.

    O contador de kills (Type 0) valida a janela com folga de uma run
    parcial em cada ponta; se nao bater (saves perdidos misturando mapas),
    a janela e descartada sem contaminar o modelo.

    Retorna (sample|None, keep_anchor, info):
      sample          -> amostra pronta (o chamador re-ancora no save atual)
      None, True      -> janela ainda acumulando (mantem o anchor)
      None, False     -> janela invalida (re-ancora no save atual)
      info            -> dict com os numeros da decisao, para auditoria
    """
    info = {"why": "?"}
    if not anchor_state or not state or party_dps <= 0:
        info["why"] = "estado incompleto"
        return None, False, info
    stage = state.get("currentStage")
    info["stage"] = stage
    if stage != anchor_state.get("currentStage"):
        info["why"] = "trocou de mapa (janela reaberta)"
        return None, False, info
    # tempo da janela: prefere playTime (segundos de jogo; ignora tempo de jogo
    # fechado), cai pro lastSavedTime (.NET ticks) quando playTime nao veio
    pt0, pt1 = anchor_state.get("playTime"), state.get("playTime")
    if pt0 is not None and pt1 is not None:
        dt = pt1 - pt0
    else:
        dt = (state["lastSavedTime"] - anchor_state["lastSavedTime"]) / 1e7
    info["dt"] = round(dt, 1)
    if dt < 15:
        info["why"] = "janela curta, acumulando"
        return None, True, info
    if dt > 7200:
        info["why"] = "janela velha demais (>2h)"
        return None, False, info
    econ = gd.stage_econ(stage)
    if not econ or econ["hp"] <= 0:
        info["why"] = "estagio sem dados"
        return None, False, info

    c0, c1 = anchor_state.get("totalClears"), state.get("totalClears")
    if c0 is not None and c1 is not None:
        dc = c1 - c0
        info["clears"] = dc
        if dc < 1:
            info["why"] = "run em andamento, acumulando"
            return None, True, info
        if dt < 60:
            # janela curta demais para media confiavel: segue acumulando
            info["why"] = "janela curta com clear, acumulando"
            return None, True, info
        # kills observados entram no info para o aprendizado de kills/run
        # empirico (a composicao da wiki se mostrou inflada em varias fases,
        # entao NAO usamos ela como gate - o alinhamento de janela e feito
        # pelo chamador: a 1a janela apos entrar num mapa nunca vira amostra)
        k0, k1 = anchor_state.get("totalKills"), state.get("totalKills")
        if k0 is not None and k1 is not None:
            info["killsWindow"] = k1 - k0
            info["killsPorRun"] = round((k1 - k0) / dc, 1)
            if econ["kills"] > 0:
                info["killsWiki"] = round(econ["kills"])
                info["ratio"] = round((k1 - k0) / (dc * econ["kills"]), 2)
        clears, method = dc, "clears"
    else:
        # fallback para saves sem contador: estima por gold ganho
        dg = state["gold"] - anchor_state["gold"]
        if dg <= 0:
            info["why"] = "gold gasto na janela"
            return None, False, info
        gpc = _gold_per_clear(gd, rune_stats(gd, save), econ)
        if gpc <= 0:
            info["why"] = "estagio sem gold"
            return None, False, info
        clears = dg / gpc
        info["clears"] = round(clears, 2)
        if clears < 1:
            info["why"] = "run em andamento (por gold), acumulando"
            return None, True, info
        method = "gold"

    clear_sec = dt / clears
    if not (2 <= clear_sec <= 7200):
        info["why"] = f"tempo/run fora dos limites ({clear_sec:.0f}s)"
        return None, False, info
    info["why"] = "amostra registrada"
    info["clearSec"] = round(clear_sec, 1)
    return {"ts": time.time(), "stage": stage, "lvl": econ["lvl"],
            "clearSec": round(clear_sec, 2), "clears": round(clears, 2),
            "method": method, "hp": econ["hp"], "waves": econ["waves"],
            "partyDps": round(party_dps, 1)}, False, info


def fit_clear_model(samples: list, now: float | None = None, hp_of=None):
    """Regressao linear ponderada sobre as amostras de clear.

    Modelo:  clearSec = T_fixo + tWave * waves + (1/c) * (hp / partyDps)

    onde c e a eficiencia de kill (quanto de HP/s o time mata por unidade de
    DPS efetivo). Normalizar pelo DPS da epoca da amostra permite aproveitar
    amostras antigas mesmo depois de o time ficar mais forte.

    Pesos:
      - amostra MANUAL (cronometrada pelo usuario) = W_MANUAL fixo, sem decair:
        e a verdade-base e domina as automaticas.
      - amostra AUTO = 0.5^(idade/14d) * min(clears,5): janelas com mais runs
        erram menos nas pontas; amostras antigas pesam menos.

    Com 5+ pontos ajusta os 3 parametros (inclui o T_fixo); com menos, ou se o
    ajuste de 3 sair sem sentido fisico, cai pro de 2 com T_fixo fixo.
    """
    now = now or time.time()
    pts = []
    for s in samples or []:
        if not s:
            continue
        cs = s.get("clearSec") or 0
        hp_raw = s.get("hp") or 0
        pd = s.get("partyDps") or 0
        if cs <= 0 or hp_raw <= 0 or pd <= 0:
            continue
        src = s.get("source")
        if src == "manual":
            w = W_MANUAL
        else:
            age_days = max(now - s.get("ts", now), 0) / 86400
            w = 0.5 ** (age_days / 14) * min(s.get("clears") or 1, 5)
        # hp corrigido pela escala empirica atual da fase, quando disponivel
        hp = (hp_of(s["stage"]) if hp_of else None) or hp_raw
        pts.append((w, s.get("waves") or 0, hp / pd, cs, s["stage"], src))
    if not pts:
        return None
    # amostra manual (cronometrada) e verdade-base. O automatico deriva de
    # totalClears, que se mostrou NAO-confiavel (conta ~Nx mais que runs reais,
    # deixando o clearSec curto demais). Entao: havendo QUALQUER manual, o
    # automatico e ignorado no ajuste.
    manual_pts = [p for p in pts if p[5] == "manual"]
    if manual_pts:
        pts = manual_pts

    def solve2(points):
        # 2 parametros (tWave, q=1/c) com T_fixo preso em T_FIXED
        Sxx = Sxz = Szz = Sxy = Szy = 0.0
        for w, x, z, cs, *_ in points:
            y = cs - T_FIXED
            Sxx += w * x * x; Sxz += w * x * z; Szz += w * z * z
            Sxy += w * x * y; Szy += w * z * y
        det = Sxx * Szz - Sxz * Sxz
        t = q = None
        if abs(det) > 1e-9:
            t = (Sxy * Szz - Szy * Sxz) / det
            q = (Sxx * Szy - Sxz * Sxy) / det
        if q is None or q <= 1e-9 or (t is not None and t < 0):
            if Szz <= 1e-9:
                return None
            q = Szy / Szz; t = 0.0
            if q <= 1e-9:
                return None
        return T_FIXED, t, q

    def solve3(points):
        # 3 parametros: a=T_fixo, t=tWave, q=1/c. Normal equations 3x3 (Cramer).
        S1 = Sx = Sz = Sxx = Szz = Sxz = Sy = Sxy = Szy = 0.0
        for w, x, z, cs, *_ in points:
            S1 += w; Sx += w * x; Sz += w * z
            Sxx += w * x * x; Szz += w * z * z; Sxz += w * x * z
            Sy += w * cs; Sxy += w * x * cs; Szy += w * z * cs
        M = [[S1, Sx, Sz], [Sx, Sxx, Sxz], [Sz, Sxz, Szz]]
        b = [Sy, Sxy, Szy]

        def det3(m):
            return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                    - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                    + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

        d = det3(M)
        if abs(d) < 1e-6:
            return None
        col = lambda i: [[b[r] if c == i else M[r][c] for c in range(3)] for r in range(3)]
        a, t, q = det3(col(0)) / d, det3(col(1)) / d, det3(col(2)) / d
        if q <= 1e-9 or t < -1e-6 or a < -3:   # sem sentido fisico: descarta
            return None
        return max(a, 0.0), max(t, 0.0), q

    def solve1(points):
        # so q (=1/c), com tWave e T_fixo nos defaults: ancora a eficiencia de
        # kill num tempo real. Util com 1-2 tempos manuais (verdade-base), pra
        # um unico tempo cronometrado ja melhorar a previsao na hora.
        Szz = Szy = 0.0
        for w, x, z, cs, *_ in points:
            y = cs - T_FIXED - T_WAVE * x
            Szz += w * z * z; Szy += w * z * y
        if Szz <= 1e-9:
            return None
        q = Szy / Szz
        return (T_FIXED, T_WAVE, q) if q > 1e-9 else None

    n_manual = sum(1 for p in pts if p[5] == "manual")
    sol3 = solve3(pts) if len(pts) >= 5 else None
    if sol3:
        solver, sol = solve3, sol3
    elif len(pts) >= 3:
        solver, sol = solve2, solve2(pts)
    elif n_manual >= 1:                 # 1-2 tempos manuais: ancora so o c
        solver, sol = solve1, solve1(pts)
    else:
        return None                     # 1-2 amostras auto: deixa o gold/h ancorar
    if not sol:
        return None
    a, t_wave, q = sol

    # rejeicao de outliers: o jogo gera janelas erraticas as vezes (runs
    # relampago, contadores estranhos); descarta residuos > 2.5x o mediano
    # e reajusta uma vez com o mesmo solver
    if len(pts) >= 5:
        resid = [abs(cs - (a + t_wave * x + q * z)) for w, x, z, cs, *_ in pts]
        med = sorted(resid)[len(resid) // 2] or 1e-9
        kept = [p for p, r in zip(pts, resid) if r <= 2.5 * med]
        if 3 <= len(kept) < len(pts):
            again = solver(kept) or solve2(kept)
            if again:
                a, t_wave, q = again
                pts = kept

    return {"tFixed": round(a, 2), "tWave": round(t_wave, 2), "c": 1 / q,
            "n": len(pts), "stages": len({p[4] for p in pts}),
            "manual": sum(1 for p in pts if p[5] == "manual")}


# ---------------------------------------------------------------------------
# Recompensa offline
# ---------------------------------------------------------------------------
OFFLINE_CAP_SEC = 28800  # 8h (wiki/mechanics)


def offline_info(gd: GameData, runes: dict, current_lvl: int, farm_rows: list):
    """Rendimento offline no estagio atual + melhor estagio para estacionar."""
    unlocked = runes.get("UnlockOfflineReward", 0) > 0
    gb = runes.get("OfflineRewardGoldPercent", 0) / PCT
    eb = runes.get("OfflineRewardExpPercent", 0) / PCT
    table = {r["StageLevel"]: r for r in gd.offline_rewards}

    def full(lvl):
        row = table.get(lvl)
        if not row:
            return None
        return {"gold": row["BaseGold"] * row["KillCount"] * (1 + gb),
                "exp": row["BaseExp"] * row["KillCount"] * (1 + eb)}

    cur = full(current_lvl)
    park = None
    for r in farm_rows:
        if not r.get("cleared") and not r.get("current"):
            continue  # nao estacione onde voce ainda nao limpou
        f = full(r["lvl"])
        if f and (park is None or f["gold"] > park["gold"]):
            park = {"key": r["key"], "label": r["label"], "tag": r["tag"],
                    "name": r["name"], "lvl": r["lvl"],
                    "gold": f["gold"], "exp": f["exp"]}
    return {
        "unlocked": unlocked,
        "capHours": OFFLINE_CAP_SEC / 3600,
        "goldBonusPct": round(gb * 100),
        "expBonusPct": round(eb * 100),
        "current": ({"gold": round(cur["gold"]), "exp": round(cur["exp"]),
                     "goldPerHour": round(cur["gold"] / 8),
                     "expPerHour": round(cur["exp"] / 8)} if cur else None),
        "park": ({**park, "gold": round(park["gold"]), "exp": round(park["exp"])}
                 if park else None),
    }


# ---------------------------------------------------------------------------
# Comparador de gear
# ---------------------------------------------------------------------------
SLOT_FIXED = {2: "HELMET", 3: "ARMOR", 4: "GLOVES", 5: "BOOTS",
              6: "AMULET", 7: "EARING", 8: "RING", 9: "BRACER"}


def _slot_gear_type(hero_row: dict, slot: int):
    if slot == 0:
        return hero_row.get("MainWeaponGearType")
    if slot == 1:
        return hero_row.get("SubWeaponGearType")
    return SLOT_FIXED.get(slot)


def _power(dps: float, ehp: float):
    return math.sqrt(max(dps, 0.0) * max(ehp, 0.0))


def _item_brief(gd: GameData, item_key):
    item = gd.items.get(item_key) or {}
    return {"itemKey": item_key, "name": _name(item.get("name")),
            "grade": item.get("grade"), "level": item.get("level")}


def _stat_diff(base: dict, new: dict, top: int = 4):
    """Quais stats finais mudam com a troca (os 'prefixos' que importam)."""
    out = []
    for k in set(base) | set(new):
        d = (new.get(k) or 0) - (base.get(k) or 0)
        if abs(d) > 1e-6:
            out.append({"stat": k, "delta": round(d, 1)})
    out.sort(key=lambda x: -abs(x["delta"]))
    return out[:top]


def gear_advisor(gd: GameData, save: dict, fielded_saves: list, runes: dict,
                 ref_level: int, ref_hit: float, elements):
    """Para cada slot de cada heroi do time, procura no inventario um item
    melhor que o equipado (criterio: power = sqrt(DPS x EHP))."""
    item_by_uid = {it["UniqueId"]: it for it in save.get("itemSaveDatas") or []}
    equipped_all = {uid for hs in fielded_saves
                    for uid in (hs.get("equippedItemIds") or []) if uid}
    out = []
    for hs in fielded_saves:
        hero_row = gd.heroes.get(hs["heroKey"]) or {}
        cur_uids = list(hs.get("equippedItemIds") or [])
        cur_uids += [0] * (10 - len(cur_uids))

        base_stats = collect_hero(gd, save, hs, runes)
        base_dmg = hero_damage(gd, save, hs, base_stats)
        base_ehp = hero_ehp(base_stats, ref_level, ref_hit, elements)
        base_power = _power(base_dmg["dps"], base_ehp)

        slots = []
        for slot in range(10):
            gt = _slot_gear_type(hero_row, slot)
            if not gt:
                continue
            cur_uid = cur_uids[slot]
            best = None
            for it in save.get("itemSaveDatas") or []:
                uid = it["UniqueId"]
                if uid == cur_uid:
                    continue
                if uid in equipped_all:
                    continue  # equipado em outro heroi do time
                if (gd.items.get(it["ItemKey"]) or {}).get("gear") != gt:
                    continue
                trial = cur_uids.copy()
                trial[slot] = uid
                st2 = collect_hero(gd, save, hs, runes, equip_override=trial)
                d2 = hero_damage(gd, save, hs, st2)
                e2 = hero_ehp(st2, ref_level, ref_hit, elements)
                d_power = _power(d2["dps"], e2) - base_power
                if d_power > 1e-6 and (best is None or d_power > best["dPower"]):
                    best = {**_item_brief(gd, it["ItemKey"]),
                            "dPower": round(d_power, 1),
                            "dDps": round(d2["dps"] - base_dmg["dps"], 1),
                            "dEhp": round(e2 - base_ehp, 1),
                            "statDiff": _stat_diff(base_stats, st2)}
            cur_it = item_by_uid.get(cur_uid)
            if best or not cur_uid:
                slots.append({
                    "slot": slot, "gearType": gt, "empty": not cur_uid,
                    "current": _item_brief(gd, cur_it["ItemKey"]) if cur_it else None,
                    "upgrade": best,
                })
        out.append({"heroKey": hs["heroKey"], "cls": hero_row.get("ClassType"),
                    "basePower": round(base_power, 1), "slots": slots})
    return out


# ---------------------------------------------------------------------------
# Conselheiro de runas (arvore + ganho real por compra)
# ---------------------------------------------------------------------------
GOLD_KEY = 100001  # chave da moeda gold (currenySaveDatas / CostItemKey)


def rune_advisor(gd: GameData, save: dict, runes: dict, *, fielded_saves,
                 ref_level, ref_hit, elements, cur_eff, ct,
                 gold_ph, exp_ph, gold_mult, exp_mult,
                 drop_n_mult, drop_b_mult, t_wave, gold_now):
    """Arvore de runas com estado do save + ganho estimado da PROXIMA compra.

    Combate (AllHero*): recalcula DPS/EHP do time de verdade com o stat da
    proxima compra aplicado. Farm (gold/exp/baus/offline/wave): ganho analitico
    sobre as taxas do estagio atual. QoL/desbloqueio: sem numero, so rotulo.
    """
    levels = {rs.get("RuneKey"): rs.get("Level") or 0
              for rs in save.get("RuneSaveData") or []}

    def party_power(rdict):
        dps, ehp_min = 0.0, None
        for hs in fielded_saves:
            stats = collect_hero(gd, save, hs, rdict)
            dps += hero_damage(gd, save, hs, stats)["dps"]
            e = hero_ehp(stats, ref_level, ref_hit, elements)
            ehp_min = e if ehp_min is None else min(ehp_min, e)
        return dps, (ehp_min or 0.0)

    dps0, ehp0 = party_power(runes) if fielded_saves else (0.0, 0.0)

    # flats atuais por tipo (denominador dos ganhos de farm)
    def flat_total(kind):
        if not cur_eff:
            return 0.0
        return (runes.get(f"Additional{kind}", 0) * cur_eff["kills"]
                + runes.get(f"Additional{kind}NormalMonster", 0) * cur_eff["nNormal"]
                + runes.get(f"Additional{kind}StageBoss", 0) * cur_eff["nStageBoss"]
                + runes.get(f"Additional{kind}ActBoss", 0) * cur_eff["nActBoss"])

    FLAT_COUNT = {"": "kills", "NormalMonster": "nNormal",
                  "StageBoss": "nStageBoss", "ActBoss": "nActBoss"}

    def gain_for(st, v):
        """(kind, pct, label) do proximo nivel; pct None = QoL sem numero."""
        if _rune_to_hero_stat(st):
            r2 = dict(runes)
            r2[st] = r2.get(st, 0) + v
            dps1, ehp1 = party_power(r2)
            dps_pct = (dps1 / dps0 - 1) * 100 if dps0 else 0.0
            ehp_pct = (ehp1 / ehp0 - 1) * 100 if ehp0 else 0.0
            if abs(dps_pct) >= abs(ehp_pct):
                return "combate", dps_pct, f"+{dps_pct:.2f}% DPS do time"
            return "combate", ehp_pct, f"+{ehp_pct:.2f}% EHP do time"
        if st == "IncreaseGoldAmount":
            cur = runes.get(st, 0)
            pct = (PCT + cur + v) / (PCT + cur) * 100 - 100
            return "farm", pct, f"+{pct:.2f}% gold/h"
        if st == "IncreaseExpAmount":
            cur = runes.get(st, 0)
            pct = (PCT + cur + v) / (PCT + cur) * 100 - 100
            return "farm", pct, f"+{pct:.2f}% exp/h"
        for kind, ph in (("Gold", gold_ph), ("Exp", exp_ph)):
            if st.startswith(f"Additional{kind}"):
                if not cur_eff or not ct or not ph:
                    return "farm", None, "gold/exp flat por kill"
                cnt = cur_eff[FLAT_COUNT[st[len(f"Additional{kind}"):]]]
                base = (cur_eff["gold"] if kind == "Gold" else cur_eff["exp"])
                mult = gold_mult if kind == "Gold" else exp_mult
                denom = base * mult + flat_total(kind)
                pct = (v * cnt) / denom * 100 if denom > 0 else None
                lab = "gold/h" if kind == "Gold" else "exp/h"
                return "farm", pct, (f"+{pct:.2f}% {lab} (fase atual)"
                                     if pct is not None else lab)
        if st in ("DropChanceNormalChestPercent", "DropChanceStageBossChestPercent"):
            cur_mult = drop_n_mult if st.startswith("DropChanceNormal") else drop_b_mult
            tipo = "normal" if st.startswith("DropChanceNormal") else "do boss"
            pct = (cur_mult + v / PCT) / cur_mult * 100 - 100
            return "farm", pct, f"+{pct:.2f}% baús {tipo}/h"
        if st in ("OfflineRewardGoldPercent", "OfflineRewardExpPercent"):
            cur = runes.get(st, 0)
            pct = (PCT + cur + v) / (PCT + cur) * 100 - 100
            que = "gold" if "Gold" in st else "exp"
            return "farm", pct, f"+{pct:.2f}% {que} offline"
        if st == "WaveCountReduction":
            if not ct or not t_wave:
                return "farm", None, "-1 wave por run"
            saved = t_wave * v
            pct = saved / max(ct - saved, 1) * 100
            return "farm", pct, f"-{v} wave (~+{pct:.1f}% nas taxas)"
        return "qol", None, "desbloqueio / utilidade"

    # pais: quem aponta pra quem (NextRuneKey = filhos)
    parent = {}
    for r in gd.runes.values():
        nk = r.get("NextRuneKey")
        if nk:
            for c in str(nk).split():
                parent[int(c)] = r["RuneKey"]

    nodes, edges, recs = [], [], []
    for r in gd.runes.values():
        key = r["RuneKey"]
        lv = levels.get(key, 0)
        mx = r.get("MaxLevel") or 1
        rows = gd.rune_levels.get(r["LevelDataKey"]) or {}
        req = r.get("PrevNodeRequiredLevel") or 1
        par = parent.get(key)
        unlocked = par is None or levels.get(par, 0) >= req
        nxt = rows.get(lv + 1) if lv < mx else None
        st = (rows.get(1) or {}).get("STATTYPE")
        total = sum((rows.get(L) or {}).get("Value") or 0 for L in range(1, lv + 1))

        gain = None
        if nxt and unlocked:
            kind, pct, label = gain_for(nxt["STATTYPE"], nxt["Value"] or 0)
            cost = nxt.get("CostValue") or 0
            gain = {"kind": kind, "pct": round(pct, 3) if pct is not None else None,
                    "label": label, "cost": cost,
                    "affordable": cost <= (gold_now or 0)}
            if pct is not None and pct > 0 and cost > 0:
                recs.append({"key": key, "name": _name(r.get("NameKey_i18n")),
                             "icon": r.get("IconPath"), "kind": kind,
                             "pct": round(pct, 3), "label": label, "cost": cost,
                             "level": lv + 1, "affordable": cost <= (gold_now or 0),
                             "score": pct / cost})
        nodes.append({
            "key": key, "name": _name(r.get("NameKey_i18n")),
            "icon": r.get("IconPath"), "stat": st,
            "level": lv, "max": mx, "req": req,
            "unlocked": unlocked, "owned": lv > 0, "maxed": lv >= mx,
            "nextCost": (nxt or {}).get("CostValue"),
            "nextValue": (nxt or {}).get("Value"),
            "perLevel": [{"level": L, "cost": (rows.get(L) or {}).get("CostValue"),
                          "value": (rows.get(L) or {}).get("Value")}
                         for L in range(1, mx + 1)],
            "total": total, "gain": gain,
        })
        if par is not None:
            edges.append({"from": par, "to": key, "req": req})

    recs.sort(key=lambda x: x["score"], reverse=True)
    return {
        "nodes": nodes, "edges": edges,
        "gold": gold_now,
        "recommendations": {
            "combate": [x for x in recs if x["kind"] == "combate"][:6],
            "farm": [x for x in recs if x["kind"] == "farm"][:6],
        },
    }


# ---------------------------------------------------------------------------
# Penalidade de exp por over-level
# ---------------------------------------------------------------------------
def fit_factor(party_level: int, stage_lvl: int) -> float:
    """Fracao de EXP mantida numa fase, dado o over/under-level do time.

    Formula EXATA do jogo, recuperada do Farming Planner da taskbarhero.wiki
    (funcao `Ht`); reproduz ao certo a tabela lida na tela do jogo (no Lv41:
    plato 100% em 39-47, 50% a -8, 16% a -12, 5% a -16, 85% a +10). O plato e
    DEPENDENTE DO NIVEL: alarga com log(nivel). Assimetrica: queda mais forte
    quando a fase fica abaixo do time (out-level) que quando fica acima.
    """
    e, t = party_level, stage_lvl
    over = e >= t                       # time no nivel ou acima da fase (out-level)
    r = 0.5 if over else 0.4            # piso da zona de queda quadratica
    k = math.log(e + 1) / 10 + 1        # escala que cresce com o nivel
    a = math.trunc(k * (2 if over else 5))   # meia-largura do plato
    o = math.trunc(k * (5 if over else 6))   # largura da queda quadratica
    s = abs(e - t)
    if s <= a:
        return 1.0                      # plato: EXP cheia
    if s <= a + o:
        x = (s - a) / o                 # queda quadratica suave ate o piso r
        return max(1 - (1 - r) * x * x, 0.01)
    return max((0.01 / r) ** ((s - a - o) / max(e / 3, 1)) * r, 0.01)  # cauda exp


# ---------------------------------------------------------------------------
# Projecao de nivel no tempo
# ---------------------------------------------------------------------------
def project_levels(gd: GameData, level: int, exp_now: float, eps: float,
                   stage_lvl: int | None = None, horizons=(1, 4, 8, 24)):
    """Projeta o nivel de um heroi ao longo do tempo.

    eps e a taxa MEDIDA agora; se stage_lvl for dado, a taxa decai conforme
    o heroi sobe de nivel na mesma fase (penalidade de over-level), entao a
    projecao nao superestima quem fica parado no mesmo mapa.
    """
    if not eps or eps <= 0 or level >= 100:
        return None
    f0 = fit_factor(level, stage_lvl) if stage_lvl else 1.0

    def rate(L):
        if not stage_lvl:
            return eps
        return eps * fit_factor(L, stage_lvl) / max(f0, 1e-6)

    need0 = gd.levels.get(level)
    series = [[0.0, level + (exp_now / need0 if need0 else 0)]]
    out_h = {}
    hz = sorted(horizons)
    hi = 0
    t, L, e = 0.0, level, exp_now
    max_t = hz[-1] * 3600
    while L < 100:
        need = gd.levels.get(L)
        r = rate(L)
        if not need or r <= 0:
            break
        t_up = t + (need - e) / r
        while hi < len(hz) and hz[hi] * 3600 < t_up:
            out_h[str(hz[hi])] = round(L + (e + (hz[hi] * 3600 - t) * r) / need, 2)
            hi += 1
        if t_up > max_t:
            break
        t, L, e = t_up, L + 1, 0.0
        series.append([round(t / 3600, 3), L])
    while hi < len(hz):
        r = rate(L)
        out_h[str(hz[hi])] = float(L if L >= 100 else
                                   round(L + (e + (hz[hi] * 3600 - t) * r)
                                         / (gd.levels.get(L) or 1), 2))
        hi += 1
    return {"horizons": out_h, "series": series[:60]}


# ---------------------------------------------------------------------------
# Simulacao completa a partir do save
# ---------------------------------------------------------------------------
def simulate(gd: GameData, save: dict, measured: dict | None = None,
             samples: list | None = None, stage_stats: dict | None = None):
    """Estado de combate do time + tabela de farm com taxas reais.

    measured (opcional): taxas medidas entre saves:
      {'goldPerSec': x, 'expPerSec': y, 'expPerHourByHero': {nome: v}}
    samples (opcional): amostras de clear persistidas (store.py) para a
    calibracao por regressao - a melhor fonte de verdade do modelo.
    stage_stats (opcional): kills/run empiricos por fase (store.py); corrigem
    a composicao da wiki, que se mostrou inflada em algumas fases.
    """
    measured = measured or {}

    # --- economia: HP/gold/exp dataminados CRUS, igual ao Farming Planner da
    # taskbarhero.wiki (que mostra numeros exatos: reward / tempo-de-clear).
    # O antigo "econScale" (observado/wiki via kills) foi REMOVIDO: ele saia do
    # totalClears do save, que conta varias vezes por run, e corrompia a razao
    # (puxava gold/exp pra baixo). O tempo de clear vem da calibracao manual.
    scales = {}
    global_scale = 1.0

    def scale_of(key):
        return 1.0

    def eff_econ(econ):
        return econ
    cs = save["commonSaveData"]
    runes = rune_stats(gd, save)

    # pet equipado: bonus passivos de gold/exp (pet_stats)
    pet_bonus = {}
    pet = gd.pets.get(cs.get("ArrangedPetKey"))
    if pet:
        for r in gd.pet_stats.get(pet.get("StatDataKey"), []):
            pet_bonus[r["STATTYPE"]] = pet_bonus.get(r["STATTYPE"], 0) + (r["Value"] or 0)

    gold_mult = 1 + (runes.get("IncreaseGoldAmount", 0)
                     + pet_bonus.get("IncreaseGoldAmount", 0)) / PCT
    exp_mult = 1 + (runes.get("IncreaseExpAmount", 0)
                    + pet_bonus.get("IncreaseExpAmount", 0)) / PCT

    # runas de gold/exp FLAT por kill (nao multiplicam, somam por abate)
    def flat_per_clear(econ, kind):
        return (runes.get(f"Additional{kind}", 0) * econ["kills"]
                + runes.get(f"Additional{kind}NormalMonster", 0) * econ["nNormal"]
                + runes.get(f"Additional{kind}StageBoss", 0) * econ["nStageBoss"]
                + runes.get(f"Additional{kind}ActBoss", 0) * econ["nActBoss"])

    cur_key = cs.get("currentStageKey")
    cur_econ = gd.stage_econ(cur_key)
    cur_eff = eff_econ(cur_econ) if cur_econ else None
    ref_level = cur_econ["lvl"] if cur_econ else 1
    ref_hit = cur_econ["biggestHit"] if cur_econ else 0

    # --- herois do time
    fielded = [k for k in cs.get("arrangedHeroKey") or [] if k and k > 0]
    hero_saves = {h["heroKey"]: h for h in save.get("heroSaveDatas") or []}
    heroes = []
    for hk in fielded:
        hs = hero_saves.get(hk)
        if not hs:
            continue
        stats = collect_hero(gd, save, hs, runes)
        dmg = hero_damage(gd, save, hs, stats)
        ehp = hero_ehp(stats, ref_level, ref_hit,
                       cur_econ["elements"] if cur_econ else None)
        hero_row = gd.heroes.get(hk) or {}
        heroes.append({
            "key": hk,
            "name": _name(hero_row.get("HeroNameKey_i18n")) or hero_row.get("ClassType"),
            "cls": hero_row.get("ClassType"),
            "level": hs.get("HeroLevel"),
            "dps": dmg["dps"], "autoDps": dmg["autoDps"], "skillDps": dmg["skillDps"],
            "statusDps": dmg["statusDps"],   # igual ao painel de Status do jogo
            "damage": dmg["breakdown"],      # dano real detalhado por skill
            "ehp": ehp,
            "stats": {k: round(v, 2) for k, v in stats.items()},
        })
    party_dps = sum(h["dps"] for h in heroes) or 1.0
    party_level = max((h["level"] or 1 for h in heroes), default=1)

    # --- calibracao, em ordem de confianca:
    #  1. regressao sobre amostras de clear persistidas (aprende com o tempo)
    #  2. ancora no gold/h medido da sessao no estagio atual
    #  3. modelo puro (DPS teorico + constantes default)
    kill_rate = party_dps           # hp/s teorico
    t_wave = T_WAVE
    t_fixed = T_FIXED
    calib = {"source": "modelo", "factor": 1.0, "samples": len(samples or []),
             "tWave": T_WAVE, "tFixed": T_FIXED, "manual": 0}

    def hp_scaled(stage_key):
        e = gd.stage_econ(stage_key)
        return e["hp"] * scale_of(stage_key) if e else None

    fit = fit_clear_model(samples, hp_of=hp_scaled) if samples else None
    mgps = measured.get("goldPerSec")
    if fit:
        kill_rate = fit["c"] * party_dps
        t_wave = fit["tWave"]
        t_fixed = fit.get("tFixed", T_FIXED)
        nman = fit.get("manual") or 0
        if fit["n"] < 3:
            src = f"ancorado em {nman} tempo(s) manual"
        else:
            src = f"regressão ({fit['n']} amostras, {fit['stages']} estágios"
            src += f", {nman} manual)" if nman else ")"
        calib = {"source": src,
                 "factor": round(fit["c"], 3), "samples": fit["n"],
                 "tWave": fit["tWave"], "tFixed": fit.get("tFixed", T_FIXED),
                 "manual": nman}
    elif mgps and mgps > 0 and cur_eff and cur_eff["gold"] > 0:
        gold_clear = cur_eff["gold"] * gold_mult + flat_per_clear(cur_eff, "Gold")
        ct_meas = gold_clear / mgps
        overhead = T_FIXED + T_WAVE * cur_eff["waves"]
        if ct_meas > overhead and cur_eff["hp"] > 0:
            kill_rate = cur_eff["hp"] / (ct_meas - overhead)
            calib = {"source": "gold/h medido na sessão",
                     "factor": round(kill_rate / party_dps, 3),
                     "samples": len(samples or []), "tWave": T_WAVE}

    def clear_time(econ):
        return t_fixed + t_wave * econ["waves"] + econ["hp"] / max(kill_rate, 1.0)

    # exp: calibra com a taxa medida se houver
    exp_scale = 1.0
    meps = measured.get("expPerSec")
    if meps and meps > 0 and cur_eff and cur_eff["exp"] > 0:
        # o fit_factor do estagio atual entra no modelo para que a ancora
        # medida nao "esconda" a penalidade de over-level dos outros estagios
        exp_clear = ((cur_eff["exp"] * exp_mult + flat_per_clear(cur_eff, "Exp"))
                     * fit_factor(party_level, cur_eff["lvl"]))
        model_eps = exp_clear / clear_time(cur_eff)
        if model_eps > 0:
            exp_scale = meps / model_eps

    # --- drop de baus: taxa per-mille POR KILL (confirmado na wiki:
    # /items/normal-monster-box-1 = 16%/kill; /items/stage-boss-box-lv40 =
    # 15%/boss). "~/clear" = taxa x kills (bau normal usa nNormal; bau do boss,
    # 1 boss). O bonus de drop do save multiplica como os outros (1 + bonus/1000).
    DROP_DIV = 1000.0
    drop_n_mult = 1 + runes.get("DropChanceNormalChestPercent", 0) / PCT
    drop_b_mult = 1 + runes.get("DropChanceStageBossChestPercent", 0) / PCT
    drop_n = round((drop_n_mult - 1) * 100)   # % so pra exibir
    drop_b = round((drop_b_mult - 1) * 100)

    def box_label(k):
        if not k:
            return None
        tipo = {91: "Baú normal", 92: "Baú do boss", 93: "Baú act-boss"}.get(
            k // 10000, "Baú")
        return f"{tipo} Lv{(k % 1000) // 10}"

    # --- tabela de farm dos estagios desbloqueados
    party_ehp_min = min((h["ehp"] for h in heroes), default=0)
    unlocked = set(gd.unlocked_stages(cs.get("maxCompletedStage")))
    max_idx = (gd.stage_order.index(cs.get("maxCompletedStage"))
               if cs.get("maxCompletedStage") in gd.stage_order else -1)
    rows = []
    for key in gd.stage_order:
        if key not in unlocked:
            continue
        econ = gd.stage_econ(key)
        if not econ:
            continue
        eff = eff_econ(econ)
        ct = clear_time(eff)
        in_dps = econ["monsterDps"] * MAX_CONCURRENT
        danger = (in_dps * ct) / max(party_ehp_min, 1.0)
        idx = gd.stage_order.index(key)
        fit = fit_factor(party_level, econ["lvl"])
        st = gd.stages.get(key) or {}
        mbk, bbk = st.get("MonsterDropItemKey"), st.get("BossDropItemKey")
        nbox = econ["nNormal"] * (st.get("MonsterDropItemRate") or 0) / DROP_DIV * drop_n_mult
        bbox = econ["nStageBoss"] * (st.get("BossDropItemRate") or 0) / DROP_DIV * drop_b_mult
        rows.append({
            "key": key, "label": econ["label"], "tag": econ["tag"],
            "diff": econ["diff"], "type": econ["type"], "name": econ["name"],
            "lvl": econ["lvl"],
            "clearTime": round(ct, 1),
            "goldPerHour": (eff["gold"] * gold_mult
                            + flat_per_clear(eff, "Gold")) / ct * 3600,
            "expPerHour": (eff["exp"] * exp_mult + flat_per_clear(eff, "Exp"))
                          * fit * exp_scale / ct * 3600,
            "expFit": round(fit, 3),
            "econScale": round(scale_of(key), 3),
            "measuredScale": key in scales,
            "danger": round(danger, 2),
            "normalBox": box_label(mbk),
            "bossBox": box_label(bbk),
            "normalBoxLvl": (mbk % 1000) // 10 if mbk else 0,
            "bossBoxLvl": (bbk % 1000) // 10 if bbk else 0,
            "normalBoxPerClear": round(nbox, 3),
            "bossBoxPerClear": round(bbox, 3),
            "normalBoxPerHour": nbox / ct * 3600,
            "bossBoxPerHour": bbox / ct * 3600,
            "secsPerBossBox": (ct / bbox) if bbox > 0 else None,
            "cleared": idx <= max_idx,
            "current": key == cur_key,
        })

    cur_row = next((r for r in rows if r["current"]), None)
    # perigo relativo ao estagio atual: se voce ja farma nele, ele e a regua.
    # Sem estagio atual na lista, cai para limiares absolutos.
    ref_danger = cur_row["danger"] if cur_row and cur_row["danger"] > 0 else None
    for r in rows:
        rel = r["danger"] / ref_danger if ref_danger else r["danger"]
        r["rating"] = ("seguro" if rel <= 1.2 else
                       "apertado" if rel <= 2.5 else "arriscado")

    # Recomendacao so entre fases que voce CONSEGUE clearar: nao-ACTBOSS, ja
    # LIMPAS (a fase seguinte nao-limpa vira "push", nunca recomendacao de farm)
    # e de preferencia nao "arriscado". Fallbacks pra nunca ficar sem nada.
    farmable = [r for r in rows if r["type"] != "ACTBOSS"]
    cleared_farm = [r for r in farmable if r["cleared"]] or farmable
    pool = [r for r in cleared_farm if r["rating"] != "arriscado"] or cleared_farm
    best_gold = max(pool, key=lambda r: r["goldPerHour"], default=None)
    best_exp = max(pool, key=lambda r: r["expPerHour"], default=None)
    # "push" = proxima fase nao-limpa, mas SO sugere se da pra clearar com folga
    # (rating "seguro"). Se a proxima esta "apertado"/"arriscado", o jogador nao
    # esta pronto: nao empurra (evita sugerir fase em que ele esta travado).
    push = next((r for r in rows if not r["cleared"]), None)
    if push and push.get("rating") != "seguro":
        push = None

    # rota de baus: melhor fase LIMPA. Prioriza o bau de NIVEL mais alto (gear
    # melhor) e, dentro do mesmo nivel, mais baus/hora (clear mais rapido).
    box_pool = [r for r in rows if r["cleared"] and r["type"] != "ACTBOSS"]
    best_boss_box = max((r for r in box_pool if r["bossBoxPerHour"] > 0),
                        key=lambda r: (r["bossBoxLvl"], r["bossBoxPerHour"]),
                        default=None)
    best_normal_box = max((r for r in box_pool if r["normalBoxPerHour"] > 0),
                          key=lambda r: (r["normalBoxLvl"], r["normalBoxPerHour"]),
                          default=None)

    # --- exp/s por heroi: medido se houver, senao estimado pela fase atual
    eps_party = (meps if meps and meps > 0 else
                 (cur_row["expPerHour"] / 3600 if cur_row else 0))
    by_hero = measured.get("expPerHourByHero") or {}

    def hero_eps(h):
        v = by_hero.get(h["cls"]) or by_hero.get(h["name"])
        if v and v > 0:
            return v / 3600
        return eps_party / max(len(heroes), 1)

    # --- ETA de proximo nivel + projecao no tempo
    eta, projection = [], []
    for h in heroes:
        hs = hero_saves.get(h["key"]) or {}
        need = gd.levels.get(h["level"] or 1)
        eps = hero_eps(h)
        if need is not None:
            missing = max(need - (hs.get("HeroExp") or 0), 0)
            eta.append({"key": h["key"], "level": h["level"],
                        "expToNext": missing,
                        "etaSec": missing / eps if eps > 0 else None})
        proj = project_levels(gd, h["level"] or 1, hs.get("HeroExp") or 0, eps,
                              stage_lvl=cur_econ["lvl"] if cur_econ else None)
        if proj:
            projection.append({"key": h["key"], "name": h["name"],
                               "cls": h["cls"], **proj})

    # --- offline e gear
    offline = offline_info(gd, runes, ref_level, rows)
    fielded_saves = [hero_saves[hk] for hk in fielded if hk in hero_saves]
    gear = gear_advisor(gd, save, fielded_saves, runes, ref_level, ref_hit,
                        cur_econ["elements"] if cur_econ else None)

    # --- arvore de runas + recomendacao de compra
    gold_now = next((c.get("Quantity") for c in save.get("currenySaveDatas") or []
                     if c.get("Key") == GOLD_KEY), 0)
    runes_tree = rune_advisor(
        gd, save, runes,
        fielded_saves=fielded_saves, ref_level=ref_level, ref_hit=ref_hit,
        elements=cur_econ["elements"] if cur_econ else None,
        cur_eff=cur_eff,
        ct=cur_row["clearTime"] if cur_row else None,
        gold_ph=cur_row["goldPerHour"] if cur_row else None,
        exp_ph=cur_row["expPerHour"] if cur_row else None,
        gold_mult=gold_mult, exp_mult=exp_mult,
        drop_n_mult=drop_n_mult, drop_b_mult=drop_b_mult,
        t_wave=t_wave, gold_now=gold_now)

    result = {
        "heroes": heroes,
        "party": {"dps": party_dps, "ehpMin": party_ehp_min,
                  "size": len(heroes), "level": party_level},
        "calibration": calib,
        "goldBonusPct": round((gold_mult - 1) * 100),
        "expBonusPct": round((exp_mult - 1) * 100),
        "farm": {"rows": rows, "current": cur_row, "bestGold": best_gold,
                 "bestExp": best_exp, "push": push,
                 "bestBossBox": best_boss_box, "bestNormalBox": best_normal_box,
                 "dropBonus": {"normal": drop_n, "boss": drop_b}},
        "levelEta": eta,
        "projection": projection,
        "offline": offline,
        "gear": gear,
        "runes": runes_tree,
        "econScale": {"global": round(global_scale, 3),
                      "stages": {str(k): round(v, 3) for k, v in scales.items()}},
    }
    result["coach"] = coach_text(result, state_heroes=None)
    return result


# ---------------------------------------------------------------------------
# Coach: a recomendacao em texto
# ---------------------------------------------------------------------------
def _fmt(n):
    if n is None:
        return "—"
    n = float(n)
    a = abs(n)
    if a >= 1e9:
        return f"{n / 1e9:.2f}B"
    if a >= 1e6:
        return f"{n / 1e6:.2f}M"
    if a >= 1e3:
        return f"{n / 1e3:.0f}k"
    return str(int(round(n)))


def _fmt_dur(sec):
    if sec is None:
        return "—"
    if sec < 90:
        return f"{round(sec)}s"
    if sec < 5400:
        return f"{round(sec / 60)}min"
    return f"{sec / 3600:.1f}h"


def coach_text(sim: dict, state_heroes=None):
    """Gera a narrativa em PT-BR: onde farmar, quanto custa errar, quando trocar."""
    f = sim["farm"]
    cur, bg, be, push = f["current"], f["bestGold"], f["bestExp"], f["push"]
    out = []

    # 1. melhor fase de gold + custo de estar na errada
    if bg:
        p = (f"Melhor fase para GOLD agora: {bg['tag']} {bg['label']} — "
             f"{bg['name']} (lvl {bg['lvl']}), rendendo ~{_fmt(bg['goldPerHour'])} "
             f"gold/h com clear médio de {_fmt_dur(bg['clearTime'])} e perigo "
             f"{bg['rating']}.")
        if cur and cur["key"] != bg["key"]:
            loss = bg["goldPerHour"] - cur["goldPerHour"]
            if loss > 0:
                pct = loss / max(bg["goldPerHour"], 1) * 100
                p += (f" Você está em {cur['tag']} {cur['label']} "
                      f"(~{_fmt(cur['goldPerHour'])}/h): cada hora aí custa "
                      f"~{_fmt(loss)} de gold ({pct:.0f}% a menos). "
                      f"Trocar agora já compensa.")
        elif cur:
            p += " Você já está nela — farm correto."
        out.append(p)

    # 2. melhor fase de exp + penalidade de over-level
    if be and (not bg or be["key"] != bg["key"]):
        p = (f"Para EXP, a melhor é {be['tag']} {be['label']} — {be['name']} "
             f"(~{_fmt(be['expPerHour'])} exp/h vs "
             f"{_fmt(cur['expPerHour']) if cur else '—'} na atual).")
        out.append(p)
    cur_fit = cur.get("expFit") if cur else None
    if cur_fit is not None and cur_fit < 0.7:
        out.append(f"Atenção: o time (nível {sim['party'].get('level')}) está "
                   f"acima do nível da fase atual — a exp lá sofre penalidade "
                   f"de ~{round((1 - cur_fit) * 100)}%. O ranking e a projeção "
                   f"já descontam isso.")
    for pr in (sim.get("projection") or [])[:4]:
        h4 = pr["horizons"].get("4")
        h24 = pr["horizons"].get("24")
        if h4:
            out.append(f"No ritmo medido, {pr['name']} estará no nível "
                       f"{h4:.0f} em 4h e {h24:.0f} em 24h." if h24 else
                       f"No ritmo medido, {pr['name']} chega ao nível {h4:.0f} em 4h.")
            break  # um exemplo basta no texto; o grafico mostra o resto

    # 3. push
    if push:
        if push["rating"] == "arriscado":
            out.append(f"Próximo avanço: {push['tag']} {push['label']} — "
                       f"{push['name']} (lvl {push['lvl']}). Ainda ARRISCADO para "
                       f"seu EHP mínimo de {_fmt(sim['party']['ehpMin'])}: farme "
                       f"gold na fase recomendada, compre runas de dano/armadura "
                       f"e tente depois.")
        else:
            out.append(f"Próximo avanço: {push['tag']} {push['label']} — "
                       f"{push['name']} (lvl {push['lvl']}), perigo {push['rating']}. "
                       f"Vale tentar o clear agora: destrava mais fases de farm.")

    # 4. offline / estacionamento
    off = sim.get("offline") or {}
    if off.get("unlocked") and off.get("park"):
        park = off["park"]
        cur_off = off.get("current")
        p = (f"Antes de fechar o jogo, estacione em {park['tag']} {park['label']} — "
             f"{park['name']}: rende {_fmt(park['gold'])} gold e {_fmt(park['exp'])} "
             f"exp em 8h offline (cap).")
        if cur_off and park["gold"] > cur_off["gold"] * 1.05:
            p += (f" Parado na fase atual seriam só {_fmt(cur_off['gold'])} "
                  f"({_fmt(park['gold'] - cur_off['gold'])} a menos).")
        out.append(p)

    # 5. quick wins de gear
    swaps = [(g["cls"], s) for g in sim.get("gear") or []
             for s in g["slots"] if s.get("upgrade")]
    if swaps:
        swaps.sort(key=lambda x: -x[1]["upgrade"]["dPower"])
        cls, s = swaps[0]
        up = s["upgrade"]
        extra = f" (+{len(swaps) - 1} troca(s) menores)" if len(swaps) > 1 else ""
        out.append(f"Gear: equipar “{up['name']}” ({up['grade']}, lvl {up['level']}) "
                   f"no {cls} dá +{_fmt(up['dPower'])} de power{extra}. "
                   f"Está parado no inventário.")
    empties = [(g["cls"], s) for g in sim.get("gear") or []
               for s in g["slots"] if s["empty"] and not s.get("upgrade")]
    if empties:
        out.append(f"Você tem {len(empties)} slot(s) de equipamento VAZIOS no time "
                   f"({', '.join(sorted({s['gearType'] for _, s in empties}))}) — "
                   f"qualquer item é melhor que nada.")

    # 6. estado do modelo
    cal = sim.get("calibration") or {}
    n = cal.get("samples", 0)
    if str(cal.get("source", "")).startswith("regress"):
        out.append(f"Modelo calibrado por regressão com {n} amostras de clear "
                   f"reais (tempo por wave ≈ {cal.get('tWave')}s). As taxas acima "
                   f"são medidas, não chute.")
    elif n > 0:
        out.append(f"O modelo tem {n} amostra(s) de clear — com 3+ ele passa a "
                   f"calibrar por regressão. Deixe o painel aberto enquanto joga.")
    else:
        out.append("Deixe o painel aberto enquanto joga: cada save vira uma "
                   "amostra de tempo de clear e o modelo fica mais preciso sozinho.")
    return out
