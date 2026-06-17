import { fmt } from "./format.js";

// nomes amigáveis + unidade certa de cada stat (escala /1000 ou /100 do jogo)
const sign = (d) => (d > 0 ? "+" : "−");
const abs = Math.abs;

const FMT = {
  AttackDamage: (d) => `${sign(d)}${fmt(abs(d))} dano`,
  AttackSpeed: (d) => `${sign(d)}${(abs(d) / 100).toFixed(2)} ataques/s`,
  CastSpeed: (d) => `${sign(d)}${(abs(d) / 10).toFixed(0)}% vel. de cast`,
  CriticalChance: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% crítico`,
  CriticalDamage: (d) => `${sign(d)}${(abs(d) / 10).toFixed(0)}% dano crítico`,
  CooldownReduction: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% recarga`,
  MaxHp: (d) => `${sign(d)}${fmt(abs(d))} HP`,
  Armor: (d) => `${sign(d)}${fmt(abs(d))} armadura`,
  MovementSpeed: (d) => `${sign(d)}${fmt(abs(d))} mov.`,
  BlockChance: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% block`,
  HpRegenPerSec: (d) => `${sign(d)}${(abs(d) / 100).toFixed(1)} regen/s`,
  SkillHealIncrease: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% cura`,
  DamageAbsorption: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)} absorção`,
};

const ELEM_PT = {
  Fire: "fogo", Cold: "gelo", Lightning: "raio",
  Chaos: "caos", Physical: "físico",
};

export function elemPt(el) {
  return ELEM_PT[el] || el;
}

// efeito de runa em pt (valores per-mille viram %, flats ficam crus)
const PM = (v) => (v / 10) % 1 ? (v / 10).toFixed(1) : (v / 10).toFixed(0);

export function runeStatPt(stat, v) {
  const M = {
    AllHeroAttackDamage: `+${fmt(v)} dano (todos os heróis)`,
    AllHeroAttackDamagePercent: `+${PM(v)}% dano (todos)`,
    AllHeroAttackSpeed: `+${PM(v)}% vel. de ataque (todos)`,
    AllHeroArmor: `+${fmt(v)} armadura (todos)`,
    AllHeroArmorPercent: `+${PM(v)}% armadura (todos)`,
    AllHeroMoveSpeed: `+${fmt(v)} velocidade de mov. (todos)`,
    IncreaseGoldAmount: `+${PM(v)}% gold`,
    IncreaseExpAmount: `+${PM(v)}% exp`,
    AdditionalGold: `+${fmt(v)} gold por kill`,
    AdditionalGoldNormalMonster: `+${fmt(v)} gold por monstro normal`,
    AdditionalGoldStageBoss: `+${fmt(v)} gold por boss de fase`,
    AdditionalGoldActBoss: `+${fmt(v)} gold por boss de ato`,
    AdditionalExp: `+${fmt(v)} exp por kill`,
    AdditionalExpNormalMonster: `+${fmt(v)} exp por monstro normal`,
    AdditionalExpStageBoss: `+${fmt(v)} exp por boss de fase`,
    AdditionalExpActBoss: `+${fmt(v)} exp por boss de ato`,
    DropChanceNormalChestPercent: `+${PM(v)}% chance de bau normal`,
    DropChanceStageBossChestPercent: `+${PM(v)}% chance de bau do boss`,
    MaxAmountNormalChest: `+${fmt(v)} cap de baús normais no chão`,
    MaxAmountStageBossChest: `+${fmt(v)} cap de baús de boss no chão`,
    MaxAmountActBossChest: `+${fmt(v)} cap de baús de ato no chão`,
    OfflineRewardGoldPercent: `+${PM(v)}% gold offline`,
    OfflineRewardExpPercent: `+${PM(v)}% exp offline`,
    ReduceAutoOpenNormalChestTime: `−${fmt(v)}s no auto-abrir bau normal`,
    ReduceAutoOpenStageBossChestTime: `−${fmt(v)}s no auto-abrir bau de boss`,
    ReduceAutoOpenActBossChestTime: `−${fmt(v)}s no auto-abrir bau de ato`,
    UnlockOfflineReward: "desbloqueia recompensa offline",
    UnlockAutoOpenNormalChest: "desbloqueia auto-abrir bau normal",
    UnlockAutoOpenStageBossChest: "desbloqueia auto-abrir bau de boss",
    UnlockAutoOpenActBossChest: "desbloqueia auto-abrir bau de ato",
    UnlockArrangeSlotCount: `+${fmt(v)} herói em campo`,
    UnlockSkillSlotCount: `+${fmt(v)} slot de skill`,
    UnlockStashPageCount: `+${fmt(v)} página de stash`,
    MaxInventorySlot: `+${fmt(v)} slots de inventário`,
    OpenAllTypeChestAllAtOnce: "abre todos os tipos de bau de uma vez",
    OpenOneTypeChestAllAtOnce: "abre um tipo de bau inteiro de uma vez",
    CubeAlchemyGoldPercent: `+${PM(v)}% gold de alquimia (cubo)`,
    CubeExpPercent: `+${PM(v)}% exp do cubo`,
    WaveCountReduction: `−${fmt(v)} wave por run`,
  };
  return M[stat] || `${stat} +${fmt(v)}`;
}

export function fmtStatDelta({ stat, delta }) {
  if (FMT[stat]) return FMT[stat](delta);
  const m = stat.match(/^(Fire|Cold|Lightning|Chaos|Physical)DamagePercent$/);
  if (m) return `${sign(delta)}${(abs(delta) / 10).toFixed(0)}% dano de ${ELEM_PT[m[1]]}`;
  if (stat.endsWith("Percent") || stat.startsWith("Increase"))
    return `${sign(delta)}${(abs(delta) / 10).toFixed(1)}% ${stat
      .replace(/Percent$/, "")
      .replace(/^Increase/, "")}`;
  return `${sign(delta)}${fmt(abs(delta))} ${stat}`;
}
