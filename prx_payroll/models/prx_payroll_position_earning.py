from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from lxml import etree
from .configuration.prx_enum_selection import SalaryType

class PRXPayrollPositionEarning(models.Model):
    _name = 'prx.payroll.position.earning'
    _description = 'თანამშრომლის პოზიციების ანაზღაურება'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    active = fields.Boolean(string='Active', default=True)
    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', )
    contract_id = fields.Many2one('hr.contract', string='კონტრაქტი', required=True)
    position_id = fields.Char(related='contract_id.job_id.name', string='პოზიცია', )
    identification_number = fields.Char(string='პირადი ნომერი', related='employee_id.identification_id', store=True,
                                        readonly=True, )
    earning_id = fields.Many2one('prx.payroll.earning', string='ანაზღაურება', required=True)
    start_date = fields.Date(string='საწყისი თარიღი', required=True)
    end_date = fields.Date(string='საბოლოო თარიღი', compute='_default_end', store=True, readonly=False)
    salary_type = fields.Selection(SalaryType.selection(),related='earning_id.salary_type',string="პროცესის ტიპი")
    exception = fields.Boolean(string="გამონაკლისი")
    contract_ids_domain = fields.Many2many('hr.contract', compute='_onchange_contract_domain')
    insurance_pension_deduction_id = fields.Many2one('prx.payroll.employee.deduction')
    from_wizard = fields.Boolean()
    wizard_period_id = fields.Many2one('prx.payroll.period')
    comment = fields.Text(string="კომენტარი")
    

    def unlink(self):
        unlinking_from_deduction = self.env.context.get('prx_unlinking_from_deduction')
        for rec in self:
            if rec.insurance_pension_deduction_id and not unlinking_from_deduction:
                rec.insurance_pension_deduction_id.with_context(prx_unlinking_from_position=True).unlink()
        return super(PRXPayrollPositionEarning, self).unlink()

    #return true if fond pension for employee
    def _check_if_ded_eligible(self, rec):
        #rec position earning
        domain = [
            ('employee_id', '=', rec.employee_id.id),
            ('deduction_id.pension', '=', True),
        ]
        return bool(self.env['prx.payroll.employee.deduction'].search_count(domain))
        
        
    @api.model_create_multi
    def create(self, vals_list):
        records = super(PRXPayrollPositionEarning, self).create(vals_list)
        for rec in records:
            if rec.earning_id.insurance:
                link_ded = rec.earning_id.link_insurance_ded
                if link_ded and self._check_if_ded_eligible(rec):
                    insurance_ded_id = self.env['prx.payroll.employee.deduction'].create({
                        'employee_id': rec.employee_id.id,
                        'deduction_id': link_ded.id,
                        'deduction_calc_type': link_ded.deduction_calc_type,
                        'vendor':link_ded.creditor,
                        'amount': 0.0,
                        'percentage': 0.02,
                        'start_date': rec.start_date,
                        'end_date': rec.end_date,
                        'insurance_pension_linked_earning_id': rec.id
                    })
                    rec.insurance_pension_deduction_id = insurance_ded_id.id
        return records

    @api.onchange('employee_id', 'exception','employee_id.contract_ids')
    def _onchange_contract_domain(self):
        for rec in self:
            domain = [('employee_id', '=', rec.employee_id.id)]
            if rec.exception:
                domain.append(('state', '=', 'close'))
            else:
                domain.append(('state', '=', 'open'))
            contracts_ids = self.env['hr.contract'].search(domain)
            rec.contract_ids_domain = contracts_ids

    def action_open_calculator(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'თანხის კალკულატორი',
            'res_model': 'prx.payroll.amount.calculator.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('prx_payroll.view_prx_payroll_amount_calculator_wizard').id,
            'context': {'default_net_amount': self.amount},
            'target': 'new',
        }

    @api.depends('earning_id')
    def _default_end(self):
        for rec in self:
            if rec.earning_id and rec.earning_id.salary_type in ['one_time','avanse']:
                rec.end_date = rec.start_date
            else:
                rec.end_date = None

    amount = fields.Float(string='თანხა', digits=(19, 2), tracking=True)
    currency_id = fields.Many2one('res.currency', string='ვალუტა', default=lambda self: self.env.company.currency_id.id)
    open_contract_ids = fields.Many2many(
        comodel_name='hr.employee',
        string="Employee's Open Contracts",
        compute='_compute_open_emp_ids',
    )
    is_one_time_period = fields.Boolean(compute='_is_one_time_period')

    def _is_one_time_period(self):
        for rec in self:
            rec.is_one_time_period = bool(rec.earning_id.salary_type in ['one_time','avanse'])

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

    @api.onchange('contract_id','exception')
    def get_contract_data(self):
        if self.contract_id:
            self.start_date = self.contract_id.date_start
            self.end_date = self.contract_id.date_end
            if self.contract_id.state != 'open' and not self.exception:
                self.contract_id = None

    @api.onchange('exception')
    def clear_exception(self):
        if not self.exception:
            self.contract_id = None
            self.employee_id = None

    @api.onchange('employee_id')
    def reset_contract_field(self):
        if self.employee_id:
            self.contract_id = None

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.earning_id.earning)

    @api.constrains('start_date', 'end_date', 'employee_id', 'contract_id', 'earning_id')
    def _check_date_and_contract(self):
        for record in self:
            if record.end_date and record.start_date > record.end_date:
                raise UserError('კონტრაქტის საწყისი თარიღი მეტი უნდა იყსო კონტრაქტის დასრულების თარიღზე!')
            open_records = self.search([
                ('employee_id', '=', record.employee_id.id),
                ('id', '!=', record.id),
                ('end_date', '=', False),
            ])
            if not record.exception and record.end_date and record.contract_id.date_end and record.end_date > record.contract_id.date_end:
                raise UserError(
                    f'დასრულების თარიღი კონტრაქტის: {record.contract_id.name} დასრულების თარიღზე მეტი ვერ იქნება.')
            if record.start_date < record.contract_id.date_start:
                raise UserError(
                    f'საწყისი თარიღი კონტრაქტის: {record.contract_id.name} საწყის თარიღზე ნაკლები ვერ იქნება.')
            for overlap in open_records:
                if not overlap.end_date and not record.end_date:
                    if overlap.contract_id != record.contract_id:
                        raise UserError("ამ თანამშრომელზე კონტრაქტი უკვე არსებობს.")
                    if overlap.earning_id == record.earning_id:
                        raise UserError("ეს ანაზღაურება უკვე არსებობს.")
                if record.end_date:
                    if not overlap.end_date and overlap.start_date >= record.end_date and overlap.contract_id != record.contract_id:
                        raise UserError("ეს კონტრაქტი უკვე არსებობს.")
                if not overlap.end_date and record.end_date:
                    if overlap.start_date <= record.end_date and overlap.earning_id == record.earning_id:
                        raise UserError("ეს კონტრაქტი უკვე არსებობს.")

            closed_records = self.search([
                ('employee_id', '=', record.employee_id.id),
                ('id', '!=', record.id),
                ('contract_id', '=', record.contract_id.id),
                ('end_date', '!=', False),
            ])
            if not record.exception:
                for overlap in closed_records:
                    if overlap.start_date and overlap.end_date and record.start_date:
                        if overlap.start_date <= record.start_date <= overlap.end_date and overlap.earning_id == record.earning_id:
                            raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")
                    if record.start_date <= overlap.start_date and not record.end_date and overlap.earning_id == record.earning_id:
                        raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")
                    if record.end_date and overlap.start_date >= record.end_date >= overlap.end_date and overlap.earning_id == record.earning_id:
                        raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")
                    if record.end_date and record.start_date <= overlap.start_date and record.end_date >= overlap.end_date and overlap.earning_id == record.earning_id:
                        raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")

                    # if record.end_date and record.start_date <= overlap.start_date and record.end_date <= overlap.end_date and overlap.earning_id == record.earning_id:
                    #     raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")

                    if record.end_date and record.start_date <= overlap.start_date <= record.end_date and overlap.earning_id == record.earning_id:
                        raise UserError("ეს კონტრაქტი კვეთს არსებულ კონტრაქტს.")
