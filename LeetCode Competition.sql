-- drop tables in reverse order
drop table if exists `connection`;
drop table if exists submission;
drop table if exists pg;
drop table if exists person;
drop table if exists group;

CREATE TABLE person (
  `pid` int,
  `name` varchar(50),
  `birthday` date,
  `lc_username` varchar(50),
  `current_streak` int,
  `longest_streak` int,
  `total_problems` int,
  `num_coins` int,
  `personal_goal` int,
  primary key (pid)
);
ENGINE = InnoDB;

CREATE TABLE `connection` (
  `p1` int,
  `p2` int,
  primary key (p1,p2), 
);
ENGINE = InnoDB;

CREATE TABLE pg (
  `pid` int,
  `gid` int,
  primary key (pid, gid)
);
ENGINE = InnoDB;

CREATE TABLE group (
  `gid` int,
  `group_goal` int,
  `longest_streak_id` int,
  `longest_streak` int,
  `current_streak_id` int,
  `current_streak` int,
  `comp_start` date,
  `comp_end` date,
  `last_winner` int,
  primary key(gid)
);
ENGINE = InnoDB;

CREATE TABLE submission (
  `sid` int PRIMARY KEY,
  `pid` int,
  `lc_problem` int,
  `submission_date` date,
  `difficulty` ENUM ('easy', 'medium', 'hard'),
  `coins` int
);
ENGINE = InnoDB;
