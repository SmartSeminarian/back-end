from flask import Flask, request, jsonify, render_template_string, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS, cross_origin
from functools import wraps
import logging
import os
from phi.assistant import Assistant
from phi.llm.openai import OpenAIChat
from phi.tools.duckduckgo import DuckDuckGo
import secrets
import json
from config import Config
import uuid
import openai
from gqlalchemy import Memgraph
from gqlalchemy import Node, Field
from datetime import datetime
import subprocess
import sys
import io


app = Flask(__name__)
CORS(app, support_credentials=True)
app.instance_path = '/data'
app.config.from_object(Config)
db = SQLAlchemy(app)

memgraph = Memgraph(host=Config.MEMGRAPH_HOST, port=int(Config.MEMGRAPH_PORT))

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.yaml'

logging.basicConfig(level=logging.INFO)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "API Docs"},
)

app.register_blueprint(swaggerui_blueprint)

class Token(db.Model):
    __bind_key__ = 'tokens'
    token_name = db.Column(db.String(50), primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)

class User(db.Model):
    github_username = db.Column(db.String(100), primary_key=True)

class Session(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    github_username = db.Column(db.String(100), db.ForeignKey('user.github_username'), nullable=False)

class UserProblem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(100), db.ForeignKey('user.github_username'), nullable=False)
    problem_id = db.Column(db.String(16), db.ForeignKey('problem.id'), nullable=False)
    solution_code = db.Column(db.Text)

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

class Concept(Node):
    id: str = Field()
    name: str = Field()
    description: str = Field()
    difficulty: int = Field()
    owner: str = Field()


