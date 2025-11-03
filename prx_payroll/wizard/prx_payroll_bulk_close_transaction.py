from odoo import models, fields, api
from ..models.configuration.prx_enum_selection import SalaryType
class PRXPayrollCloseTransactionWizard(models.TransientModel):
    _name = 'prx.payroll.close.transaction'
    _description = 'Bulk Close Transaction'

    period = fields.Many2one('prx.payroll.period')
    process_type = fields.Selection(SalaryType.selection()+[('all','ყველა')], string='პროცესის ტიპი',default='all',required=True)
    worksheet_id = fields.Many2one('prx.payroll.worksheet',string='ტაბელი')

    def action_close_transactions(self):
        transaction = self.env['prx.payroll.transaction']
        worksheet = self.env['prx.payroll.worksheet']

        base_domain = [
            ('period_id', '=', self.period.id),
            ('transferred', '=', False),
        ]
        if self.process_type != 'all':
            base_domain += [('worksheet_id.salary_type','=',self.process_type)]

        if self.worksheet_id:
            base_domain += [('worksheet_id','=',self.worksheet_id.id)]

        groups = transaction.read_group(
            domain=base_domain,
            fields=['amount:sum'],
            groupby=['worksheet_id'],
            lazy=False,
        )

        vals = []
        for g in groups:
            ws_info = g.get('worksheet_id')
            if not ws_info:
                continue
            ws_id = ws_info[0]
            total = g.get('amount')

            txs_ws = transaction.search(base_domain + [('worksheet_id', '=', ws_id)])
            if not txs_ws:
                continue

            # თუ ნოლის ტოლია ან ნაკლებია
            if abs(total) < 1e-9:
                continue

            ws = worksheet.browse(ws_id)
            closing_amount = -total

            vals.append({
                'company_id': ws.company_id.id,
                'worksheet_id': ws.id,
                'employee_id': ws.worker_id.id,
                'period_id': ws.period_id.id,
                'amount': closing_amount,
                'transaction_type': 'transfer',
                'transferred':True,
                'position_id': ws.worker_id.job_id.id if ws.worker_id and ws.worker_id.job_id else False,
                'organization_unit_id': ws.worker_id.department_id.id if ws.worker_id and ws.worker_id.department_id else False,
                'start_date': ws.period_id.start_date or False,
                'end_date': ws.period_id.end_date or False,
            })

            txs_ws.write({'transferred': True})
            txs_ws.mapped('worksheet_id').write({'transferred':True})
        if vals:
            transaction.create(vals)

        return {'type': 'ir.actions.act_window_close'}
