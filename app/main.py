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
from gqlalchemy import Node, Field, Relationship
from datetime import datetime
import subprocess
import sys
import io
import textwrap
import tempfile

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

class LearningPath(Node):
    id: str = Field()
    name: str = Field()
    goal: str = Field()
    created_at: str = Field()
    owner: str = Field()

class PathItem(Relationship, type="CONTAINS"):
    order: int = Field()


class Dialogue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(100), db.ForeignKey('user.github_username'), nullable=False)
    session_id = db.Column(db.String(32), db.ForeignKey('session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)

class UserKnowledge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(100), db.ForeignKey('user.github_username'), nullable=False)
    concept_id = db.Column(db.String(36), nullable=False) # UUIDs are 36 chars
    mastery_level = db.Column(db.Float, default=0.0, nullable=False) # 0.0 to 1.0
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('github_username', 'concept_id', name='_user_concept_uc'),)

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
    # Remove leading whitespace from each line
    dedented_template = textwrap.dedent(template)
    return dedented_template.format(**kwargs)


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


@app.route('/compile/c', methods=['POST'])
def compile_c_code():
    data = request.get_json()

    if not data or 'code' not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data['code']
    user_input = data.get('input', '')  # Get user input if provided

    # Create a temporary directory for compilation
    temp_dir = tempfile.mkdtemp()
    file_id = str(uuid.uuid4())
    c_file_path = os.path.join(temp_dir, f"{file_id}.c")
    executable_path = os.path.join(temp_dir, file_id)

    try:
        # Write the code to a temporary file
        with open(c_file_path, 'w') as f:
            f.write(code)

        # Compile the C code
        compile_process = subprocess.run(
            ['gcc', c_file_path, '-o', executable_path],
            capture_output=True,
            text=True
        )

        # Check if compilation was successful
        if compile_process.returncode != 0:
            return jsonify({
                "error": compile_process.stderr
            }), 200

        # Run the compiled program with user input
        run_process = subprocess.run(
            [executable_path],
            input=user_input,
            capture_output=True,
            text=True,
            timeout=5  # Set a timeout to prevent infinite loops
        )

        return jsonify({
            "output": run_process.stdout,
            "error": run_process.stderr if run_process.stderr else None
        }), 200

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "Execution timed out. Your program may contain an infinite loop."
        }), 200
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
    finally:
        # Clean up temporary files
        try:
            if os.path.exists(c_file_path):
                os.remove(c_file_path)
            if os.path.exists(executable_path):
                os.remove(executable_path)
            os.rmdir(temp_dir)
        except:
            pass



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


@app.route('/concept/<concept_id>/content', methods=['GET'])
@require_session
def get_concept_content(github_username, concept_id):
    content_type = request.args.get('type', 'explanation')  # 'explanation', 'analogy', 'quiz', 'task', 'explore'

    # 1. Получаем данные о концепции из графа
    query = "MATCH (c:Concept {id: $id, owner: $owner}) RETURN c"
    result = memgraph.execute_and_fetch(query, {"id": concept_id, "owner": github_username})
    concept = next(result, None)

    if not concept:
        return jsonify({"error": "Concept not found or unauthorized"}), 404

    concept_node = concept['c']
    concept_name = concept_node.name
    concept_description = concept_node.description

    # 2. Выбираем нужный промпт
    prompt_map = {
        "explanation": "content_explanation.txt",
        "analogy": "content_analogy.txt",
        "quiz": "content_quiz.txt"
    }

    # Special handling for 'explore' content type
    if content_type == 'explore':
        return explore_concept(github_username, concept_id, concept_name, concept_description)

    prompt_file = prompt_map.get(content_type)

    if not prompt_file:
        return jsonify({"error": f"Content type '{content_type}' is not supported"}), 400

    # 3. Генерируем контент
    prompt_template = load_prompt(prompt_file)
    prompt = format_prompt(
        prompt_template,
        concept_name=concept_name,
        concept_description=concept_description
    )

    response = assistant.run(prompt, stream=False)

    # Сохраняем это взаимодействие в диалог для истории
    session_id = request.headers.get('X-Session-ID')
    user_message = f"Tell me more about {concept_name} (type: {content_type})"
    save_dialogue(github_username, session_id, user_message, response, 'concept', concept_id)

    # Для квизов лучше возвращать JSON
    if content_type == 'quiz':
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if LLM fails to produce valid JSON
            return jsonify({"error": "Failed to generate a valid quiz JSON", "raw": response})

    return jsonify({"content": response})

