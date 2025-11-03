from odoo import api, fields, models
from ..models.prx_rs_enum import EmployeeStatusSelectionList, GenderList,Gender, WorkTypeList,EmployeeStatus
import logging

_logger = logging.getLogger(__name__)

class PRXRSEmployeeWizard(models.TransientModel):
    _name = 'prx.rs.employee.editable.wizard'
    _description = 'PRX RS Employee Wizard'

    employee_id = fields.Many2one('hr.employee',string='Employee',)
    rs_employee_id = fields.Integer(related="employee_id.rs_employee_id",string='RS Employee ID')
    is_foreigner = fields.Boolean(string='Is Foreigner')
    exit_contract = fields.Boolean(string='Exit Contract',)
    identification_id = fields.Char(string='TIN')
    name = fields.Char(string='Full Name')
    gender = fields.Selection(selection=GenderList.selection(),string='Gender')
    tax_country = fields.Many2one('prx.tax.report.country',string='Citizen Country')
    status = fields.Selection(selection=EmployeeStatusSelectionList.selection(),string='Status')
    private_phone = fields.Char(string='Phone')
    work_type = fields.Selection(selection=WorkTypeList.selection(),string='Work Type')
    birthday = fields.Date(string='Birth Date')

    def save_in_rs_employee(self):
        self.env['prx.rs.employee.integration']._create_employee(
            employee_id=self.employee_id,
            status=self.status,
        )
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields):
        result = super(PRXRSEmployeeWizard, self).default_get(fields)
        if self.env.context.get('active_id'):
            employee = self.env['hr.employee'].browse(self.env.context.get('active_id'))
            exit_contract: bool = self.env['hr.contract'].sudo().search(
                [('state', '=', 'open'), ('employee_id', '=', employee.id)]).exists()
            result.update({
                'is_foreigner': bool(employee.tax_country.code !='268'),
                'employee_id': employee.id,
                'name': employee.name,
                'gender': str(Gender.selection()[employee.gender]) if employee.gender and employee.gender in ['male','female'] else None,
                'tax_country': employee.tax_country.id,
                'birthday': employee.birthday,
                'private_phone': employee.private_phone,
                'identification_id': employee.identification_id,
                'status': str(EmployeeStatus.selection()['active']) if not employee.rs_employee_id else
                str(EmployeeStatus.selection()['active']) if exit_contract else str(EmployeeStatus.selection()['suspended']),
                'work_type': employee.work_type,
                'exit_contract': exit_contract,
            })
        return result

