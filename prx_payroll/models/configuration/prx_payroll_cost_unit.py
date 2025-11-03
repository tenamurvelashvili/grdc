from odoo import fields, models, api


class PrxCostUnit(models.Model):
	_name = 'prx_payroll.cost_unit'
	_description = 'Payroll Cost Unit'

	name = fields.Char(string='დანახარჯთა ერთეული')
	sequence = fields.Integer(string='რიგითი ნომერი რეპორტისთვის')
	cost_center = fields.Many2one(comodel_name='prx_payroll.cost_center', string='დანახარჯთა ცენტრი')
	fullname = fields.Char(string='დასახელება', compute='_compute_full_name', store=True)
	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)

	@api.depends('sequence', 'name')
	def _compute_full_name(self):
		for record in self:
			record.fullname = f"{record.sequence}. {record.name}"
