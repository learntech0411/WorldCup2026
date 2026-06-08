import styles from './HowItWorks.module.css';

const countryData = [
  'Elo rating, which gives me a simple historical strength estimate based on past results, match importance, and opponent strength.',
  'The group the country belongs to in the group stage.',
  'The base camp location where the team is expected to stay for most of the tournament.',
  'The players included in the team data.',
];

const playerData = [
  'Transfer value',
  'Position',
  'Age',
  'Club',
  'Whether the player is injured or available',
];

const matchData = [
  'All 104 World Cup matches',
  'The teams playing each match',
  'Match date',
  'Stadium',
];

const processingMultipliers = [
  ['Age Mult', 'Players in different age ranges get adjusted. Experienced players get a small boost while very young players are treated more carefully since their transfer value also includes future potential.'],
  ['Position Mult', 'Positions are weighted differently because a player’s role changes how much their value should affect the team.'],
  ['Rank Mult', 'I rank players inside each national team. The top players keep the most weight, while players who are less likely to play get reduced weight.'],
  ['Synergy Mult', 'Players from the same club get a small boost because they may already understand each other’s movement and style.'],
];

const matchPowerScoreParts = [
  ['Base strength', 'This comes from the blended Elo and player utility value of the country.'],
  ['Home boost', 'Mexico, the United States, and Canada get +100 Elo when they play in their own country.'],
  ['Rest adjustment', 'I compare how many days each team had since its previous match. The team with less rest loses 15 Elo per missing rest day, while the team with more rest gets the same amount as a boost. If both teams have not played yet, this stays neutral.'],
  ['Travel penalty', 'I use the Haversine distance to estimate travel. In the group stage, I measure from the team base camp to the match stadium. In the knockout stage, I use the previous knockout stadium if the team already played one; otherwise I use the base camp.'],
  ['Timezone penalty', 'I subtract 5 Elo for every timezone crossed, and 1 Elo for every 500 km travelled.'],
];

const predictionSteps = [
  ['Expected goals', 'I compare both match power scores and convert the difference into expected goals. If one team has a stronger score, its expected goals go up while the opponent’s expected goals go down. I also keep the values inside a reasonable range, so the model does not predict extreme results too easily.'],
  ['Poisson probabilities', 'With the expected goals, I use a Poisson model to estimate how likely each scoreline is. This gives me probabilities for results like 0-0, 1-0, 2-1, and so on.'],
  ['Dixon-Coles adjustment', 'I then apply a small Dixon-Coles adjustment, which helps football predictions handle very common low-score results like 0-0, 1-0, 0-1, and 1-1 a bit better.'],
  ['Final prediction', 'From the scoreline matrix, I pick the most likely exact score and also sum the matrix into win probability for Team A, win probability for Team B, and draw probability.'],
];

const tournamentPredictionSteps = [
  ['Group stage', 'I first predict all group matches, then build the group tables from those predicted scores. The table uses points, goal difference, goals scored, Elo, and team name as tie-breakers.'],
  ['Round of 32', 'The first and second placed teams can be placed directly from the group tables. For third placed teams, I rank all third placed teams, take the best 8, and then out of 495 possible matchups, I find the matching one so each third-place team gets the correct opponent.'],
  ['Knockout stage', 'After the Round of 32 is filled, I predict one round at a time. Winners move into the next matches, and if a predicted score is tied, the team with the higher winning probability advances. This continues until the final.'],
];

const HowItWorks = () => {
  return (
    <div className={styles.baselineCard}>
      <div className={styles.baselineHead}>
        <h2>How it works</h2>
      </div>

      <div className={styles.baselineChampCard}>
        <div className={styles.blChampLabel}>Project overview</div>
        <p className={styles.blPending}>
          This is my attempt at predicting the World cup 2026 match scores and its development from Group Stage into the Round of 32 and the later rounds of the Knockout Stage.
        </p>
      </div>

      <div className={styles.blCompareCard}>
        <h3>Data Collection</h3>
        <p className={styles.blPending}>
          I collected a few different kinds of data so that the predictions can be based on multiple factors that contribute to a team’s strength and match outcomes.
        </p>

        <div className={styles.dataGroup}>
          <h4>For each country</h4>
          <ul>
            {countryData.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.dataGroup}>
          <h4>For each player</h4>
          <ul>
            {playerData.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.dataGroup}>
          <h4>For the tournament schedule</h4>
          <ul>
            {matchData.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>

        <p className={styles.blPending}>
          For stadiums and base camps, I also used GeoPy to get latitude and longitude, then used those coordinates to calculate the local timezone.
        </p>
      </div>

      <div className={styles.blCompareCard}>
        <h3>Data Processing</h3>
        <p className={styles.blPending}>
          The player transfer value is my starting point, but I did not want to use it directly. A player can be expensive without being equally useful for this specific World Cup, so I transform the value first.
        </p>

        <div className={styles.dataGroup}>
          <h4>Player utility value</h4>
          <p className={styles.blPending}>
            I start with each player’s market value, then apply a few multipliers to estimate how useful that player could be for the tournament.
          </p>
          <ul>
            {processingMultipliers.map(([label, text]) => (
              <li key={label}>
                <strong>{label}:</strong> {text}
              </li>
            ))}
          </ul>
        </div>

        <div className={styles.dataGroup}>
          <h4>Injuries</h4>
          <p className={styles.blPending}>
            If a player is marked as injured, I set their value to 0 because they are very unlikely to help the team in the matches.
          </p>
        </div>

        <div className={styles.dataGroup}>
          <h4>Team strength</h4>
          <p className={styles.blPending}>
            After calculating the player utility values, I sum them up for each country. Then I blend that team utility with the country’s Elo rating, so the final strength uses both squad quality and historical team performance.
          </p>
        </div>

        <div className={styles.dataGroup}>
          <h4>Match power score</h4>
          <p className={styles.blPending}>
            For every match, I calculate a power score for Team A and Team B based on the match id and the two countries playing.
          </p>
          <ul>
            {matchPowerScoreParts.map(([label, text]) => (
              <li key={label}>
                <strong>{label}:</strong> {text}
              </li>
            ))}
          </ul>
          <p className={styles.blPending}>
            The result is <strong>Match_Power_Score_A</strong> and <strong>Match_Power_Score_B</strong>, which are then used for the match prediction.
          </p>
        </div>
      </div>

      <div className={styles.blCompareCard}>
        <h3>Prediction</h3>
        <p className={styles.blPending}>
          Once the match power scores are ready, I turn them into actual match predictions. I wanted this part to stay understandable, so the idea is: estimate how many goals each team is expected to score, then use those goal expectations to calculate the most likely result.
        </p>

        <div className={styles.dataGroup}>
          <h4>Predicting one match</h4>
          <ul>
            {predictionSteps.map(([label, text]) => (
              <li key={label}>
                <strong>{label}:</strong> {text}
              </li>
            ))}
          </ul>
        </div>

        <div className={styles.dataGroup}>
          <h4>Predicting the tournament flow</h4>
          <ul>
            {tournamentPredictionSteps.map(([label, text]) => (
              <li key={label}>
                <strong>{label}:</strong> {text}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default HowItWorks;
