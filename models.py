from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    date = db.Column(db.String(10), nullable= False)
    home_team = db.Column(db.String(50), nullable= False)
    away_team = db.Column(db.String(50), nullable= False)

class Diary(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    team = db.Column(db.String(50), nullable=False)  # 추가!
    date = db.Column(db.String(10), nullable= False)
    mood = db.Column(db.Text, nullable = True)
    weather = db.Column(db.String(100), nullable = True)
    result = db.Column(db.String(10), nullable =True) # 이거 100 10 이유 물어보기 왤케 기냐