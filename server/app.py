from flask import Flask, jsonify, request
from flask_cors import CORS
from weather import get_clean_weather, get_weather_state
from openaiService import getSongParams, makedescription, maketitle
from playlist import make_new_playlist

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/api/weather_new")
def weather_new():
    return jsonify(get_clean_weather())

# @app.route('/api/hello', methods=['GET'])
# def hello():
#     return jsonify({
#         'message': 'Hello from Flask backend!'
#     })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy'
    })

@app.route('/api/makeplaylistcurrentweather', methods=['GET'])
def makeplaylistcurrentweather():
    weather_data = get_weather_state()
    song_params = getSongParams(weather_data)
    title = maketitle(song_params, weather_data)
    description = makedescription(song_params, weather_data, title)
    make_new_playlist(weather_data)
    return jsonify({
        'status': 'playlist made',
        'title': title,
        'description': description
    })

@app.route('/api/makeplaylistcustomweather', methods=['POST'])
def makeplaylistcustomweather():
    weather_data = request.get_json()

    if not weather_data:
        return jsonify({'error': 'No weather data provided'}), 400

    song_params = getSongParams(weather_data)
    title = maketitle(song_params, weather_data)
    make_new_playlist(weather_data)
    return jsonify({
        'status': 'playlist made',
        'title': title
    })



if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5000)

