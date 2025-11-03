from odoo import api, fields, models, _

class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    @api.model
    def _float_to_hhmm(self, dec_hours):
        hours = int(dec_hours)
        minutes = int(round((dec_hours - hours) * 60))
        return f"{hours}:{minutes:02d}"

    @api.model
    def get_workday_hours(self, calendar, check_date):
        if isinstance(check_date, str):
            check_date = fields.Date.from_string(check_date)
        wd = str(check_date.weekday())
        parity = str(self.get_week_type(check_date))

        lines = self.search([
            ('calendar_id', '=', calendar.id),
            ('dayofweek', '=', wd),
            '|', ('date_from', '=', False), ('date_from', '<=', check_date),
            '|', ('date_to', '=', False), ('date_to', '>=', check_date),
        ])
        if calendar.two_weeks_calendar:
            lines = lines.filtered(lambda l: l.week_type == parity)
        lines = lines.filtered(lambda l: l.day_period != 'lunch')
        total_hours = sum(lines.mapped('duration_hours'))
        return self._float_to_hhmm(total_hours)