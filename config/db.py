# config/db.py

import psycopg2

def get_connection():
    """
    Retorna uma conexão com o banco de dados PostgreSQL.
    Altere os parâmetros abaixo conforme suas configurações.
    """
    return psycopg2.connect(
        host="localhost",           # ou o endereço do seu servidor
        database="omnirider",       # substitua pelo nome do seu banco de dados
        user="postres",         # substitua pelo seu nome de usuário do PostgreSQL
        password="P4ul0L31t3"        # substitua pela senha correta
    )
