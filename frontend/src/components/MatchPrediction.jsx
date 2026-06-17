import { useEffect, useMemo, useRef, useState } from 'react';
import { FC } from '../constants/data';
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
  if (type === 'percent') return `${(Number(value) * 100).toFixed(1)}%`;
  if (type === 'distance') return `${Number(value).toFixed(1)} km`;
  if (type === 'market') return `€${Number(value).toFixed(1)}m`;
  if (type === 'boolean') return value ? 'Yes' : 'No';
  if (type === 'number') return Number(value).toFixed(1);
  return String(value);
};

const TeamInput = ({ label, value, onChange, onSelect }) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const matches = useMemo(() => countryMatches(value), [value]);

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
          type="text"
          value={value}
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
  <section className={styles.teamPanel}>
    <h2>{team.Team}</h2>
    <dl className={styles.statsList}>
      {STAT_ROWS.map(([label, key, type]) => (
        <div key={key} className={styles.statRow}>
          <dt>{label}</dt>
          <dd>{formatValue(team[key], type)}</dd>
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
        <div className={styles.resultsGrid}>
          <TeamPanel team={matchData.Teams[0]} />
          <TeamPanel team={matchData.Teams[1]} />
        </div>
      )}
    </div>
  );
};

export default MatchPrediction;
