from odoo import models, fields, _
from odoo.tools import float_round


class PayrollTransactionReport(models.AbstractModel):
    _name = "prx.payroll.transaction.report"
    # _inherit = "account.report"
    _description = "Payroll Transaction Report"

    filter_date = {'mode': 'range', 'filter': 'this_month'}

    def _get_columns_name(self, options):
        return [
            {'name': _("Employee")},
            {'name': _("Transaction Date")},
            {'name': _("Description")},
            {'name': _("Amount"), 'class': 'number'},
        ]

    def _get_lines(self, options, line_id=None):
        lines = []
        date_from = options.get('date', {}).get('date_from')
        date_to = options.get('date', {}).get('date_to')

        domain = []
        if date_from:
            domain.append(('transaction_date', '>=', date_from))
        if date_to:
            domain.append(('transaction_date', '<=', date_to))

        transactions = self.env['prx.payroll.transaction'].search(domain, order="transaction_date")

        total_amount = 0.0

        for tx in transactions:
            lines.append({
                'id': tx.id,
                'name': tx.employee_id.name,
                'columns': [
                    {'name': tx.transaction_date},
                    {'name': tx.description or ''},
                    {'name': float_round(tx.amount, 2)},
                ],
                'level': 2,
            })
            total_amount += tx.amount

        # Add total line
        lines.append({
            'id': 'total',
            'name': _('Total'),
            'columns': [
                {'name': ''},
                {'name': ''},
                {'name': float_round(total_amount, 2)},
            ],
            'class': 'o_account_report_total',
            'level': 1,
        })

        return lines
