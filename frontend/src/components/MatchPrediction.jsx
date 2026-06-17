import { useEffect, useMemo, useRef, useState } from 'react';
import { FC } from '../constants/data';
import Flag from './Flag';
import styles from './MatchPrediction.module.css';

const API_PREFIX = import.meta.env.VITE_API_PREFIX || 'http://localhost:8000/api';
const COUNTRY_OPTIONS = Object.keys(FC)
  .map((country) => (country === 'Curacao' ? 'Curaçao' : country))
  .sort((a, b) => a.localeCompare(b));

const STAT_ROWS = [
  ['Winning Probability', 'Winning_Probability', 'percent'],
  ['Match Score', 'Match_Score', 'number'],
  ['Total Transfer Market Value', 'Total_Transfer_Market_Value', 'market'],
  ['Club synergies', 'Club_Synergies', 'text'],
  ['Injured Players', 'Injured_Players', 'text'],
  ['Days Rested', 'Days_Rested', 'text'],
  ['Travel Fatigue KM', 'Travel_Distance_KM', 'distance'],
  ['Home Advantage', 'Home_Advantage', 'boolean'],
];

const exactCountry = (value) => (
  COUNTRY_OPTIONS.find((country) => country.toLowerCase() === value.trim().toLowerCase()) || ''
);

const countryMatches = (value) => {
  const query = value.trim().toLowerCase();
  if (!query) return [];
  return COUNTRY_OPTIONS.filter((country) => country.toLowerCase().startsWith(query)).slice(0, 8);
};

const formatValue = (value, type) => {
  if (value == null || value === '') return 'None';
  const numericValue = Number(value);
  if (['percent', 'distance', 'market', 'number'].includes(type) && !Number.isFinite(numericValue)) {
    return 'None';
  }
  if (type === 'percent') return `${(numericValue * 100).toFixed(1)}%`;
  if (type === 'distance') return `${numericValue.toFixed(1)} km`;
  if (type === 'market') return `€${numericValue.toFixed(1)}m`;
  if (type === 'boolean') return value ? 'Yes' : 'No';
  if (type === 'number') return numericValue.toFixed(1);
  return String(value);
};

const statValueClass = (type, value) => {
  if (type === 'boolean') {
    return value ? styles.badgePositive : styles.badgeNeutral;
  }
  if (type === 'percent') return styles.probabilityValue;
  if (type === 'text' && (value == null || value === '')) return styles.mutedValue;
  return '';
};

const flagTeamName = (teamName) => (teamName === 'Curaçao' ? 'Curacao' : teamName);

const scoreRangeFromDistribution = (distribution) => {
  const goals = distribution?.Matrix?.flatMap((item) => [item.Goals_A, item.Goals_B]) || [];
  const maxGoal = goals.length ? Math.max(...goals) : 7;
  return Array.from({ length: maxGoal + 1 }, (_, index) => index);
};

const matrixProbability = (distribution, goalsA, goalsB) => (
  distribution?.Matrix?.find((item) => item.Goals_A === goalsA && item.Goals_B === goalsB)?.Probability || 0
);

const heatStyle = (goalsA, goalsB, probability, maxProbability) => {
  const intensity = maxProbability > 0 ? Math.min(1, probability / maxProbability) : 0;
  const alpha = 0.12 + intensity * 0.56;

  if (goalsA > goalsB) {
    return { backgroundColor: `rgba(5, 150, 105, ${alpha})` };
  }
  if (goalsB > goalsA) {
    return { backgroundColor: `rgba(66, 165, 245, ${alpha})` };
  }
  return { backgroundColor: `rgba(229, 181, 71, ${alpha})` };
};

