import React from 'react';
import Flag from './Flag';
import { BASELINE } from '../constants/data';
import styles from './Author.module.css';

const Author = ({ ko = {} }) => {
  const stageLbl = { R32: "R32", R16: "R16", QF: "QF", SF: "SF", F: "FINAL" };
  const userChamp = ko["FINAL"]?.w;

  return (
    <div className={styles.baselineCard}>
      <div className={styles.baselineHead}>
        <h2>✍️ Author's Pick</h2>
        <p className={styles.baselineSub}>This is the author's own call. See how your bracket stacks up against it.</p>
      </div>

      <div className={styles.baselineChampCard}>
        <div className={styles.blChampLabel}>🏆 Author's champion</div>
        <div className={styles.blChampRow}>
          <Flag team={BASELINE.champion} size="md" />
          <span className={styles.blChampName}>{BASELINE.champion}</span>
        </div>
        <div className={styles.blThird}>
          🥉 Third place：<Flag team={BASELINE.third} size="sm" /> {BASELINE.third}
        </div>
      </div>

      <div className={styles.blPathCard}>
        <h3>Path to glory</h3>
        {BASELINE.path.map((p, i) => (
          <div key={i} className={styles.blPathRow}>
            <span className={styles.blStage}>{stageLbl[p.stage]}</span>
            <span className={styles.blMatch}>
              <Flag team={BASELINE.champion} size="sm" /> {BASELINE.champion}
              <span className={styles.blVs}>vs</span>
              <Flag team={p.opp} size="sm" /> {p.opp}
            </span>
            <span className={styles.blScore}>{p.us}-{p.them}</span>
          </div>
        ))}
      </div>

      <div className={styles.blCompareCard}>
        <h3>Your prediction vs Author</h3>
        {userChamp ? (
          userChamp === BASELINE.champion ? (
            <p className={styles.blSame}>✓ You and the author backed the same champion! Great minds.</p>
          ) : (
            <p className={styles.blDiff}>Your champion: {userChamp} · Author backed: {BASELINE.champion}</p>
          )
        ) : (
          <p className={styles.blPending}>Finish your knockout to compare with the author</p>
        )}
      </div>

      <div className={styles.blCompareCard}>
        <h3>📊 Result scoring</h3>
        <p className={styles.blPending}>⏳ Once the cup kicks off (June 11, 2026), your prediction score shows up here</p>
      </div>
    </div>
  );
};

export default Author;
