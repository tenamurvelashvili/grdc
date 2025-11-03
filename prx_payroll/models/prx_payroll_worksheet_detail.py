from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class PRXPayrollWorksheetDetail(models.Model):
    _name = 'prx.payroll.worksheet.detail'
    _description = 'Payroll worksheet detail'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    worksheet_id = fields.Many2one('prx.payroll.worksheet',ondelete="cascade",string="ტაბელი")
    employee_id = fields.Many2one('hr.employee',related="worksheet_id.worker_id",string="თანამშრომელი")
    period_id = fields.Many2one('prx.payroll.period',related="worksheet_id.period_id",string="პერიოდი")
    position = fields.Char(string='პოზიცია')
    earning_id = fields.Many2one('prx.payroll.position.earning',string='ანაზღაურება')
    earning_amount = fields.Float(string='ანაზღაურების თანხა',digits=(19, 2))
    rate = fields.Float(string='განაკვეთი',digits=(19, 2))
    amount = fields.Float(string='თანხა',digits=(19, 2))
    quantity = fields.Float(string='რაოდენობა',digits=(19, 2))
    date = fields.Date(string='თარიღი')
    proportion = fields.Float(compute='_compute_proportion',string='პროპორცია',digits=(19, 10))

    payroll_admin = fields.Boolean(compute="_is_payroll_admin")
    def _is_payroll_admin(self):
        self.payroll_admin = bool(self.env.user.has_group('prx_payroll.prx_payroll_administrator'))

    @api.depends('amount','earning_amount')
    def _compute_proportion(self):
        for rec in self:
            try:
                rec.proportion = rec.amount / sum(self.search([('worksheet_id','=',rec.worksheet_id.id)]).mapped('amount'))
            except ZeroDivisionError:
                rec.proportion = 0

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.position)

