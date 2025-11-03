from odoo import models, fields,api

class PRXPayrollTodoNote(models.Model):
    _name = 'prx.payroll.todo.note'
    _description = 'Payroll Note'

    name = fields.Char(required=True)
    note = fields.Html(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
