import os
import json
from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from google.cloud import storage

BUCKET_NAME = "fantasy_cricket" 

app = Flask(__name__)
app.secret_key = "secretkey"  # Replace with a secure key

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Dictionary to store user apartment numbers
user_apartments = {}  # Format: {username: apartment_number}
team_dir = "user_teams"  # Directory to store user teams

# Ensure the directory exists
os.makedirs(team_dir, exist_ok=True)

# Load player data from JSON
def load_players():
    try:
        with open("players.json", "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

players = load_players()

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    return User(username)

@app.route("/Index")
@login_required
def index():
    username = current_user.id
    team = load_team(username)
    budget = 100 - sum(player["price"] for player in team)
    return render_template("index.html", players=players, budget=budget, team=team)

@app.route("/" , methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        apartment_number = request.form["apartment_number"]
        user = User(username)
        login_user(user)
        
        # Save apartment number
        user_apartments[username] = apartment_number

        # Load team if it exists
        team = load_team(username)
        if not team:  # If no team, initialize an empty team
            save_team(username, [])

        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/select/<int:player_id>")
@login_required
def select_player(player_id):
    username = current_user.id
    team = load_team(username)
    player = next((p for p in players if p["id"] == player_id), None)

    if player and player not in team:
        budget = 100 - sum(p["price"] for p in team)
        if budget >= player["price"] and len(team) < 11:
            team.append(player)
            save_team(username, team)  # Save the updated team
    return redirect(url_for("index"))

@app.route("/remove/<int:player_id>")
@login_required
def remove_player(player_id):
    username = current_user.id
    team = load_team(username)
    player = next((p for p in team if p["id"] == player_id), None)

    if player:
        team.remove(player)
        save_team(username, team)  # Save the updated team
    return redirect(url_for("index"))

@app.route("/submit", methods=["POST"])
@login_required
def submit_team():
    username = current_user.id
    apartment_number = user_apartments.get(username, "unknown")
    team = load_team(username)
    
    # Create the file content (team in .txt format)
    file_content = ""
    for player in team:
        file_content += f"{player['name']} - {player['role']}\n"

    # Save the team to Google Cloud Storage
    filename = f"{username}_{apartment_number}.txt"
    
    # Initialize the storage client and get the bucket
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    
    # Create a blob object in the bucket and upload the content
    blob = bucket.blob(filename)
    blob.upload_from_string(file_content)
    
    # Return the filename or the URL of the file
    file_url = blob.public_url  # Make the file publicly accessible
    return render_template("submit.html", team=team, filename=filename, file_url=file_url)



# Helper Functions
def save_team(username, team):
    apartment_number = user_apartments.get(username, "unknown")
    filename = f"{username}_{apartment_number}.json"
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(json.dumps(team))

def load_team(username):
    apartment_number = user_apartments.get(username, "unknown")
    filename = f"{username}_{apartment_number}.json"
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    if blob.exists():
        return json.loads(blob.download_as_text())
    return []

def get_storage_client():
    return storage.Client()

if __name__ == "__main__":
    app.run(debug=True)
