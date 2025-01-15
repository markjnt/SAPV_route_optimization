from flask import session

class SessionService:
    @staticmethod
    def get_selected_weekday():
        """Gibt den ausgewählten Wochentag zurück"""
        return session.get('selected_weekday', 'Montag')

    @staticmethod
    def set_selected_weekday(weekday):
        """Setzt den ausgewählten Wochentag"""
        if 'selected_weekday' not in session:
            session['selected_weekday'] = 'Montag'
        else:
            session['selected_weekday'] = weekday

    @staticmethod
    def get_selected_week():
        """Gibt die ausgewählte Kalenderwoche zurück"""
        return session.get('selected_week')

    @staticmethod
    def set_selected_week(week):
        """Setzt die ausgewählte Kalenderwoche"""
        session['selected_week'] = week 