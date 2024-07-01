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

@app.route('/generate_key', methods=['GET'])
def generate_key():
    random_key = secrets.token_urlsafe(16)
    return jsonify({'key': random_key})

@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.json
    github_username = data.get('username')
    random_key = data.get('key')

    if not github_username or not random_key:
        return jsonify({'error': 'Missing username or key'}), 400

    # Store the username and key in the database
    user = User(github_username=github_username, random_key=random_key)
    db.session.add(user)
    db.session.commit()

    # Generate a session ID
    session_id = secrets.token_urlsafe(16)
    session[session_id] = github_username

    return jsonify({'session_id': session_id})

@app.route('/api/protected', methods=['GET'])
def protected_api():
    session_id = request.headers.get('Authorization')
    if session_id and session_id in session:
        github_username = session[session_id]
        return jsonify({'message': f'This is a protected API endpoint for user {github_username}!'})
    return jsonify({'message': 'Unauthorized'}), 401

if __name__ == '__main__':
    app.run(debug=True)
