-- Drop in dependency order
DROP TABLE IF EXISTS submission;
DROP TABLE IF EXISTS connection;
DROP TABLE IF EXISTS userpass;
DROP TABLE IF EXISTS person;
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS problem;
DROP TABLE IF EXISTS userpass;


-- Problem metadata: one row per LeetCode problem
CREATE TABLE problem (
  lc_problem  INT PRIMARY KEY,                    -- LeetCode frontend ID (1,2,3,...)
  title_slug  VARCHAR(255) UNIQUE NOT NULL,       -- 'two-sum'
  title       VARCHAR(255) NOT NULL,              -- 'Two Sum'
  difficulty  ENUM('easy', 'medium', 'hard')
) ENGINE=InnoDB;


-- Groups
CREATE TABLE groups (
  gid               INT AUTO_INCREMENT PRIMARY KEY,
  group_goal        INT,
  comp_start        DATE,
  comp_end          DATE
) ENGINE=InnoDB;


-- Person: LeetCode users / players
-- Each person may belong to at most one group via gid
CREATE TABLE person (
  pid            INT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(50),
  name           VARCHAR(50),
  birthday       DATE,
  lc_username    VARCHAR(50),
  current_streak INT,
  longest_streak INT,
  total_problems INT,
  num_coins      INT,
  personal_goal  INT,
  gid            INT,                  -- current group membership (nullable)
  latest_submission DATE,
  FOREIGN KEY (gid) REFERENCES groups(gid)
    ON DELETE SET NULL
    ON UPDATE CASCADE
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
    person_id  INT PRIMARY KEY,          -- PK and FK to person
    username   VARCHAR(50) NOT NULL UNIQUE,
    hashed     CHAR(60) NOT NULL,
    FOREIGN KEY (person_id) REFERENCES person(pid)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;
