from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from pendulum import timezone
import pendulum
import json

class LastCall:
    def __init__(self, time=pendulum.now()):
        self.time = time
        
    def update(self, new_time):
        self.time = new_time

def game_to_local_time(game_date, game_start_time):
    if game_start_time == "":
        return None
    
    game_time = game_date + ' ' + game_start_time[:-1]
    game_time += game_start_time[-1].upper() + 'M'
    local_tz = timezone(pendulum.now().timezone_name)
    eastern_time = pendulum.from_format(game_time, "ddd, MMM D, YYYY h:mmA", "US/Eastern")
    return local_tz.convert(eastern_time)

def update_cache(cache_name, newGames, time):
    # save furuture games
    with open(cache_name, 'w') as file:
        text = str(newGames).replace("'", '"')
        file.write(text)
    last_call.update(time)
    
    
def load_cache(cache_name):
    with open(cache_name, 'r') as file:
        try:
            games = json.loads(file.read())
            return games
        except ValueError as e:
            return []
    
last_call = LastCall()
with open('future_games_cache.txt', 'w') as file:
    file.write("")
with open('past_games_cache.txt', 'w') as file:
    file.write("")

app = FastAPI()

origins = [
    'http://localhost:5173',
    'https://react-nba-game.vercel.app'
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
def root():
    return {"A python api to get nba schedual data."}

@app.get('/future_games')
def get_future_games():
    now = pendulum.now()
    future_games_cache = load_cache('future_games_cache.txt')
    
    if last_call.time.hour == now.hour and last_call.time.diff(now).in_hours() < 1 and future_games_cache != []:
        print("used cache. ✔️")
        return future_games_cache
    
    print('didnt use cache. ❌')
    print(f'last call: {last_call.time.hour}, now: {now.hour}')
    print(f'difference: {last_call.time.diff(now).in_hours()}')
    
    season = now.add(months=6).year
    month = now.format('MMMM').lower()
    query = 'https://www.basketball-reference.com/leagues/NBA_{}_games-{}.html'.format(
        season, month
    )
    response = requests.get(query)
    try:
        html = BeautifulSoup(response.text, "html.parser")
        games_table = html.find("table", attrs={"id": "schedule"})
        games = games_table.find("tbody").find_all("tr")
    except:
        print(response.headers)
        raise HTTPException(
            status_code=429, 
            detail="API Blocked by basketball reference due to too many requests.", 
            headers={'Retry-After': '5min - 1hour'}
        )
        
    future_games = []
    for game in games:
        if game.has_attr('class'):
            continue
        date = game.find("th").find("a").text
        start_time = game.find("td").text
        game_time = game_to_local_time(date, start_time)
        if game_time == None:
            continue
        
        diff_in_hours = now.diff(game_time, False).in_hours()
        if  diff_in_hours < 0:
            continue
        if diff_in_hours > 24:
            update_cache('future_games_cache.txt', future_games, now)
            return future_games
        
        home_team =  game.find('td', attrs={'data-stat': 'home_team_name'})
        away_team = game.find('td', attrs={'data-stat': 'visitor_team_name'})
        game_object = dict(
            id = game.find("th").get("csk"),
            home = dict(
                credentials = home_team.get('csk').split('.')[0],
                name =  home_team.find("a").text.split(' ')[-1],
                side = "home"
            ),
            away = dict(
                credentials = away_team.get('csk').split('.')[0],
                name =  away_team.find("a").text.split(' ')[-1],
                side = "away"
            ),
            start_time = game_time.to_iso8601_string()
        )
        future_games.append(game_object)
    
    update_cache('future_games_cache.txt', future_games, now)
    return future_games

@app.get('/past_games')
def get_past_games():
    now = pendulum.now()
    past_games_cache = load_cache('past_games_cache.txt')
    
    if last_call.time.diff(now).in_minutes() < 15 and past_games_cache != []:
        print("used cache. ✔️")
        return past_games_cache
    
    print('didnt use cache. ❌')
    print(f'last call: {last_call.time.hour}, now: {now.hour}')
    print(f'difference: {last_call.time.diff(now).in_hours()}')
    
    season = now.add(months=6).year
    month = now.format('MMMM').lower()
    query = 'https://www.basketball-reference.com/leagues/NBA_{}_games-{}.html'.format(
        season, month
    )
    response = requests.get(query)
    try:
        html = BeautifulSoup(response.text, "html.parser")
        games_table = html.find("table", attrs={"id": "schedule"})
        games = games_table.find("tbody").find_all("tr")
    except:
        print(response.headers)
        raise HTTPException(
            status_code=429, 
            detail="API Blocked by basketball reference due to too many requests.", 
            headers={'Retry-After': '5min - 1hour'}
        )
        
    past_games = []
    for game in games:
        if game.has_attr('class'):
            continue
        date = game.find("th").find("a").text
        start_time = game.find("td").text
        game_time = game_to_local_time(date, start_time)
        if game_time == None:
            continue
        
        diff_in_hours = now.diff(game_time, False).in_hours()
        if  diff_in_hours < -24:
            continue
        if diff_in_hours > 0:
            update_cache('past_games_cache.txt', past_games, now)
            return past_games
        
        home_team =  game.find('td', attrs={'data-stat': 'home_team_name'})
        away_team = game.find('td', attrs={'data-stat': 'visitor_team_name'})
        home_score = game.find('td', attrs={'data-stat': 'home_pts'}).text
        away_score = game.find('td', attrs={'data-stat': 'visitor_pts'}).text
        game_object = dict(
            id = game.find("th").get("csk"),
            home = dict(
                credentials = home_team.get('csk').split('.')[0],
                name =  home_team.find("a").text.split(' ')[-1],
                side = "home",
                score =  int(home_score) if len(home_score) > 0 else ''
            ),
            away = dict(
                credentials = away_team.get('csk').split('.')[0],
                name =  away_team.find("a").text.split(' ')[-1],
                side = "away",
                score =  int(away_score) if len(away_score) > 0 else ''
            ),
            start_time = game_time.to_iso8601_string()
        )
        past_games.append(game_object)
    
    update_cache('past_games_cache.txt', past_games, now)
    return past_games

@app.get('/time')
def get_time():
    return game_to_local_time("Fri, Mar 1, 2024", "7:00p").to_iso8601_string()