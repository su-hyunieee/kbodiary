from flask import Flask, render_template, request, redirect, url_for, session
from models import db, Schedule, Diary
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'kbodiary.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev'
db.init_app(app)

TEAM_CITY_API_MAPPING = {
    '한화': 'Daejeon', 'KIA': 'Gwangju', '삼성': 'Daegu', '두산': 'Seoul',
    'LG': 'Seoul', '롯데': 'Busan', 'SSG': 'Incheon', 'NC': 'Changwon',
    'KT': 'Suwon', '키움': 'Seoul'
}

TEAM_LOGO_MAPPING = {
    '한화': 'hanwha',
    'KIA': 'kia',
    '삼성': 'samsung',
    '두산': 'doosan',
    'LG': 'lg',
    '롯데': 'lotte',
    'SSG': 'ssg',
    'NC': 'nc',
    'KT': 'kt',
    '키움': 'kiwoom'
}

WEATHER_API_KEY = 'your_key'

@app.cli.command('initdb')
def initdb_command():
    db.drop_all()
    db.create_all()
    print('📂 Database 초기화 완료')

def crawl_games():
    today = datetime.date.today()
    #정규시즌인 9월까지
    for i in range(150):
        date = (today + datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        url = f'https://m.sports.naver.com/kbaseball/schedule/index?date={date}'

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')

        service = Service('/usr/local/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(3)

        games = driver.find_elements(By.CLASS_NAME, 'MatchBox_match_item__3_D0Q')
        print(f"{date} 경기 수:", len(games))

        for game in games:
            teams = game.find_elements(By.CLASS_NAME, 'MatchBoxHeadToHeadArea_team_item__25jg6')
            if len(teams) >= 2:
                away_team_raw = teams[0].text.strip().replace('\n', ' ')
                home_team_raw = teams[1].text.strip().replace('\n', ' ')

                away_team = away_team_raw.split()[0]
                home_team = home_team_raw.split()[0]

                exists = Schedule.query.filter_by(date=date, home_team=home_team, away_team=away_team).first()
                if not exists:
                    schedule = Schedule(date=date, home_team=home_team, away_team=away_team)
                    db.session.add(schedule)
                    print(f"✅ 저장: {date} {home_team} vs {away_team}")

        db.session.commit()
        driver.quit()

    print("✅ 모든 팀 경기 DB 저장 완료!")



@app.route('/select_team', methods=['GET', 'POST'])
def select_team():
    if request.method == 'POST':
        team = request.form.get('team')
        session['team'] = team
        return redirect(url_for('index'))
    return render_template('select_team.html', team_list=TEAM_LOGO_MAPPING.keys(), logo_mapping=TEAM_LOGO_MAPPING)

def decorate_weather(desc):
    if not desc:
        return "날씨 정보 없음"
    if "맑음" in desc: return "☀️ " + desc
    elif "흐림" in desc: return "☁️ " + desc
    elif "비" in desc or "소나기" in desc: return "🌧️ " + desc
    elif "눈" in desc: return "❄️ " + desc
    else: return "🌡️ " + desc

def get_weather(city):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': f"{city},KR",
        'appid': WEATHER_API_KEY,
        'units': 'metric',
        'lang': 'kr'
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        desc = data['weather'][0]['description']
        temp = data['main']['temp']
        decorated = decorate_weather(desc)
        return f"{desc}, {temp}°C"
    else:
        print(f"❌ Weather API 오류: {response.status_code}, {response.text}")
        return "날씨 정보 없음"

@app.route('/')
def home():
    return redirect(url_for('select_team'))

@app.route('/index')
def index():
    team = session.get('team')
    if not team:
        return redirect(url_for('select_team'))
    schedules = Schedule.query.filter(
        (Schedule.home_team.like(f"%{team}%"))|
        (Schedule.away_team.like(f"%{team}%"))
    ).all()
    diaries = {d.date: d for d in Diary.query.filter_by(team=team).all()}
    return render_template('index.html', schedules=schedules, diaries=diaries)

@app.route('/diary/<date>', methods=['GET', 'POST'])
def diary(date):
    team = session.get('team')
    if not team:
        return redirect(url_for('select_team'))

    diaries = {d.date: d for d in Diary.query.filter_by(team=team).all()}

    logo_filename = TEAM_LOGO_MAPPING.get(team, 'default') + '.png'

    schedules = Schedule.query.filter_by(date=date).filter(
        (Schedule.home_team.like(f"%{team}%")) |
        (Schedule.away_team.like(f"%{team}%"))
    ).all()
    diary_entry = Diary.query.filter_by(date=date, team = team).first()
 
    # home_team에서 '홈' 같은 거 제거
    first_home = schedules[0].home_team.split()[0] if schedules else "Seoul"
    city = TEAM_CITY_API_MAPPING.get(first_home, "Seoul")

    today_str = datetime.datetime.today().strftime('%Y-%m-%d')
    display_weather = None

    if date == today_str and not diary_entry:
        display_weather = get_weather(city)
    elif diary_entry:
        display_weather = diary_entry.weather
    else:
        display_weather = "날씨 정보 없음"

    if request.method == 'POST':
        mood = request.form.get('mood')
        result = request.form.get('result')
        weather = get_weather(city)

        if diary_entry:
            diary_entry.mood = mood
            diary_entry.result = result
            diary_entry.weather = weather
            db.session.commit()
        else:
            new_diary = Diary(date=date, team = team, mood=mood, result=result, weather=weather)
            db.session.add(new_diary)
            db.session.commit()

        return redirect(url_for('index'))

    return render_template('diary.html', date=date, schedules=schedules, diary=diary_entry, display_weather=display_weather, logo_filename=logo_filename, diaries = diaries)

@app.route('/diary/delete/<int:diary_id>', methods=['POST'])
def delete_diary(diary_id):
    diary_entry = Diary.query.get_or_404(diary_id)
    db.session.delete(diary_entry)
    db.session.commit()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
