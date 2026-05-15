import psycopg2

def get_connection():
    conn = psycopg2.connect(
        host     = "localhost",
        database = "gestion_cotisations",
        user     = "postgres",
        password = "aristide08"  # ← remplacez par votre mot de passe PostgreSQL
    )
    return conn

    # Identifiants de connexion
ADMIN_USERNAME = "Aristide"
ADMIN_PASSWORD = "Bertin08"  # ← changez par votre mot de passe