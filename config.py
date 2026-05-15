import psycopg2
import os

def get_connection():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # On est sur Render
        conn = psycopg2.connect(database_url, sslmode='require')
    else:
        # On est en local
        conn = psycopg2.connect(
            host     = "localhost",
            database = "gestion_cotisations",
            user     = "postgres",
            password = "votre_mot_de_passe"
        )
    return conn

# Identifiants de connexion
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"