def explore_concept(github_username, concept_id, concept_name, concept_description):
    """
    Generate a detailed learning path for exploring a specific concept.

    Args:
        github_username: The GitHub username of the user
        concept_id: The ID of the concept to explore
        concept_name: The name of the concept
        concept_description: The description of the concept

    Returns:
        A JSON response with the exploration path
    """
    # Create a prompt for the LLM to generate subconcepts for this concept
    exploration_prompt = f"""
    You are an expert in breaking down complex topics into learnable components.

    I want to learn more about: "{concept_name}"

    Description: {concept_description}

    Please break this concept down into 5-8 more specific subconcepts or components that would help me master it.
    Return your response as a JSON object with a single key "subconcepts" containing an array of strings.
    Each string should be a specific subconcept or component of {concept_name}.

    For example, if the concept was "Python Programming", subconcepts might include:
    {{
      "subconcepts": [
        "Python Syntax and Basic Data Types",
        "Control Flow (if statements, loops)",
        "Functions and Modules",
        "Object-Oriented Programming in Python",
        "File I/O and Exception Handling",
        "Python Standard Library",
        "Third-party Libraries and Package Management"
      ]
    }}

    Provide only the JSON, no additional text.
    """

    # Generate subconcepts using the LLM
    raw_response = assistant.run(exploration_prompt, stream=False)

    try:
        # Parse the JSON response
        subconcepts = json.loads(raw_response)["subconcepts"]
    except (json.JSONDecodeError, KeyError):
        return jsonify({"error": "Failed to parse subconcepts from LLM response", "details": raw_response}), 500

    # Create a new learning path for exploring this concept
    path_name = f"Exploring {concept_name}"
    goal = f"Learn more about {concept_name}"

    # Create placeholder nodes for each subconcept
    path_nodes = []
    for subconcept in subconcepts:
        temp_id = f"temp_{uuid.uuid4().hex[:8]}"
        path_nodes.append({
            "id": temp_id,
            "name": subconcept,
            "is_placeholder": True
        })

    # Save the exploration path
    path_id = save_learning_path(github_username, goal, path_nodes, path_name)

    # Return the exploration path
    return jsonify({
        "path_id": path_id,
        "name": path_name,
        "goal": goal,
        "subconcepts": subconcepts
    })

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

@app.route('/concept/<concept_id>/mastery', methods=['POST'])
@require_session
def update_mastery(github_username, concept_id):
    data = request.get_json()
    if not data or 'masteryLevel' not in data:
        return jsonify({"error": "masteryLevel is required"}), 400

    mastery_level = float(data['masteryLevel'])
    if not (0.0 <= mastery_level <= 1.0):
        return jsonify({"error": "masteryLevel must be between 0.0 and 1.0"}), 400

    knowledge = UserKnowledge.query.filter_by(
        github_username=github_username,
        concept_id=concept_id
    ).first()

    if not knowledge:
        knowledge = UserKnowledge(
            github_username=github_username,
            concept_id=concept_id,
            mastery_level=mastery_level
        )
        db.session.add(knowledge)
    else:
        knowledge.mastery_level = mastery_level

    db.session.commit()

    return jsonify({"message": "Mastery level updated successfully."}), 200


# ...

def get_user_knowledge_map(github_username):
    """Вспомогательная функция для получения карты знаний пользователя."""
    knowledge_records = UserKnowledge.query.filter_by(github_username=github_username).all()
    # Возвращаем словарь {concept_id: mastery_level} для быстрой проверки
    return {record.concept_id: record.mastery_level for record in knowledge_records}


