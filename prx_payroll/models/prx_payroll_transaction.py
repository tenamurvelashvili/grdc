from odoo import models, fields, api
from odoo.exceptions import UserError
from .configuration.prx_enum_selection import TransactionType


class PrxPayrollTransaction(models.Model):
    """
        In payroll transaction maybe three type transaction
        [EARNING, TAX, DEDUCTION]
    """
    _name = 'prx.payroll.transaction'
    _description = 'Payroll Transaction'
    _order = 'sequence'
    _rec_name = 'sequence'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Char(string="ნომერი", readonly=True, default='New')
    worksheet_id = fields.Many2one('prx.payroll.worksheet', string="ტაბელი")
    employee_id = fields.Many2one('hr.employee', string="თანამშრომელი")
    period_id = fields.Many2one('prx.payroll.period', string="პერიოდი")
    code = fields.Char(size=255, string="კოდი")
    amount = fields.Float(string="თანხა", digits=(19, 2))
    transaction_type = fields.Selection(TransactionType.selection(),
                                        string="ტრანზაქციის ტიპი",
                                        required=True)
    position_id = fields.Many2one('hr.job', string="პოზიცია")
    organization_unit_id = fields.Many2one('hr.department',
                                           string="ორგანიზაციული ერთეული",
                                           compute='_compute_employee_details',
                                           store=True)
    earning_id = fields.Many2one('prx.payroll.earning', string="ანაზღაურება",
                                 compute='_compute_employee_details',
                                 store=True)
    tax_id = fields.Many2one('prx.payroll.tax', string="გადასახადი")
    employee_tax_id = fields.Many2one('prx.payroll.employee.tax', string="თანამშრომლის გადასახადი")
    deduction_id = fields.Many2one('prx.payroll.deduction', string="დაქვითვა")
    employee_deduction_id = fields.Many2one('prx.payroll.employee.deduction', string="თანამშრომლის დაქვითვა")
    personal_number = fields.Char(size=20, string="პირადი ნომერი",
                                  compute='_compute_employee_details',
                                  store=True)
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
    combined_employee_info = fields.Char(string='დასახელება', compute='_compute_combined_employee_info', store=True)
    report_name = fields.Char(string='რეპორტის დასახელება')

    transaction_type_rank = fields.Integer(string="Type Rank", compute='_compute_type_rank', store=True)
    transaction_type_label = fields.Char(string="Transaction Type", compute='_compute_type_label', store=True)

    pension_proportion = fields.Float(digits=(19, 2), string="საპენსიოს წილი")
    tax_proportion = fields.Float(digits=(19, 2), string="გადასახადის წილი")
    earning_proportion = fields.Float(digits=(19, 10), string="ანაზღაურების წილი")
    transferred = fields.Boolean(string="გადარიცხულია")

    def unlink(self):
        for rec in self:
            if rec.transferred:
                raise UserError("გადარიცხული ტრანზაქციის წაშლა შეუძლებელია!")
        return super(PrxPayrollTransaction, self).unlink()

    def action_open_transfer_wizard(self):
        action = self.env.ref('prx_payroll.action_prx_payroll_transaction_transfer').read()[0]
        return action

    @api.depends('transaction_type')
    def _compute_type_rank(self):
        order = {'earning': 1, 'tax': 2, 'deduction': 3}
        for rec in self:
            rec.transaction_type_rank = order.get(rec.transaction_type, 99)

    @api.depends('transaction_type')
    def _compute_type_label(self):
        labels = dict(self._fields['transaction_type'].selection)
        for rec in self:
            rec.transaction_type_label = labels.get(rec.transaction_type, rec.transaction_type)

    @api.depends('employee_id')
    def _compute_combined_employee_info(self):
        for rec in self:
            if rec.employee_id:
                rec.combined_employee_info = f"{rec.employee_id.name}-{rec.employee_id.identification_id}-{rec.employee_id.job_id.name}"
            else:
                rec.combined_employee_info = False

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PrxPayrollTransaction, self).create(vals_list)
        for rec in res:
            rec.sequence = self.env['ir.sequence'].next_by_code('prx.payroll.transaction')
        return res

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.code

    @api.depends('employee_id')
    def _compute_employee_details(self):
        for rec in self:
            if rec.employee_id:
                rec.position_id = rec.employee_id.job_id
                rec.organization_unit_id = rec.employee_id.department_id
                rec.personal_number = rec.employee_id.identification_id
            else:
                rec.position_id = False
                rec.organization_unit_id = False
                rec.personal_number = False

    def action_close_transactions(self):
        action = self.env.ref('prx_payroll.action_prx_payroll_close_transaction_wizard').read()[0]
        return action
