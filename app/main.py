from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from functools import wraps
import logging
import os
from phi.assistant import Assistant
from phi.llm.openai import OpenAIChat
from phi.tools.duckduckgo import DuckDuckGo
import secrets

app = Flask(__name__)
CORS(app)
app.instance_path = '/tmp'

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.yaml'

logging.basicConfig(level=logging.INFO)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "API Docs"},
)

app.register_blueprint(swaggerui_blueprint)

app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Set OpenAI API key from environment variables
if not os.getenv('OPENAI_API_KEY'):
    logging.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    raise EnvironmentError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
else:
    logging.info("OpenAI API key found and loaded successfully.")

class QueryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(80), nullable=False)
    response = db.Column(db.String(120), nullable=False)

assistant = Assistant(
    llm=OpenAIChat(model="gpt-4", api_key=os.getenv('OPENAI_API_KEY')),
    tools=[DuckDuckGo()],
    show_tool_calls=True,
)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('x-api-key') == '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':
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorized"}), 403
    return decorated_function

@app.route('/')
def index():
    return "Phidata Agent is running"

@app.route('/ask', methods=['POST'])
@require_api_key
def ask():
    data = request.json
    question = data.get("question")

    if not question:
        logging.warning("No question provided")
        return jsonify({"error": "No question provided"}), 400

    response = assistant.print_response(question, markdown=True)
    logging.info(f"Question: {question}, Response: {response}")

    new_log = QueryLog(query=question, response=response)
    db.session.add(new_log)
    db.session.commit()

    return jsonify({"response": response})

@app.route('/generate_task', methods=['POST'])
@require_api_key
def generate_task():
    data = request.json
    topic = data.get("topic")

    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    task_prompt = f"Generate a C programming task on the topic: {topic}"
    response = assistant.print_response(task_prompt, markdown=True)

    new_log = QueryLog(query=task_prompt, response=response)
    db.session.add(new_log)
    db.session.commit()

    return jsonify({"task": response})

@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': '0.0.1'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
