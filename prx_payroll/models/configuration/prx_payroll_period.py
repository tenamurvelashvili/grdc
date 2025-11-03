from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PRXPayrollPeriod(models.Model):
    _name = 'prx.payroll.period'
    _description = 'Period of payroll module'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    period = fields.Char(string='პერიოდი', required=True)
    start_date = fields.Date(string='საწყისი თარიღი', required=True)
    end_date = fields.Date(string='საბოლოო თარიღი', required=True)
    payment_date = fields.Date(string='გადახდის თარიღი', required=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.period)

    @api.constrains('period', 'start_date', 'end_date')
    def _check_date_overlap(self):
        for record in self:
            if not record.start_date or not record.end_date:
                continue

            if record.start_date > record.end_date:
                raise ValidationError('საწყისი თარიღი არ უნდა იყოს საბოლოო თარიღზე მეტი.')

            overlapping_period = self.search([
                ('id', '!=', record.id),
                ('start_date', '<=', record.end_date),
                ('end_date', '>=', record.start_date),
            ], limit=1)

            unique_period = self.search([
                ('id', '!=', record.id),
                ('period', '=', record.period)
            ], limit=1)

            if unique_period:
                raise ValidationError(f"{record.period} ამ პერიოდზე ჩანაწერი უკვე არსებობს")

            if overlapping_period:
                raise ValidationError("მითითებულ თარიღებში ჩანაწერი უკვე არსებობს, გთხოვთ გადაამოწმოთ")

    def generate_period(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Period',
            'res_model': 'prx.payroll.period.year',
            'view_mode': 'form',
            'target': 'new',
        }