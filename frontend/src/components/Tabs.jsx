import React from 'react';
import styles from './Tabs.module.css';

const Tabs = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'groups', name: 'Group Stage', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <rect x="4" y="4" width="6" height="6" rx="1"></rect>
        <rect x="14" y="4" width="6" height="6" rx="1"></rect>
        <rect x="4" y="14" width="6" height="6" rx="1"></rect>
        <rect x="14" y="14" width="6" height="6" rx="1"></rect>
      </svg>
    )},
    { id: 'knockout', name: 'Knockout', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <path d="M6 6h6v12H6"></path>
        <path d="M12 12h6"></path>
        <path d="M18 12l-3-3"></path>
        <path d="M18 12l-3 3"></path>
      </svg>
    )},
    { id: 'history', name: 'History', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
      </svg>
    )},
    { id: 'author', name: 'Author', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9"></circle>
        <path d="M12 7v5l3 3"></path>
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
