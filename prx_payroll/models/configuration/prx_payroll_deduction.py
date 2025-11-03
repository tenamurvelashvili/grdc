from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError
from .prx_enum_selection import DeducationType,DeducationBase,SalaryType


class PRXPayrollDeduction(models.Model):
    _name = 'prx.payroll.deduction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll deduction'
    _rec_name = 'deduction'

    deduction = fields.Char(string = 'დაქვითვა',required=True,tracking=True,translate=True)
    description = fields.Char(string = 'აღწერა',tracking=True,translate=True)
    deduction_calc_type = fields.Selection(DeducationType.selection(),string = 'კალკულაციის ტიპი',required=True,tracking=True)
    deduction_base = fields.Selection(DeducationBase.selection(),string = 'დაკავების ბაზა',required=True,tracking=True)
    reduces_income_tax_base = fields.Boolean(string='ამცირებს საშემოსავლოთი დასაბეგრ ბაზას',tracking=True)
    is_limited = fields.Boolean(string='ლიმიტის თანხის გათვალისწინება',tracking=True)
    need_creditor = fields.Boolean(string='კრედიტორის მოთხოვნა',tracking=True)
    ignor_living_wage = fields.Boolean(string='არ გაითვალისწინოს საარსებო მინიმუმი',tracking=True)
    deduction_order = fields.Integer(string='დაქვითვის რიგითობა',tracking=True)
    creditor = fields.Many2one('res.partner',string='კრედიტორი',tracking=True)
    pension = fields.Boolean(string='საპენსიო')
    code = fields.Char(string="კოდი")
    alimony = fields.Boolean(string="ალიმეტი")
    avanse = fields.Boolean(string="ავანსი")
    report_name = fields.Char(compute="_compute_report_name",string="რეპორტის დასახელება",store=True,compute_sudo=True)
    salary_type = fields.Selection(SalaryType.selection(),required=True,default='standard',string="პროცესის ტიპი")
    payment_description = fields.Char(string='გადარიცხვის დანიშნულება')

    @api.depends('code','deduction')
    def _compute_report_name(self):
        for rec in self:
            print(rec.code,rec.deduction)
            rec.report_name = "{}.{}".format(rec.code,rec.deduction)

    def create(self, vals):
        if vals.get('pension'):
            vals['deduction_base'] = 'gross_amount'
            vals['reduces_income_tax_base'] = True
        return super().create(vals)


    def write(self, vals):
        res = super().write(vals)
        if 'pension' in vals:
            if self.pension:
                self.deduction_base = 'gross_amount'
                self.reduces_income_tax_base = True
        return res

    @api.onchange('pension')
    def _onchange_pension(self):
        for rec in self:
            if rec.pension:
                rec.deduction_base = 'gross_amount'
                rec.reduces_income_tax_base = True
            else:
                rec.deduction_base = False
                rec.reduces_income_tax_base = False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.deduction)
