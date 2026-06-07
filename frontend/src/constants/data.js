export const FC = {
  "Mexico": "mx", "South Africa": "za", "South Korea": "kr", "Czechia": "cz", "Canada": "ca", "Bosnia and Herzegovina": "ba",
  "Qatar": "qa", "Switzerland": "ch", "Brazil": "br", "Morocco": "ma", "Haiti": "ht", "Scotland": "gb-sct",
  "United States": "us", "Paraguay": "py", "Australia": "au", "Turkey": "tr", "Germany": "de", "Curacao": "cw",
  "Ivory Coast": "ci", "Ecuador": "ec", "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
  "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz", "Spain": "es", "Cape Verde": "cv",
  "Saudi Arabia": "sa", "Uruguay": "uy", "France": "fr", "Iraq": "iq", "Senegal": "sn", "Norway": "no",
  "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo", "Portugal": "pt", "DR Congo": "cd",
  "Uzbekistan": "uz", "Colombia": "co", "England": "gb-eng", "Croatia": "hr", "Ghana": "gh", "Panama": "pa"
};

export const GD = {
  A: ["Mexico", "South Africa", "South Korea", "Czechia"],
  B: ["Canada", "Bosnia", "Qatar", "Switzerland"],
  C: ["Brazil", "Morocco", "Haiti", "Scotland"],
  D: ["USA", "Paraguay", "Australia", "Türkiye"],
  E: ["Germany", "Curaçao", "Côte d'Ivoire", "Ecuador"],
  F: ["Netherlands", "Japan", "Sweden", "Tunisia"],
  G: ["Belgium", "Egypt", "Iran", "New Zealand"],
  H: ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
  I: ["France", "Iraq", "Senegal", "Norway"],
  J: ["Argentina", "Algeria", "Austria", "Jordan"],
  K: ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
  L: ["England", "Croatia", "Ghana", "Panama"]
};

export const R32D = [
  { i: "R1", h: "2A", a: "2B" }, { i: "R2", h: "1E", a: "3_ABCDF" },
  { i: "R3", h: "1F", a: "2C" }, { i: "R4", h: "1C", a: "2F" },
  { i: "R5", h: "1I", a: "3_CDFGH" }, { i: "R6", h: "2E", a: "2I" },
  { i: "R7", h: "1A", a: "3_CEFHI" }, { i: "R8", h: "1L", a: "3_EHIJK" },
  { i: "R9", h: "1D", a: "3_BEFIJ" }, { i: "R10", h: "1G", a: "3_AEHIJ" },
  { i: "R11", h: "2K", a: "2L" }, { i: "R12", h: "1H", a: "2J" },
  { i: "R13", h: "1B", a: "3_EFGIJ" }, { i: "R14", h: "1J", a: "2H" },
  { i: "R15", h: "1K", a: "3_DEIJL" }, { i: "R16", h: "2D", a: "2G" }
];

export const R16P = [["R2", "R5"], ["R1", "R3"], ["R4", "R6"], ["R7", "R8"], ["R11", "R12"], ["R9", "R10"], ["R14", "R16"], ["R13", "R15"]];
export const QFP = [["L1", "L2"], ["L5", "L6"], ["L3", "L4"], ["L7", "L8"]];
export const SFP = [["Q1", "Q2"], ["Q3", "Q4"]];

export const TEAM_ORDER = {};
(function () {
  let n = 1;
  for (let g in GD) {
    for (let i = 0; i < GD[g].length; i++) TEAM_ORDER[GD[g][i]] = n++;
  }
})();
