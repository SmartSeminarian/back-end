import os
from flask import Flask, redirect, url_for
from flask_dance.contrib.github import make_github_blueprint, github
from dotenv import load_dotenv

load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

github_bp = make_github_blueprint(
    client_id=os.getenv("GITHUB_OAUTH_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_OAUTH_CLIENT_SECRET"),
)
app.register_blueprint(github_bp, url_prefix="/login")

@app.route("/")
def index():
    if not github.authorized:
        return redirect(url_for("github.login"))
    resp = github.get("/user")
    assert resp.ok, resp.text
    user_info = resp.json()
    return f"You are @{user_info['login']} on GitHub"

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
