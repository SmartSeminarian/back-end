import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'problems.db')
    SQLALCHEMY_BINDS = {
        'tokens': 'sqlite:///' + os.path.join(basedir, 'tokens.db')
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

    # Memgraph connection settings
    MEMGRAPH_HOST = os.getenv('MEMGRAPH_HOST', 'memgraph')
    MEMGRAPH_PORT = os.getenv('MEMGRAPH_PORT', '7687')
    MEMGRAPH_USERNAME = os.getenv('MEMGRAPH_USERNAME', '')  # Default is no authentication
    MEMGRAPH_PASSWORD = os.getenv('MEMGRAPH_PASSWORD', '')  # Default is no authentication

    # Construct Memgraph URI
    MEMGRAPH_URI = f"bolt://{MEMGRAPH_HOST}:{MEMGRAPH_PORT}"

    # OpenAI API key
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
