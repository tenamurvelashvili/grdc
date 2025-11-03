from odoo import fields, models, api
from odoo.exceptions import ValidationError


class PRXPayrollWorksheetCostLine(models.Model):
	_name = 'prx_payroll.worksheet.cost.line'
	_description = 'Payroll Worksheet Cost Line'
	_check_company_auto = True

	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
	worksheet_id = fields.Many2one('prx.payroll.worksheet', ondelete="cascade", string="ტაბელი")
	ref_employee_id = fields.Many2one(related='worksheet_id.worker_id')
	cost_document_line_id = fields.Many2one(comodel_name='prx_payroll.employee.cost.document.line')
	document_id = fields.Many2one(comodel_name='prx_payroll.employee.cost.document',
	                              domain="[('employee_id', '=', ref_employee_id)]")
	cost_unit_id = fields.Many2one(comodel_name='prx_payroll.cost_unit', string='დანახარჯთა ერთეული')
	cost_center_id = fields.Many2one(related='cost_unit_id.cost_center', store=True)
	rate = fields.Float(string='კოეფიციენტი', required=True, default=0.0,
	                    digits=(5, 4), domain="[('rate', '>', 0), ('rate', '<=', 1)]")
	is_init_record = fields.Boolean(default=False)
	marked_as_deleted = fields.Boolean(default=False)