from functools import lru_cache
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

from datetime import datetime, timedelta, time
import pytz


WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

WEATHER_CATEGORY_MAP = {
    "clear": {0},
    "partly cloudy": {1, 2},
    "overcast": {3},
    "fog": {45, 48},
    "rain": {51, 53, 55, 56, 61, 63, 65, 67, 80, 81, 82},
    "snow": {71, 73, 75, 77, 85, 86},
    "thunderstorm": {95, 96, 99},
}

TIMEZONE = "America/Vancouver"
LATITUDE = 49.2593
LONGITUDE = -123.2475
CACHE_BUCKET_MINUTES = 15

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

API_URL = "https://api.open-meteo.com/v1/forecast"
API_PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "daily": ["sunset", "sunrise"],
    "hourly": ["weather_code", "temperature_2m"],
    "forecast_days": 1,
    "timezone": "auto",
}


def _fetch_weather_response():
    responses = openmeteo.weather_api(API_URL, params=API_PARAMS)
    return responses[0]


def _build_hourly_dataframe(response):
    hourly = response.Hourly()
    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )
    }
    hourly_data["weather_code"] = hourly.Variables(0).ValuesAsNumpy()
    hourly_data["temperature"] = hourly.Variables(1).ValuesAsNumpy()

    hourly_dataframe = pd.DataFrame(data=hourly_data)
    hourly_dataframe["weather_description"] = hourly_dataframe["weather_code"].map(
        WEATHER_CODE_MAP
    )
    return hourly_dataframe


def _build_daily_dataframe(response):
    daily = response.Daily()
    daily_sunset = daily.Variables(0).ValuesInt64AsNumpy()
    daily_sunrise = daily.Variables(1).ValuesInt64AsNumpy()

    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        )
    }

    daily_data["sunset"] = daily_sunset
    daily_data["sunrise"] = daily_sunrise

    daily_dataframe = pd.DataFrame(data=daily_data)
    daily_dataframe["sunset_time"] = (
        pd.to_datetime(daily_sunset, unit="s").tz_localize("UTC").tz_convert(TIMEZONE)
    )
    daily_dataframe["sunrise_time"] = (
        pd.to_datetime(daily_sunrise, unit="s").tz_localize("UTC").tz_convert(TIMEZONE)
    )

    return daily_dataframe


def _cache_bucket():
    now_utc = datetime.now(pytz.UTC)
    return int(now_utc.timestamp() // (CACHE_BUCKET_MINUTES * 60))


@lru_cache(maxsize=4)
def _load_weather_data(_bucket):
    response = _fetch_weather_response()
    hourly_df = _build_hourly_dataframe(response)
    daily_df = _build_daily_dataframe(response)
    return hourly_df, daily_df


def _get_weather_data():
    hourly_df, daily_df = _load_weather_data(_cache_bucket())
    return hourly_df.copy(), daily_df.copy()


def _now_local():
    return datetime.now(pytz.timezone(TIMEZONE))


def _now_utc():
    return _now_local().astimezone(pytz.UTC)


def get_current_weather(hourly_df=None):
    if hourly_df is None:
        hourly_df, _ = _get_weather_data()

    now_utc = _now_utc()
    filtered = hourly_df[hourly_df["date"] <= now_utc]
    if filtered.empty:
        return None
    return filtered.iloc[-1]["weather_description"]


def is_within_one_hour_of_sunset(daily_df):
    now = _now_local()
    today_row = daily_df[daily_df["date"].dt.date == now.date()]
    if today_row.empty:
        return False
    sunset_time = today_row.iloc[0]["sunset_time"]
    diff = abs(now - sunset_time)
    return diff <= timedelta(hours=1)


def is_within_one_hour_of_sunrise(daily_df):
    now = _now_local()
    today_row = daily_df[daily_df["date"].dt.date == now.date()]
    if today_row.empty:
        return False
    sunrise_time = today_row.iloc[0]["sunrise_time"]
    diff = abs(now - sunrise_time)
    return diff <= timedelta(hours=1)


# Define time-of-day cutoffs
morning_start = time(6, 0, 0)
morning_cutoff = time(12, 0, 0)
afternoon_cutoff = time(16, 0, 0)
evening_cutoff = time(20, 0, 0)


def get_current_time_of_day():
    _, daily_df = _get_weather_data()
    now = _now_local().time()

    if is_within_one_hour_of_sunrise(daily_df):
        return "Sunrise"
    if is_within_one_hour_of_sunset(daily_df):
        return "Sunset"
    if now < morning_start:
        return "Night"
    if now < morning_cutoff:
        return "Morning"
    if now < afternoon_cutoff:
        return "Afternoon"
    if now < evening_cutoff:
        return "Evening"
    return "Night"


def get_weather_state():
    hourly_df, _ = _get_weather_data()
    return {
        "current_weather": get_current_weather(hourly_df),
        "current_time": get_current_time_of_day(),
    }


def _category_from_code(code):
    for category, codes in WEATHER_CATEGORY_MAP.items():
        if int(code) in codes:
            return category
    return "clear"


def _get_today_row(daily_df, now):
    today_row = daily_df[daily_df["date"].dt.date == now.date()]
    if today_row.empty:
        return daily_df.iloc[[0]]
    return today_row


def get_clean_weather():
    hourly_df, daily_df = _get_weather_data()
    now_local = _now_local()
    now_utc = now_local.astimezone(pytz.UTC)

    filtered = hourly_df[hourly_df["date"] <= now_utc]
    if filtered.empty:
        raise ValueError("No hourly weather data available")

    current_row = filtered.iloc[-1]
    code = int(current_row["weather_code"])
    temperature = float(current_row["temperature"])

    today_row = _get_today_row(daily_df, now_local)
    sunrise_time = today_row.iloc[0]["sunrise_time"]
    sunset_time = today_row.iloc[0]["sunset_time"]

    is_day = int(sunrise_time <= now_local <= sunset_time)

    return {
        "date": now_local.date().isoformat(),
        "time": now_local.strftime("%H:%M"),
        "temperature": temperature,
        "condition": WEATHER_CODE_MAP.get(code, "Unknown"),
        "sunrise": sunrise_time.strftime("%H:%M"),
        "sunset": sunset_time.strftime("%H:%M"),
        "is_day": is_day,
        "category": _category_from_code(code),
    }