def save_learning_path(github_username, goal, path_nodes, path_name=None):
    """
    Save a learning path to the knowledge graph.

    Args:
        github_username: The GitHub username of the user
        goal: The learning goal
        path_nodes: The list of concept nodes in the path
        path_name: Optional name for the path (defaults to the goal)

    Returns:
        The ID of the created learning path
    """
    # Generate a unique ID for the path
    path_id = f"path_{uuid.uuid4().hex[:8]}"

    # Use the goal as the path name if none is provided
    if not path_name:
        path_name = f"Learning path for: {goal}"

    # Create the learning path node
    create_path_query = """
    CREATE (p:LearningPath {
        id: $id,
        name: $name,
        goal: $goal,
        created_at: $created_at,
        owner: $owner
    })
    RETURN p
    """

    try:
        result = memgraph.execute_and_fetch(create_path_query, {
            "id": path_id,
            "name": path_name,
            "goal": goal,
            "created_at": datetime.utcnow().isoformat(),
            "owner": github_username
        })

        created_path = next(result, None)
        if not created_path:
            raise Exception("Failed to create learning path")

        # Connect the path to each concept with the correct order
        for i, node in enumerate(path_nodes):
            concept_id = node["id"]

            # For placeholder concepts, create them first
            if node.get("is_placeholder", False):
                create_concept_query = """
                CREATE (c:Concept {
                    id: $id,
                    name: $name,
                    description: $description,
                    difficulty: $difficulty,
                    owner: $owner
                })
                RETURN c
                """

                concept_result = memgraph.execute_and_fetch(create_concept_query, {
                    "id": concept_id,
                    "name": node["name"],
                    "description": f"Auto-generated concept for '{node['name']}'",
                    "difficulty": 1,  # Default difficulty
                    "owner": github_username
                })

                created_concept = next(concept_result, None)
                if not created_concept:
                    raise Exception(f"Failed to create concept {node['name']}")

            # Connect the path to the concept
            connect_query = """
            MATCH (p:LearningPath {id: $path_id})
            MATCH (c:Concept {id: $concept_id})
            CREATE (p)-[r:CONTAINS {order: $order}]->(c)
            RETURN r
            """

            connect_result = memgraph.execute_and_fetch(connect_query, {
                "path_id": path_id,
                "concept_id": concept_id,
                "order": i
            })

            created_relation = next(connect_result, None)
            if not created_relation:
                raise Exception(f"Failed to connect path to concept {node['name']}")

        return path_id

    except Exception as e:
        print(f"Error saving learning path: {str(e)}")
        return None

