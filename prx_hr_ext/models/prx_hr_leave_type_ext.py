from odoo import api, fields, models

class HolidaysType(models.Model):
    _inherit = "hr.leave.type"

    prx_time_off_code_id = fields.Many2one(
        'prx.time.off.code',
        string='Holidays Type',
        required=True,
    )