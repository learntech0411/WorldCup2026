import { TEAM_ORDER, GD, R32D, R16P, QFP, SFP, FC } from '../constants/data';

const SHARE_STATE_VERSION = 3;

export function serializeState(gm, ko) {
  try {
    const teams = Object.keys(FC);
    const tIdx = (name) => teams.indexOf(name);
    const g = {};
    for (const grp in gm) {
      const arr = [];
      for (let i = 0; i < gm[grp].length; i++) {
        const m = gm[grp][i];
        if (m.hs === "" || m.as === "") {
          arr.push(0);
          continue;
        }
        arr.push([parseInt(m.hs) || 0, parseInt(m.as) || 0]);
      }
      g[grp] = arr;
    }
    const k = {};
    for (const kid in ko) {
      const ks = ko[kid];
      if (!ks || !ks.w) continue;
      k[kid] = [tIdx(ks.w), tIdx(ks.l), ks.h, ks.a];
    }
    const json = JSON.stringify({ v: SHARE_STATE_VERSION, g, k });
    return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  } catch (e) {
    console.error("serializeState failed:", e);
    return null;
  }
}

export function deserializeState(encoded) {
  if (!encoded) return null;
  try {
    const b64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
    let padded = b64;
    while (padded.length % 4) padded += "=";
    const json = decodeURIComponent(escape(atob(padded)));
    const data = JSON.parse(json);
    if (!data) return null;
    const teams = Object.keys(FC);
    const gm = initGM();
    for (const grp in data.g) {
      if (!gm[grp]) continue;
      const arr = data.g[grp];
      for (let i = 0; i < arr.length && i < gm[grp].length; i++) {
        const entry = arr[i];
        if (!entry || entry === 0) continue;
        const [hs, as] = entry;
        gm[grp][i].hs = String(hs);
        gm[grp][i].as = String(as);
      }
    }
    const ko = {};
    for (const kid in data.k) {
      const e2 = data.k[kid];
      if (!e2) continue;
      const [wIdx, lIdx, hScore, aScore] = e2;
      const wTeam = teams[wIdx];
      const lTeam = teams[lIdx];
      if (!wTeam || !lTeam) continue;
      ko[kid] = { w: wTeam, l: lTeam, h: hScore, a: aScore };
    }
    return { gm, ko };
  } catch (e) {
    console.error("deserializeState failed:", e);
    return null;
  }
}

export function splitRank(list, valueFn) {
  const arr = list.slice().sort((a, b) => valueFn(b) - valueFn(a));
  const out = [];
  let i = 0;
  while (i < arr.length) {
    const v = valueFn(arr[i]);
    const g = [arr[i]];
    let j = i + 1;
    while (j < arr.length && valueFn(arr[j]) === v) {
      g.push(arr[j]);
      j++;
    }
    out.push(g);
    i = j;
  }
  return out;
}

export function teamFallback(a, b) {
  return (TEAM_ORDER[a.t] || 999) - (TEAM_ORDER[b.t] || 999);
}

export function rankGroup(arr, ms) {
  const pointBuckets = splitRank(arr, (x) => x.p);
  const final = [];
  for (let bi = 0; bi < pointBuckets.length; bi++) {
    let buckets = [pointBuckets[bi]];
    const criteria = [
      (list) => {
        const set = {}; const st = {};
        for (let i = 0; i < list.length; i++) {
          set[list[i].t] = 1;
          st[list[i].t] = { p: 0, gf: 0, ga: 0, gd: 0 };
        }
        for (let j = 0; j < ms.length; j++) {
          const m = ms[j]; const h = parseInt(m.hs); const a = parseInt(m.as);
          if (!set[m.h] || !set[m.a] || isNaN(h) || isNaN(a)) continue;
          st[m.h].gf += h; st[m.h].ga += a; st[m.a].gf += a; st[m.a].ga += h;
          if (h > a) st[m.h].p += 3; else if (h < a) st[m.a].p += 3; else { st[m.h].p++; st[m.a].p++; }
        }
        for (const k in st) st[k].gd = st[k].gf - st[k].ga;
        return (x) => st[x.t].p;
      },
      (list) => {
        const set = {}; const st = {};
        for (let i = 0; i < list.length; i++) {
          set[list[i].t] = 1;
          st[list[i].t] = { gf: 0, ga: 0, gd: 0 };
        }
        for (let j = 0; j < ms.length; j++) {
          const m = ms[j]; const h = parseInt(m.hs); const a = parseInt(m.as);
          if (!set[m.h] || !set[m.a] || isNaN(h) || isNaN(a)) continue;
          st[m.h].gf += h; st[m.h].ga += a; st[m.a].gf += a; st[m.a].ga += h;
        }
        for (const k in st) st[k].gd = st[k].gf - st[k].ga;
        return (x) => st[x.t].gd;
      },
      (list) => {
        const set = {}; const st = {};
        for (let i = 0; i < list.length; i++) {
          set[list[i].t] = 1;
          st[list[i].t] = { gf: 0 };
        }
        for (let j = 0; j < ms.length; j++) {
          const m = ms[j]; const h = parseInt(m.hs); const a = parseInt(m.as);
          if (!set[m.h] || !set[m.a] || isNaN(h) || isNaN(a)) continue;
          st[m.h].gf += h; st[m.a].gf += a;
        }
        return (x) => st[x.t].gf;
      },
      () => (x) => x.gd,
      () => (x) => x.gf,
    ];
    for (let ci = 0; ci < criteria.length; ci++) {
      const next = [];
      for (let gi = 0; gi < buckets.length; gi++) {
        const b = buckets[gi];
        if (b.length <= 1) { next.push(b); continue; }
        const vf = criteria[ci](b);
        const parts = splitRank(b, vf);
        for (let pi = 0; pi < parts.length; pi++) next.push(parts[pi]);
      }
      buckets = next;
    }
    for (let gi = 0; gi < buckets.length; gi++) {
      buckets[gi].sort(teamFallback);
      for (let ti = 0; ti < buckets[gi].length; ti++) final.push(buckets[gi][ti]);
    }
  }
  return final;
}