@app.route('/learning-path/generate', methods=['POST'])
@require_session
def generate_learning_path(github_username):
    data = request.get_json()
    if not data or 'goal' not in data:
        return jsonify({"error": "A 'goal' is required to generate a learning path"}), 400

    goal = data['goal']
    path_name = data.get('name')  # Optional path name

    # 1. Декомпозиция цели с помощью LLM
    # Вам нужно будет создать этот промпт
    decomposition_prompt_template = load_prompt('path_decomposition.txt')
    decomposition_prompt = format_prompt(decomposition_prompt_template, goal=goal)

    # Рекомендую настроить ассистента на возврат JSON
    raw_response = assistant.run(decomposition_prompt, stream=False)

    try:
        # Ожидаем от LLM ответ в формате: {"concepts": ["Concept 1", "Concept 2", ...]}
        concepts_list = json.loads(raw_response)["concepts"]
    except (json.JSONDecodeError, KeyError):
        return jsonify({"error": "Failed to parse concepts from LLM response", "details": raw_response}), 500

    # 2. Поиск концепций в графе и фильтрация по знаниям пользователя
    # Получаем текущие знания пользователя
    user_knowledge = get_user_knowledge_map(github_username)

    # Ищем все концепции в графе, принадлежащие пользователю (или общие)
    query = """
    MATCH (c:Concept) WHERE c.owner = $owner
    RETURN c.id as id, c.name as name
    """
    all_concepts_from_graph = list(memgraph.execute_and_fetch(query, {"owner": github_username}))

    # Сопоставляем имена из LLM с ID из графа
    path_nodes = []
    matched_concepts = set()  # Track which concepts have been matched

    for concept_name in concepts_list:
        concept_matched = False
        concept_words = set(concept_name.lower().split())

        for graph_node in all_concepts_from_graph:
            graph_node_name = graph_node['name'].lower()

            # Try different matching strategies
            # 1. Exact match
            if concept_name.lower() == graph_node_name:
                match_score = 1.0
            # 2. Substring match (original approach)
            elif concept_name.lower() in graph_node_name:
                match_score = 0.8
            # 3. Word overlap match
            else:
                graph_node_words = set(graph_node_name.split())
                common_words = concept_words.intersection(graph_node_words)
                if common_words:
                    match_score = len(common_words) / max(len(concept_words), len(graph_node_words))
                else:
                    match_score = 0

            # If we have a reasonable match
            if match_score > 0.3:  # Threshold for considering it a match
                concept_matched = True
                # Не добавляем в путь те концепции, которыми пользователь уже владеет (mastery > 0.8)
                if user_knowledge.get(graph_node['id'], 0.0) < 0.8 and graph_node['id'] not in matched_concepts:
                    path_nodes.append({
                        "id": graph_node['id'],
                        "name": graph_node['name'],
                        "match_score": match_score
                    })
                    matched_concepts.add(graph_node['id'])
                    # Don't break here to allow multiple matches for a concept

        # If no match was found for this concept, create a placeholder
        if not concept_matched:
            # Generate a temporary ID for this concept
            temp_id = f"temp_{uuid.uuid4().hex[:8]}"
            path_nodes.append({
                "id": temp_id,
                "name": concept_name,
                "is_placeholder": True
            })

    # 3. TODO: Упорядочивание пути (Ordering)
    # Это продвинутый шаг. Начать можно с возврата просто отфильтрованного списка.
    # В идеале здесь должен быть графовый алгоритм, который находит
    # оптимальный путь, используя связи IS_PREREQUISITE_FOR.

    # Sort path nodes by match score (if available) in descending order
    path_nodes.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    # Save the learning path to the knowledge graph
    path_id = save_learning_path(github_username, goal, path_nodes, path_name)

    # If the path is empty or very short, add a message
    response = {
        "goal": goal,
        "suggested_path": path_nodes,
        "path_id": path_id
    }

    if len(path_nodes) == 0:
        response["message"] = "No matching concepts found. Try a more specific learning goal."
    elif len(path_nodes) == 1 and path_nodes[0].get('is_placeholder', False):
        response["message"] = f"No existing concepts found for '{goal}'. Consider exploring more specific aspects of this topic."

    return jsonify(response)

