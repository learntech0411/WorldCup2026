import styles from './Author.module.css';

const Author = () => {
  return (
    <div className={styles.baselineCard}>
      <div className={styles.baselineHead}>
        <h2>How it works</h2>
        <p className={styles.baselineSub}>
          A guided space for explaining the data, prediction flow, and design choices behind this World Cup dashboard.
        </p>
      </div>

      <div className={styles.baselineChampCard}>
        <div className={styles.blChampLabel}>Project overview</div>
        <p className={styles.blPending}>
          Use this section to introduce what the app does, what data it uses, and the main idea behind the predictions.
        </p>
      </div>

      <div className={styles.blPathCard}>
        <h3>Data pipeline</h3>
        <div className={styles.blPathRow}>
          <span className={styles.blStage}>Input</span>
          <span className={styles.blMatch}>Match schedule, teams, scores, and supporting football data</span>
        </div>
        <div className={styles.blPathRow}>
          <span className={styles.blStage}>Backend</span>
          <span className={styles.blMatch}>Processing, transformations, and prediction calculations</span>
        </div>
        <div className={styles.blPathRow}>
          <span className={styles.blStage}>Frontend</span>
          <span className={styles.blMatch}>Group tables, knockout bracket, and stats views</span>
        </div>
      </div>

      <div className={styles.blCompareCard}>
        <h3>Prediction method</h3>
        <p className={styles.blPending}>
          Use this section to explain how team strength, expected goals, match probabilities, and simulated results are produced.
        </p>
      </div>

      <div className={styles.blCompareCard}>
        <h3>Frontend behavior</h3>
        <p className={styles.blPending}>
          Use this section to describe how the interface loads scores, switches between current and prediction modes, and updates the bracket.
        </p>
      </div>
    </div>
  );
};

export default Author;
