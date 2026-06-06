import { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import GroupStage from './components/GroupStage';
import Knockout from './components/Knockout';
import History from './components/History';
import Author from './components/Author';
import './App.css';

const API_PREFIX = import.meta.env.VITE_API_PREFIX || 'http://localhost:8000/api';
const MODES = {
  Current: 'current',
  Prediction: 'predicted',
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
        (Array.isArray(data) ? data : []).map((score) => [Number(score.Match_ID), score])
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
            loading={loadingGroups || loadingScores[mode]}
          />
        )}
        {activeTab === 'knockout' && (
          <Knockout
            mode={mode}
            groupMatrix={currentGroupMatrix}
            matchScores={currentMatchScores}
          />
        )}
        {activeTab === 'history' && (
          <History />
        )}
        {activeTab === 'author' && (
          <Author />
        )}
      </main>
    </div>
  );
}

export default App;
