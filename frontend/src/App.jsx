import { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import GroupStage from './components/GroupStage';
import Knockout from './components/Knockout';
import Stats from './components/Stats';
import HowItWorks from './components/HowItWorks';
import { FC } from './constants/data';
import './App.css';

const API_PREFIX = import.meta.env.VITE_API_PREFIX || 'http://localhost:8000/api';
const MODES = {
  Current: 'current',
  Prediction: 'predicted',
};

const subdivisionFlagEmoji = (tag) => {
  const tagCharacters = tag
    .split('')
    .map((letter) => String.fromCodePoint(0xE0061 + letter.charCodeAt(0) - 97))
    .join('');

  return `🏴${tagCharacters}${String.fromCodePoint(0xE007F)}`;
};

const countryCodeToFlagEmoji = (code) => {
  if (code === 'gb-eng') return subdivisionFlagEmoji('gbeng');
  if (code === 'gb-sct') return subdivisionFlagEmoji('gbsct');
  if (!/^[a-z]{2}$/i.test(code)) return '';

  return code
    .toUpperCase()
    .split('')
    .map((letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)))
    .join('');
};

const PARTICIPATING_COUNTRY_FLAGS = Object.values(FC)
  .map(countryCodeToFlagEmoji)
  .filter(Boolean);
const FLOATING_EMOJIS = ['⚽', '⚽', '⚽', '⚽', '⚽', '⚽', '⚽', '⚽', '⚽', '🌍', '🏆', '🎉', ...PARTICIPATING_COUNTRY_FLAGS];
const EMOJIS_PER_EMPTY_SPACE_CLICK = 7;
const EMPTY_SPACE_IGNORE_SELECTOR = [
  'button',
  'a',
  'input',
  'select',
  'textarea',
  '[role="button"]',
  'img',
  'svg',
  'canvas',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'h1',
  'h2',
  'h3',
  'h4',
  'p',
  'span',
  'li',
  'ul',
  '[class*="card"]',
  '[class*="Card"]',
  '[class*="row"]',
  '[class*="Row"]',
  '[class*="match"]',
  '[class*="Match"]',
  '[class*="bkM"]',
  '[class*="bkTitle"]',
  '[class*="dataGroup"]',
  '[class*="topbar"]',
  '[class*="tabs"]',
  '[class*="Tabs"]',
].join(',');

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
  const [floatingEmojis, setFloatingEmojis] = useState([]);
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

  const handleEmptySpaceClick = (event) => {
    if (event.target.closest(EMPTY_SPACE_IGNORE_SELECTOR)) return;

    const newEmojis = Array.from({ length: EMOJIS_PER_EMPTY_SPACE_CLICK }, (_, index) => {
      const emoji = FLOATING_EMOJIS[Math.floor(Math.random() * FLOATING_EMOJIS.length)];
      const offsetX = Math.round((Math.random() - 0.5) * 44);
      const offsetY = Math.round((Math.random() - 0.5) * 30);
      const drift = Math.round((Math.random() - 0.5) * 90);
      const rotation = Math.round((Math.random() - 0.5) * 70);

      return {
        id: `${Date.now()}-${index}-${Math.random()}`,
        emoji,
        x: event.clientX + offsetX,
        y: event.clientY + offsetY,
        drift,
        rotation,
      };
    });

    setFloatingEmojis((prev) => [
      ...prev.slice(-42),
      ...newEmojis,
    ]);
  };

  const removeFloatingEmoji = (id) => {
    setFloatingEmojis((prev) => prev.filter((item) => item.id !== id));
  };

  const currentGroupMatrix = groupMatrices[mode];
  const currentMatchScores = matchScores[mode];
  const currentGroupStageComplete = Array.from(
    { length: 72 },
    (_, index) => matchScores.Current[index + 1]
  ).every((score) => score && hasScore(score.Goals_A) && hasScore(score.Goals_B));

  return (
    <div className="App" onClick={handleEmptySpaceClick}>
      <div className="floating-emoji-layer" aria-hidden="true">
        {floatingEmojis.map((item) => (
          <span
            key={item.id}
            className="floating-emoji"
            style={{
              left: item.x,
              top: item.y,
              '--emoji-drift': `${item.drift}px`,
              '--emoji-rotation': `${item.rotation}deg`,
            }}
            onAnimationEnd={() => removeFloatingEmoji(item.id)}
          >
            {item.emoji}
          </span>
        ))}
      </div>

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
            onToggleMode={toggleMode}
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
