from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from datetime import date, timedelta
import logging
from .configuration.prx_enum_selection import SalaryType
from pprint import pprint
_logger = logging.getLogger(__name__)


class PRXPayrollWorksheetCalculation(models.Model):
    _name = 'prx.payroll.worksheet.calculation'
    _description = 'Payroll worksheet calculation'
    _check_company_auto = True
    _rec_name = 'display_name'
    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    period = fields.Many2one('prx.payroll.period', string='პერიოდი', compute="_get_period", readonly=False, store=True)
    worksheet = fields.Many2one('prx.payroll.worksheet', string='ტაბელი')
    calc_type = fields.Many2many('prx.calculation.type', string='კალკულაციის ტიპი')
    worksheet_domain = fields.Many2many('prx.payroll.worksheet', compute="_get_worksheet_domain")
    salary_type = fields.Selection(SalaryType.selection(), required=True, default='standard', string="პროცესის ტიპი")

    @api.depends('period')
    def _get_worksheet_domain(self):
        model = self.env['prx.payroll.worksheet'].search([('status', 'in', ('open', 'closed'))])
        for rec in self:
            domain = model.ids
            if rec.period:
                domain = model.search([('period_id', '=', rec.period.id)]).ids
            rec.worksheet_domain = domain

    @api.depends('worksheet')
    def _get_period(self):
        for rec in self:
            if rec.worksheet:
                rec.period = rec.worksheet.period_id.id
            else:
                rec.period = rec.period

    def _compute_display_name(self):
        for rec in self:
            if rec.worksheet:
                rec.display_name = str(rec.worksheet.sequence or '')
            elif rec.period:
                rec.display_name = rec.period.display_name or ''
            else:
                rec.display_name = ''

    def generate_worksheet_lines(self):
        if self.worksheet and self.worksheet.status == 'open':
            self.worksheet.write({'period_id': self.period.id})
            self.worksheet.generate_worksheet()

    def create_worksheet(self, with_tabel=False, with_lines=False):
        active_earning = self.env['prx.payroll.position.earning'].search([
            ('start_date', '<=', self.period.end_date),
            '|',
            ('end_date', '>=', self.period.start_date),
            ('end_date', '=', False),
            ('salary_type', '=', self.salary_type),
        ])

        _logger.info(f"ACTIVE EARNING COUNT: {len(active_earning)}")

        employees_ids = [ids.id for ids in active_earning.mapped('employee_id')]
        _logger.info(f"EMPLOYEES IDS: {employees_ids}")

        have_tabel = self.env['prx.payroll.worksheet'].search(
            [('worker_id', 'in', employees_ids), ('period_id', '=', self.period.id),
             ('status', '=', 'open'), ('salary_type', '=', self.salary_type)])  # ვისაც აქვს ტაბელი იმასაც გადავატარებთ
        _logger.info(f"HAVE TABEL COUNT: {len(have_tabel)}")

        if not with_tabel and with_lines:
            # ვისაც აქვს ტაბელი იმას დავუგენერირებ ლაინებს
            for tab in have_tabel:
                tab.generate_worksheet()

        employee_without_worksheet = self.env['prx.payroll.worksheet'].search(
            [('worker_id', 'in', employees_ids), ('period_id', '=', self.period.id),
             ('salary_type', '=', self.salary_type)]).mapped('worker_id').ids
        
        _logger.info(f"EMPLOYEES WITHOUT WORKSHEET IDS: {employee_without_worksheet}")

        employees = list(set(employees_ids) - set(employee_without_worksheet))  # ამ პერიოდზე ვისაც არაქვს ტაბელი
        if employees:
            _logger.info(f"IN EMPLOYEES")
            if with_tabel:
                _logger.info(f"WITH TABEL")
                for emp in employees:
                    worksheet_id = self.env['prx.payroll.worksheet'].create(
                        {
                            'period_id': self.period.id,
                            'worker_id': emp,
                            'type': 'generated',
                            'salary_type': self.salary_type
                        }
                    )
                    _logger.info(f"WORKSHEET CREATED: {worksheet_id.id} FOR EMPLOYEE: {emp}")
                    if with_lines:
                        worksheet_id.generate_worksheet()

            if not with_tabel and with_lines:
                worksheet_ids = self.env['prx.payroll.worksheet'].search(
                    [('worker_id', 'in', employees), ('status', '=', 'open'), ('salary_type', '=', self.salary_type)])
                if worksheet_ids:
                    for worksheet_id in worksheet_ids:
                        worksheet_id.generate_worksheet()

    def execute_calculation(self):
        """'worksheet', 'worksheet_line', 'transaction'"""
        codes = set(self.calc_type.mapped('code'))

        if self.worksheet and self.period:
            if self.worksheet.period_id.id != self.period.id:
                raise UserError('ტაბელის გენერაცია ამ პერიოდში შეუძლებელია!')

        if {'worksheet', 'worksheet_line'}.issubset(codes):
            """ტაბელის და ლაინისების გენერაცია"""
            self.create_worksheet(with_tabel=True, with_lines=True)

        if codes == {'worksheet'}:
            """მხოლოდ ტაბელის გენერაცია"""
            self.create_worksheet(with_tabel=True)

        if self.worksheet and {'worksheet_line'}.issubset(codes):
            self.generate_worksheet_lines()
        if not self.worksheet and {'worksheet_line'}.issubset(codes):
            self.create_worksheet(with_tabel=False, with_lines=True)

        if 'transaction' in codes:
            prx_close_tabel = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_close_tabel')
            if self.period and not self.worksheet:
                if prx_close_tabel:
                    tabel_employees = self.env['prx.payroll.worksheet'].search([]).mapped('worker_id')
                    manager_line_employees = self.env['prx.payroll.worksheet.manager.line'].search([]).mapped(
                        'employee_id')
                    need_employees = tabel_employees.filtered(lambda emp: emp.id not in manager_line_employees.ids)
                    self.env['prx.payroll.worksheet'].search([('salary_type', '=', self.salary_type),
                                                              ('period_id', '=', self.period.id),
                                                              ('status', '=', 'open'),
                                                              ('worker_id','in',need_employees.ids)]).document_close() # ვხურავ ტაბელებს რომლებიც არ არის
                worksheet = self.env['prx.payroll.worksheet'].search([('status', '=', 'closed'), ('salary_type', '=', self.salary_type),
                                              ('period_id', '=', self.period.id)])
                self.create_transaction(worksheet=worksheet)
            if self.worksheet:
                if self.worksheet.status != 'closed':
                    if not prx_close_tabel:
                        raise UserError("ტრანზაქციის გატარება შესაძლებელია 'დახურული' სტატუსის ტაბელზე. ")
                    else:
                        self.worksheet.document_close()
                self.create_transaction(worksheet=self.worksheet)

    def _prepare_transaction_vals(self, employee_id, amount, transaction_type, start_date, end_date,code=False, **kwargs):
        return {
            'worksheet_id': kwargs.get('worksheet_id', None),
            'employee_id': employee_id,
            'period_id': kwargs.get('period_id', self.period.id),
            'code': code,
            'amount': amount,
            'transaction_type': transaction_type,
            'earning_id': kwargs.get('earning_id', False),
            'position_earning_id': kwargs.get('position_earning_id', False),
            'tax_id': kwargs.get('tax_id', False),
            'deduction_id': kwargs.get('deduction_id', False),
            'tax_proportion': kwargs.get('tax_proportion', 0.0),
            'pension_proportion': kwargs.get('pension_proportion', 0.0),
            'earning_proportion': kwargs.get('earning_proportion', 0.0),
            'include_tax_base': kwargs.get('include_tax_base', True),
            'start_date': start_date,
            'end_date': end_date,
            'earning_unit': kwargs.get('earning_unit', False),
            'qty': kwargs.get('qty', 0.0),
            'rate': kwargs.get('rate', 0.0),
            'exchange_rate': kwargs.get('exchange_rate', 0.0),
            'creditor': kwargs.get('creditor', False),
            'employee_tax_id': kwargs.get('employee_tax_id', False),
            'employee_deduction_id': kwargs.get('employee_deduction_id', False),
            'report_name': kwargs.get('report_name', ''),
        }

    @staticmethod
    def compute_tax_base_by_employee(vals_list):
        amounts_by_employee = defaultdict(float)
        for val in vals_list:
            if val.get('include_tax_base') and val.get('amount', 0):
                emp_id = val.get('employee_id')
                if emp_id:
                    amounts_by_employee[emp_id] += val['amount']

        return amounts_by_employee

    @staticmethod
    def _get_effective_pension_amount(pension_proportion):
        return abs(pension_proportion or 0.0)

    def _log_tax_base_summary(self, employee_bases, label):
        for employee_id, base_data in employee_bases.items():
            employee = self.env['hr.employee'].browse(employee_id)
            _logger.info(
                "TAX BASE SUMMARY [%s] employee=%s(%s) normal=%s no_material=%s adjustment=%s total=%s",
                label,
                employee.name,
                employee_id,
                base_data.get('normal', 0.0),
                base_data.get('no_material', 0.0),
                base_data.get('adjustment', 0.0),
                base_data.get('total', 0.0),
            )

    def _build_employee_tax_bases(self, transactions):
        employee_bases = defaultdict(lambda: {
            'normal': 0.0,
            'no_material': 0.0,
            'adjustment': 0.0,
            'total': 0.0,
        })

        for tx in transactions.filtered(lambda rec: rec.include_tax_base and rec.amount):
            emp_id = tx.employee_id.id
            if not emp_id:
                continue

            if tx.transaction_type != 'earning':
                employee_bases[emp_id]['adjustment'] += tx.amount
                employee_bases[emp_id]['total'] += tx.amount
                continue

            taxable_amount = tx.amount - self._get_effective_pension_amount(tx.pension_proportion)

            if tx.earning_id.no_material or tx.earning_id.no_material_without_tax:
                employee_bases[emp_id]['no_material'] += taxable_amount
            else:
                employee_bases[emp_id]['normal'] += taxable_amount

            employee_bases[emp_id]['total'] += taxable_amount
            
        _logger.info(f"COMPUTED EMPLOYEE TAX BASES: {dict(employee_bases)}")

        return employee_bases

    def _calculate_no_material_tax_base(self, employee_id, worksheet_id):
        earnings = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', '=', worksheet_id),
            ('employee_id', '=', employee_id),
            ('period_id', '=', self.period.id),
            ('transaction_type', '=', 'earning'),
            ('include_tax_base', '=', True),
            ('transferred', '=', False),
        ]).filtered(lambda tx: tx.amount and tx.earning_id and (tx.earning_id.no_material or tx.earning_id.no_material_without_tax))

        return sum(
            tx.amount - self._get_effective_pension_amount(tx.pension_proportion)
            for tx in earnings
        )

    def create_transaction(self, worksheet):
        target_emp_ids = list({ws.worker_id.id for ws in worksheet.filtered(lambda d:d.transferred == False)})

        def employee_worksheet(employee_id):
            domain_search = [
                ('period_id', '=', self.period.id),
                ('status', '=', 'closed'),
                ('worksheet_line_ids', '!=', False),
                ('worker_id', '=', employee_id),
                ('salary_type', '=', self.salary_type),
                ('transferred', '=', False),
            ]
            result = self.env['prx.payroll.worksheet'].search(domain_search, limit=1)
            return result.id if result else None

        period_start = self.period.start_date
        period_end = self.period.end_date
        TransactionModel = self.env['prx.payroll.transaction']
        TransactionModel.search([('worksheet_id', 'in', worksheet.ids),('transferred','=',False)]).unlink()
        tr = TransactionModel  # fresh model reference (no stale record IDs)
        total_by_emp = defaultdict(float)

        vals_list = []
        for ws in worksheet.filtered(lambda d: d.transferred==False):
            for det in ws.worksheet_detail_ids:
                emp_id = ws.worker_id.id
                total_by_emp[emp_id] += det.amount
                vals_list.append(
                    self._prepare_transaction_vals(
                        employee_id=ws.worker_id.id,
                        amount=self.math_round(det.amount),
                        code=det.earning_id.earning_id.earning,
                        transaction_type='earning',
                        start_date=det.period_id.start_date,
                        end_date=det.period_id.end_date,
                        worksheet_id=ws.id,
                        period_id=ws.period_id.id,
                        earning_id=det.earning_id.earning_id.id,
                        position_earning_id=det.earning_id.id,
                        earning_unit=det.earning_id.earning_id.earning_unit,
                        qty=det.quantity,
                        rate=det.rate,
                        exchange_rate=det.rate,
                        include_tax_base=True,
                        report_name=det.earning_id.earning_id.report_name,
                        tax_proportion=0.0,
                        pension_proportion=0.0,
                        earning_proportion=det.proportion,
                    ))
        if not vals_list:
            return None
        all_deduction_ids = self.env['prx.payroll.employee.deduction'].search(
            [
                ('employee_id', 'in', target_emp_ids),
                ('start_date', '<=', period_end),
                '|',
                ('end_date', '>=', period_start),
                ('end_date', '=', False)]

        )
        with_reduces_income_tax_base_and_avanse = all_deduction_ids.filtered(
            lambda d: d.deduction_id.reduces_income_tax_base or d.deduction_id.avanse)
        # აქ მინდა დავსორტო ავანსი და reduces_income_tax_base
        with_reduces_income_tax_base_sorted = sorted(
            with_reduces_income_tax_base_and_avanse,
            key=lambda d: (not d.deduction_id.avanse, not d.deduction_id.reduces_income_tax_base)
        )
        for ded in with_reduces_income_tax_base_sorted:
            emp = ded.employee_id.id
            ws_id = employee_worksheet(emp)
            if not ws_id:
                continue
            ws = self.env['prx.payroll.worksheet'].browse(ws_id)
            if ded.deduction_id.avanse and ws.salary_type != 'standard':
                # ავანსი მხოლოდ სტანდარტულ ტაბელზე დაგენერირდეს
                continue
            if ded.deduction_id.avanse:
                total_by_emp[emp] += - ded.amount

            is_one_time_ws = ws.salary_type in ['one_time', 'avanse']
            is_one_time_ded = ded.deduction_id.salary_type in ['one_time', 'avanse']

            if is_one_time_ws:
                if not is_one_time_ded and not ded.deduction_id.pension:
                    continue

            if ded.deduction_id.deduction_calc_type == 'fix_amount':
                amt = ded.amount
            else:
                amt = total_by_emp.get(emp, 0.0) * ded.percentage
            # თუ არაქვს ანაზღაურება არ აქვს დაქვითვა
            if total_by_emp.get(emp, 0.0):
                # საპენსიოს ტრანზაქციები
                vals_list.append(
                    self._prepare_transaction_vals(
                        worksheet_id=employee_worksheet(emp),
                        employee_id=emp,
                        amount=self.math_round(-amt),
                        code=ded.deduction_id.deduction,
                        transaction_type='deduction',
                        start_date=period_start,
                        end_date=period_end,
                        deduction_id=ded.deduction_id.id,
                        employee_deduction_id=ded.id,
                        creditor=ded.vendor.id if ded.vendor else False,
                        period_id=self.period.id,
                        include_tax_base=True,
                        report_name=ded.deduction_id.report_name,
                        tax_proportion=0.0,
                        pension_proportion=0.0,
                    ))
                if ded.deduction_id.pension:
                    for sign in (-1, 1):
                        vals_list.append(
                            self._prepare_transaction_vals(
                                worksheet_id=employee_worksheet(emp),
                                employee_id=emp,
                                amount=self.math_round(amt * sign),
                                transaction_type='company_pension',
                                start_date=period_start,
                                end_date=period_end,
                                creditor=ded.vendor.id if ded.vendor else False,
                                period_id=self.period.id,
                                include_tax_base=False,
                                tax_proportion=0.0,
                                pension_proportion=0.0,
                            )
                        )

        all_tax_ids = self.env['prx.payroll.employee.tax'].search(
            [
                ('employee_id', 'in', target_emp_ids),
                ('start_date', '<=', period_end),
                '|',
                ('end_date', '>=', period_start),
                ('end_date', '=', False)]
        )
        tr.create(vals_list)
        vals_list.clear()
        
        prx_pension_insurance = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_pension_insurance')
        if prx_pension_insurance:
            self.create_insurance_pension_deductions(worksheet=worksheet)
            _logger.info(f"CREATED INSURANCE PENSION DEDUCTIONS FOR WORKSHEET")
        self.update_proportions_for_existing_transactions(worksheet)
        _logger.info(f"UPDATED PROPORTIONS FOR EXISTING TRANSACTIONS FOR WORKSHEET")
        

        taxable_transactions = tr.search([
            ('employee_id', 'in', target_emp_ids),
            ('period_id', '=', self.period.id),
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False),
        ])
        employee_tax_bases = self._build_employee_tax_bases(taxable_transactions)
        self._log_tax_base_summary(employee_tax_bases, label='current_period_taxable_transactions')

        non_rate_base_taxes = all_tax_ids.filtered(lambda t: t.tax.rate_base == 0.0)
        _logger.info(f"NON RATE BASE TAXES COUNT: {len(non_rate_base_taxes)}")
        _logger.info(f"NON RATE BASE TAXES: {pprint(non_rate_base_taxes.mapped('tax.tax'))}")
        for tax in non_rate_base_taxes:
            emp = tax.employee_id.id
            ws_id = employee_worksheet(emp)
            if not ws_id:
                continue
            employee_base = employee_tax_bases.get(emp, {})
            total_taxable_amount = (
                employee_base.get('normal', 0.0)
                + employee_base.get('no_material', 0.0)
                + employee_base.get('adjustment', 0.0)
            )
            if total_by_emp.get(emp, 0.0):
                # If there are earnings marked with `no_material_without_tax`, calculate
                # non-rate-base taxes per-earning as (earning - pension_proportion) * gross_rate
                if self._earning_no_material_check():
                    emp_taxable_transactions = taxable_transactions.filtered(
                        lambda tr: tr.employee_id.id == emp and tr.transaction_type == 'earning' and tr.include_tax_base and not tr.transferred
                    )
                    tax_amount = sum(
                        max(0.0, tx.amount - self._get_effective_pension_amount(tx.pension_proportion)) * tax.tax.rate_gross
                        for tx in emp_taxable_transactions
                    )
                    
                    _logger.info(f"NON RATE BASE TAXES FOR EMPLOYEE {emp}: {[(tx.id, tx.amount) for tx in emp_taxable_transactions]}")
                else:
                    tax_amount = total_taxable_amount * tax.tax.rate_gross
                    _logger.info(f"MATERIAL NO NON RATE BASE TAX FOR EMPLOYEE {emp}: total_taxable_amount={total_taxable_amount} tax_rate={tax.tax.rate_gross} calculated_tax_amount={tax_amount}")

                _logger.info(
                    "NON RATE TAX employee=%s(%s) tax=%s normal=%s no_material=%s adjustment=%s total_taxable=%s gross_rate=%s tax_amount=%s",
                    tax.employee_id.name,
                    emp,
                    tax.tax.tax,
                    employee_base.get('normal', 0.0),
                    employee_base.get('no_material', 0.0),
                    employee_base.get('adjustment', 0.0),
                    total_taxable_amount,
                    tax.tax.rate_gross,
                    tax_amount,
                )
                vals_list.append(
                    self._prepare_transaction_vals(
                        amount= -self.math_round(tax_amount),
                        worksheet_id=ws_id,
                        employee_id=emp,
                        include_tax_base=False,
                        code=tax.tax.tax,
                        transaction_type='tax',
                        start_date=period_start,
                        end_date=period_end,
                        tax_id=tax.tax.id,
                        employee_tax_id=tax.id,
                        period_id=self.period.id,
                        report_name=tax.tax.report_name,
                        tax_proportion=0.0,
                        pension_proportion=0.0,
                    ))
        _logger.info(f"PREPARED TAX TRANSACTIONS FOR EMPLOYEES: {[tax.employee_id.name for tax in non_rate_base_taxes]}")

        with_rate_base_taxes = all_tax_ids.filtered(lambda t: t.tax.rate_base != 0.0)
        tax_proportion_plans = []
        self._add_not_material_tax_to(worksheet)
        for tax in with_rate_base_taxes:
            emp = tax.employee_id.id
            ws_id = employee_worksheet(emp)
            if not ws_id:
                continue
            employee_base = employee_tax_bases.get(emp, {})
            normal_current_amount = employee_base.get('normal', 0.0) + employee_base.get('adjustment', 0.0)
            no_material_current_amount = self._calculate_no_material_tax_base(emp, ws_id)
            current_year = period_start.replace(month=1, day=1)
            tax_amount = 0.0
            year_tax_amount = 0.0
            # if current_year >= tax.start_date:
            #     year_tax_amount = sum(tr.search([('start_date', '>=', tax.start_date), ('end_date', '<=', period_end),
            #                                          ('include_tax_base', '=', True), ('employee_id', '=', emp)]).mapped('amount'))
            if current_year.year > tax.start_date.year or (current_year.year <= tax.start_date.year and self._has_previously_used_limit(emp, tax.start_date)): 
                _logger.info("""
                            CURRENT YEAR {} -
                            TAX START DATE {} -
                            PERIOD END {} -
                            
                            CALCULATING YEAR TAX AMOUNT FOR EMPLOYEE {}
                             
                             """.format(current_year, tax.start_date, period_end, tax.employee_id.name))
                year_tax_transactions = tr.search([
                    ('start_date', '>=', current_year),
                    ('end_date', '<=', period_end),
                    ('include_tax_base', '=', True),
                    ('employee_id', '=', emp),
                    ('transferred', '=', False),
                ])
                year_tax_base = self._build_employee_tax_bases(year_tax_transactions)[emp]
                _logger.info(f"YEAR TAX BASE FOR EMPLOYEE {tax.employee_id.name} is {year_tax_base} based on transactions: {year_tax_transactions.ids}")
                year_tax_amount = year_tax_base['normal']
                _logger.info(f"YEAR TAX AMOUNT FOR EMPLOYEE {tax.employee_id.name} is {year_tax_amount} based on year tax base {year_tax_amount}")
            
            elif current_year <= tax.start_date and not self._has_previously_used_limit(emp, tax.start_date):
                #calculate tax from that month (means that was not used during the year)
                _logger.info("CORRECTLY CALLED THIS BUSHIT")
                year_tax_transactions = tr.search([ 
                    ('start_date', '>=', tax.start_date),
                    ('end_date', '<=', period_end),
                    ('include_tax_base', '=', True),
                    ('employee_id', '=', emp)])
                
                year_tax_base = self._build_employee_tax_bases(year_tax_transactions)[emp]
                _logger.info(f"YEAR TAX BASE FOR EMPLOYEE {tax.employee_id.name} (using previous transactions since tax start date) is {year_tax_base} based on transactions: {year_tax_transactions.ids}")
                
                year_tax_amount = year_tax_base['normal']
                _logger.info(f"YEAR TAX AMOUNT FOR EMPLOYEE {tax.employee_id.name} is {year_tax_amount} based on year tax base {year_tax_amount}")

            else:
                year_tax_amount = 0.0
            
            #  TODO გადასახადების დაანგარიშებისას V1 იყო (year_tax_amount * tax.tax.rate_gross)  და (current_month_amount * tax.tax.rate_gross) შემდეგ ეს ლოგიკა ამოვიღეთ
            #  TODO ('worksheet_id','=',employee_worksheet(emp)) ეს დავამატე ბოლოს
            current_month_amount = normal_current_amount
            _logger.info(f"CURRENT MONTH AMOUNT FOR EMPLOYEE {tax.employee_id.name} is {current_month_amount} based on normal_current_amount {normal_current_amount}")
            
            remining_limit = tax.tax.rate_base
            _logger.info(f"INITIAL REMAINING LIMIT for EMPLOYEE {tax.employee_id.name} is {remining_limit} based on tax.rate_base {tax.tax.rate_base}")
            normal_tax_amount = 0.0
            no_material_tax_amount = no_material_current_amount * tax.tax.rate_gross
            if tax.start_date.year >= current_year.year:
                remining_limit = tax.tax.rate_base - tax.used_tax_amount
            
            #TODO არ შეეხო
            #ᲒᲐᲓᲐᲡᲐᲮᲐᲓᲘᲡ ᲬᲘᲚᲘᲡᲛᲐᲤᲓᲔᲘᲗᲘ (ᲪᲐᲚᲙᲔ)
            if year_tax_amount - remining_limit <= 0:
                normal_tax_amount = 0.0
            elif year_tax_amount - remining_limit > 0:
                if year_tax_amount - remining_limit <= current_month_amount:
                    #TODO აქ ის ზემოდან მაღლა ლოგიკა
                    normal_tax_amount = (year_tax_amount - remining_limit) * tax.tax.rate_gross
                    _logger.info(f"YEAR TAX AMOUNT {year_tax_amount} has exceeded the remaining limit {remining_limit} for EMPLOYEE {tax.employee_id.name}, applying tax to the exceeded amount: {year_tax_amount - remining_limit}")
                else:
                    #TODO პროპორციეციულად
                    normal_tax_amount = current_month_amount * tax.tax.rate_gross
                    _logger.info(f"YEAR TAX AMOUNT {year_tax_amount} has exceeded the remaining limit {remining_limit} for EMPLOYEE {tax.employee_id.name}, but the exceeded amount is greater than current month amount {current_month_amount}, applying tax to the entire current month amount")

            tax_amount = normal_tax_amount + no_material_tax_amount
            # print(f"თანამშრომელი <> {tax.employee_id.name} -- წლიური-{year_tax_amount} - თვიური გადასახადი - {current_month_amount} -- დარჩენილი ლიმიტი {remining_limit} -- გადასახადი ჯამური:{tax_amount}")

            _logger.info(f"APPENDED: {tax_amount}")
            
            tax_proportion_plans.append({
                'employee_id': emp,
                'worksheet_id': ws_id,
                'tax_rate': tax.tax.rate_gross,
                'year_tax_amount': year_tax_amount,
                'remaining_limit': remining_limit,
                'current_month_amount': current_month_amount,
            })
            _logger.info(f"TAX PROPORTION PLANS APPENDED: {tax_proportion_plans[-1]}")
            vals_list.append(
                self._prepare_transaction_vals(
                    amount=self.math_round(-tax_amount),
                    worksheet_id=ws_id,
                    employee_id=emp,
                    include_tax_base=False,
                    code=tax.tax.tax,
                    transaction_type='tax',
                    start_date=period_start,
                    end_date=period_end,
                    tax_id=tax.tax.id,
                    employee_tax_id=tax.id,
                    period_id=self.period.id,
                    report_name=tax.tax.report_name,
                    tax_proportion=0.0,
                    pension_proportion=0.0,
                ))
        tr.create(vals_list)
        vals_list.clear()
        self.update_proportions_for_existing_transactions(worksheet,pension_update=False, has_no_material_without_tax= self._earning_no_material_check())  
        _logger.info(f"TAX PROPORTION: {tax_proportion_plans}")


        
        if tax_proportion_plans:
            #TODO აქ რაცხა წავშალე რო რამე ვაბრუნებ
            # New distribution is only for employees that have rate_base taxes.
            self._apply_tax_proportion_by_code_distribution(tax_proportion_plans)
        else:
            # Keep old logic when no rate_base tax is configured.
            _logger.info("NO RATE BASE TAX FOUND, KEEPING OLD TAX PROPORTION LOGIC")
        _logger.info(f"UPDATED PROPORTIONS AFTER TAX TRANSACTIONS FOR WORKSHEET")
        ordered_vals = []
        not_reduces_income_tax_base = all_deduction_ids.filtered(lambda d: not d.deduction_id.reduces_income_tax_base
                                                                           and not d.deduction_id.avanse
                                                                           and not d.insurance_pension_linked_earning_id
                                                                 )

        def get_earning_codes():
            earning_code = [rec.link_insurance_ded.id for rec in self.env['prx.payroll.earning'].search([('link_insurance_ded','!=',False)])]
            return earning_code

        not_reduces_income_tax_base = not_reduces_income_tax_base.filtered(lambda d: d.deduction_id.id not in get_earning_codes())

        for ded in not_reduces_income_tax_base:
            emp = ded.employee_id.id
            ws_id = employee_worksheet(emp)
            if not ws_id:
                continue

            ws = self.env['prx.payroll.worksheet'].browse(ws_id)
            is_one_time_ws = ws.salary_type in ['one_time', 'avanse']
            is_one_time_ded = ded.deduction_id.salary_type in ['one_time', 'avanse']

            if is_one_time_ws:
                if not is_one_time_ded and not ded.deduction_id.pension:
                    continue

            if ded.deduction_id.deduction_calc_type == 'fix_amount':
                amt = ded.amount
            else:
                # პროცენტულს აქ ვითვლი დაქვითვას
                if ded.deduction_id.deduction_base == 'net_amount':
                    # net_amount
                    domain = [
                        ('period_id', '=', self.period.id),
                        ('employee_id', '=', emp),
                        '|',
                        ('include_tax_base', '=', True),
                        ('transaction_type', '=', 'tax'),
                    ]
                # gross_amount
                else:
                    domain = [
                        ('period_id', '=', self.period.id),
                        ('employee_id', '=', emp),
                        ('transaction_type', '=', 'earning'),
                    ]

                percentage_amount = sum(tr.search(domain).mapped('amount'))

                amt = percentage_amount * ded.percentage

            if total_by_emp.get(emp, 0.0):
                vals = self._prepare_transaction_vals(
                    worksheet_id=ws_id,
                    employee_id=emp,
                    amount=self.math_round(-amt),
                    code=ded.deduction_id.deduction,
                    transaction_type='deduction',
                    start_date=period_start,
                    end_date=period_end,
                    deduction_id=ded.deduction_id.id,
                    employee_deduction_id=ded.id,
                    creditor=ded.vendor.id if ded.vendor else False,
                    period_id=self.period.id,
                    include_tax_base=False,
                    report_name=ded.deduction_id.report_name,
                    tax_proportion=0.0,
                    pension_proportion=0.0,
                )
                ordered_vals.append((ded.deduction_id.deduction_order or 0, vals))
        ordered_vals.sort(key=lambda x: x[0])
        vals_list.extend(vals for _, vals in ordered_vals)
        # აქ დალაგებული არის deduction_order მიხედვით და ამის მიხედვით მოხდება ჩანაწერების შექმნა რაღაც დონეზე
        _logger.info(f"CREATING DEDUCTION TRANSACTIONS FOR EMPLOYEES: {[ded.employee_id.name for ded in not_reduces_income_tax_base]} with ordered vals: {ordered_vals}")
        tr.create(vals_list)
        vals_list.clear()

        for ws in worksheet:
            if ws.salary_type == "avanse" and self.has_avanse_worksheet(ws.worker_id, ws.period_id):
                _logger.info(f"CALLED TRANSACTION {ws.sequence}")
                self.flip_transactions(ws)

        return True

    def create_insurance_pension_deductions(self, worksheet):
        """Create pension deductions for EARNINGGs with insurance = True and pension_proportion > 0."""
        """დაზღვევის საპენსიოს ტრანზაქცია"""

        tr = self.env['prx.payroll.transaction']
        period_start = self.period.start_date
        period_end = self.period.end_date

        earnings = tr.search([
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False),
            ('pension_proportion', '<', 0.0),
            ('earning_id', '=', self.env['prx.payroll.earning'].search([('insurance','=',True),('link_insurance_ded','!=',False)],limit=1).id),
            ('period_id', '>=', self.period.id),
        ])
        for earning in earnings.filtered(lambda d:not d.transferred):
            pension_amount = -abs(self.math_round(earning.amount) * earning.position_earning_id.insurance_pension_deduction_id.percentage)
            if pension_amount:
                pension_vals = self._prepare_transaction_vals(
                    worksheet_id=earning.worksheet_id.id,
                    employee_id=earning.employee_id.id,
                    amount= self.math_round(pension_amount),
                    code=earning.earning_id.link_insurance_ded.deduction,
                    transaction_type='deduction',
                    start_date=period_start,
                    end_date=period_end,
                    deduction_id=earning.earning_id.link_insurance_ded.id,
                    employee_deduction_id=earning.position_earning_id.insurance_pension_deduction_id.id,
                    creditor=False,
                    period_id=self.period.id,
                    include_tax_base=False,
                    report_name=earning.earning_id.link_insurance_ded.report_name or '',
                    tax_proportion=0.0,
                    pension_proportion=0.0,
                    earning_id=False,
                )
                tr.create(pension_vals)

    def math_round(self, number, places=2):
        format_str = '0.1' if places == 0 else '0.' + '1'.zfill(places)
        return Decimal(str(number)).quantize(Decimal(format_str), rounding=ROUND_HALF_UP)

    def update_proportions_for_existing_transactions(self, worksheet, pension_update=True, has_no_material_without_tax=False):
        """Update tax and pension proportions for all EARNING transactions in worksheet."""
        pension_ids = self.env['prx.payroll.deduction'].search([('pension', '=', True)]).ids
        earnings = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False)
        ])

        for earning in earnings.filtered(lambda d:not d.transferred):
            base = earning.earning_proportion or 1.0

            # tax ჩანაწერები
            tax = self.env['prx.payroll.transaction'].search([
                ('employee_id', '=', earning.employee_id.id),
                ('worksheet_id', '=', earning.worksheet_id.id),
                ('transaction_type', '=', 'tax'),
                ('transferred', '=', False)
            ])
            gross_rate = tax.tax_id.rate_gross 
            _logger.info(f"GROSS_RATE: {gross_rate} for tax transactions {tax.ids} of employee {earning.employee_id.name}")
            
            tax_amount = self.math_round(sum(tax.mapped('amount')))

            pension_amount = sum(self.env['prx.payroll.transaction'].search([
                ('employee_id', '=', earning.employee_id.id),
                ('worksheet_id', '=', earning.worksheet_id.id),
                ('transaction_type', '=', 'deduction'),
                ('deduction_id', 'in', pension_ids),
                ('transferred', '=', False)
            ]).mapped('amount'))

            has_rate_base = self.env['prx.payroll.employee.tax'].search_count([
                ('employee_id', '=', earning.employee_id.id),
                ('start_date', '<=', earning.worksheet_id.period_id.end_date),
                '|', ('end_date', '>=', earning.worksheet_id.period_id.start_date), ('end_date', '=', False),
                ('tax.rate_base', '!=', 0.0)
            ]) > 0
            
            if has_rate_base:
                _logger.info(f"UPDATING PROPORTIONS FOR EARNING {earning.id} with base {base}, tax_amount {tax_amount}, pension_amount {pension_amount}")
                earning.write({
                    'tax_proportion': tax_amount,
                    'pension_proportion':  self.math_round(float(self.math_round(pension_amount,)) * base if pension_update else earning.pension_proportion),
                })
            else:
                _logger.info(f"UPDATING PROPORTIONS FOR EARNING {earning.id} WITHOUT RATE BASE TAX, setting tax_proportion to 0 and pension_proportion to {pension_amount * base}")
                earning.write({
                    'tax_proportion': -(float(tax_amount )* base if not has_no_material_without_tax else (earning.amount - abs(earning.pension_proportion)) * gross_rate),
                    'pension_proportion':float(self.math_round(pension_amount,)) * base if pension_update else earning.pension_proportion,
                })

    def _add_not_material_tax_to(self, worksheet):
        earnings = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False)
        ])

        by_employee = defaultdict(lambda: self.env['prx.payroll.transaction'])
        for earning in earnings:
            by_employee[earning.employee_id.id] |= earning

        for employee_id, emp_earnings in by_employee.items():
            
            no_material_taxes = emp_earnings.filtered(lambda tx: tx.earning_id and tx.earning_id.no_material_without_tax)
            
            no_material_pension = sum(
                no_material_taxes
                .mapped('pension_proportion')
            )
            
            no_material_taxes.write({'pension_proportion': 0.0})

            if not no_material_pension:
                continue

            lowest = sorted(
                emp_earnings,
                key=lambda tx: tx.earning_id.code if tx.earning_id else '',
            )[0]

            _logger.info(f"EMPLOYEE {employee_id} - lowest code: {lowest.earning_id.code}, adding no_material_pension: {no_material_pension}")

            lowest.write({
                'pension_proportion': lowest.pension_proportion + no_material_pension
            })
        
    def _calculate_tax_proportion_distribution(
        self,
        employee_id,
        worksheet_id,
        tax_rate,
        year_tax_amount,
        remaining_limit,
        current_month_amount,
    ):
        """Return mapping {earning_tx_id: negative_tax_amount} for normal earnings only."""
        distributions = {}
        exceeded_amount = year_tax_amount - remaining_limit

        earning_transactions = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', '=', worksheet_id),
            ('employee_id', '=', employee_id),
            ('period_id', '=', self.period.id),
            ('transaction_type', '=', 'earning'),
            ('include_tax_base', '=', True),
            ('transferred', '=', False),
        ]).filtered(lambda tx: tx.amount > 0.0 and not (tx.earning_id.no_material or tx.earning_id.no_material_without_tax))

        sorted_earnings = sorted(
            earning_transactions,
            key=lambda tx: tx.earning_id.code if tx.earning_id else '',
            reverse=True,
        )
        
        _logger.info(f"EARNINGS: {[earning.earning_id.code for earning in sorted_earnings]}")
        
        _logger.info(f'FUCKASS DISTRIBUTION FOR {employee_id}')

        # Case 1: no tax on normal earnings
        if exceeded_amount <= 0:
            return distributions

        # Case 2: apply tax by earning code order (DESC)
        if exceeded_amount <= current_month_amount:
            remaining_to_allocate = exceeded_amount
            for tx in sorted_earnings:
                if remaining_to_allocate <= 0:
                    break
                taxable_tx_amount = max(
                    0.0,
                    tx.amount - self._get_effective_pension_amount(tx.pension_proportion)
                )
                allocated = min(taxable_tx_amount, remaining_to_allocate)
                if allocated > 0:
                    distributions[tx.id] = distributions.get(tx.id, 0.0) - (allocated * tax_rate)
                    remaining_to_allocate -= allocated
            return distributions

        # Case 3: tax all normal earnings fully
        for tx in sorted_earnings:
            taxable_tx_amount = max(
                0.0,
                tx.amount - self._get_effective_pension_amount(tx.pension_proportion)
            )
            distributions[tx.id] = distributions.get(tx.id, 0.0) - (taxable_tx_amount * tax_rate)

        return distributions

    def _apply_tax_proportion_by_code_distribution(self, tax_proportion_plans):
        """Apply custom tax_proportion distribution without changing original tax amount cases."""
        if not tax_proportion_plans:
            return

        grouped_plans = defaultdict(list)
        
        _logger.info(f"GROUPING TAX PROPORTION PLANS BY EMPLOYEE AND WORKSHEET")
        for plan in tax_proportion_plans:
            key = (plan['employee_id'], plan['worksheet_id'])
            grouped_plans[key].append(plan)
        
        _logger.info(f"TAX PROPORTION PLANS: {grouped_plans}");

        for (employee_id, worksheet_id), plans in grouped_plans.items():
            earnings = self.env['prx.payroll.transaction'].search([
                ('worksheet_id', '=', worksheet_id),
                ('employee_id', '=', employee_id),
                ('period_id', '=', self.period.id),
                ('transaction_type', '=', 'earning'),
                ('include_tax_base', '=', True),
                ('transferred', '=', False),
            ]).filtered(lambda tx: tx.amount > 0.0 and tx.earning_id)

            normal_earnings = earnings.filtered(lambda tx: not (tx.earning_id.no_material or tx.earning_id.no_material_without_tax))
            no_material_earnings = earnings.filtered(lambda tx: tx.earning_id.no_material or tx.earning_id.no_material_without_tax)

            if not earnings:
                continue

            # reset earning tax proportions and recalculate by custom distribution
            earnings.write({'tax_proportion': 0.0})

            aggregated = defaultdict(float)
            _logger.info(f"PLANS: {plans} FOR EMPLOYEE {employee_id} IN WORKSHEET {worksheet_id}")
            for plan in plans:
                dist = self._calculate_tax_proportion_distribution(
                    employee_id=plan['employee_id'],
                    worksheet_id=plan['worksheet_id'],
                    tax_rate=plan['tax_rate'],
                    year_tax_amount= plan['year_tax_amount'],
                    remaining_limit=plan['remaining_limit'],
                    current_month_amount=plan['current_month_amount'],
                )
                for tx_id, amount in dist.items():
                    aggregated[tx_id] += amount

                # no_material earnings are always taxed directly on (amount - pension) * rate
                for tx in no_material_earnings:
                    taxable_tx_amount = max(
                        0.0,
                        tx.amount -  self._get_effective_pension_amount(tx.pension_proportion) 
                    )
                    aggregated[tx.id] += -(taxable_tx_amount * plan['tax_rate'])

            for tx in normal_earnings:
                tx.write({'tax_proportion': aggregated.get(tx.id, 0.0)})

            for tx in no_material_earnings:
                tx.write({'tax_proportion': aggregated.get(tx.id, 0.0)})

    def _has_previously_used_limit(self, employee_id, start_date):
        tr = self.env['prx.payroll.transaction']
        #find if employee has base_rate not 0 in previous month
        transactions = tr.search([
            ('employee_id', '=', employee_id),
            ('end_date', '<', start_date - timedelta(days=1)),
            ('tax_id', '!=', False),
        ], limit=1)#
        
        for tr in transactions:
            if tr.tax_id and tr.tax_id.rate_base and tr.tax_id.rate_base != 0.0:
                return True
            
        return False
    
    def _earning_no_material_check(self):
        earning = self.env['prx.payroll.earning'].search([('no_material_without_tax', '=', True)], limit=1).exists()
        return earning

    def has_avanse_worksheet(self, emp_id, period_id):
        return self.env['prx.payroll.worksheet'].search([
            ("worker_id",'=',emp_id.id),
            ('period_id', '=', period_id.id),
            ('salary_type', '=', 'avanse')
        ]).exists()

    def flip_transactions(self, worksheet):
        _logger.info(f"FLIPPING TRANSACTIONS FOR WORKSHEET {worksheet.sequence}")
        transactions = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', '=', worksheet.id),
        ])
        _logger.info(f"FLIPPING TRANSACTIONS: {transactions}")
        for transaction in transactions:
            transaction.write({'amount': -transaction.amount,
                               'tax_proportion': -transaction.tax_proportion,
                               'pension_proportion': -transaction.pension_proportion,
                               'exchange_rate': -transaction.exchange_rate,
                               })