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
import json

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


assistant = Assistant(
    llm=OpenAIChat(model="gpt-4", max_tokens=100),
    description="You are an expert in c language and can accomplish any task that is asked of you.",
    #instructions=[""],
)


@app.route('/')
def index():
    return "Phidata Agent is running"


@app.route('/problem', methods=['GET'])
def problem():
    prompt = """
    Generate a brief and concise algorithmic problem for people studying C language.
    Limit the problem description to a few sentences without any example inputs or outputs.
    """
    # {
    #     "description": "string",
    #     "exampleInput": "string",
    #     "exampleOutput": "string"
    # }
    response = assistant.run(prompt, stream=False)
    #print(type(response))

    # try:
    #     response_json = json.loads(response)
    # except json.JSONDecodeError:
    #     return jsonify({"error": "Failed to decode JSON from assistant response"}), 500

    # Add an ID to the response
    problem_data = {
        "id": secrets.token_hex(8),  # Generating a unique ID
        "description": response.replace('\n', ' '),
        # "exampleInput": response_json.get("exampleInput", "").replace('\n', ' '),
        # "exampleOutput": response_json.get("exampleOutput", "").replace('\n', ' ')
    }

    return jsonify(problem_data)


@app.route('/solution', methods=['POST'])
def solution():
    data = request.get_json()

    if not data or 'problemId' not in data or 'solutionCode' not in data:
        return jsonify({"error": "Invalid request"}), 400

    problem_id = data['problemId']
    solution_code = data['solutionCode']

    prompt = f"""
    Evaluate the following C code solution for the given problem ID: {problem_id}.
    Code:
    {solution_code}

    Provide a brief evaluation of the solution's correctness and efficiency.
    """
    response = assistant.run(prompt, stream=False)

    solution_data = {
        "problemId": problem_id,
        "evaluation": response.replace('\n', ' '),
    }

    return jsonify(solution_data)



@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': '0.0.1'})


if __name__ == '__main__':
    app.run(debug=True)
