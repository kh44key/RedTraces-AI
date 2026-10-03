"""Container configuration; secrets are supplied by Compose, never baked in."""
import os

def load_private_settings():
    return dict(os.environ)

def get_secret(name, default=""):
    return os.environ.get(name, default)

def mysql_config(database):
    return dict(host=get_secret("PKCERT_DB_HOST", "mysql"),
                port=int(get_secret("PKCERT_DB_PORT", "3306")),
                user=get_secret("PKCERT_DB_USER", "pkcert"),
                password=get_secret("PKCERT_DB_PASSWORD"), database=database)
