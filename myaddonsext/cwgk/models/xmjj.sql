create table cwgk_department(
    id integer,
    name varchar(50),
    parent_id integer,
    primary key(id)
);

CREATE SEQUENCE cwgk_department_id_seq
INCREMENT 1
MINVALUE 1;

create table cwgk_employee(
    id integer,
    name varchar(50),
    department_id integer,
    number integer,
    post varchar(20),
    rz_date date,
    zz_date date,
    current_pay float,
    primary key(id)
);

create sequence cwgk_employee_id_seq
increment 1 minvalue 1;

