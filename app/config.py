import os

basedir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.abspath(os.path.join(basedir, os.pardir))
data_dir = os.path.join(root_dir, 'data')
class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(data_dir, 'problems.db')
    SQLALCHEMY_BINDS = {
        'tokens': 'sqlite:///' + os.path.join(data_dir, 'tokens.db')
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

    NEO4J_URI = os.getenv('NEO4J_URI')
    NEO4J_USER = os.getenv('NEO4J_USER')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')