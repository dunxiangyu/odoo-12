drop table xtgldxlx

drop SEQUENCE xtgldxlx_id_seq

create table xtgldxlx(
	id integer,
	dxlxid varchar(20),
	name varchar(200),
	value integer,
	value2 integer
)

CREATE SEQUENCE xtgldxlx_id_seq
INCREMENT 1
MINVALUE 1

insert into xtgldxlx(id,dxlxid,name,value)
values(nextval('xtgldxlx_id_seq'),'1001','组织',10200)

insert into xtgldxlx(id,dxlxid,name,value)
values(nextval('xtgldxlx_id_seq'),'1002','用户',10201)

