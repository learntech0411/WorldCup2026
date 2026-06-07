import { R16P, QFP, SFP } from '../constants/data';

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
