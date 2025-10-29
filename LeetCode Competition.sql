CREATE TABLE `person` (
  `pid` int PRIMARY KEY,
  `name` varchar(50),
  `birthday` date,
  `lc_username` varchar(50),
  `current_streak` int,
  `longest_streak` int,
  `total_problems` int,
  `num_coins` int,
  `personal_goal` int,
  `gid` int
);

CREATE TABLE `connection` (
  `cid` int PRIMARY KEY,
  `p1` int,
  `p2` int
);

CREATE TABLE `group` (
  `gid` int PRIMARY KEY,
  `group_goal` int,
  `longest_streak_id` int,
  `longest_streak` int,
  `current_streak_id` int,
  `current_streak` int,
  `comp_start` date,
  `comp_end` date,
  `last_winner` int
);

CREATE TABLE `submission` (
  `sid` int PRIMARY KEY,
  `pid` int,
  `lc_problem` int,
  `submission_date` date,
  `difficulty` ENUM ('easy', 'medium', 'hard'),
  `coins` int
);

ALTER TABLE `person` ADD FOREIGN KEY (`gid`) REFERENCES `group` (`gid`);

ALTER TABLE `connection` ADD FOREIGN KEY (`p1`) REFERENCES `person` (`pid`);

ALTER TABLE `connection` ADD FOREIGN KEY (`p2`) REFERENCES `person` (`pid`);

ALTER TABLE `group` ADD FOREIGN KEY (`last_winner`) REFERENCES `person` (`pid`);

ALTER TABLE `group` ADD FOREIGN KEY (`longest_streak_id`) REFERENCES `person` (`pid`);

ALTER TABLE `group` ADD FOREIGN KEY (`current_streak_id`) REFERENCES `person` (`pid`);

ALTER TABLE `submission` ADD FOREIGN KEY (`pid`) REFERENCES `person` (`pid`);
