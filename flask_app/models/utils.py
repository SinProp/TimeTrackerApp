# utils.py
from datetime import datetime
import pytz

dateFormat = "%m/%d/%Y %I:%M %p"


def to_eastern(time_value):
    utc_time = pytz.utc.localize(time_value)
    eastern = pytz.timezone('America/New_York')
    return utc_time.astimezone(eastern)


def format_datetime_eastern(datetime_obj):
    return to_eastern(datetime_obj).strftime(dateFormat)
