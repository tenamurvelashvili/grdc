from odoo import api, fields, models
from odoo.exceptions import UserError


class PRXPayrollAmountCalculatorWizard(models.TransientModel):
    _name = 'prx.payroll.amount.calculator.wizard'
    _description = 'Payroll Gross Amount Calculator'

    def _default_net_amount(self):
        return self.env.context.get('default_net_amount', 0.0)

    net_amount = fields.Float(string="ნეტო თანხა", required=True, default=lambda self: self._default_net_amount())
    pension_percent = fields.Float(string="საპენსიო (%)", default=0.98)
    income_tax_percent = fields.Float(string="საშემოსავლო (%)", default=0.8)
    gross_amount = fields.Float(string="გროს თანხა", compute="_compute_gross_amount")

    @api.depends('net_amount', 'pension_percent', 'income_tax_percent')
    def _compute_gross_amount(self):
        for rec in self:
            if rec.pension_percent and rec.income_tax_percent:
                rec.gross_amount = rec.net_amount / rec.pension_percent / rec.income_tax_percent
            else:
                rec.gross_amount = 0.0

    def save_amount(self):
        self.env['prx.payroll.position.earning'].browse(self.env.context.get('active_id')).write(
            {'amount': self.gross_amount}
        )
