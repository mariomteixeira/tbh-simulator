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

import bisect
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

        # detalhes de item (matEffects = Decoration/Engraving/Inscription); usado
        # pela pagina de Builds (catalogo de gems + tipo de socket). Keyed por id.
        try:
            _idet = _load(gd_dir, "items_detail")
            self.items_detail = ({int(k): v for k, v in _idet.items()}
                                 if isinstance(_idet, dict)
                                 else {i.get("id"): i for i in _idet})
        except FileNotFoundError:
            self.items_detail = {}

        # --- alquimia/cubo: escalas do CubeExp por item (grade/tipo/gear/lvl) ---
        self.grades = {g["GRADE"]: g for g in _load(gd_dir, "grades")}
        self.item_type_scales = {r["ItemType"]: r
                                 for r in _load(gd_dir, "item_type_scales")}
        self.gear_type_scales = {r["GearType"]: r
                                 for r in _load(gd_dir, "gear_type_scales")}
        _ils = sorted(_load(gd_dir, "item_level_scales"),
                      key=lambda r: r["Level"])
        self.ils_levels = [r["Level"] for r in _ils]
        self.ils_cube = [r["CubeExpScale"] for r in _ils]
        # curva de nivel do cubo (Level -> ExpForLevelUp); pode faltar em
        # instalacoes antigas que ainda nao rodaram o fetch novo
        try:
            self.cube_levels = {r["Level"]: r["ExpForLevelUp"]
                                for r in _load(gd_dir, "cube_levels")}
        except FileNotFoundError:
            self.cube_levels = {}

        # buffs de skill (ativos por cooldown): grupo -> chaves -> stat
        try:
            self.buffs = {b["BuffKey"]: b for b in _load(gd_dir, "buffs")}
            self.buff_groups = {g["BuffGroupKey"]: g
                                for g in _load(gd_dir, "buff_groups")}
        except FileNotFoundError:
            self.buffs, self.buff_groups = {}, {}

        self.runes = {r["RuneKey"]: r for r in _load(gd_dir, "runes")}
        self.rune_levels = {}
        for r in _load(gd_dir, "rune_levels"):
            self.rune_levels.setdefault(r["LevelKey"], {})[r["Level"]] = r
        # posicoes do mapa de runas (extraidas da wiki; arvore identica ao site)
        self.rune_layout = {}
        layout_file = Path(gd_dir) / "rune_layout.json"
        if layout_file.exists():
            data = json.loads(layout_file.read_text(encoding="utf-8-sig"))
            self.rune_layout = {int(k): v for k, v in
                                (data.get("positions") or {}).items()}

        # elemento de ataque por monstro (raspado das páginas da wiki — não está
        # nas tabelas; chave -> Physical/Fire/Cold/Lightning/Chaos)
        try:
            self.monster_elements = {int(k): v for k, v in
                                     _load(gd_dir, "monster_elements").items()}
        except FileNotFoundError:
            self.monster_elements = {}

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
        elem_hits = {}            # elemento -> maior golpe daquele elemento
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
            # elemento real do monstro (raspado) -> maior hit por elemento
            el = self.monster_elements.get(mon.get("MonsterKey"), "Physical")
            elem_hits[el] = max(elem_hits.get(el, 0.0), hit)

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
            "elemHits": {k: round(v, 1) for k, v in elem_hits.items()},
            # 'elements' = tipos NÃO-físicos (compat com EHP elemental existente)
            "elements": sorted(k for k in elem_hits if k != "Physical"),
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


# Stats que são "% de aumento PURO" (não têm base própria): FLAT e ADDITIVE
# apenas SOMAM as fontes, não multiplicam. Ex.: SkillHealIncrease — gear dá 175
# FLAT (+17,5%) e a passiva 700 ADDITIVE (+70%); total = 87,5%, não 175×1,7.
_SUM_STATS = {"SkillHealIncrease", "DamageAbsorption"}


class StatBag:
    """Acumula modificadores e aplica a formula de stacking documentada."""

    def __init__(self):
        self.flat = {}
        self.add = {}
        self.mult = {}

    def put(self, stat, mod, value):
        if not stat or stat == "NONE" or not value:
            return
        # o datamine do jogo tem sujeira: alguns BaseStat_Value vem como string
        # com espaco no fim ("190 "); coage pra numero e ignora o invalido
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError:
                return
            if not value:
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
            if stat in _SUM_STATS:   # % puro: soma as fontes (flat + additive)
                out[stat] = ((self.flat.get(stat, 0.0) + self.add.get(stat, 0.0))
                             * self.mult.get(stat, 1.0))
                continue
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


# ---------------------------------------------------------------------------
# Alquimia: EXP que cada item dá ao Cubo
# ---------------------------------------------------------------------------
_CUBE_MAX_NEED = 999_999_999  # sentinela de "nivel maximo" na curva do cubo


def _item_level_scale(gd: GameData, level):
    """CubeExpScale para um nivel de item. A tabela vem em passos de 5 niveis;
    interpola linear no meio e extrapola linear acima do ultimo ponto."""
    if level is None:
        return 1000.0
    xs, ys = gd.ils_levels, gd.ils_cube
    if not xs:
        return 1000.0
    if level <= xs[0]:
        return ys[0]
    if level >= xs[-1]:
        slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2]) if len(xs) > 1 else 0.0
        return ys[-1] + slope * (level - xs[-1])
    k = bisect.bisect_right(xs, level) - 1
    if xs[k] == level:
        return ys[k]
    t = (level - xs[k]) / (xs[k + 1] - xs[k])
    return ys[k] + t * (ys[k + 1] - ys[k])


def cube_exp(gd: GameData, item: dict) -> int:
    """EXP base que um item dá ao Cubo na Alquimia.

    Validado EXATO contra os 5744 valores dataminados (itemCubeExp):
      base(grade) × ItemTypeScale/1000 × GearTypeScale/1000 (só GEAR)
                  × ItemLevelScale/1000
    NÃO depende do nível do cubo. O buff de runa (CubeExpPercent) entra depois.
    """
    grade = gd.grades.get(item.get("grade"))
    if not grade:
        return 0
    val = float(grade.get("BaseCubeExp", 0) or 0)
    ts = gd.item_type_scales.get(item.get("type"))
    if not ts:
        return 0
    val *= (ts.get("CubeExpScale", 1000) or 1000) / 1000.0
    if item.get("type") == "GEAR":
        gs = gd.gear_type_scales.get(item.get("gear"))
        if not gs:
            return 0
        val *= (gs.get("CubeExpScale", 1000) or 1000) / 1000.0
    val *= _item_level_scale(gd, item.get("level")) / 1000.0
    return round(val)


def _project_cube(gd: GameData, level: int, exp: float, add: float) -> dict:
    """Aplica `add` de EXP no cubo a partir de (level, exp) e diz onde para."""
    total = exp + max(0.0, add)
    lvl, gained = level, 0
    while True:
        need = gd.cube_levels.get(lvl)
        if not need or need >= _CUBE_MAX_NEED or total < need:
            break
        total -= need
        lvl += 1
        gained += 1
    return {"level": lvl, "exp": round(total, 1), "gained": gained}