const TeamInput = ({ label, value, onChange, onSelect }) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const matches = useMemo(() => countryMatches(value), [value]);
  const hasExactMatch = Boolean(exactCountry(value));

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => document.removeEventListener('mousedown', closeOnOutsideClick);
  }, []);

  return (
    <div className={styles.inputWrap} ref={wrapRef}>
      <label className={styles.inputLabel}>
        <span>{label}</span>
        <input
          className={`${styles.countryInput} ${hasExactMatch ? styles.countryInputReady : ''}`}
          type="text"
          value={value}
          placeholder="Country"
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          autoComplete="off"
        />
      </label>

      {open && matches.length > 0 && (
        <div className={styles.dropdown}>
          {matches.map((country) => (
            <button
              key={country}
              type="button"
              onClick={() => {
                onSelect(country);
                setOpen(false);
              }}
            >
              {country}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const TeamPanel = ({ team }) => (
  <section className={`${styles.teamPanel} ${team.Home_Advantage ? styles.homePanel : ''}`}>
    <div className={styles.teamHead}>
      <div className={styles.flagFrame}>
        <Flag team={flagTeamName(team.Team)} size="lg" />
      </div>
      <div className={styles.teamTitleGroup}>
        <span className={team.Home_Advantage ? styles.homeBadge : styles.neutralBadge}>
          {team.Home_Advantage ? 'Home advantage' : 'Away / neutral'}
        </span>
        <h2>{team.Team}</h2>
      </div>
    </div>
    <dl className={styles.statsList}>
      {STAT_ROWS.map(([label, key, type]) => (
        <div
          key={key}
          className={`${styles.statRow} ${key === 'Winning_Probability' ? styles.statRowPrimary : ''}`}
        >
          <dt>{label}</dt>
          <dd className={statValueClass(type, team[key])}>{formatValue(team[key], type)}</dd>
        </div>
      ))}
    </dl>
  </section>
);

const ScoreDistribution = ({ distribution, teams }) => {
  if (!distribution?.Matrix?.length || teams.length !== 2) return null;

  const goals = scoreRangeFromDistribution(distribution);
  const maxProbability = Math.max(...distribution.Matrix.map((item) => item.Probability));

  return (
    <section className={styles.matrixCard}>
      <div className={styles.matrixHead}>
        <div>
          <span>Score distribution</span>
          <h2>{teams[0].Team} vs {teams[1].Team}</h2>
        </div>
        <div className={styles.xgPills}>
          <span>xG {teams[0].Team}: {distribution.Expected_Goals_A.toFixed(2)}</span>
          <span>xG {teams[1].Team}: {distribution.Expected_Goals_B.toFixed(2)}</span>
        </div>
      </div>

      <div className={styles.matrixLegend}>
        <span className={styles.legendWinA}>{teams[0].Team} win</span>
        <span className={styles.legendDraw}>Draw</span>
        <span className={styles.legendWinB}>{teams[1].Team} win</span>
      </div>

      <div className={styles.axisCaption}>
        <span>Rows: {teams[0].Team} goals</span>
        <span>Columns: {teams[1].Team} goals</span>
      </div>

      <div
        className={styles.matrixGrid}
        style={{ gridTemplateColumns: `68px repeat(${goals.length}, minmax(52px, 1fr))` }}
      >
        <div className={styles.axisCorner}>Score</div>
        {goals.map((goalsB) => (
          <div key={`col-${goalsB}`} className={styles.axisHeader}>
            {goalsB}
          </div>
        ))}

        {goals.map((goalsA) => (
          <div key={`row-${goalsA}`} className={styles.matrixRow}>
            <div className={styles.axisHeader}>{goalsA}</div>
            {goals.map((goalsB) => {
              const probability = matrixProbability(distribution, goalsA, goalsB);
              return (
                <div
                  key={`${goalsA}-${goalsB}`}
                  className={styles.matrixCell}
                  style={heatStyle(goalsA, goalsB, probability, maxProbability)}
                  title={`${teams[0].Team} ${goalsA}-${goalsB} ${teams[1].Team}: ${(probability * 100).toFixed(2)}%`}
                >
                  <strong>{goalsA}-{goalsB}</strong>
                  <span>{(probability * 100).toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
};

const MatchPrediction = () => {
  const [teamOne, setTeamOne] = useState('');
  const [teamTwo, setTeamTwo] = useState('');
  const [matchData, setMatchData] = useState(null);
  const [scoreDistribution, setScoreDistribution] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingDistribution, setLoadingDistribution] = useState(false);
  const [error, setError] = useState('');
  const [distributionError, setDistributionError] = useState('');

  const selectedTeamOne = exactCountry(teamOne);
  const selectedTeamTwo = exactCountry(teamTwo);

  useEffect(() => {
    let ignore = false;

    const loadMatchData = async () => {
      if (!selectedTeamOne || !selectedTeamTwo || selectedTeamOne === selectedTeamTwo) {
        setMatchData(null);
        setScoreDistribution(null);
        setError('');
        setDistributionError('');
        return;
      }

      setLoading(true);
      setError('');

      try {
        const params = new URLSearchParams({
          team_1: selectedTeamOne,
          team_2: selectedTeamTwo,
        });
        const response = await fetch(`${API_PREFIX}/match-data?${params.toString()}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Could not load match data.');
        }

        if (!ignore) {
          setMatchData(data);
          setScoreDistribution(null);
          setDistributionError('');
        }
      } catch (requestError) {
        if (!ignore) {
          setMatchData(null);
          setError(requestError.message || 'Could not load match data.');
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    loadMatchData();

    return () => {
      ignore = true;
    };
  }, [selectedTeamOne, selectedTeamTwo]);

  useEffect(() => {
    let ignore = false;

    const loadScoreDistribution = async () => {
      const teams = matchData?.Teams;
      if (!teams || teams.length !== 2) {
        setScoreDistribution(null);
        setDistributionError('');
        return;
      }

      setLoadingDistribution(true);
      setDistributionError('');

      try {
        const params = new URLSearchParams({
          match_score_a: teams[0].Match_Score,
          match_score_b: teams[1].Match_Score,
        });
        const response = await fetch(`${API_PREFIX}/score-distribution?${params.toString()}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Could not load score distribution.');
        }

        if (!ignore) {
          setScoreDistribution(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setScoreDistribution(null);
          setDistributionError(requestError.message || 'Could not load score distribution.');
        }
      } finally {
        if (!ignore) {
          setLoadingDistribution(false);
        }
      }
    };

    loadScoreDistribution();

    return () => {
      ignore = true;
    };
  }, [matchData]);

  return (
    <div className={styles.wrap}>
      <div className={styles.selectorBar}>
        <TeamInput
          label="Team 1"
          value={teamOne}
          onChange={setTeamOne}
          onSelect={setTeamOne}
        />
        <div className={styles.vs}>vs</div>
        <TeamInput
          label="Team 2"
          value={teamTwo}
          onChange={setTeamTwo}
          onSelect={setTeamTwo}
        />
      </div>

      {loading && <div className={styles.state}>Loading match data...</div>}
      {!loading && error && <div className={styles.state}>{error}</div>}

      {!loading && !error && matchData?.Teams?.length === 2 && (
        <>
          <div className={styles.matchSummary}>
            <span>Match {matchData.Match_ID}</span>
            <strong>{matchData.Team_A} vs {matchData.Team_B}</strong>
          </div>
          <div className={styles.resultsGrid}>
            <TeamPanel team={matchData.Teams[0]} />
            <TeamPanel team={matchData.Teams[1]} />
          </div>
          {loadingDistribution && <div className={styles.state}>Loading score distribution...</div>}
          {!loadingDistribution && distributionError && (
            <div className={styles.state}>{distributionError}</div>
          )}
          {!loadingDistribution && !distributionError && scoreDistribution && (
            <ScoreDistribution distribution={scoreDistribution} teams={matchData.Teams} />
          )}
        </>
      )}

      {!loading && !error && !matchData && (
        <div className={styles.emptyState}>
          <strong>Awaiting matchup</strong>
          <span>Completed fixture data will appear here.</span>
        </div>
      )}
    </div>
  );
};

export default MatchPrediction;
