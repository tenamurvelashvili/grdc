from odoo import api, fields, models

class PRXTimeOffCode(models.Model):
    _name = 'prx.time.off.code'
    _description = 'პირობითი აღნიშვნები'
    _rec_name = 'name'

    code = fields.Char(string='კოდი', required=True)
    name = fields.Char(string='აღწერა', required=True)