import os
import json
from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user 
from google.cloud import storage
import openpyxl
from google.cloud import storage
import io
from flask import jsonify

BUCKET_NAME = "fantasy_cricket" 
DO_SERVER_DOWN = "doServerdown.txt"

app = Flask(__name__)
app.secret_key = "secretkey"  # Replace with a secure key

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Dictionary to store user apartment numbers
user_apartments = {}  # Format: {username: apartment_number}
team_dir = "user_teams"  # Directory to store user teams
is_Cloud = True

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
        if IsDownTimeReached() :
            return redirect(url_for("server_down"))
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/server_down")
def server_down():
    print (123)
    return render_template("server_down.html")

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
    if IsDownTimeReached() :
            return redirect(url_for("server_down"))
    username = current_user.id
    apartment_number = user_apartments.get(username, "unknown")
    team = load_team(username)
    
    captain_id = request.form.get('captain_id')
    # Create the file content (team in .txt format)
    # file_content = ""
    # for player in team:
    #     file_content += f"{player['name']} - {player['role']}\n"

    # # Save the team to Google Cloud Storage
    # filename = f"{username}_{apartment_number}.txt"
    
    # # Initialize the storage client and get the bucket
    # client = get_storage_client()
    # bucket = client.bucket(BUCKET_NAME)
    
    # # Create a blob object in the bucket and upload the content
    # blob = bucket.blob(filename)
    # blob.upload_from_string(file_content)
    
    # # Return the filename or the URL of the file
    # file_url = blob.public_url  # Make the file publicly accessible
    file_url = update_excel_file(username, apartment_number,team,captain_id)
    return render_template("submit.html", team=team)

@app.route('/update_captain/<int:player_id>', methods=['POST'])
def update_captain(player_id):
    try:
        # Get player ID from the request
        #player_id = request.json.get('player_id')

        if not player_id:
            return jsonify({'error': 'Player ID is required'}), 400


        # Read the file from Google Cloud Storage
        username = current_user.id
        team = load_team(username)

        # Update IsCaptain field
        captain_updated = False
        for player in team:
            if player["id"] == player_id:
                player["IsCaptain"] = 1
                captain_updated = True
            else:
                player["IsCaptain"] = 0

        if not captain_updated:
            return jsonify({'error': 'Player not found'}), 404

        # Save the updated JSON
        save_team(username, team)

        return jsonify({'message': 'Captain updated successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper Functions
def save_team(username, team):
    apartment_number = user_apartments.get(username, "unknown")
    if is_Cloud :
      filename = f"{username}_{apartment_number}.json"
      client = get_storage_client()
      bucket = client.bucket(BUCKET_NAME)
      blob = bucket.blob(filename)
      blob.upload_from_string(json.dumps(team))
    else :
      filepath = os.path.join(team_dir, f"{username}_{apartment_number}.json")
      with open(filepath, "w") as file:
          json.dump(team, file)

def load_team(username):
    apartment_number = user_apartments.get(username, "unknown")
    filename = f"{username}_{apartment_number}.json"
    if(is_Cloud) :
       client = get_storage_client()
       bucket = client.bucket(BUCKET_NAME)
       blob = bucket.blob(filename)
       if blob.exists():
          return json.loads(blob.download_as_text())
    else :
        filepath = os.path.join(team_dir, f"{username}_{apartment_number}.json")
        if os.path.exists(filepath):
           with open(filepath, "r") as file:
            return json.load(file)
    return []

def get_storage_client():
    return storage.Client()

def update_excel_file(username,apartment_number ,team,captain_id):
    # Define the Excel file name in the GCS bucket
    excel_filename = "user_players.xlsx"
    
    # Initialize the GCS client and bucket
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)  # Replace with your actual GCS bucket name
    blob = bucket.blob(excel_filename)

    # Check if the file exists
    if blob.exists():
        # Download the existing file from GCS
        excel_data = blob.download_as_bytes()
        workbook = openpyxl.load_workbook(io.BytesIO(excel_data))
        sheet = workbook.active
    else:
        # If the file does not exist, create a new Excel file
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Username", "Player 1", "Player 2", "Player 3", "Player 4", "Player 5", "Player 6", "Player 7", "Player 8", "Player 9", "Player 10", "Player 11", "Apartment Number"])  # Add header row
    # Prepare the row to be added (username + selected players)
    row = [username]  # Start with the username in the first column

    # Add player names to the row
    for player in team:
        if str(player["id"]) == str(captain_id):
            row.append(player["name"] + " (C) ")
        else:
            row.append(player["name"])

    # Append the row to the sheet
    row.extend([""] * (12 - len(row)))  # Fill remaining columns if fewer than 11 players
    row.append(apartment_number)  # Add the apartment number as the last column

    # Check if an entry for this username and apartment number already exists
    existing_row = None
    for r_idx, existing_row_data in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if existing_row_data[0] == username and existing_row_data[-1] == apartment_number:
            existing_row = r_idx
            break

    if existing_row:
        # Update the existing row
        for col_idx, value in enumerate(row, start=1):
            sheet.cell(row=existing_row, column=col_idx, value=value)
    else:
        # Append a new row if no existing entry is found
        sheet.append(row)

    # Save the workbook to a BytesIO object
    updated_excel_data = io.BytesIO()
    workbook.save(updated_excel_data)
    updated_excel_data.seek(0)  # Rewind the stream to the beginning

    # Upload the updated Excel file back to GCS
    blob.upload_from_file(updated_excel_data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Make the file publicly accessible (optional)
    blob.make_public()

    # Return the public URL of the Excel file (or you can return a signed URL if needed)
    return blob.public_url

def IsDownTimeReached():
    try:
        if(is_Cloud) :
        # Initialize a client
            client = get_storage_client()

        # Get the bucket
            bucket = client.bucket(BUCKET_NAME)

        # Get the blob (file)
            blob = bucket.blob(DO_SERVER_DOWN)

        # Read the content of the file
            flag_value = blob.download_as_text().strip()
        else :
            filepath = os.path.join(team_dir, DO_SERVER_DOWN)
            with open(filepath, 'r') as file:
              flag_value = file.read().strip()
        # Check if the flag is 0
        print(type(flag_value))
        if flag_value =="1" :
         return True
        return False
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    app.run(debug=True)
