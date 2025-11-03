from odoo import models, fields, api
from datetime import date
from calendar import monthrange
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

class PRXPayrollPeriodYear(models.TransientModel):
    _name = 'prx.payroll.period.year'
    _description = 'Period of payroll year'

    year = fields.Integer(string='აირჩიე წელი')

    def generate_period_with_year(self):
        if not self.year:
            raise UserError("შეიყვანე წელის მნიშვნელობა!")

        selected_year = self.year
        period_obj = self.env['prx.payroll.period']
        existing_date_validate = []

        for month in range(1, 13):
            start_day = date(selected_year, month, 1)
            last_day = monthrange(selected_year, month)[1]
            end_day = date(selected_year, month, last_day)
            payment_date = start_day + relativedelta(months=1)

            overlapping_period = period_obj.search([
                ('company_id', '=', self.env.company.id),
                ('start_date', '<=', start_day),
                ('end_date', '>=', end_day),
            ], limit=1)

            if overlapping_period:
                existing_date_validate.append(f"{selected_year}-{month}")
            else:
                period_obj.create({
                    'company_id': self.env.company.id,
                    'period': f"{selected_year}-{month}",
                    'start_date': start_day,
                    'end_date': end_day,
                    'payment_date': payment_date,
                })
        self.env.cr.commit()
        if existing_date_validate:
            months_str = ", ".join(str(m) for m in existing_date_validate)
            raise UserError(f"პერიოდზე: {months_str} ჩანაწერი უკვე არსებობს .")