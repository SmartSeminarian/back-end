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


problems = {}


@app.route('/problem', methods=['GET'])
def problem():
    prompt = """
    Generate a brief and concise algorithmic problem for people studying C language.
    Provide your response in the following JSON format:
    {
        "description": "Problem description here",
        "exampleInput": "Example input here",
        "exampleOutput": "Example output here"
    }
    """
    response = assistant.run(prompt, stream=False)

    try:
        response_json = json.loads(response)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to decode JSON from assistant response"}), 500

    problem_id = secrets.token_hex(8)
    problem_data = {
        "id": problem_id,
        "description": response_json.get("description", "").replace('\n', ' '),
        "exampleInput": response_json.get("exampleInput", "").replace('\n', ' '),
        "exampleOutput": response_json.get("exampleOutput", "").replace('\n', ' ')
    }

    # Store the problem
    problems[problem_id] = problem_data

    return jsonify(problem_data)


@app.route('/solution', methods=['POST'])
def solution():
    data = request.get_json()

    if not data or 'problemId' not in data or 'solutionCode' not in data:
        return jsonify({"error": "Invalid request"}), 400

    problem_id = data['problemId']
    solution_code = data['solutionCode']

    # Retrieve the problem
    problem = problems.get(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    prompt = f"""
    Evaluate the following C code solution for the given problem:

    Problem Description: {problem['description']}
    Example Input: {problem['exampleInput']}
    Example Output: {problem['exampleOutput']}

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
