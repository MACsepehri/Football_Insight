import requests
import pandas
import os
import json
import time
import dotenv
from sklearn.linear_model import LinearRegression


class dataset:
    def __init__(self):
        self.dataset_path = 'api/v1/data/index.csv'
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

            return teams

        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError, KeyError) as error:
            print(f'Failed to load teams: {error}')
            return False

    def get(self, team):
        if not os.path.isfile(self.dataset_path):
            print('Dataset does not exist.')
            return False

        try:
            data = pandas.read_csv(self.dataset_path, sep=';')

            if data.empty:
                print('Dataset is empty.')
                return False

            info = data[data['team'] == team]

            if info.empty:
                print(f'No data found for {team}.')
                return False

            return info
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError, KeyError) as error:
            print(f'Failed to get team: {error}')
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
        self.dataset_path = 'api/v1/data/index.csv' ### dataset path
        self.window = None ### matches used for the form (None = all matches)
        self.is_fitted = False
        self.teams = {}
        self.X = None

    def __valid_dataset(self, path=None):
        ### checking that the dataset does exists or does it have any content or not
        path = path or self.dataset_path
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) == 0:
            return False
        try:
            data = pandas.read_csv(path, sep=';')
            return not data.empty
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return False

    def load_data(self):
        ### loading dataset
        if not self.__valid_dataset():
            return [], False
        try:
            data = pandas.read_csv(self.dataset_path, sep=';')
            return [data], True
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return [], False

    def __load_teams(self, path=None):
        ### building a dict of team name -> list of matches (oldest first)
        path = path or self.dataset_path
        data = pandas.read_csv(path, sep=';')

        teams = {}

        for _, row in data.iterrows():
            matches = row.get('matches')

            if isinstance(matches, str):
                try:
                    matches = json.loads(matches)
                except json.JSONDecodeError:
                    matches = []

            if not isinstance(matches, list):
                matches = []

            matches = [
                match for match in matches
                if isinstance(match, dict) and match.get('result')
            ]

            name = row.get('team')
            teams.setdefault(name, [])
            teams[name].extend(matches)

        for name, matches in teams.items():
            matches.sort(key=lambda match: match.get('date') or '')

        return teams

    def __find_team(self, name):
        ### finding a team by name, ignoring case and spaces
        if name in self.teams:
            return name

        target = str(name).strip().lower()

        for team in self.teams:
            if team.strip().lower() == target:
                return team

        return None

    def __stats(self, matches, before=None):
        ### form of a team over its last matches before an optional date
        if before is not None:
            matches = [
                match for match in matches
                if (match.get('date') or '') < before
            ]

        if self.window is not None:
            matches = matches[-self.window:]

        if not matches:
            return None

        scored = 0
        conceded = 0
        wins = 0

        for match in matches:
            result = match['result']
            own = result.get('homeScore')
            opponent = result.get('opponentScore')

            if own is None or opponent is None:
                continue

            scored += own
            conceded += opponent

            if own > opponent:
                wins += 1

        count = len(matches)

        return {
            'own_avg_scored': scored / count,
            'own_avg_conceded': conceded / count,
            'own_win_rate': wins / count,
        }

    def __features(self, own, opponent):
        ### features of one team against a concrete opponent
        return {
            'own_avg_scored': own['own_avg_scored'],
            'own_avg_conceded': own['own_avg_conceded'],
            'own_win_rate': own['own_win_rate'],
            'opp_avg_scored': opponent['own_avg_scored'],
            'opp_avg_conceded': opponent['own_avg_conceded'],
        }

    def fit(self):
        ### loading the dataset and fitting the model automatically
        if not self.__valid_dataset():
            print('Dataset is not valid.')
            return False

        self.teams = self.__load_teams()

        rows = []
        targets = []

        for team, matches in self.teams.items():
            for match in matches:
                own = self.__stats(matches, before=match.get('date'))

                if own is None:
                    continue

                opponent = self.teams.get(match.get('name'))

                if not opponent:
                    continue

                opponent = self.__stats(
                    opponent,
                    before=match.get('date')
                )

                if opponent is None:
                    continue

                goals = match['result'].get('homeScore')

                if goals is None:
                    continue

                rows.append(self.__features(own, opponent))
                targets.append(goals)

        if len(rows) < 2:
            print('Not enough matches to fit the model.')
            return False

        self.X = pandas.DataFrame(
            rows,
            columns=[
                'own_avg_scored',
                'own_avg_conceded',
                'own_win_rate',
                'opp_avg_scored',
                'opp_avg_conceded'
            ]
        )

        self.lr.fit(self.X, targets)
        self.is_fitted = True

        print(f'Model fitted on {len(self.X)} matches.')

        return True

    def __print_matches(self, name, matches):
        last = matches if self.window is None else matches[-self.window:]

        print(f'{name} - last {len(last)} matches:')

        for match in last:
            result = match['result']

            print(
                f"  {match.get('date')} vs {match.get('name')} "
                f"{result.get('homeScore')}-"
                f"{result.get('opponentScore')}"
            )

    def predict_match(self, home_team, away_team):
        ### predicting the score of a game between two teams
        if not self.is_fitted and not self.fit():
            return False

        home = self.__find_team(home_team)
        away = self.__find_team(away_team)

        if home is None:
            print(f'Team not found: {home_team}')
            return False

        if away is None:
            print(f'Team not found: {away_team}')
            return False

        home_form = self.__stats(self.teams[home])
        away_form = self.__stats(self.teams[away])

        if home_form is None or away_form is None:
            print('Not enough matches for one of the teams.')
            return False

        self.__print_matches(home, self.teams[home])
        self.__print_matches(away, self.teams[away])

        home_goals = self.lr.predict(
            pandas.DataFrame([self.__features(home_form, away_form)])
        )[0]

        away_goals = self.lr.predict(
            pandas.DataFrame([self.__features(away_form, home_form)])
        )[0]

        home_goals = max(0, round(home_goals))
        away_goals = max(0, round(away_goals))

        print(f'Predicted score: {home} {home_goals} - {away_goals} {away}')

        return {
            'home': home,
            'away': away,
            'home_goals': home_goals,
            'away_goals': away_goals
        }