class Dialogue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(100), db.ForeignKey('user.github_username'), nullable=False)
    session_id = db.Column(db.String(32), db.ForeignKey('session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)

def require_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID')
        if not session_id:
            return jsonify({"error": "No session ID provided"}), 401

        session = db.session.get(Session, session_id)
        if not session:
            return jsonify({"error": "Invalid session ID"}), 401

        kwargs['github_username'] = session.github_username
        return f(*args, **kwargs)

    return decorated_function

def save_dialogue(github_username, session_id, user_message, assistant_response, context_type=None, context_id=None):
    dialogue_content = json.dumps({
        "user": user_message,
        "assistant": assistant_response,
        "context_type": context_type,
        "context_id": context_id
    })
    new_dialogue = Dialogue(github_username=github_username, session_id=session_id, content=dialogue_content)
    db.session.add(new_dialogue)
    db.session.commit()


@app.route('/dialogues', methods=['GET'])
@require_session
def get_dialogues(github_username):
    session_id = request.headers.get('X-Session-ID')
    dialogues = Dialogue.query.filter_by(github_username=github_username, session_id=session_id).order_by(Dialogue.timestamp.desc()).all()
    return jsonify([{
        "id": d.id,
        "timestamp": d.timestamp.isoformat(),
        "content": json.loads(d.content)
    } for d in dialogues])


def load_prompt(filename):
    with open(os.path.join('prompts', filename), 'r') as file:
        return file.read().strip()


def format_prompt(template, **kwargs):
    return template.format(**kwargs)


def generate_session_id():
    return secrets.token_hex(16)


assistant = Assistant(
    llm=OpenAIChat(model="gpt-4", max_tokens=300, temperature=0.9),
    description=load_prompt('tutor_description.txt'),
    tools=[DuckDuckGo()],
)


@app.route('/')
def index():
    return "Phidata Agent is running"


@app.route('/login', methods=['POST'])
@cross_origin(supports_credentials=True)
def login():
    data = request.get_json()
    if not data or 'github_username' not in data or 'token' not in data:
        return jsonify({"error": "Invalid request"}), 400

    github_username = data['github_username']
    full_token = data['token']

    token_parts = full_token.split(':')
    if len(token_parts) != 2:
        return jsonify({"error": "Invalid token format"}), 400

    token_name, token_value = token_parts

    token_record = Token.query.filter_by(token_name=token_name, token=token_value).first()
    if not token_record:
        return jsonify({"error": "Invalid token"}), 401

    user = db.session.get(User, github_username)

    if not user:
        user = User(github_username=github_username)
        db.session.add(user)

    session_id = generate_session_id()
    new_session = Session(id=session_id, github_username=github_username)
    db.session.add(new_session)

    db.session.commit()
    return jsonify({"session_id": session_id}), 200


@app.route('/chat', methods=['POST'])
@require_session
def chat(github_username):
    session_id = request.headers.get('X-Session-ID')
    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({"error": "Invalid request. Message is required."}), 400

    user_message = data['message']
    context = data.get('context', {})
    context_type = context.get('type')
    context_id = context.get('id')

    # Load dialogue history for this session
    dialogues = Dialogue.query.filter_by(github_username=github_username, session_id=session_id).order_by(Dialogue.timestamp.desc()).limit(5).all()
    dialogue_history = [json.loads(d.content) for d in dialogues][::-1]  # Reverse the order

    # Formulate prompt with context
    prompt = ""

    if context_type and context_id:
        prompt += f"Context: {context_type} {context_id}\n\n"

        if context_type == 'problem':
            problem = Problem.query.get(context_id)
            if problem:
                prompt += f"Problem: {problem.description}\n"
                prompt += f"Example Input: {problem.example_input}\n"
                prompt += f"Example Output: {problem.example_output}\n\n"
        elif context_type == 'solution':
            user_problem = UserProblem.query.filter_by(github_username=github_username, problem_id=context_id).first()
            if user_problem and user_problem.solution_code:
                problem = Problem.query.get(context_id)
                if problem:
                    prompt += f"Problem: {problem.description}\n"
                    prompt += f"Your previous solution: {user_problem.solution_code}\n\n"
        elif context_type == 'concept':
            # Add concept context handling
            query = "MATCH (c:Concept {id: $id}) RETURN c"
            result = memgraph.execute_and_fetch(query, {"id": context_id})
            concept = next(result, None)
            if concept:
                concept_node = concept['c']
                prompt += f"Concept: {concept_node.name}\n"
                prompt += f"Description: {concept_node.description}\n"
                prompt += f"Difficulty Level: {concept_node.difficulty}\n\n"
    else:
        prompt += "General Chat\n\n"

    prompt += "Dialogue History:\n"
    for d in dialogue_history:
        prompt += f"User: {d['user']}\nAssistant: {d['assistant']}\n"
    prompt += f"\nUser: {user_message}\nAssistant:"

    # Get response from GPT
    response = assistant.run(prompt, stream=False)

    # Save the new dialogue
    save_dialogue(github_username, session_id, user_message, response, context_type, context_id)

    return jsonify({
        "assistant_response": response
    })

@app.route('/problem', methods=['GET'])
@require_session
def problem(github_username):
    session_id = request.headers.get('X-Session-ID')
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

    user_problem = UserProblem(github_username=github_username, problem_id=problem_id)
    db.session.add(user_problem)

    db.session.commit()

    # Save the dialogue with session_id and context
    save_dialogue(github_username, session_id, "Generate a problem", json.dumps(response_json), 'problem', problem_id)

    return jsonify({
        "problem": new_problem.to_dict(),
        "message": "If you want a different problem or have any questions, feel free to use the /chat endpoint."
    })


@app.route('/user/problems', methods=['GET'])
@require_session
def get_user_problems(github_username):
    try:
        user_problems = (
            db.session.query(
                Problem,
                UserProblem.solution_code,
                UserProblem.id.label('user_problem_id')
            )
            .join(
                UserProblem,
                (UserProblem.problem_id == Problem.id) &
                (UserProblem.github_username == github_username)
            )
            .all()
        )

        problems_list = []
        for problem, solution_code, user_problem_id in user_problems:
            problem_data = {
                "id": problem.id,
                "description": problem.description,
                "exampleInput": problem.example_input,
                "exampleOutput": problem.example_output,
                "userProblemId": user_problem_id,
                "hasSubmission": solution_code is not None,
                "solutionCode": solution_code if solution_code else None
            }
            problems_list.append(problem_data)

        return jsonify({
            "problems": problems_list,
            "totalCount": len(problems_list)
        }), 200

    except Exception as e:
        app.logger.error(f"Error fetching user problems: {str(e)}")
        return jsonify({
            "error": "Failed to fetch user problems",
            "details": str(e)
        }), 500

@app.route('/solution', methods=['POST'])
@require_session
def solution(github_username):
    session_id = request.headers.get('X-Session-ID')
    data = request.get_json()

    if not data or 'problemId' not in data or 'solutionCode' not in data:
        return jsonify({"error": "Invalid request"}), 400

    problem_id = data['problemId']
    solution_code = data['solutionCode']

    user_problem = UserProblem.query.filter_by(github_username=github_username, problem_id=problem_id).first()
    if not user_problem:
        user_problem = UserProblem(github_username=github_username, problem_id=problem_id)
        db.session.add(user_problem)

    user_problem.solution_code = solution_code
    db.session.commit()

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

    # Save the dialogue with session_id and context
    save_dialogue(github_username, session_id, f"Solution submitted for problem {problem_id}: {solution_code}",
                  response, 'solution', problem_id)

    solution_data = {
        "problemId": problem_id,
        "evaluation": response.replace('\n', ' '),
    }

    return jsonify({
        "evaluation": solution_data,
        "message": "You can continue discussing this solution using the /chat endpoint with the 'solution' context."
    })


@app.route('/sessions', methods=['GET'])
@require_session
def get_sessions(github_username):
    sessions = Session.query.filter_by(github_username=github_username).all()
    return jsonify([{
        "id": s.id,
        "created_at": s.created_at.isoformat() if hasattr(s, 'created_at') else None
    } for s in sessions])



@app.route('/concept', methods=['POST'])
@require_session
def create_concept(github_username):
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"error": "Name is required"}), 400

    name = data['name']
    description = data.get('description')
    difficulty = data.get('difficulty', 1)

    # Check if concept already exists for this user
    query = "MATCH (c:Concept {name: $name, owner: $owner}) RETURN c"
    result = memgraph.execute_and_fetch(query, {"name": name, "owner": github_username})
    if next(result, None):
        return jsonify({"error": "Concept with this name already exists for this user"}), 409

    # Create new concept with owner
    new_concept_id = str(uuid.uuid4())
    query = (
        "CREATE (c:Concept {id: $id, name: $name, description: $description, "
        "difficulty: $difficulty, owner: $owner}) RETURN c"
    )
    params = {
        "id": new_concept_id,
        "name": name,
        "description": description,
        "difficulty": difficulty,
        "owner": github_username
    }

    try:
        result = memgraph.execute_and_fetch(query, params)
        created_concept = next(result, None)
        if not created_concept:
            raise Exception("No result returned from create query")

        concept_node = created_concept['c']
        concept_data = {
            "id": concept_node.id,
            "name": concept_node.name,
            "description": concept_node.description,
            "difficulty": concept_node.difficulty,
            "owner": concept_node.owner
        }
        return jsonify(concept_data), 201
    except Exception as e:
        error_message = f"Failed to create concept. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500