export function calcS(ts, ms) {
  const s = {};
  for (let i = 0; i < ts.length; i++) s[ts[i]] = { t: ts[i], p: 0, gf: 0, ga: 0, gd: 0, w: 0, d: 0, l: 0, mp: 0 };
  for (let j = 0; j < ms.length; j++) {
    const m = ms[j];
    if (m.hs === "" || m.as === "") continue;
    const h = parseInt(m.hs);
    const a = parseInt(m.as);
    if (isNaN(h) || isNaN(a)) continue;
    s[m.h].mp++; s[m.a].mp++;
    s[m.h].gf += h; s[m.h].ga += a;
    s[m.a].gf += a; s[m.a].ga += h;
    if (h > a) { s[m.h].p += 3; s[m.h].w++; s[m.a].l++; }
    else if (h < a) { s[m.a].p += 3; s[m.a].w++; s[m.h].l++; }
    else { s[m.h].p++; s[m.a].p++; s[m.h].d++; s[m.a].d++; }
  }
  const arr = [];
  for (const k in s) {
    s[k].gd = s[k].gf - s[k].ga;
    arr.push(s[k]);
  }
  return rankGroup(arr, ms);
}

export function initGM() {
  const g = {};
  for (const k in GD) {
    const ts = GD[k];
    const pp = [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]];
    g[k] = [];
    for (let p = 0; p < pp.length; p++) g[k].push({ h: ts[pp[p][0]], a: ts[pp[p][1]], hs: "", as: "" });
  }
  return g;
}

export function getSt(gm) {
  const s = {};
  for (const k in GD) s[k] = calcS(GD[k], gm[k]);
  return s;
}

export function getT3(st) {
  const t = [];
  for (const k in st) if (st[k][2]) t.push({ t: st[k][2].t, p: st[k][2].p, gf: st[k][2].gf, ga: st[k][2].ga, gd: st[k][2].gd, g: k });
  t.sort((a, b) => b.p - a.p || b.gd - a.gd || b.gf - a.gf || teamFallback(a, b));
  return t.slice(0, 8);
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

export function getS(s, st, t3Assign) {
  if (s.indexOf('3_') === 0) return t3Assign[s] || null;
  const p = parseInt(s[0]); const g = s[1];
  if (st[g] && st[g][p - 1]) return st[g][p - 1].t;
  return null;
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

export const SCORE_RULES = {
  groupOutcome: 3, groupExact: 2, reachR16: 5, reachQF: 8, reachSF: 12, reachFinal: 16, third: 15, runnerUp: 20, champion: 30
};

export function scorePrediction(gm, ko, actualResults) {
  if (!actualResults || !actualResults.ready) return null;
  const R = SCORE_RULES;
  let total = 0;
  const bd = { group: 0, r16: 0, qf: 0, sf: 0, final: 0, third: 0, runnerUp: 0, champ: 0 };

  for (const g in gm) {
    const ag = actualResults.groups[g];
    if (!ag) continue;
    for (let i = 0; i < gm[g].length; i++) {
      const p = gm[g][i]; const a = ag[i];
      if (!a || p.hs === "" || p.as === "" || a.hs == null || a.as == null) continue;
      const ph = parseInt(p.hs); const pa = parseInt(p.as);
      const pSign = (ph > pa) - (ph < pa); const aSign = (a.hs > a.as) - (a.hs < a.as);
      if (pSign === aSign) {
        total += R.groupOutcome; bd.group += R.groupOutcome;
        if (ph === a.hs && pa === a.as) { total += R.groupExact; bd.group += R.groupExact; }
      }
    }
  }

  const teamsAdvanced = (koObj, prefix, count) => {
    const s = {};
    for (let i = 1; i <= count; i++) { const m = koObj[prefix + i]; if (m && m.w) s[m.w] = 1; }
    return s;
  };

  const AK = actualResults.knockout;
  const roundScore = (prefix, count, pts, key) => {
    const pred = teamsAdvanced(ko, prefix, count);
    const act = teamsAdvanced(AK, prefix, count);
    let n = 0;
    for (const t in pred) if (act[t]) n++;
    const got = n * pts; total += got; bd[key] += got;
  };

  roundScore("R", 16, R.reachR16, "r16");
  roundScore("L", 8, R.reachQF, "qf");
  roundScore("Q", 4, R.reachSF, "sf");
  roundScore("S", 2, R.reachFinal, "final");

  if (ko.FINAL && AK.FINAL) {
    if (ko.FINAL.w === AK.FINAL.w) { total += R.champion; bd.champ += R.champion; }
    if (ko.FINAL.l && ko.FINAL.l === AK.FINAL.l) { total += R.runnerUp; bd.runnerUp += R.runnerUp; }
  }
  if (ko["3RD"] && AK["3RD"] && ko["3RD"].w === AK["3RD"].w) { total += R.third; bd.third += R.third; }

  return { total, breakdown: bd };
}
