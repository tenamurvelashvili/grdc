from odoo import models, fields, api
from odoo.exceptions import UserError

class PRXRSEmployeeWizard(models.TransientModel):
    _name = 'prx.rs.employee.wizard'
    _description = 'PRX RS Employee Wizard'

    import_type = fields.Selection(
        [
            ('tin', 'თანამშრომლის საიდენტიფიკაციო'),
            ('full', 'სრული ინფორმაცია')
        ],
        string="იმპორტის ტიპი",
        required=True,
        default='tin',
    )
    tin = fields.Char(string='თანამშრიმლის საიდენტიფიკაციო ნომერი')

    def action_run_import_rs_employees(self):
        if self.import_type == 'tin':
            self.env['prx.rs.service.employee'].create_rs_employee(self.tin)
        elif self.import_type == 'full':
            self.env['prx.rs.service.employee'].create_rs_employee()