@app.route('/concept', methods=['GET'])
@require_session
def get_all_concepts(github_username):
    # Modified query to include relationships
    query = """
    MATCH (c:Concept)
    WHERE c.owner = $owner
    OPTIONAL MATCH (c)-[r:RELATED]->(related:Concept)
    WHERE related.owner = $owner
    RETURN c,
           COLLECT(DISTINCT {
               id: related.id,
               name: related.name,
               description: related.description,
               difficulty: related.difficulty,
               relation: r.type
           }) as outgoing_relations,
           size(COLLECT(DISTINCT related)) as related_count
    """
    result = memgraph.execute_and_fetch(query, {"owner": github_username})

    concepts = []
    for record in result:
        concept_node = record['c']
        # Filter out empty relationships
        related_concepts = [rel for rel in record['outgoing_relations'] if rel['id'] is not None]

        concepts.append({
            "id": concept_node.id,
            "name": concept_node.name,
            "description": concept_node.description,
            "difficulty": concept_node.difficulty,
            "owner": concept_node.owner,
            "related_concepts": related_concepts,
            "related_count": record['related_count']
        })

    return jsonify(concepts), 200


@app.route('/concept/<concept_id>', methods=['DELETE'])
@require_session
def delete_concept(github_username, concept_id):
    # Check if concept exists and belongs to user
    query = """
    MATCH (c:Concept {id: $id})
    WHERE c.owner = $owner
    RETURN c
    """
    result = memgraph.execute_and_fetch(query, {"id": concept_id, "owner": github_username})
    concept = next(result, None)

    if not concept:
        return jsonify({"error": "Concept not found or unauthorized access"}), 404

    # Delete the concept
    delete_query = """
    MATCH (c:Concept {id: $id, owner: $owner})
    DETACH DELETE c
    """
    try:
        memgraph.execute(delete_query, {"id": concept_id, "owner": github_username})
        return jsonify({"message": "Concept deleted successfully"}), 200
    except Exception as e:
        error_message = f"Failed to delete concept. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500