def alchemy_panel(gd: GameData, save: dict, runes: dict):
    """Itens do inventário/stash com o EXP de Cubo de cada um (base e com buff
    de runa), agrupados como no jogo, + estado e projeção do cubo.

    Itens equipados, bloqueados ou sem valor de cubo são marcados como não
    alquimizáveis (igual ao jogo) e ficam fora dos totais."""
    if not gd.grades or not gd.cube_levels:
        return None
    cube = save.get("cubeSaveLevelData") or {}
    level = int(cube.get("Level", 1) or 1)
    exp = float(cube.get("Exp", 0) or 0)
    need = gd.cube_levels.get(level)
    raw = runes.get("CubeExpPercent", 0) or 0      # per-mille no datamine: 40 = 4%
    mult = 1 + raw / PCT

    equipped = set()
    for h in save.get("heroSaveDatas") or []:
        for u in h.get("equippedItemIds") or []:
            if u:
                equipped.add(u)
    by_uid = {it.get("UniqueId"): it for it in save.get("itemSaveDatas") or []}

    def entry(uid):
        if not uid:
            return None
        it = by_uid.get(uid)
        if not it:
            return None
        item = gd.items.get(it.get("ItemKey"))
        if not item:
            return None
        base = cube_exp(gd, item)
        ilvl = item.get("level")
        # LEVEL MATCHING: o EXP que o cubo recebe e escalado pela proximidade
        # entre o nivel do item e o nivel do CUBO (mesma escala da EXP de
        # monstro = fit_factor). Item ~no nivel do cubo (ou um pouco acima) =
        # cheio; gap grande = quase nada. Sem nivel (material) = sem matching.
        match = fit_factor(level, ilvl) if ilvl else 1.0
        blocked = bool(it.get("IsBlocked"))
        eq = uid in equipped
        return {
            "uid": str(uid),
            "key": item["id"],
            "name": _name(item.get("name")),
            "grade": item.get("grade"),
            "type": item.get("type"),
            "gear": item.get("gear"),
            "level": ilvl,
            "base": base,
            "match": round(match, 3),
            "eff": round(base * match * mult),
            "blocked": blocked,
            "equipped": eq,
            "ok": base > 0 and not blocked and not eq,
        }

    containers = []
    for cid, label, key in (("inventory", "Inventário", "inventorySaveDatas"),
                            ("stash", "Stash", "stashSaveDatas"),
                            ("trading", "Stash de troca", "tradingStashSaveDatas")):
        slots = [entry(s.get("ItemUniqueId")) for s in (save.get(key) or [])]
        alch = [e for e in slots if e and e["ok"]]
        s_eff = sum(e["eff"] for e in alch)
        containers.append({
            "id": cid, "label": label, "slots": slots,
            "filled": sum(1 for e in slots if e),
            "alchCount": len(alch), "sumEff": s_eff,
            "project": _project_cube(gd, level, exp, s_eff),
        })

    sum_all = sum(c["sumEff"] for c in containers)
    # nível de item que rende MAIS EXP de cubo agora (base×matching), entre os
    # níveis reais de gear — leva em conta que subir base compensa perder match
    gear_levels = sorted({it.get("level") for it in gd.items.values()
                          if it.get("type") == "GEAR" and it.get("level")})
    reco_level = (max(gear_levels,
                      key=lambda L: _item_level_scale(gd, L) * fit_factor(level, L))
                  if gear_levels else level)
    reco_match = round(fit_factor(level, reco_level) * 100)  # % de matching nesse nível
    return {
        "cube": {
            "level": level, "exp": round(exp, 1), "need": need,
            "nextNeed": gd.cube_levels.get(level + 1),   # limiar do nível seguinte
            "recoLevel": reco_level,                      # nível de item ideal p/ alquimia
            "recoMatch": reco_match,                      # matching (%) nesse nível
            "maxed": not need or need >= _CUBE_MAX_NEED,
            "pctToNext": (round(exp / need * 100, 1)
                          if need and need < _CUBE_MAX_NEED else None),
        },
        "buff": {"pct": round(raw / 10, 1), "mult": round(mult, 4)},
        "containers": containers,
        "projectAll": _project_cube(gd, level, exp, sum_all),
        "sumAll": sum_all,
    }


def collect_hero(gd: GameData, save: dict, hero_save: dict, runes: dict,
                 equip_override: list | None = None, loadout: list | None = None):
    """Junta base + gear + encantos + passivas + runas num StatBag.

    equip_override: lista de UniqueIds para simular trocas de equipamento
    (usada pelo comparador de gear) sem mexer no save.
    loadout: loadout HIPOTÉTICO da página de Builds — lista de
    {itemKey, sockets:[{stat, mod, value}]} por slot. Substitui o gear do save
    (itens + decorações/gravações/inscrições já resolvidos em stat/mod/valor).
    """
    bag = StatBag()
    hero = gd.heroes.get(hero_save["heroKey"]) or {}
    for st in BASE_STATS:
        bag.put(st, "FLAT", hero.get(st) or 0)

    def _apply_gear_item(item_key):
        """Aplica BaseStat1/2 + InherentStat1-3 de um item (base do gear)."""
        gear = gd.gear.get(item_key)
        item = gd.items.get(item_key)
        if not (gear and item):
            return
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

    if loadout is not None:
        # loadout hipotético (Builds): item por slot + sockets já resolvidos
        for ent in loadout:
            if ent.get("itemKey"):
                _apply_gear_item(ent["itemKey"])
            for sk in ent.get("sockets") or []:
                st, md = sk.get("stat"), sk.get("mod")
                if st and md and st != "NONE":
                    bag.put(st, md, sk.get("value") or 0)
    else:
        # gear equipado (save)
        item_by_uid = {it["UniqueId"]: it for it in save.get("itemSaveDatas") or []}
        equipped = (equip_override if equip_override is not None
                    else hero_save.get("equippedItemIds") or [])
        for uid in equipped:
            if not uid:
                continue
            it = item_by_uid.get(uid)
            if not it:
                continue
            _apply_gear_item(it["ItemKey"])
            # encantos + gems socketados: o save guarda o valor rolado; o tipo
            # (stat/mod) vem de stat_mods. Decoração/gravação/inscrição entram
            # por aqui também (são linhas de EnchantData com StatModKey válido).
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

    # blessings: skills CONTINUOUS (ativas enquanto equipadas) dão stat passivo
    # — Blessing of Might (+AttackDamage), Blessing of Warding (+resist elemental)
    for sk in hero_save.get("equippedSKillKey") or []:
        row = gd.skills.get(sk)
        if not row or row.get("ACTIVATIONTYPE") != "CONTINUOUS":
            continue
        lvl_rows = gd.skill_levels.get(row.get("SkillLevelKey")) or {}
        if not lvl_rows:
            continue
        lvl = _skill_level(gd, save, hero_save["heroKey"], sk)
        val = lvl_rows.get(lvl) or lvl_rows.get(max(lvl_rows)) or 0
        bset = _skill_buffs(gd, row.get("BuffGroupKey"))
        if bset:
            for b in bset:
                bag.put(b.get("STATTYPE"), b.get("MODTYPE"), val)
        else:
            # buff keys fora da tabela `buffs` (ex.: Warding): usa a descrição
            desc = ((row.get("SkillDescriptionKey_i18n") or {}).get("en-US") or "").lower()
            if "elemental resistance" in desc:
                for el in ("Fire", "Cold", "Lightning"):
                    bag.put(f"{el}Resistance", "FLAT", val)

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
    """Nível REAL da skill = o Level do nó ACTIVESKILL na árvore (já é o nível
    mostrado no jogo). NÃO somar uma base 1 — isso dava +1 (ex.: Cura nó Level=5
    aparecia como 6, e ainda pegava o Value do nível 6 na tabela). Sem nó (ataque
    básico) = nível 1."""
    lvl = 0
    for a in save.get("attributeSaveDatas") or []:
        node = gd.attributes.get(a.get("Key"))
        if (node and node["HeroKey"] == hero_key
                and node["ATTRIBUTETYPE"] == "ACTIVESKILL"
                and node["Value"] == skill_key):
            lvl += a.get("Level") or 0
    return max(lvl, 1)


# rótulos pt-BR de stats afetados por buffs de skill
_STAT_PT = {
    "AttackSpeed": "Vel. Ataque", "AttackDamage": "Dano de Ataque",
    "CriticalChance": "Chance Crítica", "CriticalDamage": "Dano Crítico",
    "MovementSpeed": "Vel. Movimento", "MoveSpeed": "Vel. Movimento",
    "Armor": "Armadura", "MaxHp": "HP Máx", "CooldownReduction": "Recarga",
}


def _auto_dps_from(stats: dict, base_skill: dict):
    """(statusDps, auto) do ataque básico para um dado dict de stats.
    Usado tanto pro stats real quanto pro stats COM buff aplicado."""
    ad = stats.get("AttackDamage") or 0
    crit = _crit_factor(stats)
    aps = (stats.get("AttackSpeed") or 0) / 100.0
    base_mult = (base_skill.get("Value") or PCT) / PCT
    delivery = base_skill.get("DamageDeliveryType") or "Melee"
    element = base_skill.get("DamageType") or "Physical"
    status_dps = ad * aps * crit * base_mult * BASIC_ATTACK_MULT
    return status_dps, status_dps * _dmg_bonus(stats, delivery, element)


def _skill_buffs(gd: GameData, buff_group_key):
    """Resolve BuffGroupKey -> lista de buffs {STATTYPE, MODTYPE, Value}."""
    g = gd.buff_groups.get(buff_group_key)
    if not g:
        return []
    keys = g.get("BuffKeys")
    keys = keys if isinstance(keys, list) else [keys]
    return [gd.buffs[k] for k in keys if k in gd.buffs]


def _stats_with_buff(stats: dict, stat: str, frac: float):
    """Cópia de stats com o buff aplicado. None se o stat não muda o DPS do
    ataque básico (ex.: Vel. Movimento). frac = valor/PCT (900 -> 0.9 = +90%).
    Modelo simples: trata o bônus como multiplicativo sobre o stat final
    (AttackSpeed/AttackDamage) ou aditivo no pool per-mille (crítico)."""
    s = dict(stats)
    if stat == "AttackSpeed":
        s["AttackSpeed"] = (stats.get("AttackSpeed") or 0) * (1 + frac)
    elif stat == "AttackDamage":
        s["AttackDamage"] = (stats.get("AttackDamage") or 0) * (1 + frac)
    elif stat == "CriticalChance":
        s["CriticalChance"] = (stats.get("CriticalChance") or 0) + frac * PCT
    elif stat == "CriticalDamage":
        s["CriticalDamage"] = (stats.get("CriticalDamage") or 0) + frac * PCT
    else:
        return None
    return s


