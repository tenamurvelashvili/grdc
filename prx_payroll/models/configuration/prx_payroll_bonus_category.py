from odoo import api, fields, models

class PRXPayrollBonusCategory(models.Model):
    _name = "prx.payroll.bonus.category"
    _description = "Payroll Bonus Category"
    _rec_name = "name"

    name = fields.Char(
        string="დასახელება",
        required=True,
        translate=True,
    )
    description = fields.Text(
        string="აღწერა",
        translate=True,
    )