@app.route('/concept/<concept_id>', methods=['GET'])
@require_session
def get_concept(github_username, concept_id):
    # Modified query to fetch concept and its relationships
    query = """
    MATCH (c:Concept {id: $id})
    WHERE c.owner = $owner
    OPTIONAL MATCH (c)-[r:RELATED]->(related:Concept)
    WHERE related.owner = $owner
    RETURN c,
           COLLECT(DISTINCT {
               id: related.id,
               name: related.name,
               description: related.description,
               difficulty: related.difficulty,
               relation: r.type
           }) as outgoing_relations,
           size(COLLECT(DISTINCT related)) as related_count
    """
    result = memgraph.execute_and_fetch(query, {"id": concept_id, "owner": github_username})
    concept = next(result, None)

    if not concept:
        return jsonify({"error": "Concept not found or unauthorized access"}), 404

    concept_node = concept['c']
    # Filter out empty relationships (when there are no related concepts)
    related_concepts = [rel for rel in concept['outgoing_relations'] if rel['id'] is not None]

    concept_data = {
        "id": concept_node.id,
        "name": concept_node.name,
        "description": concept_node.description,
        "difficulty": concept_node.difficulty,
        "owner": concept_node.owner,
        "related_concepts": related_concepts,
        "related_count": concept['related_count']
    }

    return jsonify(concept_data), 200


@app.route('/concept/<concept_id>', methods=['PUT'])
@require_session
def update_concept(github_username, concept_id):
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Check if the concept exists and belongs to the user
    query = """
    MATCH (c:Concept {id: $id})
    WHERE c.owner = $owner
    RETURN c
    """
    result = memgraph.execute_and_fetch(query, {"id": concept_id, "owner": github_username})
    old_concept = next(result, None)

    if not old_concept:
        return jsonify({"error": "Concept not found or unauthorized access"}), 404

    old_concept_node = old_concept['c']

    # Create a new node with updated information
    new_concept_id = str(uuid.uuid4())
    new_version = old_concept_node.version + 1 if hasattr(old_concept_node, 'version') else 1

    create_query = """
    CREATE (new:Concept {
        id: $new_id,
        name: $name,
        description: $description,
        difficulty: $difficulty,
        version: $version,
        created_at: $created_at,
        owner: $owner
    })
    WITH new
    MATCH (old:Concept {id: $old_id, owner: $owner})
    CREATE (new)-[:PREVIOUS_VERSION]->(old)
    RETURN new
    """

    params = {
        "new_id": new_concept_id,
        "name": data.get('name', old_concept_node.name),
        "description": data.get('description', old_concept_node.description),
        "difficulty": data.get('difficulty', old_concept_node.difficulty),
        "version": new_version,
        "created_at": datetime.utcnow().isoformat(),
        "old_id": concept_id,
        "owner": github_username
    }

    try:
        result = memgraph.execute_and_fetch(create_query, params)
        new_concept = next(result, None)

        if not new_concept:
            raise Exception("Failed to create new version of concept")

        # Update relations to maintain the same relationships with the new version
        update_relations_query = """
        MATCH (old:Concept {id: $old_id, owner: $owner})-[r:RELATED]->(target)
        WHERE NOT type(r) = 'PREVIOUS_VERSION'
        MATCH (new:Concept {id: $new_id, owner: $owner})
        CREATE (new)-[new_r:RELATED]->(target)
        SET new_r = r
        DELETE r
        """
        memgraph.execute(update_relations_query, {
            "old_id": concept_id,
            "new_id": new_concept_id,
            "owner": github_username
        })

        new_concept_data = {
            "id": new_concept['new'].id,
            "name": new_concept['new'].name,
            "description": new_concept['new'].description,
            "difficulty": new_concept['new'].difficulty,
            "version": new_concept['new'].version,
            "created_at": new_concept['new'].created_at,
            "owner": new_concept['new'].owner
        }

        return jsonify(new_concept_data), 200

    except Exception as e:
        error_message = f"Failed to update concept. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/concept/bind', methods=['POST'])
