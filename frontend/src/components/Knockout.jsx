import { useMemo, useCallback } from 'react';
import Flag from './Flag';
import { R32D } from '../constants/data';
import { KNOCKOUT_MATCH_IDS } from '../constants/matchSchedule';
import styles from './Knockout.module.css';

const NEXT_ROUND_SLOTS = {
  89: ['W74', 'W77'],
  90: ['W73', 'W75'],
  91: ['W76', 'W78'],
  92: ['W79', 'W80'],
  93: ['W83', 'W84'],
  94: ['W81', 'W82'],
  95: ['W86', 'W88'],
  96: ['W85', 'W87'],
  97: ['W89', 'W90'],
  98: ['W93', 'W94'],
  99: ['W91', 'W92'],
  100: ['W95', 'W96'],
  101: ['W97', 'W98'],
  102: ['W99', 'W100'],
  103: ['L101', 'L102'],
  104: ['W101', 'W102'],
};

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

const hasScore = (score) => (
  score?.Goals_A != null
  && score?.Goals_B != null
  && score.Goals_A !== ''
  && score.Goals_B !== ''
);

const cleanTeam = (team) => {
  if (team == null || String(team).trim() === '') return null;
  return String(team);
};

const Knockout = ({ mode, onToggleMode, matchScores, predictionScores, currentGroupStageComplete }) => {
  const hideCurrentKnockoutTeams = mode === 'Current' && !currentGroupStageComplete;

  const scoreFor = useCallback((id) => matchScores?.[id] || {}, [matchScores]);
  const predictionFor = useCallback((id) => predictionScores?.[id] || {}, [predictionScores]);

  const actualWinnerFor = useCallback((id) => {
    const score = scoreFor(id);
    const teamA = cleanTeam(score.Team_A);
    const teamB = cleanTeam(score.Team_B);
    const actualWinner = cleanTeam(score.Actual_Winner);

    if (actualWinner) {
      if (actualWinner === teamA) return { winner: teamA, loser: teamB };
      if (actualWinner === teamB) return { winner: teamB, loser: teamA };
      return { winner: actualWinner, loser: null };
    }

    if (!hasScore(score) || !teamA || !teamB) return null;

    const goalsA = Number(score.Goals_A);
    const goalsB = Number(score.Goals_B);
    if (!Number.isFinite(goalsA) || !Number.isFinite(goalsB) || goalsA === goalsB) return null;

    return goalsA > goalsB
      ? { winner: teamA, loser: teamB }
      : { winner: teamB, loser: teamA };
  }, [scoreFor]);

  const inferredCurrentTeam = useCallback((slot) => {
    const marker = slot.slice(0, 1);
    const sourceMatchId = Number(slot.slice(1));
    if (!['W', 'L'].includes(marker) || !Number.isFinite(sourceMatchId)) return null;

    const result = actualWinnerFor(sourceMatchId);
    if (!result) return null;
    return marker === 'W' ? result.winner : result.loser;
  }, [actualWinnerFor]);

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
    const actualWinner = mode === 'Current' ? cleanTeam(score.Actual_Winner) : null;
    const winner = actualWinner === ht || actualWinner === at
      ? actualWinner
      : hVal > aVal
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
    const score = scoreFor(id);

    if (mode !== 'Current') {
      return cleanTeam(score[field]);
    }

    if (hasScore(score) || KNOCKOUT_MATCH_IDS.R32.includes(id)) {
      return cleanTeam(score[field]);
    }

    const slots = NEXT_ROUND_SLOTS[id];
    if (!slots) return null;
    return inferredCurrentTeam(field === 'Team_A' ? slots[0] : slots[1]);
  }, [hideCurrentKnockoutTeams, inferredCurrentTeam, mode, scoreFor]);

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

  const renderFinalWinner = () => {
    const winner = finalMatch.result?.w;
    if (!winner) return null;

    return (
      <div className={styles.winnerCard}>
        <div className={styles.winnerLabel}>
          {mode === 'Prediction' ? 'Predicted Winner' : 'Winner'}
        </div>
        <Flag team={winner} size="lg" className={styles.winnerFlag} />
        <div className={styles.winnerName}>{winner}</div>
      </div>
    );
  };

  return (
    <div className={styles.container}>
      <div className={styles.modebar}>
        <button className={styles.btnMode} onClick={onToggleMode}>
          Switch to {mode === 'Current' ? 'Prediction' : 'Current'} Mode
        </button>
      </div>

      <div className={styles.bkWrap}>
        <div className={styles.bkContent}>
          <div className={styles.topbar}>
            <div className={styles.statusOk}>
              Prediction knockout bracket is powered by backend scores.
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
              {renderFinalWinner()}
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
