use leetcode_db;

-- create table to keep track of upload files' filenames
drop table if exists picfile;
create table picfile (
    pid int primary key,
    filename varchar(50),
    foreign key (pid) references person(pid) 
        on delete cascade on update cascade
);
