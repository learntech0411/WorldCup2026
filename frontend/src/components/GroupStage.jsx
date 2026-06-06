import React, { useState, useMemo, useEffect } from 'react';
import Flag from './Flag';
import styles from './GroupStage.module.css';
import { GROUP_MATCHES } from '../constants/matchSchedule';

const GroupStage = ({ mode, onToggleMode, groupMatrix, matchScores, fetchMatchScore, loading }) => {
  const [expandedGroup, setExpandedGroup] = useState(null);

  useEffect(() => {
    if (!groupMatrix) return;
    GROUP_MATCHES.forEach((match) => fetchMatchScore(match.id));
  }, [groupMatrix, fetchMatchScore]);

  const groupKeys = useMemo(() => {
    if (!groupMatrix) return [];
    return Object.keys(groupMatrix).sort();
  }, [groupMatrix]);

  const renderMatchRow = (match) => {
    const score = matchScores?.[match.id] || {};
    const homeScore = mode === 'Current' ? score.Goals_A : score.Predicted_Goals_A;
    const awayScore = mode === 'Current' ? score.Goals_B : score.Predicted_Goals_B;
    const homeVal = homeScore == null || homeScore === '' ? '-' : homeScore;
    const awayVal = awayScore == null || awayScore === '' ? '-' : awayScore;
    const isHomeWinner = homeScore != null && awayScore != null && homeScore !== '' && awayScore !== '' && Number(homeScore) > Number(awayScore);
    const isAwayWinner = homeScore != null && awayScore != null && homeScore !== '' && awayScore !== '' && Number(awayScore) > Number(homeScore);

    return (
      <div key={match.id} className={styles.matchRow}>
        <div className={`${styles.matchTeam}`}>
          <Flag team={match.h} size="sm" /> {match.h}
        </div>
        <div className={styles.scoreBadge}>{homeVal}</div>
        <span className={styles.sep}>-</span>
        <div className={styles.scoreBadge}>{awayVal}</div>
        <div className={`${styles.matchTeam}`}>
          <Flag team={match.a} size="sm" /> {match.a}
        </div>
      </div>
    );
  };

  const renderGroup = (groupKey) => {
    const rows = groupMatrix?.[groupKey] || [];
    const standings = [...rows].sort((a, b) => Number(a.Rank) - Number(b.Rank));
    const groupMatches = GROUP_MATCHES.filter((m) => m.group === groupKey);

    return (
      <div key={groupKey} className={styles.card}>
        <div className={styles.cardH} onClick={() => setExpandedGroup(expandedGroup === groupKey ? null : groupKey)}>
          <span className={styles.gName}>Group {groupKey}</span>
          <span className={`${styles.arr} ${expandedGroup === groupKey ? styles.open : ''}`}>▾</span>
        </div>
        <div className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                <th style={{ width: '20px' }}></th>
                <th>Team</th>
                <th style={{ width: '20px' }}>P</th>
                <th style={{ width: '20px' }}>W</th>
                <th style={{ width: '20px' }}>D</th>
                <th style={{ width: '20px' }}>L</th>
                <th style={{ width: '28px' }}>GD</th>
                <th style={{ width: '28px' }}>Pts</th>
              </tr>
            </thead>
            <tbody>
              {standings.map((team) => {
                const rank = Number(team.Rank);
                const rowClass = rank === 1 ? styles.goldRow : rank === 2 ? styles.silverRow : rank === 3 ? styles.q3 : '';
                const posClass = rank <= 2 ? styles.p1 : rank === 3 ? styles.p3 : styles.p4;
                const gdClass = Number(team.GD) > 0 ? styles.gdP : Number(team.GD) < 0 ? styles.gdN : styles.gdZ;
                return (
                  <tr key={team.Team} className={rowClass}>
                    <td className={`${styles.pos} ${posClass}`}>{team.Rank}</td>
                    <td className={styles.teamCell}>
                      <Flag team={team.Team} size="sm" /> {team.Team}
                    </td>
                    <td className={styles.ctr}>{team.MP}</td>
                    <td className={styles.ctr}>{team.W}</td>
                    <td className={styles.ctr}>{team.D}</td>
                    <td className={styles.ctr}>{team.L}</td>
                    <td className={`${styles.ctr} ${gdClass}`}>{Number(team.GD) > 0 ? `+${team.GD}` : team.GD}</td>
                    <td className={styles.pts}>{team.Pts}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {expandedGroup === groupKey && (
          <div className={styles.matchInline}>
            <div className={styles.matchList}>
              {groupMatches.map((match) => renderMatchRow(match))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.container}>
      <div className={styles.topbar}>
        <button className={styles.btnMode} onClick={onToggleMode}>
          Switch to {mode === 'Current' ? 'Prediction' : 'Current'} Mode
        </button>
      </div>

      {loading && (
        <div className={styles.statusOk}>Loading {mode.toLowerCase()} group data…</div>
      )}

      {!groupMatrix && !loading && (
        <div className={styles.statusOk}>No group data available yet.</div>
      )}

      <div className={styles.split}>
        <div className={styles.splitLeft}>
          <div className={styles.gg}>
            {groupKeys.map((groupKey) => renderGroup(groupKey))}
          </div>
        </div>
        <div className={styles.splitRight}>
          {expandedGroup ? (
            <>
              <h3 className={styles.sideTitle}>⚽ Group {expandedGroup} · Matches</h3>
              <div className={styles.matchList}>
                {GROUP_MATCHES.filter((match) => match.group === expandedGroup).map((match) => renderMatchRow(match))}
              </div>
            </>
          ) : (
            <div className={styles.emptySide}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>👈</div>
              <p>Tap a group on the left to view match scores</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GroupStage;