@app.route('/concept/bind', methods=['POST'])
@require_session
def bind_concepts(github_username):
    # ... (проверка данных)

    source_id = data['source_id']
    target_id = data['target_id']
    # 'relation' теперь 'type' для ясности
    relation_type = data['relation_type']  # например, "IS_PREREQUISITE_FOR"

    # Рекомендуется определить список допустимых типов связей
    ALLOWED_RELATIONS = ["IS_PREREQUISITE_FOR", "DEEPENS", "IS_AN_ALTERNATIVE_TO"]
    if relation_type not in ALLOWED_RELATIONS:
        return jsonify({"error": f"Invalid relation_type. Allowed: {ALLOWED_RELATIONS}"}), 400

    # Cypher-запрос теперь создает связь с определенным типом
    query = f"""
    MATCH (source:Concept {{id: $source_id, owner: $owner}})
    MATCH (target:Concept {{id: $target_id, owner: $owner}})
    CREATE (source)-[r:{relation_type}]->(target)
    RETURN source.id as source_id, target.id as target_id, type(r) as relation_type
    """

    try:
        result = memgraph.execute_and_fetch(query, {
            "source_id": source_id,
            "target_id": target_id,
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

@app.route('/learning-path', methods=['GET'])
@require_session
def get_learning_paths(github_username):
    """
    Get all learning paths for a user.
    """
    query = """
    MATCH (p:LearningPath)
    WHERE p.owner = $owner
    RETURN p.id as id, p.name as name, p.goal as goal, p.created_at as created_at
    ORDER BY p.created_at DESC
    """

    try:
        result = memgraph.execute_and_fetch(query, {"owner": github_username})
        paths = list(result)

        return jsonify(paths), 200
    except Exception as e:
        error_message = f"Failed to retrieve learning paths. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/learning-path/<path_id>', methods=['GET'])
@require_session
def get_learning_path(github_username, path_id):
    """
    Get a specific learning path with its concepts.
    """
    # First, check if the path exists and belongs to the user
    path_query = """
    MATCH (p:LearningPath {id: $path_id})
    WHERE p.owner = $owner
    RETURN p.id as id, p.name as name, p.goal as goal, p.created_at as created_at
    """

    try:
        path_result = memgraph.execute_and_fetch(path_query, {
            "path_id": path_id,
            "owner": github_username
        })
        path = next(path_result, None)

        if not path:
            return jsonify({"error": "Learning path not found or unauthorized access"}), 404

        # Get the concepts in the path with their order
        concepts_query = """
        MATCH (p:LearningPath {id: $path_id})-[r:CONTAINS]->(c:Concept)
        WHERE p.owner = $owner
        RETURN c.id as id, c.name as name, c.description as description, 
               c.difficulty as difficulty, r.order as order
        ORDER BY r.order
        """

        concepts_result = memgraph.execute_and_fetch(concepts_query, {
            "path_id": path_id,
            "owner": github_username
        })

        concepts = list(concepts_result)

        # Get the user's knowledge for each concept
        user_knowledge = get_user_knowledge_map(github_username)

        # Add mastery level to each concept
        for concept in concepts:
            concept["mastery_level"] = user_knowledge.get(concept["id"], 0.0)

        response = {
            "id": path["id"],
            "name": path["name"],
            "goal": path["goal"],
            "created_at": path["created_at"],
            "concepts": concepts
        }

        return jsonify(response), 200
    except Exception as e:
        error_message = f"Failed to retrieve learning path. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/learning-path/<path_id>', methods=['DELETE'])
@require_session
def delete_learning_path(github_username, path_id):
    """
    Delete a learning path.
    """
    # Check if the path exists and belongs to the user
    path_query = """
    MATCH (p:LearningPath {id: $path_id})
    WHERE p.owner = $owner
    RETURN p
    """

    try:
        path_result = memgraph.execute_and_fetch(path_query, {
            "path_id": path_id,
            "owner": github_username
        })

        path = next(path_result, None)

        if not path:
            return jsonify({"error": "Learning path not found or unauthorized access"}), 404

        # Delete the path and its relationships
        delete_query = """
        MATCH (p:LearningPath {id: $path_id, owner: $owner})
        DETACH DELETE p
        """

        memgraph.execute(delete_query, {
            "path_id": path_id,
            "owner": github_username
        })

        return jsonify({"message": "Learning path deleted successfully"}), 200
    except Exception as e:
        error_message = f"Failed to delete learning path. Error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/concept/explore', methods=['POST'])
@require_session
def explore_concept_endpoint(github_username):
    """
    Endpoint to explore a concept by name.
    """
    data = request.get_json()
    if not data or 'concept' not in data:
        return jsonify({"error": "A 'concept' is required to explore"}), 400

    concept_name = data['concept']

    # Find the concept by name
    query = """
    MATCH (c:Concept)
    WHERE c.name = $name AND c.owner = $owner
    RETURN c
    """
    result = memgraph.execute_and_fetch(query, {
        "name": concept_name,
        "owner": github_username
    })
    concept = next(result, None)

    if not concept:
        # If concept doesn't exist, create a placeholder
        concept_id = f"temp_{uuid.uuid4().hex[:8]}"
        concept_description = f"Auto-generated concept for '{concept_name}'"

        # Call explore_concept with the placeholder
        return explore_concept(github_username, concept_id, concept_name, concept_description)
    else:
        # Call explore_concept with the existing concept
        concept_node = concept['c']
        return explore_concept(github_username, concept_node.id, concept_node.name, concept_node.description)

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
