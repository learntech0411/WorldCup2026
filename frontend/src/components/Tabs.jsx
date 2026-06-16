import styles from './Tabs.module.css';

const Tabs = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'groups', name: 'Group Stage', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 5h14"></path>
        <path d="M5 12h14"></path>
        <path d="M5 19h14"></path>
        <path d="M8 3v18"></path>
        <path d="M16 3v18"></path>
      </svg>
    )},
    { id: 'knockout', name: 'Knockout', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 6h5"></path>
        <path d="M5 18h5"></path>
        <path d="M10 6v12"></path>
        <path d="M10 12h5"></path>
        <path d="M15 12h4"></path>
        <path d="m17 9 3 3-3 3"></path>
      </svg>
    )},
    { id: 'match-prediction', name: 'Match Prediction', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M7 7h10"></path>
        <path d="M7 17h10"></path>
        <path d="M9 5v4"></path>
        <path d="M15 15v4"></path>
        <path d="m11 12 2-2 2 2-2 2-2-2Z"></path>
      </svg>
    )},
    { id: 'how-it-works', name: 'How it works', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 18h6"></path>
        <path d="M10 22h4"></path>
        <path d="M12 2a7 7 0 0 0-4 12.74V16h8v-1.26A7 7 0 0 0 12 2Z"></path>
        <path d="M10 10h4"></path>
        <path d="M12 8v4"></path>
      </svg>
    )}
  ];

  return (
    <div className={styles.tabs}>
      <div className={styles.inner}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? styles.on : ''}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.icon}
            <span>{tab.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default Tabs;
