import psycopg2
import mysql.connector

dbs = {
    'core': {
        'type': 'postgresql',
        'host': 'localhost',
        'port': 5432,
        'user': 'odoo',
        'password': 'odoo',
        'database': 'odoo-12'
    },
    'mysql': {
        'type': 'mysql',
        'host': 'localhost',
        'port': 3306,
        'user': 'odoo',
        'password': 'odoo',
        'database': 'employees'
    }
}


def db_connect(name):
    config = dbs[name]
    type = config['type'] or 'postgresql'
    connection_info = {}
    for p in ['host', 'port', 'user', 'password', 'database']:
        connection_info[p] = config[p]

    if type == 'mysql':
        conn = mysql.connector.connect(**connection_info)
    else:
        conn = psycopg2.connect(**connection_info)
    return conn


def test_postgresql():
    conn = db_connect('core')
    cursor = conn.cursor()
    cursor.execute('show all')
    rs = cursor.fetchall()
    for row in rs:
        print(row)
    cursor.close()
    conn.close()


def test_mysql():
    conn = db_connect('mysql')
    cursor = conn.cursor()
    cursor.execute('show all')
    rs = cursor.fetchall()
    for row in rs:
        print(row)
    cursor.close()
    conn.close()


test_postgresql()
test_mysql()
