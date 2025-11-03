from odoo import models, fields, api, http
from odoo.exceptions import UserError
import base64
import io
import pandas as pd
from datetime import datetime
from .prx_enum_selection import DeducationType


def safe_date(val):
    try:
        if pd.isna(val) or not val:
            return None
        return pd.to_datetime(val, dayfirst=True, errors='coerce').date()
    except Exception:
        return None

class PrxPayrollImportWizard(models.TransientModel):
    _name = 'prx.payroll.import.wizard'
    _description = 'Import Payroll from Excel'

    company_id = fields.Many2one(
        'res.company',
        string='კომპანია',
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    data_file = fields.Binary(string='Excel File', attachment=True, required=True)
    filename = fields.Char()

    def action_import(self):
        if not self.data_file:
            raise UserError("ატვირთეთ ექსელის ფაილი!")
        data = base64.b64decode(self.data_file)
        excel_io = io.BytesIO(data)
        try:
            df = pd.read_excel(excel_io, sheet_name=0, dtype=str)
        except Exception as e:
            raise UserError(f"ექსელის წაკითხვა ვერ მოხერხდა!- {e}")
        df.columns = df.columns.str.strip()

        context = self.env.context
        if context.get('position_earning', False):
            self.env['prx.payroll.position.earning.import'].sudo().search([]).unlink()
            for idx, row, in df.iterrows():
                identification_number = row.get('პირადი ნომერი')
                start_date = row.get('საწყისი თარიღი')
                end_date = row.get('საბოლოო თარიღი')
                amount = row.get('თანხა')
                earning = row.get('ანაზღაურება')
                currency = row.get('ვალუტა')
                is_exception = True if row.get('გამონაკლისი') == '1' else False

                text_warning = ""
                vals = {
                    'identification_number': None if pd.isna(identification_number) else identification_number,
                    'amount': None if pd.isna(amount) else amount,
                    'start_date': safe_date(start_date),
                    'end_date': safe_date(end_date),
                    'is_exception': bool(is_exception)
                }
                if identification_number:
                    emp = self.env['hr.employee'].search([('identification_id', '=', identification_number)], limit=1)
                    if emp:
                        vals['employee_id'] = emp.id
                        if emp.id:
                            cont = self.env['hr.contract'].search(
                                [('state', '=', 'open' if not is_exception else 'close'),('employee_id', '=', emp.id)],limit=1)
                            if cont:
                                vals['contract_id'] = cont.id
                            else:
                                text_warning += 'მსგავსი კონტრაქტი ვერ მოიძებნა \n'
                    else:
                        text_warning += 'მსგავსი საიდენთიფიკაციოთი თანამშრომელი ვერ მოიძებნა \n'
                else:
                    text_warning += 'საიდენთიფიკაციო არ არის შევსებული \n'

                if pd.isna(start_date):
                    text_warning += 'საწყისი თარიღი არ არის შევსებული \n'

                if earning:
                    vals['earning_name'] = earning
                    earn = self.env['prx.payroll.earning'].search([('earning', '=', earning)], limit=1)
                    if earn:
                        vals['earning_id'] = earn.id
                    else:
                        text_warning += 'მსგავსი ანაზღაურების კოდი ვერ მოიძებნა \n'
                else:
                    text_warning += 'ანაზღაურების ველი არ არის შევსებული \n'

                if currency:
                    vals['currency_name'] = currency
                    curr = self.env['res.currency'].search([('name', '=', currency)], limit=1)
                    if curr:
                        vals['currency_id'] = curr.id
                    else:
                        text_warning += 'მსგავსი ვალუტა ვერ მოიძებნა \n'
                else:
                    text_warning += 'ვალუტის ველი არ არის შევსებული \n'

                vals['error_text'] = text_warning
                self.env['prx.payroll.position.earning.import'].create(vals)
            action = self.env.ref('prx_payroll.action_employee_position_import').read()[0]
            return action
        if context.get('employee_deduction', False):
            self.env['prx.payroll.employee.deduction.import'].sudo().search([]).unlink()
            for idx, row, in df.iterrows():
                identification_number = row.get('პირადი ნომერი')
                amount = row.get('თანხა')
                percentage = row.get('პროცენტი')
                limit_amount = row.get('თანხის ლიმიტი')
                start_date = row.get('საწყისი თარიღი')
                end_date = row.get('საბოლოო თარიღი')
                vendor_tax = row.get('ვენოდრი')
                is_exception = True if row.get('გამონაკლისი') == '1' else False

                text_warning = ""
                vals = {
                    'vendor_tax': None if pd.isna(vendor_tax) else vendor_tax,
                    'identification_number': None if pd.isna(identification_number) else identification_number,
                    'amount': None if pd.isna(amount) else amount,
                    'percentage': None if pd.isna(percentage) else percentage,
                    'limit_amount': None if pd.isna(limit_amount) else limit_amount,
                    'start_date': safe_date(start_date),
                    'end_date': safe_date(end_date),
                    'is_exception': bool(is_exception)
                }

                if identification_number:
                    emp = self.env['hr.employee'].search([('identification_id', '=', identification_number)], limit=1)
                    if emp:
                        closed = self.env['hr.contract'].sudo().search(
                            [('state', '=', 'close'),('employee_id', '=', emp.id)])
                        if is_exception:
                            if closed:
                                vals['employee_id'] = emp.id
                            else:
                                vals['employee_id'] = False
                                text_warning += 'თანამშრომელს აქვს აქტიური კონტრაქტი \n'
                        if emp and not is_exception:
                            vals['employee_id'] = emp.id
                    else:
                        text_warning += 'მსგავსი საიდენთიფიკაციოთი თანამშრომელი ვერ მოიძებნა \n'
                else:
                    text_warning += 'საიდენთიფიკაციო არ არის შევსებული \n'

                if vendor_tax:
                    vendor = self.env['res.partner'].search([('vat', '=', vendor_tax)], limit=1)
                    if vendor:
                        vals['vendor'] = vendor.id
                #     else:
                #         text_warning += 'მსგავსი საიდენთიფიკაციოთი ვენდორი ვერ მოიძებნა \n'
                # else:
                #     text_warning += 'ვენდორის საიდენთიფიკაციო არ არის შევსებული \n'

                deduction_name = row.get('დაქვითვა')
                if deduction_name:
                    vals['deduction_name'] = deduction_name
                    deduction = self.env['prx.payroll.deduction'].search([('deduction', '=', deduction_name)], limit=1)
                    if deduction:
                        vals['deduction_id'] = deduction.id
                        if deduction.deduction_calc_type == 'fix_amount' and not pd.isna(percentage):
                            text_warning += 'პროცენტი უნდა იყოს 0\n'
                        if deduction.deduction_calc_type == 'fix_amount' and not pd.isna(limit_amount):
                            text_warning += 'თანხის ლიმიტი უნდა იყოს 0\n'
                        if deduction.deduction_calc_type == 'percentage' and not (pd.isna(amount) or amount != 0.0):
                            text_warning += 'თანხა უნდა იყოს 0\n'

                    else:
                        text_warning += 'მსგავსი დაქვითვით ჩანაწერი ვერ მოიძება \n'
                else:
                    text_warning += 'დაქვითვის დასახელება არ არის შევსებული \n'

                if pd.isna(start_date):
                    text_warning += 'საწყისი თარიღი არაა შევსებული \n'

                vals['error_text'] = text_warning
                self.env['prx.payroll.employee.deduction.import'].create(vals)
            action = self.env.ref('prx_payroll.action_employee_deduction_import').read()[0]
            return action

        if context.get('employee_tax', False):
            self.env['prx.payroll.employee.tax.import'].sudo().search([]).unlink()
            for idx, row, in df.iterrows():
                identification_number = row.get('საიდენთიფიკაციო ნომერი')
                start_date = row.get('საწყისი თარიღი')
                end_date = row.get('საბოლოო თარიღი')
                used_tax_amount = row.get('მიღებამდე გამოყენებული შეღავათი')
                text_warning = " "
                is_exception = True if row.get('გამონაკლისი') == '1' else False
                vals = {
                    'identification_number': None if pd.isna(identification_number) else identification_number,
                    'start_date': safe_date(start_date),
                    'end_date': safe_date(end_date),
                    'used_tax_amount': None if pd.isna(used_tax_amount) else used_tax_amount,
                    'is_exception': bool(is_exception)
                }

                emp_ref = identification_number
                if emp_ref:
                    emp = self.env['hr.employee'].search([('identification_id', '=', emp_ref)], limit=1)
                    closed = self.env['hr.contract'].search(
                        [('state', '=', 'closed'),
                         ('employee_id', '=', emp.id)], limit=1)
                    if is_exception:
                        if closed:
                            vals['employee_id'] = emp.id
                        else:
                            text_warning += 'თანამშრომელს აქვს აქტიური კონტრაქტი \n'
                            vals['employee_id'] = False
                    if emp and not is_exception:
                        vals['employee_id'] = emp.id
                    else:
                        text_warning += 'მსგავსი საიდენთიფიკაციოთი თანამშრომელი ვერ მოიძებნა \n'
                else:
                    text_warning += 'საიდენთიფიკაციო არ არის შევსებული \n'

                tax_name = row.get('გადასახადი')
                if tax_name:
                    vals['tax_name'] = tax_name
                    tax = self.env['prx.payroll.tax'].search([('tax', '=', tax_name)], limit=1)
                    if tax:
                        vals['tax'] = tax.id
                    else:
                        text_warning += 'მსგავსი გადასახადით ჩანაწერი ვერ მოიძებნა \n'
                else:
                    text_warning += 'გადასახადის ველი არ არის შევსებული\n'

                if pd.isna(start_date):
                    text_warning += 'საწყისი თარიღი არაა შევსებული \n'

                vals['error_text'] = text_warning
                self.env['prx.payroll.employee.tax.import'].create(vals)
            action = self.env.ref('prx_payroll.prx_payroll_employee_tax_import_action').read()[0]
            return action
        return None


class PrxPayrollEmployeeTaxImport(models.Model):
    _name = 'prx.payroll.employee.tax.import'
    _description = 'Payroll Employee Tax Import'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    is_valid = fields.Boolean(string='ვალიდური', default=False, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', compute="_compute_employee", store=True)
    identification_number = fields.Char(string='პირადი ნომერი', compute="_compute_pn", store=True)
    tax_name = fields.Char(string="გადასახადის დასახელება", compute="_get_tax_name", store=True)
    tax = fields.Many2one('prx.payroll.tax', string='გადასახადი', compute='_compute_tax', store=True)
    start_date = fields.Date(string='საწყისი თარიღი')
    end_date = fields.Date(string='საბოლოო თარიღი')
    used_tax_amount = fields.Float(string='მიღებამდე გამოყენებული შეღავათი', digits=(19, 2))
    error_text = fields.Text(string='შეცდომის ტექსტი', readonly=True)
    is_exception = fields.Boolean(string='გამონაკლისი', default=False)

    @api.depends('tax_name')
    def _compute_tax(self):
        for rec in self:
            if rec.tax_name:
                rec.tax = self.env['prx.payroll.tax'].search([('tax', '=', rec.tax_name)], limit=1).id
            else:
                rec.tax = None

    @api.depends('tax')
    def _get_tax_name(self):
        for rec in self:
            if rec.tax:
                rec.tax_name = rec.tax.tax

    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            try:
                rec.validate_record(create=True)
            except UserError as e:
                rec.error_text = e.name
            except Exception as e:
                rec.error_text = str(e)
        return res

    @api.depends('employee_id')
    def _compute_pn(self):
        for rec in self:
            if rec.employee_id:
                rec.identification_number = rec.employee_id.identification_id or None

    @api.depends('identification_number')
    def _compute_employee(self):
        for rec in self:
            if rec.identification_number:
                rec.employee_id = self.env['hr.employee'].search(
                    [('identification_id', '=', rec.identification_number)], limit=1).id
            else:
                rec.employee_id = None

    def import_excel(self):
        action = self.env['ir.actions.actions']._for_xml_id('prx_payroll.action_prx_payroll_import')
        return action

    def validate_record(self, create=False):
        for record in self:
            text_warning = ""
            record.error_text = ""
            if not record.start_date:
                text_warning += 'საწყისი თარიღი არაა შევსებული \n'
            if not record.tax:
                text_warning += 'მსგავსი გადასახადით ჩანაწერი არ იძებნება \n'

            if record.identification_number and not record.employee_id:
                text_warning += 'მსგავსი საიდენთიფიკაციოთი თანამშრომელი ვერ მოიძებნა \n'
            if not record.identification_number:
                text_warning += 'საიდენთიფიკაციოთი კოდი არ არის მითითებული \n'
            if record.end_date and record.start_date >= record.end_date:
                text_warning += 'საწყისი თარიღი არ შეიძლება იყოს საბოლოო თარიღზე მეტი'
            if record.is_exception:
                active_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', '=', 'open')
                ], limit=1)
                if active_contract:
                    text_warning += 'თანამშრომელს აქვს აქტიური კონტრაქტი  \n'
                record.end_date = record.start_date # თუ გამონაკლისია დასრულების თარიღი იგივე იქნება რაც დაწყების თარიღი

            text_warning += record.check_date_and_contract('prx.payroll.employee.tax')
            text_warning += record.check_date_and_contract('prx.payroll.employee.tax.import')
            record.error_text = text_warning
            if not create:
                record.is_valid = not record.error_text

    def check_date_and_contract(self, model):
        for record in self:
            if record.start_date:
                if record.end_date and record.start_date > record.end_date:
                    raise UserError('საწყისი თარიღი არშეიძლება საბოლოო თარიღზე მეტი')
                overlapping = self.env[model]
                if record.employee_id.id:
                    domain = [
                        ('employee_id', '=', record.employee_id.id),
                        ('id', '!=', record.id)
                    ]
                    overlapping = self.env[model].search(domain)
                if overlapping:
                    for overlap in overlapping:
                        checkError = 'მსგავსი ჩანაწერი უკვე არსებობს \n' if model == 'prx.payroll.employee.tax' else 'ჩანაწერი დუბლირდება \n'
                        if overlap.end_date and overlap.start_date and overlap.start_date <= record.start_date <= overlap.end_date:
                            return checkError
                        if not overlap.end_date and overlap.start_date and overlap.start_date <= record.start_date:
                            return checkError
                        if not overlap.end_date and not record.end_date and overlap.start_date and overlap.start_date >= record.start_date:
                            return checkError
                        if not overlap.end_date and record.end_date and overlap.start_date and overlap.start_date <= record.end_date:
                            return checkError
        return ''

    def move_record(self):
        create_list = []
        for rec in self:
            if rec.is_valid:
                create_list.append({
                    'employee_id': rec.employee_id.id,
                    'tax': rec.tax.id,
                    'start_date': rec.start_date,
                    'end_date': rec.end_date,
                    'used_tax_amount': rec.used_tax_amount
                })
                rec.unlink()
        if create_list:
            try:
                http.request.env['prx.payroll.employee.tax'].sudo().create(create_list)
                """აქ ამის ერრორს დავიჭერთ თუ დაგვჭირდება რასაც raise ში აბრუნებს"""
            except UserError as tp:
                print(tp)


