from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class PayrollEarningAccountLine(models.Model):
    _name = 'prx.payroll.earning.account.line'
    _description = 'Payroll Earning Account Line'
    _check_company_auto = True

    earning_id = fields.Many2one('prx.payroll.earning', string='Earning', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    account_id = fields.Many2one('account.account', string='Account')
    exact_account = fields.Text(string='Exact Account')
    take_account_from_position = fields.Boolean(string='Take Account from Position')
    debit_percent = fields.Float(string='Debit %', default=100.0)
    credit_percent = fields.Float(string='Credit %', default=0.0)
    analytic_plan_id = fields.Many2one('account.analytic.plan', string='Analytic Plan')

    @api.constrains('account_id', 'take_account_from_position')
    def _check_account_source(self):
        for line in self:
            if not line.take_account_from_position and not line.account_id:
                raise ValidationError(_('Account is required unless "Take Account from Position" is checked.'))

    @api.constrains('debit_percent', 'credit_percent')
    def _check_percentages(self):
        for line in self:
            debit = line.debit_percent or 0.0
            credit = line.credit_percent or 0.0
            if abs(debit) < 1e-9 and abs(credit) < 1e-9:
                raise ValidationError(_('Debit % and Credit % cannot both be zero.'))

    def _get_posting_account(self, position, transaction=None):
        self.ensure_one()
        position_account = position.account_id if position else False
        if self.take_account_from_position:
            if position_account:
                return position_account
            if self.account_id:
                return self.account_id
        return self.account_id

    def prepare_move_line_vals(self, transaction):
        self.ensure_one()
        account = self._get_posting_account(transaction.position_id, transaction=transaction)
        if not account:
            position_name = transaction.position_id.display_name if transaction.position_id else _('(no position)')
            employee_name = transaction.employee_id.display_name if transaction.employee_id else _('(no employee)')
            raise UserError(_(
                'No account configured for line %(line)s. Position %(position)s for employee %(employee)s has no payroll account and no fallback account on the line.'
            ) % {
                                'line': self.display_name,
                                'position': position_name,
                                'employee': employee_name,
                            })

        partner = transaction.employee_id.work_contact_id if transaction.employee_id else False

        amount = transaction.amount or 0.0
        debit_amount = amount * (self.debit_percent or 0.0) / 100.0
        credit_amount = amount * (self.credit_percent or 0.0) / 100.0

        debit = 0.0
        credit = 0.0

        if debit_amount >= 0:
            debit += debit_amount
        else:
            credit -= debit_amount

        if credit_amount >= 0:
            credit += credit_amount
        else:
            debit -= credit_amount

        if abs(debit) < 1e-9 and abs(credit) < 1e-9:
            return False

        analytic_distribution = False
        if self.analytic_plan_id:
            analytic_distribution = transaction._get_analytic_distribution_for_plan(self.analytic_plan_id)

        return {
            'account_id': account.id,
            'partner_id': partner.id if partner else False,
            'debit': debit,
            'credit': credit,
            'analytic_distribution': analytic_distribution,
        }
