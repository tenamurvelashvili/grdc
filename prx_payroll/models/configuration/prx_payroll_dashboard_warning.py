#-*- coding:utf-8 -*-

from odoo import fields, models,api
from odoo.tools.safe_eval import safe_eval, datetime as safe_eval_datetime, dateutil as safe_eval_dateutil
from odoo.exceptions import UserError

class PRXPayrollDashboardWarning(models.Model):
    _name = 'prx.payroll.dashboard.warning'
    _description = 'Payroll Dashboard Warning'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)])
    evaluation_code = fields.Text(string='Python Code',
        default='''
        # Available variables:
        #----------------------
        #  - warning_count: Number of warnings.
        #  - warning_records: Records containing warnings.
        #  - warning_action: Action to perform in response to warnings.
        #  - additional_context: Additional context to include with the action.'''
    )
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Warning Color', help='Tag color. No color means black.')

    # Payroll Dashboard
    @api.model
    def _dashboard_default_action(self, name, res_model, res_ids, additional_context=None):
        if additional_context is None:
            additional_context = {}
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'context': {**self.env.context, **additional_context},
            'domain': [('id', 'in', res_ids)],
            'views': [[False, 'list'], [False, 'kanban'], [False, 'form']],
            'view_mode': 'list,kanban,form',
        }

    @api.model
    def get_dashboard_warnings(self):
        # self.env['prx.payroll.dashboard.warning'].sudo().unlink()
        result = []
        for warning in self.search([]):
            localdict = {
                'date': safe_eval_datetime.date,
                'datetime': safe_eval_datetime.datetime,
                'relativedelta': safe_eval_dateutil.relativedelta.relativedelta,
                'warning_count': 0,
                'warning_records': self.env['base'],
                'warning_action': False,
                'additional_context': {},
            }
            globaldict = {'self': self}

            try:
                safe_eval(warning.evaluation_code, locals_dict=localdict, globals_dict=globaldict, mode='exec',nocopy=True)
            except Exception as e:
                raise UserError(
                    f"Wrong warning computation code defined for:\n- Warning: {warning.name}\n- Error: {e}")

            if localdict['warning_count']:
                result.append({
                    'string': warning.name,
                    'color': warning.color,
                    'count': localdict['warning_count'],
                    'action': localdict['warning_action'] or self._dashboard_default_action(
                        warning.name,
                        localdict['warning_records']._name,
                        localdict['warning_records'].ids,
                        additional_context=localdict['additional_context'],
                    ),
                })
        return result


