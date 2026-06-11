import { useEffect, useMemo, useState } from 'react';
import styles from './Stats.module.css';

const API_PREFIX = import.meta.env.VITE_API_PREFIX || 'http://localhost:8000/api';

const accuracyEndpoints = [
  {
    key: 'outcome',
    label: 'Correct Outcome',
    description: 'Predicted win/loss/draw matched the result.',
    endpoint: '/correct-outcome-predictions',
    responseKey: 'Correct_Outcome_Predictions',
  },
  {
    key: 'goalDifference',
    label: 'Correct Goal Difference',
    description: 'Predicted goal margin matched the result.',
    endpoint: '/correct-goal-difference-predictions',
    responseKey: 'Correct_Goal_Difference_Predictions',
  },
  {
    key: 'score',
    label: 'Correct Score',
    description: 'Predicted exact score matched the result.',
    endpoint: '/correct-score-predictions',
    responseKey: 'Correct_Score_Predictions',
  },
];

const Stats = () => {
  const [accuracy, setAccuracy] = useState(null);
  const [playedMatches, setPlayedMatches] = useState(null);
  const [loadingAccuracy, setLoadingAccuracy] = useState(true);
  const [accuracyError, setAccuracyError] = useState('');

  useEffect(() => {
    let ignore = false;

    const loadAccuracy = async () => {
      setLoadingAccuracy(true);
      setAccuracyError('');

      try {
        const [playedResponse, ...accuracyResponses] = await Promise.all([
          fetch(`${API_PREFIX}/played-matches-count`),
          ...accuracyEndpoints.map((item) => fetch(`${API_PREFIX}${item.endpoint}`)),
        ]);

        const responses = [playedResponse, ...accuracyResponses];
        if (responses.some((response) => !response.ok)) {
          throw new Error('Could not load prediction accuracy.');
        }

        const [playedData, ...accuracyData] = await Promise.all(
          responses.map((response) => response.json())
        );

        if (ignore) {
          return;
        }

        setPlayedMatches(Number(playedData.Played_Matches ?? 0));
        setAccuracy(
          accuracyEndpoints.reduce((stats, item, index) => {
            stats[item.key] = Number(accuracyData[index][item.responseKey] ?? 0);
            return stats;
          }, {})
        );
      } catch (error) {
        if (!ignore) {
          setAccuracyError(error.message || 'Could not load prediction accuracy.');
        }
      } finally {
        if (!ignore) {
          setLoadingAccuracy(false);
        }
      }
    };

    loadAccuracy();

    return () => {
      ignore = true;
    };
  }, []);

  const accuracyCards = useMemo(() => {
    return accuracyEndpoints.map((item) => {
      const count = accuracy?.[item.key] ?? 0;
      const percentage = playedMatches > 0 ? (count / playedMatches) * 100 : 0;

      return {
        ...item,
        count,
        percentage,
      };
    });
  }, [accuracy, playedMatches]);

  return (
    <div className={styles.statsWrap}>
      <section className={styles.accuracyCard}>
        <div className={styles.accuracyHead}>
          <div>
            <h2 className={styles.accuracyTitle}>Pre-Match Accuracy</h2>
            <p className={styles.accuracySubtitle}>
              Prediction quality across {playedMatches ?? 0} played matches.
            </p>
          </div>
        </div>

        {loadingAccuracy && (
          <div className={styles.accuracyState}>Loading prediction accuracy...</div>
        )}

        {!loadingAccuracy && accuracyError && (
          <div className={styles.accuracyState}>{accuracyError}</div>
        )}

        {!loadingAccuracy && !accuracyError && (
          <div className={styles.accuracyGrid}>
            {accuracyCards.map((item) => (
              <div key={item.key} className={styles.accuracyItem}>
                <div className={styles.accuracyLabel}>{item.label}</div>
                <p className={styles.accuracyDescription}>{item.description}</p>
                <div className={styles.accuracyValue}>{item.percentage.toFixed(1)}%</div>
                <div className={styles.accuracyCount}>
                  {item.count} / {playedMatches ?? 0}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default Stats;
