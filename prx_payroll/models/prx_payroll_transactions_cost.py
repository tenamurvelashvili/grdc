from odoo import fields, models, tools
from .configuration.prx_enum_selection import TransactionType


class PrxPayrollTransactionCost(models.Model):
	_name = 'prx.payroll.transaction.cost.report'
	_description = 'Payroll Transaction Cost Report'
	_check_company_auto = True
	_auto = False

	company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
	active = fields.Boolean(default=True)
	sequence = fields.Char(string="ნომერი", readonly=True, default='New')
	worksheet_id = fields.Many2one('prx.payroll.worksheet', string="ტაბელი")
	employee_id = fields.Many2one('hr.employee', string="თანამშრომელი")
	period_id = fields.Many2one('prx.payroll.period', string="პერიოდი")
	code = fields.Char(size=255, string="კოდი")
	amount = fields.Float(string="თანხა")
	transaction_type = fields.Selection(TransactionType.selection(),
	                                    string="ტრანზაქციის ტიპი",
	                                    required=True)
	position_id = fields.Many2one('hr.job', string="პოზიცია")
	organization_unit_id = fields.Many2one('hr.department',
	                                       string="ორგანიზაციული ერთეული", )
	earning_id = fields.Many2one('prx.payroll.earning', string="ანაზღაურება",

	                             store=True)
	tax_id = fields.Many2one('prx.payroll.tax', string="გადასახადი")
	employee_tax_id = fields.Many2one('prx.payroll.employee.tax', string="თანამშრომლის გადასახადი")
	deduction_id = fields.Many2one('prx.payroll.deduction', string="დაქვითვა")
	employee_deduction_id = fields.Many2one('prx.payroll.employee.deduction', string="თანამშრომლის დაქვითვა")
	personal_number = fields.Char(size=20, string="პირადი ნომერი",

	                              store=True)
	tax_proportion = fields.Float(digits=(19, 2), string="გადასახადის წილი")
	include_tax_base = fields.Boolean(
		string="გაითვალისწინოს გადასახადის დასაანგარიშებლად")
	start_date = fields.Date(string="დაწყების თარიღი")
	end_date = fields.Date(string="დასრულების თარიღი")
	earning_unit = fields.Char(size=30, string="ანაზღაურების ერთეული")
	qty = fields.Float(digits=(19, 4), string="რაოდენობა")
	rate = fields.Float(digits=(6, 2), string="განაკვეთი")
	position_earning_id = fields.Many2one('prx.payroll.position.earning',
	                                      string="თანამშრიმის ანაზღაურება")
	exchange_rate = fields.Float(digits=(6, 4), string="")
	creditor = fields.Many2one('res.partner', string="კრედიტორი")
	cost_rate = fields.Float(default=0.0,
	                         digits=(5, 4), domain="[('rate', '>', 0), ('rate', '<=', 1)]" , string='განაწილების კოეფიციენტი')
	cost_center_id = fields.Many2one(comodel_name='prx_payroll.cost_center', string='დანახარჯთა ცენტრი')
	cost_unit_id = fields.Many2one(comodel_name='prx_payroll.cost_unit', string='დანახარჯთა ერთეული')
	cost_amount = fields.Float(string="ხარჯის თანხა")

	def init(self):
		tools.drop_view_if_exists(self._cr, self._table)
		self._cr.execute("""
	            CREATE OR REPLACE VIEW %s AS (
	                SELECT
	                    row_number() OVER() as id,
				       t.company_id,
				       t.worksheet_id,
				       t.employee_id,
				       t.period_id,
				       t.position_id,
				       t.organization_unit_id,
				       t.earning_id,
				       t.tax_id,
				       t.employee_tax_id,
				       t.deduction_id,
				       t.employee_deduction_id,
				       t.position_earning_id,
				       t.creditor,
				       t.create_uid,
				       t.write_uid,
				       t.sequence,
				       t.code,
				       t.transaction_type,
				       t.personal_number,
				       t.earning_unit,
				       t.start_date,
				       t.end_date,
				       t.tax_proportion,
				       t.qty,
				       t.rate,
				       t.exchange_rate,
				       t.active,
				       t.include_tax_base,
				       t.create_date,
				       t.write_date,
				       t.amount,c.rate as cost_rate,c.cost_center_id,c.cost_unit_id,(t.amount*c.rate) as cost_amount from prx_payroll_transaction t
				left outer join prx_payroll_worksheet_cost_line c on t.worksheet_id=c.worksheet_id and t.company_id=c.company_id
				                                                                                   inner join hr_employee e on t.employee_id = e.id )
	            """ % (self._table)
		                 )