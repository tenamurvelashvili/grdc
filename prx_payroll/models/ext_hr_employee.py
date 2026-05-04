from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    creditor_id = fields.Many2one(
        'prx.exact.creditor',
        string='Exact Creditor',
        ondelete='set null',
    )
