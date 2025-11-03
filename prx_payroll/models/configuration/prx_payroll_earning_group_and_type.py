from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError

class PRXPayrollEarningGroup(models.Model):
    _name = 'prx.payroll.earning.group'
    _description = 'Payroll earning group'
    _rec_name = 'group'

    group = fields.Char(string = 'ჯგუფი',translate=True,required=True)


class PRXPayrollEarningType(models.Model):
    _name = 'prx.payroll.earning.type'
    _description = 'Payroll earning type'
    _rec_name = 'type'

    type = fields.Char(string = 'ტიპი',translate=True,required=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.type)

