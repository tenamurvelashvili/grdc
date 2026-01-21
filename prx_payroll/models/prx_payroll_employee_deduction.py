from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError
from .configuration.prx_enum_selection import  DeducationType
from lxml import etree

class PRXPayrollEmployeeDeduction(models.Model):
    _name = 'prx.payroll.employee.deduction'
    _description = 'Payroll employee deduction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    active = fields.Boolean(string='Active', default=True)
    employee_id = fields.Many2one('hr.employee',string='თანამშრომელი',required=True)
    identification_number = fields.Char(string='პირადი ნომერი',related='employee_id.identification_id',readonly=True,store=False)
    deduction_id = fields.Many2one('prx.payroll.deduction',string='დაქვითვა',required=True)
    deduction_calc_type = fields.Selection(DeducationType.selection(),related='deduction_id.deduction_calc_type',string='კალკულაციის ტიპი',)
    amount = fields.Float(string='თანხა',digits=(19, 2),tracking=True)
    percentage = fields.Float(string='პროცენტი',digits=(19, 2),tracking=True)
    limit_amount = fields.Float(string='თანხის ლიმიტი',digits=(19, 2))
    start_date = fields.Date(string='საწყისი თარიღი',required=True)
    end_date = fields.Date(string='საბოლოო თარიღი', compute='_default_end', store=True, readonly=False)
    exception = fields.Boolean(string="გამონაკლისი")
    insurance_pension_linked_earning_id = fields.Many2one('prx.payroll.position.earning')

    def unlink(self):
        for rec in self:
            if rec.insurance_pension_linked_earning_id:
                rec.insurance_pension_linked_earning_id.unlink()
        return super().unlink()

    @api.depends('deduction_id','start_date')
    def _default_end(self):
        for rec in self:
            if rec.deduction_id and rec.deduction_id.salary_type in ['one_time','avanse']:
                rec.end_date = rec.start_date
            else:
                rec.end_date = None

    vendor = fields.Many2one('res.partner',string='კრედიტორი')
    is_need_creditor = fields.Boolean(compute="_compute_need_creditor")
    is_one_time_period = fields.Boolean(compute='_is_one_time_period')

    def _is_one_time_period(self):
        for rec in self:
            rec.is_one_time_period = bool(rec.deduction_id.salary_type in ['one_time','avanse'])

    open_contract_ids = fields.Many2many(
        comodel_name='hr.employee',
        string="Employee's Open Contracts",
        compute='_compute_open_emp_ids',
    )

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            if isinstance(arch, str):
                doc = etree.fromstring(arch)
            else:
                doc = arch
            for field in doc.xpath(".//field"):
                field.set('readonly', '1')
            sheet_list = doc.xpath(".//sheet")
            if sheet_list:
                sheet = sheet_list[0]
                parent = sheet.getparent()
                if parent is not None and not doc.xpath('.//chatter'):
                    index = list(parent).index(sheet)
                    chatter = etree.Element('chatter')
                    parent.insert(index + 1, chatter)
        return arch, view

    @api.depends('employee_id.contract_ids', 'employee_id','exception')
    def _compute_open_emp_ids(self):
        for rec in self:
            if rec.exception:
                rec.open_contract_ids = self.env['hr.employee'].search([]).contract_ids.filtered(
                    lambda c: c.state == 'close').mapped('employee_id')
            else:
                rec.open_contract_ids = self.env['hr.employee'].search([]).contract_ids.filtered(
                    lambda c: c.state == 'open').mapped('employee_id')

    @api.onchange('exception')
    def clear_exception(self):
        if not self.exception:
            self.employee_id = None

    @api.depends('deduction_id.need_creditor')
    def _compute_need_creditor(self):
        for rec in self:
            rec.is_need_creditor = rec.deduction_id.need_creditor

    @api.onchange('deduction_id')
    def _onchange_deduction_id(self):
        if self.deduction_id:
            self.vendor = self.deduction_id.creditor.id

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.deduction_id.deduction)

    # @api.constrains('employee_id', 'start_date', 'end_date')
    # def _check_unique_employee_date_range(self):
    #     for record in self:
    #         if record.start_date and record.end_date:
    #             overlapping = self.search([
    #                 ('employee_id', '=', record.employee_id.id),
    #                 ('id', '!=', record.id),
    #                 ('start_date', '<=', record.end_date),
    #                 ('end_date', '>=', record.start_date),
    #             ])
    #             if overlapping:
    #                 raise ValidationError(
    #                     "There is already a deduction record for this employee "
    #                     "that overlaps with the selected date range."
    #                 )