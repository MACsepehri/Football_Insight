# from __init__ import model

# m = model()
# print(m.load_data())

import requests
import dotenv
import os

dotenv.load_dotenv('../../.env')

API_TOKEN = os.environ['API-TOEKN']

url = "https://api.football-data.org/v4/competitions/PD/matches"

headers = {
    "X-Auth-Token": API_TOKEN
}

params = {
    "season": 2026,
    "status": "FINISHED",
    "limit": 500
}

response = requests.get(
    url,
    headers=headers,
    params=params,
    timeout=30
)

if response.status_code == 200:
    matches = response.json()["matches"]

    for match in matches:
        if match["homeTeam"]["id"] == 81 or match["awayTeam"]["id"] == 81:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]

            score = match["score"]["fullTime"]

            print(f"{match['utcDate']} | {home} {score['home']} - {score['away']} {away}")
else:
    print(response.status_code, response.text)