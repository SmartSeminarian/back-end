from flask import Flask, redirect, url_for, jsonify
import os
from logger import log
from dotenv import load_dotenv
import secrets

load_dotenv()

# read version from file if exists
version = "unknown"
try:
    with open("/VERSION") as f:
        version = f.read()
except FileNotFoundError:
    pass

app = Flask(__name__)
GUNICORN_VERSION=f"{os.getenv('GUNICORN_VERSION', 'Unknown')}"
log.info('Service started, version: [%s]', GUNICORN_VERSION)


@app.route('/')
def index():
    return f"FIX ME! {GUNICORN_VERSION}"


@app.route('/generate_key', methods=['GET'])
def generate_key():
    random_key = secrets.token_urlsafe(16)
    return jsonify({'key': random_key})


@app.route('/version', methods=['GET'])
def version():
    answer = {
        'api_version': "0.0.1",
        'build_info' : 'TBD'
    }
    return jsonify(answer)

