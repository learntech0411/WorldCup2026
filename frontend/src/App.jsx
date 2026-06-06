import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import GroupStage from './components/GroupStage';
import Knockout from './components/Knockout';
import History from './components/History';
import Author from './components/Author';
import './App.css';

const API_PREFIX = 'https://worldcup2026-ksnz.onrender.com/api';
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

  const fetchMatchScore = useCallback(async (matchId) => {
    if (!matchId) return;
    const cache = matchScores[mode];
    if (cache[matchId] && !cache[matchId].error) return;

    setMatchScores((prev) => ({
      ...prev,
      [mode]: {
        ...prev[mode],
        [matchId]: { loading: true },
      },
    }));

    try {
      const endpoint = `${API_PREFIX}/${MODES[mode]}-score/${matchId}`;
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`Failed to load score ${matchId}`);
      }
      const data = await response.json();
      setMatchScores((prev) => ({
        ...prev,
        [mode]: {
          ...prev[mode],
          [matchId]: { ...data, loading: false },
        },
      }));
    } catch (error) {
      console.error(error);
      setMatchScores((prev) => ({
        ...prev,
        [mode]: {
          ...prev[mode],
          [matchId]: { error: true, loading: false },
        },
      }));
    }
  }, [mode, matchScores]);

  useEffect(() => {
    fetchGroupMatrix(mode);
  }, [mode, fetchGroupMatrix]);

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
            fetchMatchScore={fetchMatchScore}
            loading={loadingGroups}
          />
        )}
        {activeTab === 'knockout' && (
          <Knockout
            mode={mode}
            groupMatrix={currentGroupMatrix}
            matchScores={currentMatchScores}
            fetchMatchScore={fetchMatchScore}
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