# marcadores (en-US) de skills de UTILIDADE: curam/revivem/escudam — NÃO dão
# dano, mesmo com delivery AOE (Sanctuary regenera HP, Aegis bloqueia dano).
_UTIL_MARKERS = ("regenerate", "restore", "revive", "rise again",
                 "blocks ", "protective aura")


def _is_damage_skill(row: dict) -> bool:
    """True se a skill dá dano direto. Cura/revive/escudo/regen = False."""
    deliv = (row.get("DamageDeliveryType") or "").strip()
    if not deliv or deliv == "None":
        return False                       # Heal, Resurrection, Unyielding Will
    desc = ((row.get("SkillDescriptionKey_i18n") or {}).get("en-US") or "").lower()
    return not any(m in desc for m in _UTIL_MARKERS)


def _util_kind(row: dict) -> str:
    desc = ((row.get("SkillDescriptionKey_i18n") or {}).get("en-US") or "").lower()
    if "revive" in desc or "rise again" in desc:
        return "reviver"
    if "blocks " in desc or "protective" in desc:
        return "escudo"
    return "cura"


def hero_damage(gd: GameData, save: dict, hero_save: dict, stats: dict):
    """DPS de ataque basico + skills de cooldown equipadas.

    Skills de BUFF (SkillBuffType="Buff", ex.: Surto Veloz = +90% Vel. Ataque)
    NÃO contam como dano — elas escalam o DPS do ataque básico enquanto ativas.
    A duração do buff não está no datamine/wiki; o uptime médio é ESTIMADO de
    Param1/100 (convenção do status_effects) e marcado como estimativa."""
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
    buffs_detail = []
    utility_detail = []
    buff_dps = 0.0
    cast = max((stats.get("CastSpeed") or 100) / 100.0, 0.1)
    cdr = min((stats.get("CooldownReduction") or 0) / PCT, 0.75)
    for sk in hero_save.get("equippedSKillKey") or []:
        row = gd.skills.get(sk)
        act = row.get("ACTIVATIONTYPE") if row else None
        # COOLDOWN: dispara por tempo; BASEATTACK_COUNT: a cada N ataques básicos
        if act not in ("COOLDOWN", "BASEATTACK_COUNT"):
            continue
        cd = row.get("ActivationValue") or 0   # COOLDOWN: seg | BASEATTACK_COUNT: nº ataques
        lvl_rows = gd.skill_levels.get(row.get("SkillLevelKey"))
        if not lvl_rows or cd <= 0:
            continue
        lvl = _skill_level(gd, save, hero_save["heroKey"], sk)
        val = lvl_rows.get(lvl) or lvl_rows.get(max(lvl_rows)) or 0

        # --- skill de BUFF (não é dano): escala o DPS do ataque básico ---
        if row.get("SkillBuffType") == "Buff":
            if act != "COOLDOWN":
                continue   # buff por contagem de ataque (Skewer/Shock Bolt): stacking complexo
            frac = val / PCT                     # 900 -> 0.9 (+90%)
            p1 = row.get("Param1")
            dur = (p1 / 100.0) if p1 else None   # duração ESTIMADA (não datada)
            uptime = min(1.0, dur / cd) if (dur and cd > 0) else None
            for b in _skill_buffs(gd, row.get("BuffGroupKey")):
                st = b.get("STATTYPE")
                buffed = _stats_with_buff(stats, st, frac)
                active = avg = None
                if buffed is not None:
                    _, a2 = _auto_dps_from(buffed, base_skill)
                    active = a2                  # DPS do básico com buff ativo
                    if uptime is not None:
                        avg = (a2 - auto) * uptime
                        buff_dps += avg
                buffs_detail.append({
                    "key": sk,
                    "name": _name(row.get("SkillNameKey_i18n")) or f"Skill {sk}",
                    "level": lvl, "stat": _STAT_PT.get(st, st), "statType": st,
                    "mod": b.get("MODTYPE"), "pct": round(val / 10.0, 1),
                    "cooldown": cd,
                    "durEst": round(dur, 1) if dur else None,
                    "uptime": round(uptime * 100) if uptime is not None else None,
                    "dpsActive": round(active, 1) if active else None,
                    "dpsAvg": round(avg, 1) if avg is not None else None,
                    "affectsDps": buffed is not None,
                })
            continue

        # --- skill de UTILIDADE (cura/revive/escudo): NÃO é dano ---
        if not _is_damage_skill(row):
            desc = ((row.get("SkillDescriptionKey_i18n") or {}).get("en-US") or "").lower()
            # cura = {0}% do HP MÁX do alvo. Escala do Value igual aos outros
            # skills (validado nos buffs): %% mostrado = val/10; fração = val/PCT.
            heal_pct = heal_amt = heal_bonus = None
            if "restore" in desc and "hp" in desc and "%" in desc:
                heal_pct = round(val / 10.0, 1)                 # 180 -> 18.0%
                # +% de cura da ÁRVORE/gear (SkillHealIncrease): mesma escala /PCT
                # dos outros "increase" (validado p/ dano). 297.5 -> +29.75%.
                boost = (stats.get("SkillHealIncrease") or 0) / PCT
                heal_amt = round(val / PCT * (stats.get("MaxHp") or 0) * (1 + boost))
                heal_bonus = round(boost * 100, 1) if boost else None
            # recarga efetiva (recarga/cast da healer = cura mais vezes)
            cd_eff = (cd * (1 - cdr) / cast) if (act == "COOLDOWN" and cast > 0) else cd
            utility_detail.append({
                "key": sk,
                "name": _name(row.get("SkillNameKey_i18n")) or f"Skill {sk}",
                "level": lvl, "kind": _util_kind(row),
                "cooldown": round(cd_eff, 2), "cooldownBase": cd,
                "healPct": heal_pct, "healAmount": heal_amt, "healBonus": heal_bonus,
            })
            continue

        # --- skill de DANO ---
        # delivery pode vir composto ("Projectile, AOE"): usa o primeiro
        sdel = (row.get("DamageDeliveryType") or "").split(",")[0].strip()
        if not sdel or sdel == "None":
            sdel = delivery
        selem = row.get("DamageType") or element
        per_cast = ad * (val / PCT) * crit * _dmg_bonus(stats, sdel, selem)
        if act == "COOLDOWN":
            # cooldown recarrega mais rapido com Cast Speed; CDR por cima
            cd_eff = cd * (1 - cdr) / cast
            dps_i = per_cast / cd_eff if cd_eff > 0 else 0.0
            extra = {"cooldownBase": cd, "cooldown": round(cd_eff, 2)}
        else:  # BASEATTACK_COUNT: dispara a cada `cd` ataques -> taxa = aps/cd por seg
            rate = (aps / cd) if cd > 0 else 0.0
            dps_i = per_cast * rate
            extra = {"everyAttacks": cd}
        skill += dps_i
        skills_detail.append({
            "key": sk,
            "name": _name(row.get("SkillNameKey_i18n")) or f"Skill {sk}",
            "level": lvl, "perCast": round(per_cast, 1),
            "dps": round(dps_i, 1), "element": selem, "delivery": sdel,
            **extra,
        })

    return {"statusDps": status_dps, "autoDps": auto, "skillDps": skill,
            "dps": auto + skill,
            "buffDps": round(buff_dps, 1),
            "dpsBuffed": round(auto + skill + buff_dps, 1),
            "delivery": delivery, "element": element,
            "breakdown": {
                "auto": {"statusDps": round(status_dps, 1),
                         "bonusMult": round(auto_bonus, 3),
                         "dps": round(auto, 1), "element": element,
                         "delivery": delivery},
                "skills": skills_detail,
                "buffs": buffs_detail,
                "utility": utility_detail,
            }}


def mitigation(armor: float, stage_level: int, damage: float):
    """Formula exata de armadura da wiki, com pierce de hits grandes."""
    a = max(armor, 0.0)
    thr = 14.0 * max(stage_level, 1) + 12.0
    denom = a * a + thr * (a + 0.4 * max(damage, 0.0))
    red = (a * a) / denom if denom > 0 else 0.0
    return min(red, 0.75)


# "Elemental" = fogo/gelo/raio. CHAOS é separado e NÃO é coberto por
# AllElementalResistance (só por ChaosResistance). Armadura só corta físico.
_ELEMENTAL = ("Fire", "Cold", "Lightning")
_RES_CAP = 75.0  # teto padrão de resistência (%); MaxXResistance aumenta
# Penalidade de resistência ELEMENTAL por dificuldade (subtrai da resistência
# antes do cap de 75%). Confirmado pelo usuário: NM −20, Hell −40.
# TORMENT −60 é PROVISÓRIO (padrão +20/tier; ainda não confirmado in-game).
_DIFF_RES_PENALTY = {"NORMAL": 0.0, "NIGHTMARE": 20.0, "HELL": 40.0, "TORMENT": 60.0}
_DIFF_TORMENT_CONFIRMED = False  # quando souber o real, atualizar e marcar True
_DIFF_PENALTY_HITS_CHAOS = False  # penalidade é elemental; chaos não é afetado
# Alvo de sobrevivência: aguentar este nº de golpes do pior elemento = "passa"
# (mesmo limiar do veredito em combat_focus: <3 arriscado, <5 apertado, >=5 ok).
COMBAT_TARGET_HITS = 5


