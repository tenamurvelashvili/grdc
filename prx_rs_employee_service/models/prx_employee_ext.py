from odoo import models, fields, api
from .prx_rs_enum import EmployeeStatusSelectionList, WorkTypeList


class Employee(models.Model):
    _inherit = 'hr.employee'

    rs_employee_id = fields.Integer('RS Employee ID', groups="hr.group_hr_user")
    rs_employee_status = fields.Selection(EmployeeStatusSelectionList.selection(), groups="hr.group_hr_user")
    work_type = fields.Selection(WorkTypeList.selection(), string='Work Type', groups="hr.group_hr_user")
    have_running_contract = fields.Boolean(compute='_compute_have_running_contract')

    @api.depends('contract_ids')
    def _compute_have_running_contract(self):
        for rec in self:
            rec.have_running_contract = bool(rec.contract_ids.filtered(lambda c: c.state == 'open'))

    def open_employee_wizards(self):
        action = self.env.ref('prx_rs_employee_service.action_prx_rs_employee_editable_wizard').read()[0]
        return action

class Contract(models.Model):
    _inherit = 'hr.contract'
    work_type = fields.Selection(WorkTypeList.selection(), string='Work Type')

    def write(self, vals):
        res = super().write(vals)
        if 'work_type' in vals:
            self.employee_id.write({'work_type': vals['work_type']})
        return res
