from openaiService import getSongParams, makedescription, maketitle

from weather import get_weather_state

weather_data = get_weather_state()
print(weather_data)

song_params = getSongParams(weather_data)
print(f"Valence: {song_params.valence}")         # Output: 0.85 (example)
print(f"Danceability: {song_params.danceability}") # Output: 0.72 (example)
print(f"Energy: {song_params.energy}")
title = maketitle(song_params, weather_data)
description = makedescription(song_params, weather_data, title)
print(title)
print(description)


sunny_weather_data = {'current_weather': 'Clear sky', 'current_time': 'Morning'}
sunny_song_params = getSongParams(sunny_weather_data)
print(f"Sunny Valence: {sunny_song_params.valence}")         # Output: 0.85 (example)
print(f"Sunny Danceability: {sunny_song_params.danceability}") # Output: 0.72 (example)
print(f"Sunny Energy: {sunny_song_params.energy}")
sunny_title = maketitle(sunny_song_params, sunny_weather_data)
sunny_description = makedescription(sunny_song_params, sunny_weather_data, sunny_title)
print(sunny_title)
print(sunny_description)
