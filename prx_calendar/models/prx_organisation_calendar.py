from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from .selection import CalendarStatus, CalendarWeekdayGeo, CalendarMonthGeo
from datetime import date, timedelta
import operator


class PRXOrganisationCalendar(models.Model):
    _name = 'prx.organisation.calendar'
    _description = 'Organisation Calendar'
    _rec_name = 'year'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    year = fields.Integer(string="წელი", required=True)
    schedule_type_id = fields.Many2one('resource.calendar', string='გრაფიკის ტიპი', required=True,
                                       domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    calendar_details_id = fields.One2many('prx.organisation.calendar.details', string='დეტალები',
                                          inverse_name='calendar_id')

    def action_view_worksheet_earning(self):
        action = self.env.ref('prx_calendar.prx_organisation_calendar_details').read()[0]
        action['domain'] = [('calendar_id', '=', self.id)]
        return action

    @api.constrains('year', 'schedule_type_id')
    def _check_unique_calendar(self):
        duplicate = self.search([
            ('year', '=', self.year),
            ('schedule_type_id', '=', self.schedule_type_id.id),
            ('id', '!=', self.id)
        ])
        if duplicate:
            raise ValidationError("ეს კალენდარი უკვე არსებობს .")

    def generate_calendar_details(self):
        self.ensure_one()
        if self.calendar_details_id:
            raise ValidationError("ეს კალენდარი უკვე არსებობს .")

        start_date = date(self.year, 1, 1)
        end_date = date(self.year, 12, 31)
        delta = timedelta(days=1)
        day = start_date
        public_holidays = self.env['resource.calendar.leaves'].search([
            ('holiday_id', '=', False),
            ('time_type', '=', 'leave'),
            ('date_from', '<=', end_date),
            ('date_to', '>=', start_date),
            '|',
            ('calendar_id', '=', self.schedule_type_id.id),
            ('calendar_id', '=', False),
        ])

        holidays_set = set()
        for leave in public_holidays:
            current = leave.date_from.date()
            while current <= leave.date_to.date():
                holidays_set.add(current)
                current += timedelta(days=1)
        attendances = self.schedule_type_id.attendance_ids.mapped('dayofweek')  # კვირრის დღეები
        workdays = set(int(d) for d in attendances)
        CalendarStatus = {
            True: 'open',
            False: 'closed'
        }

        records = []
        while day <= end_date:
            is_workday = day.weekday() in workdays
            is_holiday = day in holidays_set
            status = CalendarStatus[is_workday]
            records.append((0, 0, {
                'date': day,
                'status': status if not self.schedule_type_id.flexible_hours else 'open',
                'holiday': is_holiday if not self.schedule_type_id.flexible_hours else False,
                'weekday': CalendarWeekdayGeo[day.strftime('%A').lower()].value[1],
                'weeknumber': day.isocalendar()[1],
                'month': CalendarMonthGeo[day.strftime('%B').lower()].value[1],
                'year': day.year,
                'work_calendar': self.schedule_type_id.name,
            }))
            day += delta
        self.write({'calendar_details_id': records})

    def is_working_day(self, check_date, resource):
        """აბრუნებს არის თუ არა სამუშაო დღე"""
        calendar = self.env['prx.organisation.calendar'].search([
            ('schedule_type_id', '=', resource.id),('year', '=', check_date.year)
        ])
        if len(calendar) > 1:
            return 'Something wrong!'
        if not calendar:
            return 'Detail records not found!'
        detail = calendar.calendar_details_id.filtered(lambda d: d.date == check_date)
        if detail and detail.status == 'open' and not detail.holiday:
            return True
        return False

    def calculate_parameter_work_date(self, from_dt, length_days, resource):
        """გვიბრუნბეს მერამდენე სამუშაო დღე გვინდა length_days პარამეტრით"""
        calendar = self.env['prx.organisation.calendar'].search([
            ('schedule_type_id', '=', resource.id)
        ])
        if len(calendar) > 1:
            return 'Something wrong!'
        if not calendar:
            return 'Detail records not found!'
        get_interest_objects = calendar.calendar_details_id.filtered(
            lambda d: d.date > from_dt and d.status == 'open' and not d.holiday)
        sort_date = get_interest_objects.sorted(key=lambda d: d.date).mapped('date')
        return sort_date[length_days - 1]

    def get_next_working_days(self, check_date, resource, contains=False):
        """გვიბრუნბეს შემდეგ სამუშაო დღეს"""
        calendar = self.env['prx.organisation.calendar'].search([
            ('schedule_type_id', '=', resource.id), ('year', '=', check_date.year)
        ])
        op_fn = operator.ge if contains else operator.gt
        if len(calendar) > 1:
            return None
        if not calendar:
            return None
        get_interest_objects = calendar.calendar_details_id.filtered(
            lambda d: op_fn(d.date, check_date) and d.status == 'open' and not d.holiday)
        sort_date = get_interest_objects.sorted(key=lambda d: d.date).mapped('date')
        if not sort_date:
            return None
        return sort_date[0]

    def get_last_working_days(self, check_date, resource):
        """გვიბრუნებეს წინა  სამუშაო დღეს თუ check_date არ არის სამუშაო დღე"""
        calendar = self.env['prx.organisation.calendar'].search([
            ('schedule_type_id', '=', resource.id), ('year', '=', check_date.year)
        ])
        if len(calendar) > 1:
            return None
        if not calendar:
            return None
        get_interest_objects = calendar.calendar_details_id.search(
            [('date', '<=', check_date),
             ('status', '=', 'open'),
             ('holiday', '=', False)], limit=1, order='date desc')
        return get_interest_objects.date

    def get_length_of_workdays_range(self, start_date, end_date, resource, exclude_start_date=False,
                                     exclude_end_date=False,return_days=False):
        """გვიბრუნებს სამუშაო დღეების რაოდენობა"""
        from_date = start_date + timedelta(days=1) if exclude_start_date else start_date
        to_date = end_date - timedelta(days=1) if exclude_end_date else end_date
        calendar = self.env['prx.organisation.calendar'].search([
            ('schedule_type_id', '=', resource.id)
        ])
        if len(calendar) > 1:
            return 'Something wrong!'
        if not calendar:
            return 'Detail records not found!'
        get_interest_objects = calendar.calendar_details_id.filtered(
            lambda d: from_date <= d.date <= to_date and d.status == 'open' and not d.holiday)
        if return_days:
            return get_interest_objects.mapped('date')
        return len(get_interest_objects)

    def get_day_work_hours(self, dates, resource):
        """
            აბრუნებს dict-ს: {date: სამუშაო საათები}
            - dates: iterable of datetime.date
            - resource: resource.calendar
        """
        if not resource:
            return {}
        # თუ არის მოქნილი გრაფიკი ვაბრუნებ საშუალო რაც არის და სათითაოდ არ ვითვლი საათების რაოდენობას hours_per_day
        if resource.flexible_hours:
            return {d: resource.hours_per_day for d in dates}

        result = {}
        for check_date in dates:
            weekday = check_date.weekday()
            slots = resource.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == weekday and a.day_period != 'lunch'
            )

            if not slots:
                result[check_date] = resource.hours_per_day
                continue

            total = sum(float(s.hour_to - s.hour_from) for s in slots)
            result[check_date] = total or resource.hours_per_day

        return result