def _taken_fraction(stats: dict, stage_level: int, hit: float, el: str,
                    penalty: float) -> float:
    """Fração do golpe `hit` (do elemento `el`) que passa: físico pela armadura,
    elemental/chaos pela resistência linear (com penalidade e teto)."""
    if el == "Physical":
        return 1 - mitigation(stats.get("Armor") or 0, stage_level, hit)
    res = stats.get(f"{el}Resistance") or 0
    if el in _ELEMENTAL:        # chaos NÃO recebe AllElementalResistance
        res += stats.get("AllElementalResistance") or 0
    if el in _ELEMENTAL or _DIFF_PENALTY_HITS_CHAOS:
        res -= penalty          # penalidade de dificuldade (não atinge chaos)
    cap = _RES_CAP + (stats.get(f"Max{el}Resistance") or 0)
    res = min(res, cap)         # teto: 75% padrão, MaxXResistance sobe o cap
    return max(1 - res / 100.0, 0.0) if res >= 0 else 1 + abs(res) / 100.0


def _final_mult(stats: dict) -> float:
    """DamageReduction = multiplicador do dano final ×(1 − DR). (DamageAbsorption
    NÃO é %: é flat, subtraído à parte no hero_ehp.)"""
    dr = min((stats.get("DamageReduction") or 0) / PCT, 0.9)
    return 1 - dr


def hero_ehp(stats: dict, stage_level: int, hit: float, elements, difficulty=None):
    """EHP contra um estagio: HP / fracao de dano que passa.

    `elements` aceita:
      - list[str]: usa o `hit` escalar pra todos, com PESO IGUAL (legado).
      - dict{elemento: golpe}: golpe próprio de cada elemento, MÉDIA PONDERADA
        pelo tamanho do golpe — o físico costuma ser o MAIOR e não pode ser
        ignorado (senão a armadura some do cálculo). Esse é o caminho usado
        pra ranquear gear e pra mostrar o EHP do herói.

    difficulty (NORMAL/NIGHTMARE/HELL/TORMENT): aplica penalidade de resistência
    da fase (mapas mais difíceis reduzem sua resistência elemental)."""
    hp = stats.get("MaxHp") or 0
    penalty = _DIFF_RES_PENALTY.get(difficulty, 0.0)
    drm = _final_mult(stats)                              # ×(1 − DamageReduction)
    absorb = (stats.get("DamageAbsorption") or 0) / 10.0  # FLAT (físico), escala /10

    def taken_frac(el, h):
        # pipeline real: resist/armadura -> ×(1-DR) -> Absorption (subtrai flat de
        # QUALQUER dano, incl. elemental) -> piso de 1 de dano por golpe. Absorption
        # é forte contra golpe PEQUENO e quase nada contra golpe grande (por ser flat).
        frac = _taken_fraction(stats, stage_level, h, el, penalty)
        if h <= 0:                                        # sem golpe real (testes): só a fração
            return frac * drm
        amt = max(h * frac * drm - absorb, 1.0)           # absorção flat + piso 1 por golpe
        return amt / h

    if isinstance(elements, dict):
        # dict {elemento: golpe}: média do "taken" PONDERADA pelo golpe — o
        # físico costuma ser o MAIOR; ignorá-lo apagaria a armadura do cálculo.
        pairs = [(el, h) for el, h in elements.items() if h and h > 0]
        if not pairs:
            pairs = [("Physical", hit or 1.0)]
        num = sum(h * taken_frac(el, h) for el, h in pairs)
        den = sum(h for _, h in pairs)
        avg_taken = num / den if den else 1.0
    else:
        # lista[str] (legado): mesmo golpe escalar pra todos, PESO IGUAL
        els = elements or ["Physical"]
        avg_taken = sum(taken_frac(el, hit) for el in els) / len(els)
    return hp / max(avg_taken, 0.01)


def resist_needed(stats: dict, stage_level: int, hit: float, el: str,
                  target_hits: float, difficulty=None):
    """Quantos PONTOS de resistência de `el` faltam pro herói aguentar
    `target_hits` golpes desse elemento nesta fase. Mesma conta do hero_ehp,
    invertida: taken = (1 - res/100)·(1 - dr), golpes = HP / (taken·golpe).

    Devolve None se já aguenta, se for físico (não tem como subir resist) ou
    se não há dado. Senão {points, capped, resNow, resTarget}:
      - capped=True: nem chegando no teto (75% + MaxXResistance) aguenta só com
        resist — precisa de HP/DamageReduction/MaxXResistance também."""
    if el == "Physical" or hit <= 0 or target_hits <= 0:
        return None
    hp = stats.get("MaxHp") or 0
    if hp <= 0:
        return None
    fm = _final_mult(stats)   # (1-DR)·(1-Absorption): reduções de dano final
    if fm <= 0:
        return None
    penalty = _DIFF_RES_PENALTY.get(difficulty, 0.0)
    res = stats.get(f"{el}Resistance") or 0
    if el in _ELEMENTAL:
        res += stats.get("AllElementalResistance") or 0
    if el in _ELEMENTAL or _DIFF_PENALTY_HITS_CHAOS:
        res -= penalty
    cap = _RES_CAP + (stats.get(f"Max{el}Resistance") or 0)
    res_eff = min(res, cap)
    taken_cur = (max(1 - res_eff / 100.0, 0.0) if res_eff >= 0
                 else 1 + abs(res_eff) / 100.0) * fm
    hits_cur = hp / max(taken_cur, 1e-9) / hit
    if hits_cur >= target_hits:
        return None
    # fração de dano alvo p/ aguentar target_hits, e a resist efetiva que a dá
    taken_tgt = hp / (target_hits * hit)
    res_tgt = 100.0 * (1 - taken_tgt / fm)
    if res_tgt > cap:                 # nem no teto aguenta só com resist
        return {"points": max(0, round(cap - res_eff)), "capped": True,
                "resNow": round(res_eff), "resTarget": round(cap)}
    return {"points": max(0, round(res_tgt - res_eff)), "capped": False,
            "resNow": round(res_eff), "resTarget": round(res_tgt)}


