import { useMemo, useCallback } from 'react';
import Flag from './Flag';
import { R32D } from '../constants/data';
import { KNOCKOUT_MATCH_IDS } from '../constants/matchSchedule';
import styles from './Knockout.module.css';

const formatProbability = (value) => {
  if (value == null || value === '') return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  const percent = numeric <= 1 ? numeric * 100 : numeric;
  return `${percent.toFixed(1)}%`;
};

const getNumericProbability = (value) => {
  if (value == null || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const Knockout = ({ mode, matchScores, predictionScores, currentGroupStageComplete }) => {
  const hideCurrentKnockoutTeams = mode === 'Current' && !currentGroupStageComplete;

  const scoreFor = useCallback((id) => matchScores?.[id] || {}, [matchScores]);
  const predictionFor = useCallback((id) => predictionScores?.[id] || {}, [predictionScores]);

  const resultFor = useCallback((id, ht, at) => {
    const score = scoreFor(id);
    const h = mode === 'Current' ? score.Goals_A : score.Predicted_Goals_A;
    const a = mode === 'Current' ? score.Goals_B : score.Predicted_Goals_B;
    if (h == null || a == null || h === '' || a === '') return null;
    const hVal = Number(h);
    const aVal = Number(a);
    if (Number.isNaN(hVal) || Number.isNaN(aVal)) return null;
    const prediction = predictionFor(id);
    const probabilityA = getNumericProbability(prediction.Winning_Probability_A ?? score.Winning_Probability_A);
    const probabilityB = getNumericProbability(prediction.Winning_Probability_B ?? score.Winning_Probability_B);
    const winner = hVal > aVal
      ? ht
      : aVal > hVal
        ? at
        : probabilityA != null && probabilityB != null && probabilityA !== probabilityB
          ? (probabilityA > probabilityB ? ht : at)
          : null;
    return { h: hVal, a: aVal, w: winner };
  }, [mode, predictionFor, scoreFor]);

  const teamFor = useCallback((id, field) => {
    if (hideCurrentKnockoutTeams) return null;
    const team = scoreFor(id)[field];
    if (team == null || String(team).trim() === '') return null;
    return team;
  }, [hideCurrentKnockoutTeams, scoreFor]);

  const buildMatch = useCallback((id) => {
    const ht = teamFor(id, 'Team_A');
    const at = teamFor(id, 'Team_B');
    return {
      id,
      ht,
      at,
      result: resultFor(id, ht, at),
    };
  }, [resultFor, teamFor]);

  const r32ByPlaceholder = useMemo(() => {
    return Object.fromEntries(
      R32D.map((match, idx) => [match.i, buildMatch(KNOCKOUT_MATCH_IDS.R32[idx])])
    );
  }, [buildMatch]);

  const r16ByPlaceholder = useMemo(() => {
    return Object.fromEntries(
      KNOCKOUT_MATCH_IDS.R16.map((id, idx) => [`L${idx + 1}`, buildMatch(id)])
    );
  }, [buildMatch]);

  const qfByPlaceholder = useMemo(() => {
    return Object.fromEntries(
      KNOCKOUT_MATCH_IDS.QF.map((id, idx) => [`Q${idx + 1}`, buildMatch(id)])
    );
  }, [buildMatch]);

  const sfByPlaceholder = useMemo(() => {
    return Object.fromEntries(
      KNOCKOUT_MATCH_IDS.SF.map((id, idx) => [`S${idx + 1}`, buildMatch(id)])
    );
  }, [buildMatch]);

  const finalMatch = useMemo(() => buildMatch(KNOCKOUT_MATCH_IDS.FINAL), [buildMatch]);

  const thirdPlaceMatch = useMemo(() => {
    return buildMatch(KNOCKOUT_MATCH_IDS.THIRD);
  }, [buildMatch]);

  const leftR32 = [
    r32ByPlaceholder.R2,
    r32ByPlaceholder.R5,
    r32ByPlaceholder.R1,
    r32ByPlaceholder.R3,
    r32ByPlaceholder.R11,
    r32ByPlaceholder.R12,
    r32ByPlaceholder.R9,
    r32ByPlaceholder.R10,
  ].filter(Boolean);

  const rightR32 = [
    r32ByPlaceholder.R4,
    r32ByPlaceholder.R6,
    r32ByPlaceholder.R7,
    r32ByPlaceholder.R8,
    r32ByPlaceholder.R14,
    r32ByPlaceholder.R16,
    r32ByPlaceholder.R13,
    r32ByPlaceholder.R15,
  ].filter(Boolean);

  const leftR16 = [
    r16ByPlaceholder.L1,
    r16ByPlaceholder.L2,
    r16ByPlaceholder.L5,
    r16ByPlaceholder.L6,
  ].filter(Boolean);

  const rightR16 = [
    r16ByPlaceholder.L3,
    r16ByPlaceholder.L4,
    r16ByPlaceholder.L7,
    r16ByPlaceholder.L8,
  ].filter(Boolean);

  const leftQF = [
    qfByPlaceholder.Q1,
    qfByPlaceholder.Q2,
  ].filter(Boolean);

  const rightQF = [
    qfByPlaceholder.Q3,
    qfByPlaceholder.Q4,
  ].filter(Boolean);

  const sfList = [sfByPlaceholder.S1, sfByPlaceholder.S2].filter(Boolean);

  const renderMatch = (m) => {
    if (!m.ht || !m.at) {
      return (
        <div className={`${styles.bkM} ${styles.wait}`}>
          <div className={styles.bkRow}><span className={styles.name}>-</span></div>
          <div className={styles.bkVs}>vs</div>
          <div className={styles.bkRow}><span className={styles.name}>-</span></div>
        </div>
      );
    }

    const isHomeWinner = m.result?.w === m.ht;
    const isAwayWinner = m.result?.w === m.at;
    const prediction = predictionFor(m.id);

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
        <div className={styles.probPanel}>
          <div className={styles.probTitle}>Win probability</div>
          <div className={styles.probRow}>
            <span className={styles.probTeam}>{m.ht}</span>
            <span className={`${styles.probValue} ${styles.probHome}`}>
              {formatProbability(prediction.Winning_Probability_A)}
            </span>
          </div>
          <div className={styles.probRow}>
            <span className={styles.probTeam}>Draw</span>
            <span className={`${styles.probValue} ${styles.probDraw}`}>
              {formatProbability(prediction.Draw_Probability)}
            </span>
          </div>
          <div className={styles.probRow}>
            <span className={styles.probTeam}>{m.at}</span>
            <span className={`${styles.probValue} ${styles.probAway}`}>
              {formatProbability(prediction.Winning_Probability_B)}
            </span>
          </div>
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
      <div className={styles.bkWrap}>
        <div className={styles.bkContent}>
          <div className={styles.topbar}>
            <div className={styles.statusOk}>
              {mode} knockout bracket is powered by backend scores.
            </div>
            <p className={styles.hint}>👈 Scroll horizontally to view the bracket. Winning teams are highlighted.</p>
          </div>

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
              <div className={styles.finalBlock}>
                <div className={styles.bkTitle}>🏆 Final</div>
                {renderMatch(finalMatch)}
              </div>
              <div className={styles.finalBlock}>
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
    </div>
  );
};

export default Knockout;
