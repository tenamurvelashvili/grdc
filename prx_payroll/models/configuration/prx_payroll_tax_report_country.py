from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError

class PRXPayrollTaxReportCountry(models.Model):
    _name = 'prx.payroll.tax.report.country'
    _description = 'Payroll tax report country'

    code = fields.Char(string = 'კოდი',required=True)
    country = fields.Char(string = 'ქვეყნის დასახელება',translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Code must be unique!')
    ]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.country)
