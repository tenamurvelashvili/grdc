from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    managed_employee_ids = fields.Many2many(
        'hr.employee',
        'res_users_managed_employee_rel',
        'user_id',
        'employee_id',
        string='Managed Employees'
    )

