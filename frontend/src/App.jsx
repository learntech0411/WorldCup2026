import { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import GroupStage from './components/GroupStage';
import Knockout from './components/Knockout';
import Stats from './components/History';
import HowItWorks from './components/Author';
import './App.css';

const API_PREFIX = import.meta.env.VITE_API_PREFIX || 'http://localhost:8000/api';
const MODES = {
  Current: 'current',
  Prediction: 'predicted',
};

const hasScore = (value) => value != null && String(value).trim() !== '';

const normalizeScore = (score, targetMode) => {
  const base = {
    Match_ID: Number(score.Match_ID),
    Team_A: score.Team_A ?? null,
    Team_B: score.Team_B ?? null,
  };

  if (targetMode === 'Current') {
    return {
      ...base,
      Goals_A: score.Goals_A ?? null,
      Goals_B: score.Goals_B ?? null,
    };
  }

  return {
    ...base,
    Predicted_Goals_A: score.Predicted_Goals_A ?? null,
    Predicted_Goals_B: score.Predicted_Goals_B ?? null,
    Winning_Probability_A: score.Winning_Probability_A ?? null,
    Winning_Probability_B: score.Winning_Probability_B ?? null,
    Draw_Probability: score.Draw_Probability ?? null,
  };
};

function App() {
  const [activeTab, setActiveTab] = useState('groups');
  const [mode, setMode] = useState('Current');
  const [groupMatrices, setGroupMatrices] = useState({ Current: null, Prediction: null });
  const [matchScores, setMatchScores] = useState({ Current: {}, Prediction: {} });
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadingScores, setLoadingScores] = useState({ Current: false, Prediction: false });
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('wc26_theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  });

  const fetchGroupMatrix = useCallback(async (targetMode) => {
    if (groupMatrices[targetMode]) return;
    setLoadingGroups(true);
    try {
      const endpoint = `${API_PREFIX}/all-groups-${MODES[targetMode]}-matrix`;
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`Failed to load ${targetMode} groups`);
      }
      const data = await response.json();
      setGroupMatrices((prev) => ({
        ...prev,
        [targetMode]: data.Groups || data.groups || {},
      }));
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingGroups(false);
    }
  }, [groupMatrices]);

  const fetchMatchScores = useCallback(async (targetMode) => {
    setLoadingScores((prev) => ({ ...prev, [targetMode]: true }));
    try {
      const endpoint = `${API_PREFIX}/all-${MODES[targetMode]}-scores`;
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`Failed to load ${targetMode} scores`);
      }
      const data = await response.json();
      const scoresById = Object.fromEntries(
        (Array.isArray(data) ? data : [])
          .map((score) => normalizeScore(score, targetMode))
          .filter((score) => Number.isFinite(score.Match_ID))
          .map((score) => [score.Match_ID, score])
      );

      setMatchScores((prev) => ({
        ...prev,
        [targetMode]: scoresById,
      }));
    } catch (error) {
      console.error(error);
    } finally {
      setLoadingScores((prev) => ({ ...prev, [targetMode]: false }));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchGroupMatrix(mode);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [mode, fetchGroupMatrix]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchMatchScores('Current');
      fetchMatchScores('Prediction');
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchMatchScores]);

  useEffect(() => {
    localStorage.setItem('wc26_theme', theme);
    if (theme === 'dark') {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const toggleMode = () => {
    setMode((prev) => (prev === 'Current' ? 'Prediction' : 'Current'));
  };

  const currentGroupMatrix = groupMatrices[mode];
  const currentMatchScores = matchScores[mode];
  const currentGroupStageComplete = Array.from(
    { length: 72 },
    (_, index) => matchScores.Current[index + 1]
  ).every((score) => score && hasScore(score.Goals_A) && hasScore(score.Goals_B));

  return (
    <div className="App">
      <div className="topbar-ctrl">
        <button className="ctrl-icon" onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? '☀' : '🌙'}
        </button>
      </div>

      <Header />
      <Tabs activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="main-content">
        {activeTab === 'groups' && (
          <GroupStage
            mode={mode}
            onToggleMode={toggleMode}
            groupMatrix={currentGroupMatrix}
            matchScores={currentMatchScores}
            predictionScores={matchScores.Prediction}
            loading={loadingGroups || loadingScores[mode]}
          />
        )}
        {activeTab === 'knockout' && (
          <Knockout
            mode={mode}
            matchScores={currentMatchScores}
            predictionScores={matchScores.Prediction}
            currentGroupStageComplete={currentGroupStageComplete}
          />
        )}
        {activeTab === 'stats' && (
          <Stats />
        )}
        {activeTab === 'how-it-works' && (
          <HowItWorks />
        )}
      </main>
    </div>
  );
}

export default App;
