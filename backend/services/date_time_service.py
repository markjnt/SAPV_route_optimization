from datetime import datetime, timedelta

class DateTimeService:
    @staticmethod
    def get_date_from_week(week_number: int, weekday_name: str, year: int = None) -> datetime:
        weekdays = {
            'Montag': 0,
            'Dienstag': 1,
            'Mittwoch': 2,
            'Donnerstag': 3,
            'Freitag': 4,
            'Samstag': 5,
            'Sonntag': 6
        }
        
        if year is None:
            year = datetime.now().year
        
        first_day = datetime(year, 1, 1)
        
        while first_day.strftime('%W') == '00':
            first_day += timedelta(days=1)
        
        target_monday = first_day + timedelta(weeks=week_number-1)
        target_date = target_monday + timedelta(days=weekdays[weekday_name])
        
        return target_date

    @staticmethod
    def get_start_time(weekday_name: str, week_number: int = None) -> str:
        if week_number is None:
            current_date = datetime.utcnow()
            week_number = int(current_date.strftime('%W'))
        
        target_date = DateTimeService.get_date_from_week(week_number, weekday_name)
        start_time = datetime(target_date.year, target_date.month, target_date.day, 8, 0, 0)
        return start_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    @staticmethod
    def get_end_time(weekday_name: str, week_number: int = None) -> str:
        if week_number is None:
            current_date = datetime.utcnow()
            week_number = int(current_date.strftime('%W'))
        
        target_date = DateTimeService.get_date_from_week(week_number, weekday_name)
        end_time = datetime(target_date.year, target_date.month, target_date.day, 16, 0, 0)
        return end_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z" 