class PRXPayrollEmployeeDeductionImport(models.Model):
    _name = 'prx.payroll.employee.deduction.import'
    _description = 'Payroll employee deduction import'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    identification_number = fields.Char(string='პირადი ნომერი', readonly=False, compute='_compute_pn', store=True)
    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', compute='_compute_employee', store=True)
    deduction_name = fields.Char(string="დაქვითვის დასახელება", compute="_compute_deduction_name", readonly=False,
                                 store=True)
    deduction_id = fields.Many2one('prx.payroll.deduction', string='დაქვითვა', readonly=False,
                                   compute="_compute_deduction", store=True)
    deduction_calc_type = fields.Selection(DeducationType.selection(), related='deduction_id.deduction_calc_type',
                                           string='კალკულაციის ტიპი', )
    amount = fields.Float(string='თანხა', digits=(19, 2))
    percentage = fields.Float(string='პროცენტი', digits=(19, 2))
    limit_amount = fields.Float(string='თანხის ლიმიტი', digits=(19, 2))
    start_date = fields.Date(string='საწყისი თარიღი')
    end_date = fields.Date(string='საბოლოო თარიღი')
    vendor_tax = fields.Char(string='ვენდორის საიდენტიფიკაციო', compute="_compute_vendor_vat", readonly=False,
                             store=True)
    vendor = fields.Many2one('res.partner', string='ვენდორი', compute='_compute_vendor', readonly=False, store=True)
    error_text = fields.Text(string="შეცდომის ტექსტი", readonly=True)
    is_valid = fields.Boolean(string='ვალიდური', default=False, readonly=True)
    is_exception = fields.Boolean(string='გამონაკლისი', default=False)

    def import_excel(self):
        action = self.env['ir.actions.actions']._for_xml_id('prx_payroll.action_prx_payroll_import')
        return action

    @api.depends('deduction_name')
    def _compute_deduction(self):
        for rec in self:
            if rec.deduction_name:
                rec.deduction_id = self.env['prx.payroll.deduction'].search([('deduction', '=', rec.deduction_name)],
                                                                            limit=1).id or None
            else:
                rec.deduction_id = None

    @api.depends('deduction_id')
    def _compute_deduction_name(self):
        for rec in self:
            if rec.deduction_id:
                rec.deduction_name = rec.deduction_id.deduction or None

    @api.depends('identification_number')
    def _compute_employee(self):
        for rec in self:
            if rec.identification_number:
                rec.employee_id = self.env['hr.employee'].search(
                    [('identification_id', '=', rec.identification_number)], limit=1).id
            else:
                rec.employee_id = None

    @api.depends('employee_id')
    def _compute_pn(self):
        for rec in self:
            if rec.employee_id:
                rec.identification_number = rec.employee_id.identification_id or None

    @api.depends('vendor_tax')
    def _compute_vendor(self):
        for rec in self:
            if rec.vendor_tax:
                rec.vendor = self.env['res.partner'].search([('vat', '=', rec.vendor_tax)], limit=1).id
            else:
                rec.vendor = None

    @api.depends('vendor')
    def _compute_vendor_vat(self):
        for rec in self:
            if rec.vendor:
                rec.vendor_tax = rec.vendor.vat or None

    def validate_record(self):
        for record in self:
            text_warning = ""
            record.error_text = ""
            if not record.start_date:
                text_warning += 'საწყისი თარიღი არაა შევსებული \n'
            if not record.identification_number:
                text_warning += 'თანამშრომლის საიდენტიფიკაციო კოდი არ არის მითითებული \n'

            if not record.employee_id and record.identification_number:
                text_warning += 'მსგავსი საიდენთიფიკაციო კოდით თანამშრომელი ვერ მოიძებნა \n'
            # if not record.vendor_tax:
            #     text_warning += 'ვენდორის საიდენტიფიკაციო კოდი არ არის მითითებული \n'
            if record.vendor_tax and not record.vendor:
                text_warning += 'მსგავსი საიდენთიფიკაციო კოდით ვენდორი ვერ მოიძებნა \n'
            if not record.deduction_id:
                text_warning += 'დაქვითვის ჩანაწერი არ არის მითითებული \n'

            if record.is_exception:
                active_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', '=', 'open')
                ], limit=1)
                if active_contract:
                    text_warning += 'თანამშრომელს აქვს აქტიური კონტრაქტი  \n'
                record.end_date = record.start_date  # თუ გამონაკლისია დასრულების თარიღი იგივე იქნება რაც დაწყების თარიღი
            if record.end_date and record.start_date > record.end_date:
                text_warning += 'საწყისი თარიღი არ შეიძლება იყოს საბოლოო თარიღზე მეტი'
            if record.deduction_calc_type == 'fix_amount' and record.percentage:
                text_warning += 'პროცენტი უნდა იყოს 0'
            if record.deduction_calc_type == 'fix_amount' and record.limit_amount:
                text_warning += 'თანხის ლიმიტი უნდა იყოს 0'
            if record.deduction_calc_type == 'percentage' and record.amount:
                text_warning += 'თანხა უნდა იყოს 0'
            record.error_text = text_warning
            if not text_warning:
                record.is_valid = True

    def move_record(self):
        create_list = []
        for rec in self:
            if rec.is_valid:
                create_list.append({
                    'employee_id': rec.employee_id.id,
                    'deduction_id': rec.deduction_id.id,
                    'deduction_calc_type': rec.deduction_calc_type,
                    'amount': rec.amount,
                    'percentage': rec.percentage,
                    'limit_amount': rec.limit_amount,
                    'start_date': rec.start_date,
                    'end_date': rec.end_date,
                    'vendor': rec.vendor.id,
                    'exception': rec.is_exception,
                })
                rec.unlink()
        if create_list:
            try:
                http.request.env['prx.payroll.employee.deduction'].sudo().create(create_list)
                """აქ ამის ერრორს დავიჭერთ თუ დაგვჭირდება რასაც raise ში აბრუნებს"""
            except UserError as tp:
                print(tp)


