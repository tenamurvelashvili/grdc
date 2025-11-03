from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError

class PRXPayrollTaxReportEarningType(models.Model):
    _name = 'prx.payroll.tax.report.earning.type'
    _description = 'Payroll tax report earning type'
    _rec_name = 'description'

    code = fields.Char(string = 'კოდი',required=True)
    description = fields.Char(string = 'განაცემის სახე',translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Code must be unique!')
    ]