class PRXOrganisationCalendarDetails(models.Model):
    _name = 'prx.organisation.calendar.details'
    _description = 'Organisation Calendar Details'
    _rec_name = 'date'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    calendar_id = fields.Many2one('prx.organisation.calendar', ondelete='cascade')
    date = fields.Date('თარიღი')
    status = fields.Selection(CalendarStatus.selection(), string='სტატუსი')
    holiday = fields.Boolean(string='უქმე დღე', default=False)
    weekday = fields.Char(string='კვირის დღე')
    weeknumber = fields.Integer(string='კვირის ნომერი')
    month = fields.Char(string='თვე')

    month_pivot = fields.Selection([
        ('01', 'იანვარი'),
        ('02', 'თებერვალი'),
        ('03', 'მარტი'),
        ('04', 'აპრილი'),
        ('05', 'მაისი'),
        ('06', 'ივნისი'),
        ('07', 'ივლისი'),
        ('08', 'აგვისტო'),
        ('09', 'სექტემბერი'),
        ('10', 'ოქტომბერი'),
        ('11', 'ნოემბერი'),
        ('12', 'დეკემბერი'),
    ], string="თვე (პივოტისთვის)", compute="_compute_month_pivot", store=True)

    @api.depends('month')
    def _compute_month_pivot(self):
        geo_to_code = {
            'იანვარი': '01',
            'თებერვალი': '02',
            'მარტი': '03',
            'აპრილი': '04',
            'მაისი': '05',
            'ივნისი': '06',
            'ივლისი': '07',
            'აგვისტო': '08',
            'სექტემბერი': '09',
            'ოქტომბერი': '10',
            'ნოემბერი': '11',
            'დეკემბერი': '12',
        }
        for rec in self:
            geo_month = (rec.month or '').strip()
            rec.month_pivot = geo_to_code.get(geo_month, False)

    year = fields.Integer(string='წელი')
    work_calendar = fields.Char(string='სამუშაო კალენდარი')
    is_holiday_int = fields.Integer(
        compute="_compute_is_holiday_int",
        store=True,
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.work_calendar)

    @api.depends('holiday')
    def _compute_is_holiday_int(self):
        for rec in self:
            rec.is_holiday_int = 1 if rec.holiday else 0
