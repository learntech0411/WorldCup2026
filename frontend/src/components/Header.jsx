import React from 'react';
import styles from './Header.module.css';

const Header = () => {
  return (
    <div className={styles.hdr}>
      <h1>
        <svg className={styles.logo} width="44" height="44" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-label="World Cup 2026">
          <circle cx="32" cy="32" r="30" fill="#07110C" />
          <circle cx="32" cy="32" r="29" fill="none" stroke="#E5C26A" stroke-width="1.5" />
          <circle cx="32" cy="20" r="6.5" fill="#E5C26A" />
          <ellipse cx="29.5" cy="17.8" rx="2.2" ry="1.5" fill="#F0CC7E" opacity="0.65" />
          <path d="M27 27 Q22.5 32 25 38 L28.5 42 L35.5 42 L39 38 Q41.5 32 37 27 Z" fill="#E5C26A" />
          <rect x="24" y="44" width="16" height="3" rx="0.6" fill="#E5C26A" />
          <rect x="22" y="48" width="20" height="3" rx="0.6" fill="#E5C26A" />
          <text x="32" y="59" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="5.5" font-weight="800" fill="#E5C26A" letter-spacing="0.4">2026</text>
        </svg>
        <span>2026 World Cup Predictor</span>
      </h1>
      <div className={styles.sub}>🇺🇸 USA · 🇲🇽 Mexico · 🇨🇦 Canada</div>
    </div>
  );
};

export default Header;