@require_session
def bind_concepts(github_username):
    data = request.json
    if not data or 'source_id' not in data or 'target_id' not in data or 'relation' not in data:
        return jsonify({"error": "Invalid request. Required fields: source_id, target_id, relation"}), 400

    source_id = data['source_id']
    target_id = data['target_id']
    relation = data['relation']

    # Modified query to check ownership of both concepts
    query = """
    MATCH (source:Concept {id: $source_id})
    MATCH (target:Concept {id: $target_id})
    WHERE source <> target 
    AND source.owner = $owner 
    AND target.owner = $owner
    CREATE (source)-[r:RELATED {type: $relation}]->(target)
    RETURN source.id as source_id, target.id as target_id, type(r) as relation_type, r.type as relation
    """

    try:
        result = memgraph.execute_and_fetch(query, {
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
            "owner": github_username
        })
        created_relation = next(result, None)

        if not created_relation:
            return jsonify({"error": "Concepts not found or unauthorized access"}), 404

        return jsonify({
            "source_id": created_relation['source_id'],
            "target_id": created_relation['target_id'],
            "relation_type": created_relation['relation_type'],
            "relation": created_relation['relation']
        }), 201

    except Exception as e:
        error_message = f"Failed to bind concepts. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/concept/unbind', methods=['POST'])
@require_session
def unbind_concepts(github_username):
    data = request.json
    if not data or 'source_id' not in data or 'target_id' not in data:
        return jsonify({"error": "Invalid request. Required fields: source_id, target_id"}), 400

    source_id = data['source_id']
    target_id = data['target_id']
    relation = data.get('relation')  # Optional: if provided, only unbind this specific relation

    # Modified query to check ownership of both concepts
    query = """
    MATCH (source:Concept {id: $source_id})-[r:RELATED]->(target:Concept {id: $target_id})
    WHERE source <> target 
    AND source.owner = $owner 
    AND target.owner = $owner
    """

    if relation:
        query += "AND r.type = $relation "

    query += """
    WITH r, source, target
    DELETE r
    RETURN source.id as source_id, target.id as target_id, 'RELATED' as relation_type
    """

    try:
        result = memgraph.execute_and_fetch(query, {
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
            "owner": github_username
        })
        deleted_relations = list(result)

        if not deleted_relations:
            return jsonify({"error": "No matching relations found to unbind or unauthorized access"}), 404

        return jsonify([{
            "source_id": rel['source_id'],
            "target_id": rel['target_id'],
            "relation_type": rel['relation_type'],
            "relation": relation if relation else "is_related_to"
        } for rel in deleted_relations]), 200

    except Exception as e:
        error_message = f"Failed to unbind concepts. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500


@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': '0.0.1'})


@app.route('/logs')
def get_logs():
    log_file_path = '/data/service.log'

    if os.path.exists(log_file_path):
        return send_file(log_file_path, mimetype='text/plain', as_attachment=True)
    else:
        return "Log file not found", 404


with app.app_context():
    db.create_all()
    existing_token = Token.query.filter_by(token_name='test').first()
    if not existing_token:
        test_token = Token(token_name='test', token=os.getenv('TEST_TOKEN'))
        db.session.add(test_token)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
