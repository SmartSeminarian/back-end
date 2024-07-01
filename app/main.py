from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import secrets

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Database URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(80), unique=True, nullable=False)
    random_key = db.Column(db.String(120), unique=True, nullable=False)

# Create the database and the User table
with app.app_context():
    db.create_all()

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    github_username = data.get('username')
    random_key = data.get('key')

    if not github_username or not random_key:
        return jsonify({'error': 'Missing username or key'}), 400

    user = User.query.filter_by(github_username=github_username, random_key=random_key).first()
    if user:
        session_id = secrets.token_urlsafe(16)
        session[session_id] = github_username
        return jsonify({'session_id': session_id})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': '0.0.1'})

@app.route('/profile', methods=['GET'])
def profile():
    session_id = request.headers.get('Authorization')
    if session_id and session_id in session:
        github_username = session[session_id]
        user = User.query.filter_by(github_username=github_username).first()
        if user:
            return jsonify({'username': user.github_username, 'random_key': user.random_key})
    return jsonify({'message': 'Unauthorized'}), 401

@app.route('/recommendation', methods=['GET'])
def recommendation():
    return jsonify({'recommendation': 'Next concept recommendation will be here'})

@app.route('/concept/<name>', methods=['GET'])
def concept(name):
    return jsonify({'concept_name': name, 'description': f'Description for concept {name}'})

@app.route('/problem', methods=['GET'])
def problem():
    return jsonify({'problem': 'Problem statement will be here'})

@app.route('/solution', methods=['POST'])
def solution():
    data = request.json
    solution_data = data.get('solution')
    if not solution_data:
        return jsonify({'error': 'Missing solution data'}), 400
    return jsonify({'message': 'Solution submitted successfully', 'solution': solution_data})

@app.route('/explanation/<type>', methods=['GET'])
def explanation(type):
    return jsonify({'type': type, 'explanation': f'Explanation for {type} will be here'})

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    feedback_data = data.get('feedback')
    if not feedback_data:
        return jsonify({'error': 'Missing feedback data'}), 400
    return jsonify({'message': 'Feedback submitted successfully', 'feedback': feedback_data})

if __name__ == '__main__':
    app.run(debug=True)
