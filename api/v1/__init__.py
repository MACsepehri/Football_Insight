import requests
import pandas
import os
import json
import time
import dotenv


class dataset:
    def __init__(self):
        self.dataset_path = 'data/index.csv'
        self.base_url = 'https://api.football-data.org/v4'

        dotenv.load_dotenv('../../.env')

        self.api_token = (
            os.getenv('API-TOKEN')
            or os.getenv('API-TOEKN')
        )

        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': self.api_token or ''
        })

    def __request(self, endpoint, params=None):
        url = f'{self.base_url}/{endpoint}'

        for attempt in range(5):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=30
                )

                if response.status_code == 429:
                    wait = int(
                        response.headers.get('Retry-After', 60)
                    )
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as error:
                if attempt == 4:
                    print(f'API request failed: {error}')
                    return None

                time.sleep(2 ** attempt)

        return None

    def show_teams(self):
        if not os.path.isfile(self.dataset_path):
            print('Dataset does not exist.')
            return False

        try:
            data = pandas.read_csv(self.dataset_path, sep=';')

            if data.empty:
                print('Dataset is empty.')
                return False

            teams = data['team'].dropna().unique()

            for index, team in enumerate(teams, start=1):
                print(f'{index}. {team}')

            print(f'\nTotal teams: {len(teams)}')
            return True

        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError, KeyError) as error:
            print(f'Failed to load teams: {error}')
            return False

    def update(self):
        if not self.api_token:
            print('API token not found.')
            return False

        os.makedirs(
            os.path.dirname(self.dataset_path) or '.',
            exist_ok=True
        )

        competitions_data = self.__request('competitions')

        if not competitions_data:
            return False

        competitions = competitions_data.get(
            'competitions', []
        )

        teams_data = {}

        for competition in competitions:
            if competition.get('type') != 'LEAGUE':
                continue

            competition_id = competition.get('id')
            competition_name = competition.get('name')
            season = competition.get('currentSeason')

            if not competition_id or not season:
                continue

            start_date = season.get('startDate')

            if not start_date:
                continue

            season_year = int(start_date[:4])

            print(
                f'Loading {competition_name} '
                f'({season_year})...'
            )

            teams_response = self.__request(
                f'competitions/{competition_id}/teams',
                {
                    'season': season_year
                }
            )

            if teams_response is None:
                continue

            for team in teams_response.get('teams', []):
                team_id = team.get('id')

                if team_id is None:
                    continue

                key = (competition_id, team_id)

                teams_data[key] = {
                    'competition': competition_name,
                    'team': team.get('name', 'Unknown'),
                    'total_win': 0,
                    'total_lose': 0,
                    'total_draw': 0,
                    'matches': []
                }

            offset = 0
            limit = 500

            while True:
                matches_response = self.__request(
                    f'competitions/{competition_id}/matches',
                    {
                        'season': season_year,
                        'status': 'FINISHED',
                        'limit': limit,
                        'offset': offset
                    }
                )

                if matches_response is None:
                    break

                matches = matches_response.get('matches', [])

                if not matches:
                    break

                for match in matches:
                    home_team = match.get('homeTeam', {})
                    away_team = match.get('awayTeam', {})

                    home_id = home_team.get('id')
                    away_id = away_team.get('id')

                    score = match.get('score', {}).get(
                        'fullTime', {}
                    )

                    home_score = score.get('home')
                    away_score = score.get('away')

                    if (
                        home_id is None
                        or away_id is None
                        or home_score is None
                        or away_score is None
                    ):
                        continue

                    home_key = (competition_id, home_id)
                    away_key = (competition_id, away_id)

                    if (
                        home_key not in teams_data
                        or away_key not in teams_data
                    ):
                        continue

                    home = teams_data[home_key]
                    away = teams_data[away_key]

                    if home_score > away_score:
                        home['total_win'] += 1
                        away['total_lose'] += 1

                    elif home_score < away_score:
                        away['total_win'] += 1
                        home['total_lose'] += 1

                    else:
                        home['total_draw'] += 1
                        away['total_draw'] += 1

                    match_date = match.get('utcDate')

                    home['matches'].append({
                        'name': away['team'],
                        'date': match_date,
                        'result': {
                            'homeScore': home_score,
                            'opponentScore': away_score,
                            'opponentWon': away_score > home_score
                        }
                    })

                    away['matches'].append({
                        'name': home['team'],
                        'date': match_date,
                        'result': {
                            'homeScore': away_score,
                            'opponentScore': home_score,
                            'opponentWon': home_score > away_score
                        }
                    })

                offset += len(matches)

                if len(matches) < limit:
                    break

        columns = [
            'competition',
            'team',
            'total_win',
            'total_lose',
            'total_draw',
            'matches'
        ]

        rows = []

        for team in teams_data.values():
            team['matches'] = json.dumps(
                team['matches'],
                ensure_ascii=False
            )

            rows.append(team)

        if not rows:
            print('No team data was retrieved.')
            return False

        data = pandas.DataFrame(rows, columns=columns)

        data.to_csv(
            self.dataset_path,
            sep=';',
            index=False,
            encoding='utf-8'
        )

        print(f'Total teams: {len(data)}')
        print(f'Dataset saved to: {self.dataset_path}')

        return True


class model:
    def __init__(self):
        self.lr = LinearRegression() ### creating linear regression model
        self.dataset_path = 'data/index.csv' ### dataset path

    def __valid_dataset(self, path=None):
        ### checking that the dataset does exists or does it have any content or not
        path = path or self.dataset_path
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) == 0:
            return False
        try:
            data = pandas.read_csv(path)
            return not data.empty
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return False

    def load_data(self):
        ### loading dataset
        if not self.__valid_dataset():
            return [], False
        try:
            data = pandas.read_csv(self.dataset_path)
            return [data], True
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return [], False