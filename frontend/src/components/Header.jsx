import styles from './Header.module.css';

const WORLD_CUP_EMBLEM_URL = 'https://upload.wikimedia.org/wikipedia/en/1/17/2026_FIFA_World_Cup_emblem.svg';

const Header = () => {
  return (
    <div className={styles.hdr}>
      <h1>
        <img
          className={styles.logo}
          src={WORLD_CUP_EMBLEM_URL}
          alt="2026 FIFA World Cup emblem"
          width="20"
          height="50"
        />
        <span>2026 World Cup Predictor</span>
      </h1>
      <div className={styles.sub}>A mathematical approach to estimate outcomes</div>
    </div>
  );
};

export default Header;
