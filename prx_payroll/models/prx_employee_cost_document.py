from odoo import fields, models, api
from odoo.exceptions import ValidationError


class PrxEmployeeCostDocument(models.Model):
	_name = 'prx_payroll.employee.cost.document'
	_description = 'Employee Cost Document'

	@api.constrains('lines')
	def _check_lines_rate_total(self):
		for record in self:
			total_rate = sum(record.lines.mapped('rate'))
			if not 0.9999 <= total_rate <= 1.0001:  # Allow for minor floating-point inaccuracies
				raise ValidationError('The total rate of lines must equal 100% for each Employee Cost Document.')

	name = fields.Char(compute='_compute_name', store=True)

	@api.depends('employee_id', 'cost_center')
	def _compute_name(self):
		for record in self:
			record.name = f"{record.employee_id.display_name or ''} - {record.cost_center.display_name or ''}"

	employee_id = fields.Many2one('hr.employee', string='Employee')
	cost_center = fields.Many2one('prx_payroll.cost_center', string='Cost Center')
	lines = fields.One2many('prx_payroll.employee.cost.document.line', 'employee_cost_document_id', string='Lines',
	                        ondelete="cascade")
	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)

	_sql_constraints = [
		('employee_cost_center_unique', 'unique (employee_id, cost_center)',
		 'An Employee Cost Document for this employee and cost center already exists!')
	]


class PrxEmployeeCostDocumentLine(models.Model):
	_name = 'prx_payroll.employee.cost.document.line'
	_description = 'Employee Cost Document Line'

	name = fields.Char(compute='_compute_name', store=True, readonly=True)

	employee_cost_document_id = fields.Many2one('prx_payroll.employee.cost.document', string='Employee Cost Document')
	cost_unit_id = fields.Many2one('prx_payroll.cost_unit', string='დანახარჯთა ერთეული')
	rate = fields.Float(string='კოეფიციენტი', required=True, default=0.0,
	                    digits=(5, 4), domain="[('rate', '>', 0), ('rate', '<=', 1)]")
	ref_employee_id = fields.Many2one(related='employee_cost_document_id.employee_id', string='თანამშრომელი')
	ref_cost_center_id = fields.Many2one(related='employee_cost_document_id.cost_center', string='დანახარჯთა ცენტრი')
	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)

	@api.depends('cost_unit_id', 'rate')
	def _compute_name(self):
		for record in self:
			record.name = f"{record.id}"
