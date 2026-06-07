import { TEAM_ORDER, R16P, QFP, SFP } from '../constants/data';

export function teamFallback(a, b) {
  return (TEAM_ORDER[a.t] || 999) - (TEAM_ORDER[b.t] || 999);
}

export function assignThirds(t3) {
  const slots = [
    { id: "3_ABCDF", gs: ["A", "B", "C", "D", "F"] },
    { id: "3_CDFGH", gs: ["C", "D", "F", "G", "H"] },
    { id: "3_CEFHI", gs: ["C", "E", "F", "H", "I"] },
    { id: "3_EHIJK", gs: ["E", "H", "I", "J", "K"] },
    { id: "3_BEFIJ", gs: ["B", "E", "F", "I", "J"] },
    { id: "3_AEHIJ", gs: ["A", "E", "H", "I", "J"] },
    { id: "3_EFGIJ", gs: ["E", "F", "G", "I", "J"] },
    { id: "3_DEIJL", gs: ["D", "E", "I", "J", "L"] }
  ];
  const used = {}; const result = {};
  function solve(idx) {
    if (idx >= slots.length) return true;
    const sl = slots[idx];
    for (let i = 0; i < t3.length; i++) {
      const tm = t3[i];
      if (used[tm.g]) continue;
      if (sl.gs.indexOf(tm.g) === -1) continue;
      used[tm.g] = true; result[sl.id] = tm.t;
      if (solve(idx + 1)) return true;
      delete used[tm.g]; delete result[sl.id];
    }
    return false;
  }
  solve(0);
  return result;
}

export function getT3FromMatrices(groupMatrices) {
  const thirds = [];
  for (const groupKey in groupMatrices) {
    const row = groupMatrices[groupKey].find((item) => Number(item.Rank) === 3);
    if (row) {
      thirds.push({
        t: row.Team,
        p: Number(row.Pts),
        gf: Number(row.GF ?? 0),
        ga: Number(row.GA ?? 0),
        gd: Number(row.GD ?? 0),
        g: groupKey,
      });
    }
  }
  thirds.sort((a, b) => b.p - a.p || b.gd - a.gd || b.gf - a.gf || teamFallback(a, b));
  return thirds.slice(0, 8);
}

export function getTeamFromRank(slot, groupRankings, thirdAssignments = {}) {
  if (!slot) return null;
  if (String(slot).indexOf('3_') === 0) {
    return thirdAssignments[slot] || null;
  }
  if (slot.length !== 2) return null;
  const rank = Number(slot[0]);
  const group = slot[1];
  if (!Number.isFinite(rank) || rank < 1 || rank > 4) return null;
  const groupRows = groupRankings[group];
  if (!groupRows || groupRows.length < rank) return null;
  const sorted = [...groupRows].sort((a, b) => Number(a.Rank) - Number(b.Rank));
  return sorted[rank - 1]?.Team || null;
}

export function getChampionPath(ko) {
  if (!ko['FINAL']) return null;
  const champ = ko['FINAL'].w;
  const ids = ['FINAL'];
  const sf = ko['S1'] && ko['S1'].w === champ ? 'S1' : (ko['S2'] && ko['S2'].w === champ ? 'S2' : null);
  if (sf) {
    ids.push(sf);
    const qfPair = SFP[sf === 'S1' ? 0 : 1];
    const qf = ko[qfPair[0]] && ko[qfPair[0]].w === champ ? qfPair[0] : (ko[qfPair[1]] && ko[qfPair[1]].w === champ ? qfPair[1] : null);
    if (qf) {
      ids.push(qf);
      const qfIdx = parseInt(qf.substring(1)) - 1;
      const r16Pair = QFP[qfIdx];
      const l = ko[r16Pair[0]] && ko[r16Pair[0]].w === champ ? r16Pair[0] : (ko[r16Pair[1]] && ko[r16Pair[1]].w === champ ? r16Pair[1] : null);
      if (l) {
        ids.push(l);
        const lIdx = parseInt(l.substring(1)) - 1;
        const r32Pair = R16P[lIdx];
        const r = ko[r32Pair[0]] && ko[r32Pair[0]].w === champ ? r32Pair[0] : (ko[r32Pair[1]] && ko[r32Pair[1]].w === champ ? r32Pair[1] : null);
        if (r) ids.push(r);
      }
    }
  }
  const set = {}; for (let i = 0; i < ids.length; i++) set[ids[i]] = true;
  const stageNames = { FINAL: 'Final', S1: 'Semifinals', S2: 'Semifinals' };
  for (let i = 1; i <= 4; i++) stageNames['Q' + i] = 'Quarterfinals';
  for (let i = 1; i <= 8; i++) stageNames['L' + i] = 'Round of 16';
  for (let i = 1; i <= 16; i++) stageNames['R' + i] = 'Round of 32';
  const route = [];
  for (let i = ids.length - 1; i >= 0; i--) {
    const id = ids[i]; const rec = ko[id]; if (!rec) continue;
    route.push({ stage: stageNames[id], id: id, opp: rec.l, cs: Math.max(rec.h, rec.a), os: Math.min(rec.h, rec.a) });
  }
  return { champ, set, route };
}
