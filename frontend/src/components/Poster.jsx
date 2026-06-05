import React from 'react';
import { FC, STRENGTH, CHAMP_TIER_LABEL, TAGLINE } from '../constants/data';
import { getChampionPath } from '../utils/logic';
import styles from './Poster.module.css';

const Poster = ({ ko }) => {
  const cp = getChampionPath(ko);
  if (!cp) return null;

  const { champ, route } = cp;
  const tier = STRENGTH[champ] || 3;
  const tierLabel = CHAMP_TIER_LABEL[tier] || "";
  const tagline = TAGLINE[tier] || "";
  
  const champStr = champ.toUpperCase();
  const fcode = FC[champ] || "";
  const flagUrl = fcode ? `https://flagcdn.com/w160/${fcode}.png` : null;

  return (
    <div className={styles.poster}>
      <div className={styles.posterTop}>
        <div className={styles.posterTag}>2026 FIFA WORLD CUP · MY PICK</div>
        <div className={styles.posterTitle}>United · Mexico · Canada</div>
      </div>

      <div className={styles.posterChampBox}>
        <div className={styles.posterChampLabel}>THE CHAMPION</div>
        <div className={styles.posterChampHeadline}>
          {flagUrl && <img className={styles.posterChampFlag} src={flagUrl} alt={champ} />}
          <div className={styles.posterChampName}>{champStr}</div>
        </div>
        <div className={styles.posterChampTier}>{tierLabel}</div>
      </div>

      <div className={styles.posterDivider}></div>

      <div className={styles.posterPath}>
        {route.map((s, i) => (
          <div key={s.id} className={`${styles.posterPathRow} ${styles[`stage${i + 1}`]}`}>
            <span className={styles.pathStage}>{s.stage}</span>
            <span className={styles.pathMatch}>
              <img 
                className={styles.miniFlag} 
                src={`https://flagcdn.com/w40/${FC[s.opp]}.png`} 
                alt={s.opp} 
              />
              <span className={styles.pathOpp}>{s.opp}</span>
            </span>
            <span className={styles.pathScore}>{s.cs}-{s.os}</span>
          </div>
        ))}
      </div>

      <div className={styles.posterConclusion}>
        {tagline}
      </div>

      <div className={styles.posterFooter}>
        <div className={styles.footerLeft}>
          <div className={styles.footerUrl}>wc2026-predictor.vercel.app</div>
          <div className={styles.footerNotice}>Scan to make yours</div>
        </div>
        <div className={styles.footerRight}>
          <div className={styles.qrPlaceholder}>
            {/* Simple representation of a QR code */}
            <div className={styles.qrGrid}>
              {Array.from({ length: 9 }).map((_, i) => (
                <div key={i} className={i % 2 === 0 ? styles.qrOn : ''}></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Poster;