class PRXPayrollPositionEarningImport(models.Model):
    _name = 'prx.payroll.position.earning.import'
    _description = 'თანამშრომლის პოზიციების ანაზღაურების იმპორტი'
    _check_company_auto = True

    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', compute='_compute_employee', readonly=False,
                                  store=True, compute_sudo=True)
    contract_id = fields.Many2one('hr.contract', string='კონტრაქტი', compute="_compute_contract", readonly=False,
                                  store=True)
    identification_number = fields.Char(string='პირადი ნომერი', store=True, compute="_compute_pn")
    earning_name = fields.Char(string='ანაზღაურების დასახელება', compute="_compute_earning_name", readonly=False,
                               store=True)
    earning_id = fields.Many2one('prx.payroll.earning', string='ანაზღაურება', compute="_compute_earning",
                                 readonly=False, store=True)
    start_date = fields.Date(string='საწყისი თარიღი')
    end_date = fields.Date(string='საბოლოო თარიღი', )
    amount = fields.Float(string='თანხა', digits=(19, 2), )
    currency_name = fields.Char(string='ვალუტის დასახელება', compute="_compute_currency", readonly=False, store=True)
    currency_id = fields.Many2one('res.currency', string='ვალუტა', compute="_compute_currency_id", readonly=False,
                                  store=True)
    position_id = fields.Char(related='contract_id.job_id.name', string='პოზიცია')
    error_text = fields.Text(string="შეცდომის ტექსტი", readonly=True)
    is_valid = fields.Boolean(string='ვალიდური', default=False, readonly=True)
    is_exception = fields.Boolean(string='გამონაკლისი', default=False)

    @api.depends('earning_id')
    def _compute_earning_name(self):
        for rec in self:
            if rec.earning_id:
                rec.earning_name = rec.earning_id.earning or None

    @api.depends('earning_name')
    def _compute_earning(self):
        for rec in self:
            if rec.earning_name:
                rec.earning_id = self.env['prx.payroll.earning'].search([('earning', '=', rec.earning_name)],
                                                                        limit=1).id or None
            else:
                rec.earning_id = None

    @api.onchange('currency_name')
    def _compute_currency_id(self):
        for rec in self:
            if rec.currency_name:
                rec.currency_id = self.env['res.currency'].search([('name', '=', rec.currency_name)],
                                                                  limit=1).id or None
            else:
                rec.currency_id = None

    @api.onchange('currency_id')
    def _compute_currency(self):
        for rec in self:
            if rec.currency_id:
                rec.currency_name = rec.currency_id.name or None
            else:
                rec.currency_name = None

    def import_excel(self):
        action = self.env['ir.actions.actions']._for_xml_id('prx_payroll.action_prx_payroll_import')
        return action

    def move_record(self):
        create_list = []
        for rec in self:
            if rec.is_valid:
                create_list.append({
                    'employee_id': rec.employee_id.id,
                    'contract_id': rec.contract_id.id,
                    'earning_id': rec.earning_id.id,
                    'amount': rec.amount,
                    'start_date': rec.start_date,
                    'end_date': rec.start_date if rec.earning_id and rec.earning_id.salary_type in ['one_time',
                                                                                                    'avanse'] else rec.end_date,
                    'exception': rec.is_exception,
                })
                rec.unlink()
        if create_list:
            try:
                http.request.env['prx.payroll.position.earning'].sudo().create(
                    create_list
                )
                """აქ ამის ერრორს დავიჭერთ თუ დაგვჭირდება რასაც raise ში აბრუნებს"""
            except UserError as tp:
                print(tp)

    @api.depends('employee_id')
    def _compute_contract(self):
        for rec in self:
            if rec.employee_id:
                rec.contract_id = self.env['hr.contract'].search(
                    [('state', '=', 'open' if not rec.is_exception else 'close'),('employee_id', '=', rec.employee_id.id)], limit=1).id or None
            else:
                rec.contract_id = None

    @api.depends('identification_number')
    def _compute_employee(self):
        for rec in self:
            if rec.identification_number:
                rec.employee_id = self.env['hr.employee'].search(
                    [('identification_id', '=', rec.identification_number)], limit=1).id or None
            else:
                rec.employee_id = None

    @api.depends('employee_id')
    def _compute_pn(self):
        for rec in self:
            if rec.employee_id:
                rec.identification_number = rec.employee_id.identification_id or None

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.earning_id.earning)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            try:
                rec.validate_record(create=True)
            except UserError as e:
                rec.error_text = e.name
            except Exception as e:
                rec.error_text = str(e)
        return res

    def validate_record(self, create=False):
        for record in self:
            warnings = set()
            record.error_text = ""
            if not record.start_date:
                warnings.add('საწყისი თარიღი არაა შევსებული')
            if not record.identification_number:
                warnings.add('თანამშრომლის საიდენტიფიკაციო კოდი არ არის მითითებული')
            if not record.employee_id and record.identification_number:
                warnings.add('მსგავსი საიდენთიფიკაციო კოდით თანამშრომელი ვერ მოიძებნა')
            record._compute_contract()
            if not record.earning_id:
                warnings.add('მსგავსი ანაზღაურების კოდი ვერ მოიძებნა')
            if not record.currency_id:
                warnings.add('მსგავსი ვალუტა ვერ მოიძებნა')

            if record.end_date and record.start_date > record.end_date:
                warnings.add('საწყისი თარიღი არ შეიძლება იყოს საბოლოო თარიღზე მეტი')
            not_allow_not_found_warning = False
            if record.is_exception:
                if record.contract_id and record.contract_id.state != 'close':
                    warnings.add('მითითებული კონტრაქტი არ არის დახურული')
                    not_allow_not_found_warning = True
            if not record.contract_id and not not_allow_not_found_warning:
                warnings.add('კონტრაქტის ჩანაწერი არ მოიძებნა')

            warnings |= set(self.check_date_and_contract(model=self._name, employee_id=record.employee_id).split('\n'))
            warnings |= set(self.check_date_and_contract(model='prx.payroll.position.earning',
                                                         employee_id=record.employee_id).split('\n'))
            record.error_text = '\n'.join(sorted(warnings))
            if not create:
                record.is_valid = not record.error_text

    def check_date_and_contract(self, employee_id, model):
        import_model = "prx.payroll.position.earning.import"
        text_warning = ''
        if employee_id:
            for record in self.env[model].search([('employee_id', '=', employee_id.id)]):
                if import_model == model and record.end_date and record.contract_id and record.contract_id.date_end:
                    if record.end_date > record.contract_id.date_end:
                        text_warning += "ჩანაწერის 'დასრულების თარიღი' ნაკლები უნდა იყოს კონტრაქტის 'დასრულების თარიღზე' \n"

                if record.end_date and record.start_date and record.start_date > record.end_date:
                    text_warning += 'კონტრაქტის საწყისი თარიღი ნაკლები უნდა იყსო კონტრაქტის დასრულების თარიღზე \n'
                domain = [
                    ('employee_id', '=', record.employee_id.id),
                    ('end_date', '=', False),
                    ('id', '!=', record.id)
                ]

                open_records = self.env[model].search(domain)
                if record.start_date and record.contract_id.date_start and record.start_date < record.contract_id.date_start:
                    text_warning += f'საწყისი თარიღი კონტრაქტის: {record.contract_id.name} საბოლოო თარიღზე ნაკლები ვერ იქნება.\n'
                for overlap in open_records:
                    if not overlap.end_date and not record.end_date:
                        if overlap.contract_id and record.contract_id and overlap.contract_id != record.contract_id:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს\n" if import_model != model else 'ჩანაწერი დუბლირდება\n'
                        if overlap.earning_id and record.earning_id and overlap.earning_id == record.earning_id:
                            text_warning += "ანაზღაურება უკვე არსებობს.\n" if import_model != model else 'ანაზღაურების ჩანაწერი დუბლირდება\n'
                    if record.end_date and overlap.start_date and overlap.contract_id != record.contract_id:
                        if not overlap.end_date and overlap.start_date >= record.end_date:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს\n" if import_model != model else 'ჩანაწერი დუბლირდება2\n'

                closed_records = self.env[model].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('contract_id', '=', record.contract_id.id),
                    ('id', '!=', record.id),
                    ('end_date', '!=', False),
                ])
                for overlap in closed_records:
                    if overlap.start_date and overlap.end_date and record.start_date:
                        if overlap.start_date <= record.start_date <= overlap.end_date and overlap.earning_id == record.earning_id:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს \n" if import_model != model else 'ჩანაწერი დუბლირდება\n'
                    if record.start_date and overlap.start_date and overlap.earning_id == record.earning_id:
                        if record.start_date <= overlap.start_date and not record.end_date:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს \n" if import_model != model else 'ჩანაწერი დუბლირდება\n'
                        if record.end_date and overlap.start_date >= record.end_date >= overlap.end_date:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს \n" if import_model != model else 'ჩანაწერი დუბლირდება\n'
                        if record.end_date and record.start_date <= overlap.start_date and record.end_date >= overlap.end_date:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს \n" if import_model != model else 'ჩანაწერი დუბლირდება\n'
                        if record.end_date and record.start_date <= overlap.start_date and record.end_date <= overlap.end_date:
                            text_warning += "მსგავსი ჩანაწერი უკვე არსებობს \n" if import_model != model else 'ჩანაწერი დუბლირდება\n'

        return text_warning
