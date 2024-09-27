from flask import Flask, jsonify
from .events import all_events

app = Flask(__name__)


@app.route('/events', methods=['GET'])
def get_data():
    events = all_events()
    for event in events:
        if event.first_date is not None:
            event.first_date = event.first_date.isoformat()
        if event.second_date is not None:
            event.second_date = event.second_date.isoformat()
    return jsonify(events)