# ---------------------------------------------------------------------------
# Calibracao por regressao (amostras MANUAIS cronometradas pelo usuario)
# NOTA: a derivacao automatica de amostras a partir do totalClears do save
# foi removida — aquele contador conta varias vezes por run e gerava tempos
# ~5x menores que o real (confirmado contra o Records do jogo).
# ---------------------------------------------------------------------------
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
    """Rendimento offline no estagio atual + melhor estagio para estacionar.

    `rate(lvl)` = recompensa offline POR HORA (BaseX x KillCount x bonus),
    VALIDADO contra o popup do jogo (~38,3M exp/h e ~2,1M gold/h no nivel 67).
    O total ate o cap = rate x capHours (8h). [antes o codigo tratava esse
    valor como o total de 8h e dividia por 8 — subestimava o offline em 8x.]"""
    unlocked = runes.get("UnlockOfflineReward", 0) > 0
    gb = runes.get("OfflineRewardGoldPercent", 0) / PCT
    eb = runes.get("OfflineRewardExpPercent", 0) / PCT
    cap_h = OFFLINE_CAP_SEC / 3600
    table = {r["StageLevel"]: r for r in gd.offline_rewards}

    def rate(lvl):
        row = table.get(lvl)
        if not row:
            return None
        return {"gold": row["BaseGold"] * row["KillCount"] * (1 + gb),
                "exp": row["BaseExp"] * row["KillCount"] * (1 + eb)}

    cur = rate(current_lvl)
    park = None
    for r in farm_rows:
        if not r.get("cleared") and not r.get("current"):
            continue  # nao estacione onde voce ainda nao limpou
        f = rate(r["lvl"])
        if f and (park is None or f["gold"] > park["gold"]):
            park = {"key": r["key"], "label": r["label"], "tag": r["tag"],
                    "name": r["name"], "lvl": r["lvl"],
                    "gold": f["gold"], "exp": f["exp"]}
    return {
        "unlocked": unlocked,
        "capHours": cap_h,
        "goldBonusPct": round(gb * 100),
        "expBonusPct": round(eb * 100),
        # current.gold/exp = total ate o cap de 8h; *PerHour = taxa por hora
        "current": ({"gold": round(cur["gold"] * cap_h),
                     "exp": round(cur["exp"] * cap_h),
                     "goldPerHour": round(cur["gold"]),
                     "expPerHour": round(cur["exp"])} if cur else None),
        "park": ({**park, "gold": round(park["gold"] * cap_h),
                  "exp": round(park["exp"] * cap_h)} if park else None),
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


# Papel de cada heroi -> peso de DPS no "power" do comparador de gear.
# Tank prioriza EHP (sobreviver); DPS prioriza dano. Knight/Priest = tank;
# Ranger/Sorcerer = dps. Hunter/Slayer = dps por padrao (ajustavel).
HERO_ROLE = {101: "tank", 401: "healer",     # Knight=tank, Priest=healer
             201: "dps", 301: "dps",         # Ranger, Sorcerer
             501: "dps", 601: "dps"}          # Hunter, Slayer
# peso do eixo OFENSIVO no power (resto = EHP). DPS prioriza dano; tank prioriza
# EHP (agressivo); healer pesa cura (eixo ofensivo = ritmo de cura, não dano).
ROLE_WDPS = {"tank": 0.25, "dps": 0.75, "healer": 0.5}


def _heal_rate(stats: dict) -> float:
    """Ritmo de cura relativo da Priest: sobe com Cast Speed e Recarga (CDR) —
    eles fazem ela curar mais VEZES — e com SkillHealIncrease, que aumenta o
    TAMANHO de cada cura (ex.: +87,5% na Priest). Assim o advisor valoriza gear
    de cura/recarga na healer."""
    cast = max((stats.get("CastSpeed") or 100) / 100.0, 0.1)
    cdr = min((stats.get("CooldownReduction") or 0) / PCT, 0.75)
    heal_boost = 1 + (stats.get("SkillHealIncrease") or 0) / PCT
    return cast / (1 - cdr) * heal_boost


def _offense_axis(role: str, dmg: dict, stats: dict) -> float:
    """Eixo 'ofensivo' do power por papel: healer = ritmo de cura; resto = DPS."""
    return _heal_rate(stats) if role == "healer" else (dmg.get("dps") or 0.0)


def _power(off: float, ehp: float, w_off: float = 0.5):
    """Media geometrica PONDERADA do eixo ofensivo (DPS ou cura) e EHP.
    w=0.5 = sqrt; tank usa w baixo (mais EHP), DPS usa w alto."""
    d, e = max(off, 0.0), max(ehp, 0.0)
    if d <= 0 or e <= 0:
        return 0.0
    return d ** w_off * e ** (1 - w_off)


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


# elementos do "cenário neutro" do advisor GERAL: perfil equilibrado (físico +
# os 3 elementais + chaos com o MESMO golpe) — assim armadura/HP/cada resist
# contam parelho e o upgrade vale "no geral", independente da fase atual.
_NEUTRAL_ELEMS = ("Physical", "Fire", "Cold", "Lightning", "Chaos")


def _hero_gear_eval(gd: GameData, save: dict, hs: dict, runes: dict):
    """Precomputa, por slot do herói, o item atual e os candidatos do inventário
    (com stats e dano JÁ calculados). NÃO depende da fase — o EHP/power é
    calculado depois, por cenário (geral ou por fase). Items equipados em OUTRO
    herói do time ficam de fora (não dá pra usar em dois lugares)."""
    item_by_uid = {it["UniqueId"]: it for it in save.get("itemSaveDatas") or []}
    equipped_all = {uid for h in save.get("heroSaveDatas") or []
                    for uid in (h.get("equippedItemIds") or [])
                    if uid and h is not hs}
    hero_row = gd.heroes.get(hs["heroKey"]) or {}
    cur_uids = list(hs.get("equippedItemIds") or [])
    cur_uids += [0] * (10 - len(cur_uids))
    base_stats = collect_hero(gd, save, hs, runes)
    base_dmg = hero_damage(gd, save, hs, base_stats)
    slots = []
    for slot in range(10):
        gt = _slot_gear_type(hero_row, slot)
        if not gt:
            continue
        cur_uid = cur_uids[slot]
        cands = []
        for it in save.get("itemSaveDatas") or []:
            uid = it["UniqueId"]
            if uid == cur_uid or uid in equipped_all:
                continue
            if (gd.items.get(it["ItemKey"]) or {}).get("gear") != gt:
                continue
            trial = cur_uids.copy()
            trial[slot] = uid
            st2 = collect_hero(gd, save, hs, runes, equip_override=trial)
            cands.append((it, st2, hero_damage(gd, save, hs, st2)))
        cur_it = item_by_uid.get(cur_uid)
        slots.append({"slot": slot, "gearType": gt, "curUid": cur_uid,
                      "current": _item_brief(gd, cur_it["ItemKey"]) if cur_it else None,
                      "empty": not cur_uid, "cands": cands})
    return {"heroKey": hs["heroKey"], "cls": hero_row.get("ClassType"),
            "role": HERO_ROLE.get(hs["heroKey"], "dps"),
            "baseStats": base_stats, "baseDmg": base_dmg, "slots": slots}


def _rank_scenario(gd: GameData, ev: dict, scn: dict):
    """Pra um cenário (level/hit/elements/difficulty), devolve a melhor troca de
    cada slot do herói (maior ganho de power)."""
    role = ev["role"]
    w = ROLE_WDPS.get(role, 0.5)
    base_dmg, base_stats = ev["baseDmg"], ev["baseStats"]
    base_ehp = hero_ehp(base_stats, scn["level"], scn["hit"], scn["elements"],
                        difficulty=scn.get("diff"))
    base_power = _power(_offense_axis(role, base_dmg, base_stats), base_ehp, w)
    out = []
    for s in ev["slots"]:
        best = None
        for it, st2, d2 in s["cands"]:
            e2 = hero_ehp(st2, scn["level"], scn["hit"], scn["elements"],
                          difficulty=scn.get("diff"))
            d_power = _power(_offense_axis(role, d2, st2), e2, w) - base_power
            if d_power > 1e-6 and (best is None or d_power > best["dPower"]):
                best = {**_item_brief(gd, it["ItemKey"]),
                        "dPower": round(d_power, 1),
                        "dDps": round(d2["dps"] - base_dmg["dps"], 1),
                        "dEhp": round(e2 - base_ehp, 1),
                        "statDiff": _stat_diff(base_stats, st2)}
        if best:
            out.append({"slot": s["slot"], "gearType": s["gearType"],
                        "current": s["current"], "upgrade": best})
    return {"heroKey": ev["heroKey"], "cls": ev["cls"], "role": role, "wDps": w,
            "basePower": round(base_power, 1), "slots": out}


def gear_advice(gd: GameData, save: dict, fielded_saves: list, runes: dict,
                neutral: dict, stage_scns: list):
    """Dois eixos de recomendação de gear, DESACOPLADOS da fase atual:
      - general: upgrades "diretos" — o item é melhor no geral (cenário neutro);
      - byStage: build pra cada fase selecionável (perfil de dano daquela fase,
        onde aparece o que troca pra AGUENTAR — resist/EHP, mesmo perdendo DPS).
    A parte cara (collect_hero por candidato) roda UMA vez por herói e é
    reaproveitada em todos os cenários."""
    evals = [_hero_gear_eval(gd, save, hs, runes) for hs in fielded_saves]
    general = [_rank_scenario(gd, ev, neutral) for ev in evals]
    by_stage = []
    for scn in stage_scns:
        heroes = [_rank_scenario(gd, ev, scn) for ev in evals]
        by_stage.append({"key": scn["id"], "label": scn.get("label"),
                         "name": scn.get("name"), "tag": scn.get("tag"),
                         "lvl": scn["level"], "diff": scn.get("diff"),
                         "current": bool(scn.get("current")), "heroes": heroes})
    return {"general": general, "byStage": by_stage}


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
            # so a CHANCE sobe; a obtencao real e limitada pelo jogo (cap +
            # auto-abrir), entao o efeito em baus/h tende a ser menor
            cur_mult = drop_n_mult if st.startswith("DropChanceNormal") else drop_b_mult
            tipo = "normal" if st.startswith("DropChanceNormal") else "do boss"
            pct = (cur_mult + v / PCT) / cur_mult * 100 - 100
            return "farm", pct, f"+{pct:.2f}% chance de bau {tipo}"
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

    def unlock_chain(key):
        """Passos (e custo) pra PODER comprar `key`: sobe ate a raiz somando os
        niveis que faltam em cada ancestral cujo gate nao esta satisfeito."""
        steps, cur = [], key
        while True:
            par = parent.get(cur)
            if par is None:
                break
            need = gd.runes[cur].get("PrevNodeRequiredLevel") or 1
            plv = levels.get(par, 0)
            if plv < need:
                rows_p = gd.rune_levels.get(gd.runes[par]["LevelDataKey"]) or {}
                cost = sum((rows_p.get(L) or {}).get("CostValue") or 0
                           for L in range(plv + 1, need + 1))
                steps.append({"key": par,
                              "name": _name(gd.runes[par].get("NameKey_i18n")),
                              "icon": gd.runes[par].get("IconPath"),
                              "fromLevel": plv, "toLevel": need, "cost": cost})
            cur = par
        steps.reverse()
        return steps, sum(s["cost"] for s in steps)

    nodes, edges, recs, unlock_recs = [], [], [], []
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

        # pathfinding: runa bloqueada -> cadeia de desbloqueio + "vale destravar?"
        path = None
        if not unlocked:
            steps, chain_cost = unlock_chain(key)
            path = {"steps": steps, "chainCost": chain_cost}
            first = rows.get(1)
            if first and steps:
                kind, pct, label = gain_for(first["STATTYPE"], first["Value"] or 0)
                total_cost = chain_cost + (first.get("CostValue") or 0)
                if pct is not None and pct > 0 and total_cost > 0:
                    unlock_recs.append({
                        "key": key, "name": _name(r.get("NameKey_i18n")),
                        "icon": r.get("IconPath"), "kind": kind,
                        "pct": round(pct, 3), "label": label,
                        "cost": total_cost, "level": 1,
                        "steps": len(steps),
                        "firstStep": {"key": steps[0]["key"], "name": steps[0]["name"],
                                      "toLevel": steps[0]["toLevel"]},
                        "affordable": total_cost <= (gold_now or 0),
                        "score": pct / total_cost})

        pos = gd.rune_layout.get(key) or {}
        nodes.append({
            "key": key, "name": _name(r.get("NameKey_i18n")),
            "icon": r.get("IconPath"), "stat": st,
            "x": pos.get("x"), "y": pos.get("y"),
            "level": lv, "max": mx, "req": req,
            "unlocked": unlocked, "owned": lv > 0, "maxed": lv >= mx,
            "nextCost": (nxt or {}).get("CostValue"),
            "nextValue": (nxt or {}).get("Value"),
            "perLevel": [{"level": L, "cost": (rows.get(L) or {}).get("CostValue"),
                          "value": (rows.get(L) or {}).get("Value")}
                         for L in range(1, mx + 1)],
            "total": total, "gain": gain, "path": path,
        })
        if par is not None:
            edges.append({"from": par, "to": key, "req": req})

    recs.sort(key=lambda x: x["score"], reverse=True)
    unlock_recs.sort(key=lambda x: x["score"], reverse=True)
    return {
        "nodes": nodes, "edges": edges,
        "gold": gold_now,
        "recommendations": {
            "combate": [x for x in recs if x["kind"] == "combate"][:6],
            "farm": [x for x in recs if x["kind"] == "farm"][:6],
            "destravar": unlock_recs[:5],
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
def combat_focus(gd: GameData, save: dict, fielded_saves: list, runes: dict,
                 rows: list, party_dps: float, max_n: int = 4):
    """Foco automático: fase ATUAL + as próximas NÃO-passadas (dentro do teto).
    Para cada uma: DPS do time, tempo de clear, EHP do herói mais frágil vs a
    fase (já com penalidade de dificuldade), monsterDPS, tempo-até-morrer,
    verdict ('dá pra passar?') e gargalo (defesa)."""
    cur = next((r for r in rows if r.get("current")), None)
    picked = [cur] if cur else []
    for r in rows:
        if r is cur:
            continue
        if r.get("cleared") or r.get("beyondCeiling") or r.get("type") == "ACTBOSS":
            continue
        picked.append(r)
        if len(picked) >= max_n:
            break
    if not picked or not fielded_saves:
        return []
    hstats = [(hs, collect_hero(gd, save, hs, runes)) for hs in fielded_saves]
    out = []
    for r in picked:
        econ = gd.stage_econ(r["key"])
        if not econ:
            continue
        diff = (gd.stages.get(r["key"]) or {}).get("STAGEDIFFICULITY")
        lvl = econ["lvl"]
        elem_hits = econ.get("elemHits") or {"Physical": econ.get("biggestHit") or 0}
        mdps = econ.get("monsterDps") or 0.0
        # sobrevivência é gateada pela LINHA DE FRENTE (tank/healer) — quem toma
        # os hits. DPS de retaguarda (Sorcerer/Ranger) é frágil de propósito e
        # não decide se a fase passa. (sem tank/healer no time -> usa todos)
        front = [(hs, st) for hs, st in hstats
                 if HERO_ROLE.get(hs["heroKey"]) in ("tank", "healer")] or hstats
        # PIOR caso: o elemento que mata mais rápido o front (NÃO a média) — é o
        # chaos/fire que decide, não o físico mitigado pela armadura
        worst = None  # (golpes, st, heroKey, elemento, ehp, golpe)
        for hs, st in front:
            for el, ehit in elem_hits.items():
                if ehit <= 0:
                    continue
                ehp_el = hero_ehp(st, lvl, ehit, [el], difficulty=diff)
                h = ehp_el / ehit
                if worst is None or h < worst[0]:
                    worst = (h, st, hs["heroKey"], el, ehp_el, ehit)
        hits = round(worst[0], 1) if worst else None
        weakest_k = worst[2] if worst else None
        threat = worst[3] if worst else None
        ehp_min = round(worst[4]) if worst else 0
        ct = r.get("clearTime") or 0.0
        rating = r.get("rating")
        # severidade = pior entre dois eixos INDEPENDENTES:
        #  - sobrevivência: golpes que o front aguenta (<3 arriscado, <5 apertado)
        #  - clear lento (rating CALIBRADO): demora a matar = falta dano/tempo
        surv_sev = (2 if hits < 3 else 1 if hits < 5 else 0) if hits is not None else 0
        rate_sev = {"seguro": 0, "apertado": 1, "arriscado": 2}.get(rating, 0)
        sev = max(surv_sev, rate_sev)
        verdict = ["passa", "apertado", "arriscado"][sev]
        # gargalo atribuído ao eixo que mandou: morre cedo -> defesa; só clear
        # lento (sobrevive, mas rating ruim) -> dano. Não rotular "defesa" quando
        # o herói aguenta de boa e o problema é velocidade de kill.
        bottleneck = None if sev == 0 else ("defesa" if surv_sev >= 1 else "dano")
        # quanto de resist falta no herói mais frágil pra deixar de morrer (alvo
        # = TARGET_HITS golpes, o mesmo limiar do veredito "passa"). Só faz
        # sentido quando o gargalo É defesa (clear lento não se resolve com resist).
        need_resist = None
        if worst and threat and bottleneck == "defesa":
            rn = resist_needed(worst[1], lvl, worst[5], threat,
                               COMBAT_TARGET_HITS, difficulty=diff)
            if rn and rn["points"] > 0:
                need_resist = {"element": threat, "hits": COMBAT_TARGET_HITS, **rn}
        out.append({
            "key": r["key"], "label": r["label"], "tag": r["tag"], "name": r["name"],
            "lvl": lvl, "diff": diff, "current": bool(r.get("current")),
            "elements": sorted(elem_hits.keys()),
            "partyDps": round(party_dps), "clearTime": round(ct, 1),
            "ehpMin": ehp_min, "hitsToDie": hits, "threat": threat,
            "weakestHero": (_name((gd.heroes.get(weakest_k) or {}).get("HeroNameKey_i18n"))
                            or str(weakest_k)),
            "verdict": verdict, "bottleneck": bottleneck, "rating": rating,
            "needResist": need_resist,
        })
    return out


# ---------------------------------------------------------------------------
# Builds: loadout atual, catalogo de itens/gems e what-if (recalculo)
# ---------------------------------------------------------------------------
_TYPE_SHORT = {"DECORATION": "deco", "ENGRAVING": "engr", "INSCRIPTION": "inscr"}


def _socket_short_type(gd: GameData, enchant_row: dict):
    """Tipo do socket (deco/engr/inscr) pelo matEffects do material aplicado."""
    det = gd.items_detail.get(enchant_row.get("MaterialKey")) or {}
    t = (det.get("matEffects") or {}).get("type")
    return _TYPE_SHORT.get(t)


def hero_loadout(gd: GameData, save: dict, hero_save: dict):
    """Loadout ATUAL do herói: por slot, item equipado + sockets resolvidos
    (stat/mod/valor já prontos para o what-if e para o paper-doll)."""
    item_by_uid = {it["UniqueId"]: it for it in save.get("itemSaveDatas") or []}
    hero_row = gd.heroes.get(hero_save["heroKey"]) or {}
    uids = list(hero_save.get("equippedItemIds") or [])
    out = []
    for slot in range(10):
        gt = _slot_gear_type(hero_row, slot)
        if not gt:
            continue
        uid = uids[slot] if slot < len(uids) else 0
        it = item_by_uid.get(uid) if uid else None
        if not it:
            out.append({"slot": slot, "gearType": gt, "itemKey": None,
                        "name": None, "grade": None, "level": None, "sockets": []})
            continue
        item = gd.items.get(it["ItemKey"]) or {}
        socks = []
        for e in it.get("EnchantData") or []:
            if not e or not e.get("StatModKey"):
                continue
            sm = gd.stat_mods.get((e["StatModKey"], e.get("Tier"))) or {}
            mat = gd.items.get(e.get("MaterialKey")) or {}
            socks.append({
                "type": _socket_short_type(gd, e),
                "stat": sm.get("STATTYPE"), "mod": sm.get("MODTYPE"),
                "value": e.get("Value") or 0, "tier": e.get("Tier"),
                "gemKey": e.get("MaterialKey"), "gemName": _name(mat.get("name")),
            })
        out.append({"slot": slot, "gearType": gt, "itemKey": it["ItemKey"],
                    "name": _name(item.get("name")), "grade": item.get("grade"),
                    "level": item.get("level"), "sockets": socks})
    return out


def _item_stat_lines(gd: GameData, item: dict):
    """Stats concretos do item (BaseStat + Inherent) com mod e VALOR reais
    (do gear.json) — p/ o tooltip mostrar cada stat com seu número."""
    out = []
    gear = gd.gear.get(item.get("id"))
    gt = gd.gear_types.get(item.get("gear"))
    if gt and gear:
        for n in (1, 2):
            st = gt.get(f"BaseStat{n}_STATTYPE")
            v = gear.get(f"BaseStat{n}_Value") or 0
            if st and st != "NONE" and v:
                out.append({"stat": st, "mod": gt.get(f"BaseStat{n}_MODTYPE"), "value": v})
    if gear:
        for i in (1, 2, 3):
            st = gear.get(f"InherentStat{i}_STATTYPE")
            v = gear.get(f"InherentStat{i}_Value") or 0
            if st and st != "NONE" and v:
                out.append({"stat": st, "mod": gear.get(f"InherentStat{i}_MODTYPE"), "value": v})
    return out


def build_catalog(gd: GameData):
    """Catalogo p/ a pagina de Builds: itens equipaveis por tipo de gear e gems
    (decoracao/gravacao/inscricao) com efeito por categoria. So depende do
    datamine — montado uma vez."""
    items = {}
    for i in gd.items.values():
        gt = i.get("gear")
        if not gt or i.get("deleted"):   # deleted=Obtainable:False (jogo removeu)
            continue
        lines = _item_stat_lines(gd, i)
        items.setdefault(gt, []).append({
            "itemKey": i["id"], "name": _name(i.get("name")),
            "grade": i.get("grade"), "level": i.get("level"), "gearType": gt,
            "stats": sorted({l["stat"] for l in lines}),  # tipos p/ filtro de buff
            "statLines": lines,                            # stat+mod+valor p/ tooltip
        })
    for gt in items:
        items[gt].sort(key=lambda x: ((x["level"] or 0), x["name"] or ""))

    gems = {"deco": [], "engr": [], "inscr": []}
    for k, det in gd.items_detail.items():
        me = (det or {}).get("matEffects")
        if not me:
            continue
        short = _TYPE_SHORT.get(me.get("type"))
        if not short:
            continue
        item = gd.items.get(k) or {}
        if item.get("deleted"):          # gem removido do jogo (Obtainable:False)
            continue
        groups = {}
        for cat, rows in (me.get("groups") or {}).items():
            if rows:
                r = rows[0]
                groups[cat] = {"stat": r.get("stat"), "mod": r.get("mod"),
                               "min": r.get("min"), "max": r.get("max"),
                               "tier": r.get("tier")}
        gems[short].append({
            "itemKey": k, "name": _name(item.get("name")) or det.get("name"),
            "grade": item.get("grade"), "groups": groups,
        })
    for t in gems:
        gems[t].sort(key=lambda x: x["name"] or "")
    return {"items": items, "gems": gems,
            "slotsByGrade": {g: {"deco": v.get("ExtraSlotAmount_Decoration", 0),
                                 "engr": v.get("ExtraSlotAmount_Engraving", 0),
                                 "inscr": v.get("ExtraSlotAmount_Inscription", 0)}
                             for g, v in gd.grades.items()}}


def current_stage_ctx(gd: GameData, save: dict):
    """Contexto da fase atual (nível/golpe/elementos/dificuldade) p/ o EHP do
    what-if — mesma referência que o simulate usa pro time."""
    cs = save.get("commonSaveData") or {}
    key = cs.get("currentStageKey")
    econ = gd.stage_econ(key)
    return {"stageKey": key,
            "level": econ["lvl"] if econ else 1,
            "hit": econ["biggestHit"] if econ else 0,
            "elems": (econ.get("elemHits") if econ else None) or None,
            "diff": (gd.stages.get(key) or {}).get("STAGEDIFFICULITY")}


def whatif_hero(gd: GameData, save: dict, hero_save: dict, runes: dict,
                loadout: list, ctx: dict | None = None):
    """Recalcula dps/ehp/stats de um herói com um loadout HIPOTÉTICO (itens +
    gems). Mesmo motor do save — só troca a fonte do gear."""
    ctx = ctx or current_stage_ctx(gd, save)
    stats = collect_hero(gd, save, hero_save, runes, loadout=loadout)
    dmg = hero_damage(gd, save, hero_save, stats)
    ehp = hero_ehp(stats, ctx["level"], ctx["hit"], ctx["elems"],
                   difficulty=ctx.get("diff"))
    return {"dps": round(dmg["dps"], 1), "statusDps": round(dmg["statusDps"], 1),
            "autoDps": round(dmg["autoDps"], 1), "skillDps": round(dmg["skillDps"], 1),
            "ehp": round(ehp, 1), "damage": dmg["breakdown"],
            "stats": {k: round(v, 2) for k, v in stats.items()}}


def simulate(gd: GameData, save: dict, measured: dict | None = None,
             samples: list | None = None, stage_stats: dict | None = None,
             ceiling: int | None = None):
    """Estado de combate do time + tabela de farm com taxas reais.

    measured (opcional): taxas medidas entre saves:
      {'goldPerSec': x, 'expPerSec': y, 'expPerHourByHero': {nome: v}}
    samples (opcional): amostras de clear persistidas (store.py) para a
    calibracao por regressao - a melhor fonte de verdade do modelo.
    ceiling (opcional): chave da fase mais alta que o jogador FARMA com
    confianca (o "highest reliable clear" da wiki). Nada acima do teto entra
    em recomendacao — o jogo libera fases que o jogador ainda nao aguenta.
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
    cur_diff = (gd.stages.get(cur_key) or {}).get("STAGEDIFFICULITY")  # NM/HELL/...
    cur_econ = gd.stage_econ(cur_key)
    cur_eff = eff_econ(cur_econ) if cur_econ else None
    ref_level = cur_econ["lvl"] if cur_econ else 1
    ref_hit = cur_econ["biggestHit"] if cur_econ else 0
    # perfil de dano da fase POR ELEMENTO (inclui Físico, o maior golpe) — é o
    # que entra no EHP e no ranqueamento de gear; sem o físico, a armadura some.
    ref_elems = (cur_econ.get("elemHits") if cur_econ else None) or None

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
        ehp = hero_ehp(stats, ref_level, ref_hit, ref_elems, difficulty=cur_diff)
        hero_row = gd.heroes.get(hk) or {}
        heroes.append({
            "key": hk,
            "name": _name(hero_row.get("HeroNameKey_i18n")) or hero_row.get("ClassType"),
            "cls": hero_row.get("ClassType"),
            "role": HERO_ROLE.get(hk, "dps"),
            "level": hs.get("HeroLevel"),
            "dps": dmg["dps"], "autoDps": dmg["autoDps"], "skillDps": dmg["skillDps"],
            "buffDps": dmg["buffDps"], "dpsBuffed": dmg["dpsBuffed"],
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

    # --- baus: a CHANCE por kill vem da wiki (per-mille; ex. 16%/kill normal,
    # 15%/boss), mas a OBTENCAO real e limitada pelo jogo (cap no chao +
    # auto-abrir): observado ~3 baus normais/h vs ~140 que a chance daria.
    # Entao: chance e so referencia; baus/h reais sao MEDIDOS dos contadores
    # do save (Type 16, em compute_rates). Nao converta chance em baus/h.
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
    ceil_idx = (gd.stage_order.index(ceiling)
                if ceiling in gd.stage_order else None)
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
            "beyondCeiling": ceil_idx is not None and idx > ceil_idx,
            "normalBox": box_label(mbk),
            "bossBox": box_label(bbk),
            "normalBoxLvl": (mbk % 1000) // 10 if mbk else 0,
            "bossBoxLvl": (bbk % 1000) // 10 if bbk else 0,
            # chance esperada por clear (referencia da wiki; NAO e baus/h —
            # a obtencao real e limitada pelo jogo e se mede do save)
            "normalBoxPerClear": round(nbox, 3),
            "bossBoxPerClear": round(bbox, 3),
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

    # Recomendacao so entre fases que voce CONSEGUE farmar: nao-ACTBOSS, ja
    # LIMPAS, e DENTRO DO TETO (ceiling) se definido — o jogo libera/marca como
    # "limpa" fase que o jogador passou raspando mas nao aguenta farmar, e o
    # modelo de perigo (EHP) nao enxerga parede de DPS. O teto e a palavra
    # final do jogador. Fallbacks pra nunca ficar sem nada.
    farmable = [r for r in rows
                if r["type"] != "ACTBOSS" and not r["beyondCeiling"]]
    cleared_farm = [r for r in farmable if r["cleared"]] or farmable
    pool = [r for r in cleared_farm if r["rating"] != "arriscado"] or cleared_farm
    best_gold = max(pool, key=lambda r: r["goldPerHour"], default=None)
    best_exp = max(pool, key=lambda r: r["expPerHour"], default=None)
    # "push" = proxima fase nao-limpa, SO se "seguro" e dentro do teto
    push = next((r for r in rows
                 if not r["cleared"] and not r["beyondCeiling"]), None)
    if push and push.get("rating") != "seguro":
        push = None

    # rota de baus: como a obtencao e limitada pelo jogo (taxa ~igual em
    # qualquer fase que voce mate rapido), o que importa e o NIVEL do bau:
    # melhor fase limpa = bau de nivel mais alto; clear mais rapido desempata.
    box_pool = [r for r in cleared_farm if r["cleared"]]
    best_boss_box = max((r for r in box_pool if r["bossBoxLvl"] > 0),
                        key=lambda r: (r["bossBoxLvl"], -r["clearTime"]),
                        default=None)
    best_normal_box = max((r for r in box_pool if r["normalBoxLvl"] > 0),
                          key=lambda r: (r["normalBoxLvl"], -r["clearTime"]),
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
        cur_lv = h["level"] or 1
        need = gd.levels.get(cur_lv)
        eps = hero_eps(h)
        if need is not None and cur_lv < 100:
            missing = max(need - (hs.get("HeroExp") or 0), 0)
            # "level" = nivel que vai ALCANCAR (cur+1); o eta/exp e ate la
            eta.append({"key": h["key"], "level": cur_lv + 1, "fromLevel": cur_lv,
                        "expToNext": missing,
                        "etaSec": missing / eps if eps > 0 else None})
        proj = project_levels(gd, cur_lv, hs.get("HeroExp") or 0, eps,
                              stage_lvl=cur_econ["lvl"] if cur_econ else None)
        if proj:
            projection.append({"key": h["key"], "name": h["name"],
                               "cls": h["cls"], **proj})

    # --- offline, combate e gear
    offline = offline_info(gd, runes, ref_level, rows)
    fielded_saves = [hero_saves[hk] for hk in fielded if hk in hero_saves]
    combat = combat_focus(gd, save, fielded_saves, runes, rows, party_dps)
    # gear DESACOPLADO da fase: (a) cenário neutro = upgrades "diretos"; (b) um
    # cenário por fase do combate (atual + próximas não-passadas) = build pra
    # aguentar AQUELA fase. golpe de referência p/ o neutro: o da fase atual.
    neutral_hit = ref_hit or 1.0
    neutral_scn = {"id": "neutral", "level": ref_level or party_level,
                   "hit": neutral_hit, "diff": None,
                   "elements": {el: neutral_hit for el in _NEUTRAL_ELEMS}}
    # fases selecionáveis no "build pra fase": janela em torno da fase ATUAL —
    # 3 pra trás + a atual + 5 pra frente (planejar o próximo push). gear_advice
    # precomputa os candidatos UMA vez e só re-pontua o EHP por cenário.
    sel_keys, seen_k = [], set()
    for r in rows:
        if r.get("type") == "ACTBOSS":
            continue
        if r["key"] not in seen_k:
            seen_k.add(r["key"]); sel_keys.append(r["key"])
    sel_keys.sort()
    if cur_key in sel_keys:
        ci = sel_keys.index(cur_key)
        sel_keys = sel_keys[max(0, ci - 3):ci + 6]   # 3 atrás + atual + 5 à frente
    else:
        sel_keys = sel_keys[:9]
    stage_scns = []
    for k in sel_keys:
        e = gd.stage_econ(k)
        if not e:
            continue
        stage_scns.append({
            "id": k, "label": e["label"], "name": e["name"], "tag": e["tag"],
            "level": e["lvl"], "hit": e["biggestHit"] or neutral_hit,
            "elements": e["elemHits"], "diff": e["diff"], "current": k == cur_key})
    gear = gear_advice(gd, save, fielded_saves, runes, neutral_scn, stage_scns)

    # --- arvore de runas + recomendacao de compra
    gold_now = next((c.get("Quantity") for c in save.get("currenySaveDatas") or []
                     if c.get("Key") == GOLD_KEY), 0)
    runes_tree = rune_advisor(
        gd, save, runes,
        fielded_saves=fielded_saves, ref_level=ref_level, ref_hit=ref_hit,
        elements=ref_elems,
        cur_eff=cur_eff,
        ct=cur_row["clearTime"] if cur_row else None,
        gold_ph=cur_row["goldPerHour"] if cur_row else None,
        exp_ph=cur_row["expPerHour"] if cur_row else None,
        gold_mult=gold_mult, exp_mult=exp_mult,
        drop_n_mult=drop_n_mult, drop_b_mult=drop_b_mult,
        t_wave=t_wave, gold_now=gold_now)

    # --- builds: TODOS os heróis do save (em campo + reserva), com loadout
    # atual e métricas — base pra página de Builds (roster + paper-doll).
    fielded_set = set(fielded)
    builds = []
    for hs in save.get("heroSaveDatas") or []:
        hk = hs.get("heroKey")
        hr = gd.heroes.get(hk) or {}
        b_stats = collect_hero(gd, save, hs, runes)
        b_dmg = hero_damage(gd, save, hs, b_stats)
        b_ehp = hero_ehp(b_stats, ref_level, ref_hit, ref_elems, difficulty=cur_diff)
        builds.append({
            "key": hk,
            # nome em inglês na página de Builds (ClassType = Ranger/Knight/...)
            "name": hr.get("ClassType") or _name(hr.get("HeroNameKey_i18n"), "en-US"),
            "cls": hr.get("ClassType"), "role": HERO_ROLE.get(hk, "dps"),
            "level": hs.get("HeroLevel"), "fielded": hk in fielded_set,
            "dps": round(b_dmg["dps"], 1), "statusDps": round(b_dmg["statusDps"], 1),
            "ehp": round(b_ehp, 1), "damage": b_dmg["breakdown"],
            "stats": {k: round(v, 2) for k, v in b_stats.items()},
            "loadout": hero_loadout(gd, save, hs),
        })

    # itens/gems POSSUÍDOS (ItemKeys do inventário) — p/ "tenho"/só-inventário
    owned = sorted({it.get("ItemKey") for it in save.get("itemSaveDatas") or []
                    if it.get("ItemKey")})

    result = {
        "heroes": heroes,
        "builds": builds,
        "owned": owned,
        "buildsStage": {"key": cur_key, "level": ref_level, "diff": cur_diff},
        "party": {"dps": party_dps, "ehpMin": party_ehp_min,
                  "size": len(heroes), "level": party_level},
        "calibration": calib,
        "goldBonusPct": round((gold_mult - 1) * 100),
        "expBonusPct": round((exp_mult - 1) * 100),
        "farm": {"rows": rows, "current": cur_row, "bestGold": best_gold,
                 "bestExp": best_exp, "push": push, "ceiling": ceiling,
                 "bestBossBox": best_boss_box, "bestNormalBox": best_normal_box,
                 "dropBonus": {"normal": drop_n, "boss": drop_b}},
        "levelEta": eta,
        "projection": projection,
        "offline": offline,
        "gear": gear,
        "combat": combat,
        "runes": runes_tree,
        "econScale": {"global": round(global_scale, 3),
                      "stages": {str(k): round(v, 3) for k, v in scales.items()}},
    }
    try:
        result["alchemy"] = alchemy_panel(gd, save, runes)
    except Exception:
        result["alchemy"] = None
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
    eta_by_key = {e["key"]: e for e in (sim.get("levelEta") or [])}
    for pr in (sim.get("projection") or [])[:4]:
        h24 = pr["horizons"].get("24")
        e = eta_by_key.get(pr["key"])
        if e and e.get("etaSec"):
            # tempo ate o PROXIMO nivel inteiro (e['level']) + onde estara em 24h
            msg = (f"No ritmo medido, {pr['name']} chega ao nível {e['level']} "
                   f"em ~{_fmt_dur(e['etaSec'])}")
            if h24 is not None:
                msg += f" e estará em ~{h24:.1f} em 24h"
            out.append(msg + ".")
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

    # 5. quick wins de gear — upgrades "diretos" (cenário neutro, indep. da fase)
    swaps = [(h["cls"], s) for h in (sim.get("gear") or {}).get("general") or []
             for s in h["slots"] if s.get("upgrade")]
    if swaps:
        swaps.sort(key=lambda x: -x[1]["upgrade"]["dPower"])
        cls, s = swaps[0]
        up = s["upgrade"]
        extra = f" (+{len(swaps) - 1} troca(s) menores)" if len(swaps) > 1 else ""
        out.append(f"Gear: equipar “{up['name']}” ({up['grade']}, lvl {up['level']}) "
                   f"no {cls} dá +{_fmt(up['dPower'])} de power{extra}. "
                   f"Está parado no inventário.")

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
