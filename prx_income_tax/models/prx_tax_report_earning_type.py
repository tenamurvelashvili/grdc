from odoo import models, fields, api

class PRXTaxReportEarningType(models.Model):
    _name = 'prx.tax.report.earning.type'
    _description = 'Tax report earning type'
    _rec_name = 'description'

    code = fields.Char(string = 'კოდი',required=True)
    description = fields.Char(string = 'განაცემის სახე',translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Code must be unique!')
    ]
