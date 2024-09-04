import os

class Config:
    DATA_DIR = '/data'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(DATA_DIR, 'problems.db')
    SQLALCHEMY_BINDS = {
        'tokens': 'sqlite:///' + os.path.join(DATA_DIR, 'tokens.db')
    }

    # Memgraph connection settings
    MEMGRAPH_HOST = os.getenv('MEMGRAPH_HOST', 'memgraph')
    MEMGRAPH_PORT = os.getenv('MEMGRAPH_PORT', '7687')
    MEMGRAPH_USERNAME = os.getenv('MEMGRAPH_USERNAME', '')  # Default is no authentication
    MEMGRAPH_PASSWORD = os.getenv('MEMGRAPH_PASSWORD', '')  # Default is no authentication

    # Construct Memgraph URI
    MEMGRAPH_URI = f"bolt://{MEMGRAPH_HOST}:{MEMGRAPH_PORT}"

    # OpenAI API key
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
