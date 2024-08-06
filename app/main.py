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
from config import Config
import time
from datetime import timedelta, datetime

app = Flask(__name__)
CORS(app)
app.instance_path = '/tmp'

app.config.from_object(Config)

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



def load_prompt(filename):
    with open(os.path.join('prompts', filename), 'r') as file:
        return file.read().strip()


def format_prompt(template, **kwargs):
    return template.format(**kwargs)


assistant = Assistant(
    llm=OpenAIChat(model="gpt-4", max_tokens=120, temperature=0.9),
    description=load_prompt('tutor_description.txt'),
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
    prompt = load_prompt('problem_generation.txt')
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

    prompt_template = load_prompt('solution_evaluation.txt')
    prompt = format_prompt(prompt_template,
                           description=problem.description,
                           example_input=problem.example_input,
                           example_output=problem.example_output,
                           solution_code=solution_code)

    response = assistant.run(prompt, stream=False)

    solution_data = {
        "problemId": problem_id,
        "evaluation": response.replace('\n', ' '),
    }

    return jsonify(solution_data)


@app.route('/version', methods=['GET'])
def version():
    if os.environ.get('DEPLOY_TIME') == None: 
        uptime = "only evailable on deploy"
    else:
        delpoy_time_str = os.getenv('DEPLOY_TIME')
        deploy_time = datetime.strptime(delpoy_time_str, "%Y-%m-%d %H:%M:%S %z").timestamp()
        uptime = str(timedelta(seconds = time.time() - deploy_time))

    return jsonify({
        'version': '0.0.1',
        'build_branch': os.getenv('BRANCH'),
        'sha_full': os.getenv('SHA_FULL'),
        'commit_time': os.getenv('COMMIT_TIME'),
        'deployment_time': os.getenv('DEPLOY_TIME', "only available on deploy"), # DEPLOY_TIME env variable only defined in cicd deploy-service workflow
        'service_uptime': uptime 
    })


if __name__ == '__main__':
    app.run(debug=True)

with app.app_context():
    db.create_all()