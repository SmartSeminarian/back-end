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
from neo4j import GraphDatabase
import uuid


app = Flask(__name__)
CORS(app)
app.instance_path = '/tmp'

app.config.from_object(Config)

db = SQLAlchemy(app)

app.config['NEO4J_URI'] = Config.NEO4J_URI
app.config['NEO4J_USER'] = Config.NEO4J_USER
app.config['NEO4J_PASSWORD'] = Config.NEO4J_PASSWORD

neo4j_driver = GraphDatabase.driver(
    Config.NEO4J_URI,
    auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
)

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.yaml'

logging.basicConfig(level=logging.INFO)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "API Docs"},
)

app.register_blueprint(swaggerui_blueprint)


class Concept:
    @staticmethod
    def create(tx, name, description=None):
        query = (
            "MERGE (c:Concept {name: $name}) "
            "ON CREATE SET c.id = $id, c.description = $description "
            "ON MATCH SET c.description = CASE WHEN c.description IS NULL THEN $description ELSE c.description END "
            "RETURN c"
        )
        result = tx.run(query, id=str(uuid.uuid4()), name=name, description=description)
        return result.single()['c']

    @staticmethod
    def get_by_name(tx, name):
        query = "MATCH (c:Concept {name: $name}) RETURN c"
        result = tx.run(query, name=name)
        record = result.single()
        return record['c'] if record else None

    @staticmethod
    def create_relationship(tx, source_name, target_name, relationship_type):
        query = (
                "MATCH (source:Concept {name: $source_name}) "
                "MATCH (target:Concept {name: $target_name}) "
                "MERGE (source)-[r:" + relationship_type + "]->(target) "
                                                           "RETURN type(r)"
        )
        result = tx.run(query, source_name=source_name, target_name=target_name)
        return result.single()['type(r)']


def load_prompt(filename):
    with open(os.path.join('prompts', filename), 'r') as file:
        return file.read().strip()


def format_prompt(template, **kwargs):
    return template.format(**kwargs)


assistant = Assistant(
    llm=OpenAIChat(model="gpt-4", max_tokens=120, temperature=0.9),
    description=load_prompt('tutor_description.txt'),
    tools=[DuckDuckGo()],
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


@app.route('/concept', methods=['POST'])
def create_concept():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Invalid request"}), 400

    name = data['name']
    description = data.get('description', '')
    related_concepts = data.get('related_concepts', [])

    with neo4j_driver.session() as session:
        # Create or get the main concept
        result = session.write_transaction(Concept.create, name, description)
        main_concept = result

        # Create relationships with related concepts
        for related in related_concepts:
            related_name = related['name']
            relationship_type = related.get('relationship', 'RELATED_TO')

            # Create the related concept if it doesn't exist
            session.write_transaction(Concept.create, related_name)

            # Create the relationship
            session.write_transaction(Concept.create_relationship, name, related_name, relationship_type)

    return jsonify({
        "id": main_concept['id'],
        "name": main_concept['name'],
        "description": main_concept['description']
    }), 201

@app.route('/concept/<name>', methods=['GET'])
def get_concept(name):
    with neo4j_driver.session() as session:
        concept = session.execute_read(Concept.get_by_name, name)
        if not concept:
            return jsonify({"error": "Concept not found"}), 404

        # Fetch related concepts
        query = (
            "MATCH (c:Concept {name: $name})-[r]-(related:Concept) "
            "RETURN type(r) as relationship, related.name as name, related.description as description"
        )
        result = session.run(query, name=name)
        related_concepts = [
            {
                "name": record["name"],
                "description": record["description"],
                "relationship": record["relationship"]
            }
            for record in result
        ]

        return jsonify({
            "id": concept['id'],
            "name": concept['name'],
            "description": concept['description'],
            "related_concepts": related_concepts
        })


@app.route('/explore_concept', methods=['POST'])
def explore_concept():
    data = request.get_json()
    if not data or 'concept' not in data:
        return jsonify({"error": "Invalid request"}), 400

    concept_name = data['concept']
    prompt_template = load_prompt('concept_exploration.txt')
    prompt = format_prompt(prompt_template, concept=concept_name)

    try:
        response = assistant.run(prompt, stream=False)
        app.logger.info(f"AI Response: {response}")  # Log the raw response
        concept_data = json.loads(response)
    except json.JSONDecodeError as e:
        app.logger.error(f"JSON Decode Error: {str(e)}")
        app.logger.error(f"Raw Response: {response}")
        return jsonify({"error": "Failed to decode JSON from assistant response", "raw_response": response}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

    # Store the concept and its relationships in the graph database
    with neo4j_driver.session() as session:
        main_concept = session.execute_write(Concept.create, concept_name, concept_data.get('description', ''))

        for related in concept_data.get('related_concepts', []):
            related_name = related['name']
            relationship_type = related.get('relationship', 'RELATED_TO')

            session.execute_write(Concept.create, related_name, related.get('description', ''))
            session.execute_write(Concept.create_relationship, concept_name, related_name, relationship_type)

    return jsonify(concept_data)


@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': '0.0.1'})


if __name__ == '__main__':
    neo4j_driver.close()
    app.run(debug=True)

with app.app_context():
    db.create_all()
