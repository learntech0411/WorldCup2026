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

const MatchPrediction = () => {
  const [teamOne, setTeamOne] = useState('');
  const [teamTwo, setTeamTwo] = useState('');
  const [matchData, setMatchData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const selectedTeamOne = exactCountry(teamOne);
  const selectedTeamTwo = exactCountry(teamTwo);

  useEffect(() => {
    let ignore = false;

    const loadMatchData = async () => {
      if (!selectedTeamOne || !selectedTeamTwo || selectedTeamOne === selectedTeamTwo) {
        setMatchData(null);
        setError('');
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
