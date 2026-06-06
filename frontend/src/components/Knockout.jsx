import { useMemo, useCallback } from 'react';
import Flag from './Flag';
import { R32D, R16P, QFP, SFP } from '../constants/data';
import { KNOCKOUT_MATCH_IDS } from '../constants/matchSchedule';
import { getTeamFromRank, getT3FromMatrices, assignThirds } from '../utils/logic';
import styles from './Knockout.module.css';

const Knockout = ({ mode, groupMatrix, matchScores }) => {
  const groupRankings = useMemo(() => {
    if (!groupMatrix) return {};
    const result = {};
    Object.keys(groupMatrix).forEach((groupKey) => {
      result[groupKey] = [...groupMatrix[groupKey]].sort((a, b) => Number(a.Rank) - Number(b.Rank));
    });
    return result;
  }, [groupMatrix]);

  const thirdAssignments = useMemo(() => {
    if (!groupMatrix) return {};
    return assignThirds(getT3FromMatrices(groupMatrix));
  }, [groupMatrix]);

  const scoreFor = useCallback((id) => matchScores?.[id] || {}, [matchScores]);

  const resultFor = useCallback((id, ht, at) => {
    const score = scoreFor(id);
    const h = mode === 'Current' ? score.Goals_A : score.Predicted_Goals_A;
    const a = mode === 'Current' ? score.Goals_B : score.Predicted_Goals_B;
    if (h == null || a == null || h === '' || a === '') return null;
    const hVal = Number(h);
    const aVal = Number(a);
    if (Number.isNaN(hVal) || Number.isNaN(aVal)) return null;
    const winner = hVal > aVal ? ht : aVal > hVal ? at : null;
    return { h: hVal, a: aVal, w: winner };
  }, [mode, scoreFor]);

  const resolveTeam = useCallback(
    (slot) => getTeamFromRank(slot, groupRankings, thirdAssignments),
    [groupRankings, thirdAssignments]
  );

  const r32m = useMemo(() => R32D.map((match, idx) => ({
    id: KNOCKOUT_MATCH_IDS.R32[idx],
    ht: resolveTeam(match.h),
    at: resolveTeam(match.a),
    placeholder: match.i,
  })), [resolveTeam]);

  const r32ByPlaceholder = useMemo(() => Object.fromEntries(r32m.map((m) => [m.placeholder, m])), [r32m]);

  const winnerFromPlaceholder = useCallback((placeholder, sourceMap) => {
    const source = sourceMap[placeholder];
    if (!source || !source.ht || !source.at) return null;
    const result = resultFor(source.id, source.ht, source.at);
    return result?.w || null;
  }, [resultFor]);

  const loserFromPlaceholder = useCallback((placeholder, sourceMap) => {
    const source = sourceMap[placeholder];
    if (!source || !source.ht || !source.at) return null;
    const result = resultFor(source.id, source.ht, source.at);
    if (!result?.w) return null;
    if (result.w === source.ht) return source.at;
    return source.ht;
  }, [resultFor]);

  const r16m = useMemo(() => {
    const map = {};
    R16P.forEach((pair, idx) => {
      const id = KNOCKOUT_MATCH_IDS.R16[idx];
      const ht = winnerFromPlaceholder(pair[0], r32ByPlaceholder);
      const at = winnerFromPlaceholder(pair[1], r32ByPlaceholder);
      map[`L${idx + 1}`] = { id, ht, at };
    });
    return Object.values(map);
  }, [r32ByPlaceholder, winnerFromPlaceholder]);

  const r16ByPlaceholder = useMemo(() => Object.fromEntries(r16m.map((m, idx) => [`L${idx + 1}`, m])), [r16m]);

  const qfm = useMemo(() => {
    const map = {};
    QFP.forEach((pair, idx) => {
      const id = KNOCKOUT_MATCH_IDS.QF[idx];
      map[`Q${idx + 1}`] = {
        id,
        ht: winnerFromPlaceholder(pair[0], r16ByPlaceholder),
        at: winnerFromPlaceholder(pair[1], r16ByPlaceholder),
      };
    });
    return Object.values(map);
  }, [r16ByPlaceholder, winnerFromPlaceholder]);

  const qfByPlaceholder = useMemo(() => Object.fromEntries(qfm.map((m, idx) => [`Q${idx + 1}`, m])), [qfm]);

  const sfm = useMemo(() => {
    const map = {};
    SFP.forEach((pair, idx) => {
      const id = KNOCKOUT_MATCH_IDS.SF[idx];
      map[`S${idx + 1}`] = {
        id,
        ht: winnerFromPlaceholder(pair[0], qfByPlaceholder),
        at: winnerFromPlaceholder(pair[1], qfByPlaceholder),
      };
    });
    return Object.values(map);
  }, [qfByPlaceholder, winnerFromPlaceholder]);

  const sfByPlaceholder = useMemo(() => Object.fromEntries(sfm.map((m, idx) => [`S${idx + 1}`, m])), [sfm]);

  const finalMatch = useMemo(() => ({
    id: KNOCKOUT_MATCH_IDS.FINAL,
    ht: winnerFromPlaceholder('S1', sfByPlaceholder),
    at: winnerFromPlaceholder('S2', sfByPlaceholder),
  }), [sfByPlaceholder, winnerFromPlaceholder]);

  const thirdPlaceMatch = useMemo(() => ({
    id: KNOCKOUT_MATCH_IDS.THIRD,
    ht: loserFromPlaceholder('S1', sfByPlaceholder),
    at: loserFromPlaceholder('S2', sfByPlaceholder),
  }), [sfByPlaceholder, loserFromPlaceholder]);

  const buildRound = (matchList) => matchList.map((m) => ({ ...m, result: resultFor(m.id, m.ht, m.at) }));

  const leftR32 = buildRound([
    r32ByPlaceholder.R2,
    r32ByPlaceholder.R5,
    r32ByPlaceholder.R1,
    r32ByPlaceholder.R3,
    r32ByPlaceholder.R11,
    r32ByPlaceholder.R12,
    r32ByPlaceholder.R9,
    r32ByPlaceholder.R10,
  ].filter(Boolean));

  const rightR32 = buildRound([
    r32ByPlaceholder.R4,
    r32ByPlaceholder.R6,
    r32ByPlaceholder.R7,
    r32ByPlaceholder.R8,
    r32ByPlaceholder.R14,
    r32ByPlaceholder.R16,
    r32ByPlaceholder.R13,
    r32ByPlaceholder.R15,
  ].filter(Boolean));

  const leftR16 = buildRound([
    r16ByPlaceholder.L1,
    r16ByPlaceholder.L2,
    r16ByPlaceholder.L5,
    r16ByPlaceholder.L6,
  ].filter(Boolean));

  const rightR16 = buildRound([
    r16ByPlaceholder.L3,
    r16ByPlaceholder.L4,
    r16ByPlaceholder.L7,
    r16ByPlaceholder.L8,
  ].filter(Boolean));

  const leftQF = buildRound([
    qfByPlaceholder.Q1,
    qfByPlaceholder.Q2,
  ].filter(Boolean));

  const rightQF = buildRound([
    qfByPlaceholder.Q3,
    qfByPlaceholder.Q4,
  ].filter(Boolean));

  const sfList = buildRound([sfByPlaceholder.S1, sfByPlaceholder.S2].filter(Boolean));

  const renderMatch = (m) => {
    if (!m.ht || !m.at) {
      return (
        <div className={`${styles.bkM} ${styles.wait}`}>
          <div className={styles.bkRow}><span className={styles.name}>?</span></div>
          <div className={styles.bkVs}>vs</div>
          <div className={styles.bkRow}><span className={styles.name}>?</span></div>
        </div>
      );
    }

    const isHomeWinner = m.result?.w === m.ht;
    const isAwayWinner = m.result?.w === m.at;

    return (
      <div className={styles.bkM}>
        <div className={styles.bkRow}>
          <Flag team={m.ht} size="xs" />
          <span className={`${styles.name} ${isHomeWinner ? styles.w : ''}`}>{m.ht}</span>
          {m.result && <span className={styles.sc}>{m.result.h}</span>}
        </div>
        <div className={styles.bkVs}>vs</div>
        <div className={styles.bkRow}>
          <Flag team={m.at} size="xs" />
          <span className={`${styles.name} ${isAwayWinner ? styles.w : ''}`}>{m.at}</span>
          {m.result && <span className={styles.sc}>{m.result.a}</span>}
        </div>
      </div>
    );
  };

  const renderRound = (title, matches) => (
    <div className={styles.bkRound}>
      <div className={styles.bkTitle}>{title}</div>
      {matches.map((m) => (
        <div key={m.id} className={styles.bkMWrap}>
          {renderMatch(m)}
        </div>
      ))}
    </div>
  );

  return (
    <div className={styles.container}>
      <div className={styles.topbar}>
        <div className={styles.statusOk}>
          {mode} knockout bracket is powered by backend scores.
        </div>
      </div>
      <p className={styles.hint}>👈 Scroll horizontally to view the bracket. Winning teams are highlighted.</p>

      <div className={styles.bkWrap}>
        <div className={styles.bk}>
          {renderRound('Round of 32', leftR32)}
          <div className={styles.bkConn} />
          {renderRound('Round of 16', leftR16)}
          <div className={styles.bkConn} />
          {renderRound('Quarterfinals', leftQF)}
          <div className={styles.bkConn} />
          {renderRound('Semifinals', sfList.slice(0, 1))}
          <div className={styles.bkConn} />

          <div className={`${styles.bkRound} ${styles.finalCol}`}>
            <div className={styles.bkTitle}>🏆 Final</div>
            {renderMatch(finalMatch)}
            <div style={{ marginTop: '20px' }}>
              <div className={styles.bkTitle}>🥉 Third Place</div>
              {renderMatch(thirdPlaceMatch)}
            </div>
          </div>

          <div className={styles.bkConn} />
          {renderRound('Semifinals', sfList.slice(1))}
          <div className={styles.bkConn} />
          {renderRound('Quarterfinals', rightQF)}
          <div className={styles.bkConn} />
          {renderRound('Round of 16', rightR16)}
          <div className={styles.bkConn} />
          {renderRound('Round of 32', rightR32)}
        </div>
      </div>
    </div>
  );
};

export default Knockout;
