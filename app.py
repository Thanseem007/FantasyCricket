import os
import json
from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

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
        filepath = os.path.join(team_dir, f"{username}_{apartment_number}.json")
        if not os.path.exists(filepath):
            save_team(username, [])  # Initialize an empty team if no file exists

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
    filepath = f"{username}_{apartment_number}.txt"
    with open(filepath, "w") as file:
        for player in team:
            file.write(f"{player['name']} - {player['role']}\n")
    return render_template("submit.html", team=team, filename=filepath)

# Helper Functions
def save_team(username, team):
    apartment_number = user_apartments.get(username, "unknown")
    filepath = os.path.join(team_dir, f"{username}_{apartment_number}.json")
    with open(filepath, "w") as file:
        json.dump(team, file)

def load_team(username):
    apartment_number = user_apartments.get(username, "unknown")
    filepath = os.path.join(team_dir, f"{username}_{apartment_number}.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as file:
            return json.load(file)
    return []

if __name__ == "__main__":
    app.run(debug=True)
