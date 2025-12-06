-- Drop in dependency order
DROP TABLE IF EXISTS submission;
DROP TABLE IF EXISTS connection;
DROP TABLE IF EXISTS userpass;
DROP TABLE IF EXISTS party_total_stats;
DROP TABLE IF EXISTS individual_party_stats;
DROP TABLE IF EXISTS party_membership;
DROP TABLE IF EXISTS code_party;
DROP TABLE IF EXISTS person;
DROP TABLE IF EXISTS problem;


-- Problem metadata: one row per LeetCode problem
CREATE TABLE problem (
  lc_problem  INT PRIMARY KEY,                    -- LeetCode frontend ID (1,2,3,...)
  title_slug  VARCHAR(255) UNIQUE NOT NULL,       -- 'two-sum'
  title       VARCHAR(255) NOT NULL,              -- 'Two Sum'
  difficulty  ENUM('easy', 'medium', 'hard')
) ENGINE=InnoDB;


-- Person: LeetCode users / players
-- Each person may belong to at most one group via gid
CREATE TABLE person (
  pid            INT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(50) NOT NULL UNIQUE,
  name           VARCHAR(50),
  birthday       DATE,
  lc_username    VARCHAR(50) NOT NULL UNIQUE,
  current_streak INT,
  longest_streak INT,
  total_problems INT,
  num_coins      INT,
  personal_goal  INT,                -- current group membership (nullable)
  latest_submission DATE
) ENGINE=InnoDB;

-- Code Parties! 
-- This is the configuration stuff/logistics of party
CREATE TABLE code_party (
  cpid        INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(200) NOT NULL DEFAULT 'Nameless Party',
  party_goal  INT,
  party_start DATE NOT NULL,
  party_end   DATE NOT NULL,
  status      ENUM('upcoming', 'in_progress', 'completed') DEFAULT 'upcoming',
  winner      INT NULL,
  FOREIGN KEY (winner) REFERENCES person(pid)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB;


-- One time membership/joining into the party
CREATE TABLE party_membership (
  pid   INT,
  cpid  INT,
  joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (pid, cpid),
  FOREIGN KEY (pid) REFERENCES person(pid)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  FOREIGN KEY (cpid) REFERENCES code_party(cpid)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB;

-- This is per-user-per-party results from party
-- could add a weighted score thing but little complicated rn to consider
CREATE TABLE individual_party_stats (
  pid   INT,
  cpid  INT,

  problems_solved INT DEFAULT 0,
  -- Local party streaks: always start at 0
  party_current_streak INT DEFAULT 0,
  party_max_streak     INT DEFAULT 0,

  rank  INT NULL,

  PRIMARY KEY (pid, cpid),

  FOREIGN KEY (pid) REFERENCES person(pid)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  FOREIGN KEY (cpid) REFERENCES code_party(cpid)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB;

-- For the whole party general stats
CREATE TABLE party_total_stats (
  cpid                 INT PRIMARY KEY,

  total_problems       INT DEFAULT 0,
  total_participants   INT DEFAULT 0,
  avg_problems         FLOAT DEFAULT 0,
  max_daily_problems   INT DEFAULT 0,

  party_duration_days  INT DEFAULT 0,

  FOREIGN KEY (cpid) REFERENCES code_party(cpid)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- Connections between people (e.g., friends)
CREATE TABLE connection (
  p1 INT NOT NULL,
  p2 INT NOT NULL,
  PRIMARY KEY (p1, p2),
  FOREIGN KEY (p1) REFERENCES person(pid)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  FOREIGN KEY (p2) REFERENCES person(pid)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB;


-- Submissions / solved problems: one row per (person, problem)
CREATE TABLE submission (
  sid             INT AUTO_INCREMENT PRIMARY KEY,
  pid             INT NOT NULL,          -- FK to person
  lc_problem      INT NOT NULL,          -- FK to problem
  submission_date DATE NOT NULL,
  coins           INT DEFAULT 0,
  latest_submission DATE,

  UNIQUE KEY uniq_user_problem (pid, lc_problem),

  FOREIGN KEY (pid) REFERENCES person(pid)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  FOREIGN KEY (lc_problem) REFERENCES problem(lc_problem)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE userpass (
    pid  INT PRIMARY KEY,          -- PK and FK to person
    hashed     CHAR(60) NOT NULL,
    FOREIGN KEY (pid) REFERENCES person(pid)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;
