import React from 'react';
import Flag from './Flag';
import styles from './History.module.css';

const History = ({ history = [], onLoadHistory = () => {}, onClearHistory = () => {} }) => {
  if (!history || history.length === 0) {
    return (
      <div className={styles.empty}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>🕰️</div>
        <p>No saved predictions yet.</p>
        <p style={{ fontSize: '12px', marginTop: '8px' }}>Finish a knockout stage to save it to your history.</p>
      </div>
    );
  }

  return (
    <div className={styles.historyCard}>
      <div className={styles.historyHead}>
        <span className={styles.historyTitle}>📅 Your history</span>
        <button className={styles.historyClear} onClick={onClearHistory}>Clear</button>
      </div>
      <div className={styles.historyRow}>
        {history.map((hh, i) => {
          const d = new Date(hh.t);
          const ds = (d.getMonth() + 1) + "/" + d.getDate();
          return (
            <div key={i} className={styles.historyItem} onClick={() => onLoadHistory(i)} title="Click to load">
              <div className={styles.historyFlagWrap}><Flag team={hh.c} size="md" /></div>
              <div className={styles.historyChamp}>{hh.c}</div>
              <div className={styles.historyDate}>{ds}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default History;
