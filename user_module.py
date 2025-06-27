# user_module.py

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection

def create_user(username, plain_password):
    """
    Cria um novo usuário com a senha criptografada.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            hashed_password = generate_password_hash(plain_password)
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_user_password(username, old_password, new_password):
    """
    Atualiza a senha de um usuário após validar a senha atual.
    Retorna uma tupla (bool, mensagem) indicando sucesso ou falha.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Busca a senha atual no banco
            cur.execute("SELECT password FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if result is None:
                return (False, "Usuário não encontrado.")
  
            stored_hash = result["password"]
            if not check_password_hash(stored_hash, old_password):
                return (False, "A senha atual está incorreta.")
  
            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password = %s WHERE username = %s", (new_hash, username))
        conn.commit()
        return (True, "Senha atualizada com sucesso!")
    except Exception as e:
        conn.rollback()
        return (False, f"Ocorreu um erro: {str(e)}")
    finally:
        conn.close()

def verify_user_password(username, plain_password):
    """
    Retorna True se a senha informada for válida para o usuário;
    caso contrário, retorna False.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if result:
                stored_hash = result[0]
                return check_password_hash(stored_hash, plain_password)
            else:
                return False
    finally:
        conn.close()

def update_user_details(username, first_name, last_name, document, amazon_search_permission, is_admin):
    """
    Atualiza os detalhes do usuário:
      - first_name: Primeiro nome
      - last_name: Sobrenome
      - document: Documento (CPF, RG etc.)
      - amazon_search_permission: Permissão para o módulo Amazon Search
      - is_admin: Permissão de administrador (True ou False)
      
    Retorna uma tupla (bool, mensagem) indicando se a atualização foi realizada com sucesso.
    
    Essa função deverá ser acionada apenas por usuários administradores.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                UPDATE users
                SET first_name = %s,
                    last_name = %s,
                    document = %s,
                    amazon_search_permission = %s,
                    is_admin = %s
                WHERE username = %s
            """
            cur.execute(query, (first_name, last_name, document, amazon_search_permission, is_admin, username))
        conn.commit()
        return (True, "Detalhes do usuário atualizados com sucesso!")
    except Exception as e:
        conn.rollback()
        return (False, f"Ocorreu um erro ao atualizar os detalhes: {str(e)}")
    finally:
        conn.close()
