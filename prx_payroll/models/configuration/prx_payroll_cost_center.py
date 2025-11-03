from odoo import fields, models, api


class PrxCostCenter(models.Model):
	_name = 'prx_payroll.cost_center'
	_description = 'Payroll Cost Center'

	name = fields.Char(string="დანახარჯთა ცენტრი", required=True)
	sequence = fields.Integer(string="რიგით ნომერი რეპორტისთვის")
	fullname = fields.Char(compute="_compute_full_name", store=True, string="დასახელება")
	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)

	@api.depends('name', 'sequence')
	def _compute_full_name(self):
		for record in self:
			record.fullname = f"{record.sequence}. {record.name}"
