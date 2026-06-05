import React from 'react';
import { FC } from '../constants/data';
import styles from './Flag.module.css';

const Flag = ({ team, size = 'md', className = '' }) => {
  const code = FC[team];
  if (!code) return <span className={`${styles.placeholder} ${styles[size]} ${className}`}>?</span>;

  return (
    <img
      className={`${styles.flag} ${styles[size]} ${className}`}
      src={`https://flagcdn.com/w40/${code}.png`}
      alt={team}
      onError={(e) => { e.target.style.display = 'none'; }}
    />
  );
};

export default Flag;
