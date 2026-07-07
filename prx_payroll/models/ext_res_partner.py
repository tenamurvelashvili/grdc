from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    exact_crdnr_code = fields.Char(
        string='Exact Credit Number',
        help='Exact creditor number (crdnr) used when exporting payroll deductions to Exact.',
    )
