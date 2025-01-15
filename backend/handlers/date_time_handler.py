from backend.services.date_time_service import DateTimeService
from backend.models import patients, vehicles

date_time_service = DateTimeService()

def get_date_from_week(week_number, weekday_name, year=None):
    return date_time_service.get_date_from_week(week_number, weekday_name, year)

def get_start_time(weekday_name, week_number=None):
    return date_time_service.get_start_time(weekday_name, week_number)

def get_end_time(weekday_name, week_number=None):
    return date_time_service.get_end_time(weekday_name, week_number) 