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


basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'problems.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    llm=OpenAIChat(model="gpt-4", max_tokens=120, temperature=0.9),
    description="""You are an excellent tutor. An excellent tutor is a guide and an
                    educator. Your main goal is to teach students problem-solving
                    skills while they work on a programming exercise.
                    An excellent tutor never under any circumstances responds
                    with code, pseudocode, or implementations of concrete func-
                    tionalities.
                    An excellent tutor never under any circumstances tells instruc-
                    tions that contain concrete steps and implementation details.
                    Instead, he provides a single subtle clue, a counter-question,
                    or best practice to move the student’s attention to an aspect of
                    his problem or task so they can find a solution on their own.
                    An excellent tutor does not guess, so if you don’t know some-
                    thing, say "Sorry, I don’t know" and tell the student to ask a
                    human tutor.""",
    #instructions=[""],
)


class Problem(db.Model):
    id = db.Column(db.String(16), primary_key=True)
    description = db.Column(db.Text, nullable=False)
    example_input = db.Column(db.Text)
    example_output = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "exampleInput": self.example_input,
            "exampleOutput": self.example_output
        }


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
    print(response)

    try:
        response_json = json.loads(response)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to decode JSON from assistant response"}), 500

    problem_id = secrets.token_hex(8)
    new_problem = Problem(
        id=problem_id,
        description=response_json.get("description", "").replace('\n', ' '),
        example_input=response_json.get("exampleInput", "").replace('\n', ' '),
        example_output=response_json.get("exampleOutput", "").replace('\n', ' ')
    )

    db.session.add(new_problem)
    db.session.commit()

    return jsonify(new_problem.to_dict())


@app.route('/solution', methods=['POST'])
def solution():
    data = request.get_json()

    if not data or 'problemId' not in data or 'solutionCode' not in data:
        return jsonify({"error": "Invalid request"}), 400

    problem_id = data['problemId']
    solution_code = data['solutionCode']

    problem = Problem.query.get(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    prompt = f"""
    Evaluate the following C code solution for the given problem:

    Problem Description: {problem.description}
    Example Input: {problem.example_input}
    Example Output: {problem.example_output}

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

with app.app_context():
    db.create_all()Zz