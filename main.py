from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv; load_dotenv()
from datetime import datetime
import requests, os

app = Flask(__name__)
file_path = os.path.abspath(os.getcwd())+"\\database.db"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + file_path
db = SQLAlchemy(app)
scheduler = BackgroundScheduler()

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    price = db.Column(db.Float)
    gpu_name = db.Column(db.String(20))
    storage_cost = db.Column(db.Float)
    inet_down = db.Column(db.Float)
    inet_up = db.Column(db.Float)

    def __init__(self, date, price, gpu_name, storage_cost, inet_down, inet_up):
        self.date = date
        self.price = price
        self.gpu_name = gpu_name
        self.storage_cost = storage_cost
        self.inet_down = inet_down
        self.inet_up = inet_up

@scheduler.scheduled_job('interval', minutes=1)
def job():
    url = "https://console.vast.ai/api/v0/bundles"

    query = {
        'q': '{"verified": {"eq": true}, "external": {"eq": false}, "rentable": {"eq": true}, "disk_space": {"gt": "50"}, "num_gpus": {"eq": "1"}, "order": [["score", "desc"]], "type": "on-demand"}',
        'api_key': os.getenv("VAST-AI-AUTHKEY")
    }
    try:
        response = requests.get(url, params=query).json()
        date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        for cardInfo in response["offers"]:
            price = float(cardInfo["dph_base"])
            gpu_name = cardInfo["gpu_name"]
            storage_cost = float(cardInfo["storage_cost"])
            inet_down = float(cardInfo["inet_down"])
            inet_up = float(cardInfo["inet_up"])
            with app.app_context():
                new_data = Data(date, price, gpu_name, storage_cost, inet_down, inet_up)
                db.session.add(new_data)
                db.session.commit()
        print("Updated Data!")
    except Exception as e:
        print("Exeption during updating! : ", e)


def get_cheapest_items_by_date(filtered_data):
    data_by_date = {}
    for item in filtered_data:
        if item.date in data_by_date:
            data_by_date[item.date].append(item)
        else:
            data_by_date[item.date] = [item]
    cheapest_items = []
    for date, items in data_by_date.items():
        cheapest_item = min(items, key=lambda x: x.price)
        cheapest_items.append(cheapest_item)
    return cheapest_items


@app.route('/data')
def getData():
    gpu_name = request.args.get('gpu_name')
    storage_cost = request.args.get('storage_cost')
    inet_down = request.args.get('inet_down')
    inet_up = request.args.get('inet_up')

    if not gpu_name or not storage_cost or not inet_down or not inet_up:
        return jsonify(error="Missing required parameters"), 400
    
    data = Data.query.filter(Data.gpu_name == gpu_name, Data.storage_cost <= storage_cost, Data.inet_down >= inet_down, Data.inet_up >= inet_up).all()
    cheapCards = get_cheapest_items_by_date(data)
    dates = []
    prices = []
    for i in cheapCards:
        dates.append(i.date)
        prices.append(i.price)
    
    print(prices, dates)
    return jsonify(dates=dates, prices=prices)


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    scheduler.start()
    with app.app_context():
        db.create_all()
    app.run(debug=True)