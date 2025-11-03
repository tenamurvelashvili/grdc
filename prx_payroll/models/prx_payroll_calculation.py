import logging
from collections import defaultdict
from datetime import date

from odoo import models, fields, api
from odoo.exceptions import UserError
from .configuration.prx_enum_selection import SalaryType

_logger = logging.getLogger(__name__)


class PRXPayrollWorksheetCalculation(models.Model):
    _name = 'prx.payroll.worksheet.calculation'
    _description = 'Payroll worksheet calculation'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    period = fields.Many2one('prx.payroll.period', string='პერიოდი', compute="_get_period", readonly=False, store=True)
    worksheet = fields.Many2one('prx.payroll.worksheet', string='ტაბელი')
    calc_type = fields.Many2many('prx.calculation.type', string='კალკულაციის ტიპი')
    worksheet_domain = fields.Many2many('prx.payroll.worksheet', compute="_get_worksheet_domain")
    salary_type = fields.Selection(SalaryType.selection(), required=True, default='standard', string="პროცესის ტიპი")

    @api.depends('period')
    def _get_worksheet_domain(self):
        model = self.env['prx.payroll.worksheet'].search([('status', 'in', ('open', 'closed'))])
        domain = model.ids
        if self.period:
            domain = model.search([('period_id', '=', self.period.id)]).ids
        self.worksheet_domain = domain

    @api.depends('worksheet')
    def _get_period(self):
        self.period = self.worksheet.period_id.id or self.period.id

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.worksheet.sequence)

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
        employees_ids = [ids.id for ids in active_earning.mapped('employee_id')]

        have_tabel = self.env['prx.payroll.worksheet'].search(
            [('worker_id', 'in', employees_ids), ('period_id', '=', self.period.id),
             ('status', '=', 'open'), ('salary_type', '=', self.salary_type)])  # ვისაც აქვს ტაბელი იმასაც გადავატარებთ
        if not with_tabel and with_lines:
            # ვისაც აქვს ტაბელი იმას დავუგენერირებ ლაინებს
            for tab in have_tabel:
                tab.generate_worksheet()

        employee_without_worksheet = self.env['prx.payroll.worksheet'].search(
            [('worker_id', 'in', employees_ids), ('period_id', '=', self.period.id),
             ('salary_type', '=', self.salary_type)]).mapped('worker_id').ids

        employees = list(set(employees_ids) - set(employee_without_worksheet))  # ამ პერიოდზე ვისაც არაქვს ტაბელი
        if employees:
            if with_tabel:
                for emp in employees:
                    worksheet_id = self.env['prx.payroll.worksheet'].create(
                        {
                            'period_id': self.period.id,
                            'worker_id': emp,
                            'type': 'generated',
                            'salary_type': self.salary_type
                        }
                    )
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
                                                              ('worker_id', 'in',
                                                               need_employees.ids)]).document_close()  # ვხურავ ტაბელებს რომლებიც არ არის
                worksheet = self.env['prx.payroll.worksheet'].search(
                    [('status', '=', 'closed'), ('salary_type', '=', self.salary_type),
                     ('period_id', '=', self.period.id)])
                self.create_transaction(worksheet=worksheet)
            if self.worksheet:
                if self.worksheet.status != 'closed':
                    if not prx_close_tabel:
                        raise UserError("ტრანზაქციის გატარება შესაძლებელია 'დახურული' სტატუსის ტაბელზე. ")
                    else:
                        self.worksheet.document_close()
                self.create_transaction(worksheet=self.worksheet)

    def _prepare_transaction_vals(self, employee_id, amount, transaction_type, start_date, end_date, code=False,
                                  **kwargs):
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

    def create_transaction(self, worksheet):
        target_emp_ids = list({ws.worker_id.id for ws in worksheet.filtered(lambda d: d.transferred == False)})

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
        tr = self.env['prx.payroll.transaction'].search([('transferred', '=', False)])
        total_by_emp = defaultdict(float)
        tr.search([('worksheet_id', 'in', worksheet.ids), ('transferred', '=', False)]).unlink()

        vals_list = []
        for ws in worksheet.filtered(lambda d: d.transferred == False):
            for det in ws.worksheet_detail_ids:
                emp_id = ws.worker_id.id
                total_by_emp[emp_id] += det.amount
                vals_list.append(
                    self._prepare_transaction_vals(
                        employee_id=ws.worker_id.id,
                        amount=det.amount,
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
                        amount=-amt,
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
                                amount=amt * sign,
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
        amount_by_employee = self.compute_tax_base_by_employee(vals_list)
        non_rate_base_taxes = all_tax_ids.filtered(lambda t: t.tax.rate_base == 0.0)
        for tax in non_rate_base_taxes:
            emp = tax.employee_id.id
            if not employee_worksheet(emp):
                continue
            if total_by_emp.get(emp, 0.0):
                amt = amount_by_employee[emp] * tax.tax.rate_gross
                vals_list.append(
                    self._prepare_transaction_vals(
                        amount=-amt,
                        worksheet_id=employee_worksheet(emp),
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

        with_rate_base_taxes = all_tax_ids.filtered(lambda t: t.tax.rate_base != 0.0)
        for tax in with_rate_base_taxes:
            emp = tax.employee_id.id
            if not employee_worksheet(emp):
                continue
            current_year = date(fields.Date.today().year, 1, 1)
            tax_amount = 0.0
            if current_year >= tax.start_date:
                year_tax_amount = sum(tr.search([('start_date', '>=', tax.start_date), ('end_date', '<=', period_end),
                                                 ('include_tax_base', '=', True), ('employee_id', '=', emp)]).mapped(
                    'amount'))
            else:
                year_tax_amount = sum(tr.search([('start_date', '>=', current_year), ('end_date', '<=', period_end),
                                                 ('include_tax_base', '=', True), ('employee_id', '=', emp)]).mapped(
                    'amount'))

            #  TODO გადასახადების დაანგარიშებისას V1 იყო (year_tax_amount * tax.tax.rate_gross)  და (current_month_amount * tax.tax.rate_gross) შემდეგ ეს ლოგიკა ამოვიღეთ
            #  TODO ('worksheet_id','=',employee_worksheet(emp)) ეს დავამატე ბოლოს
            current_month_amount = sum(tr.search([('start_date', '>=', period_start), ('end_date', '<=', period_end),
                                                  ('worksheet_id', '=', employee_worksheet(emp)),
                                                  ('include_tax_base', '=', True), ('employee_id', '=', emp)]).mapped(
                'amount'))
            remining_limit = tax.tax.rate_base
            if tax.start_date >= current_year:
                remining_limit = tax.tax.rate_base - tax.used_tax_amount

            if year_tax_amount - remining_limit <= 0:
                tax_amount = 0.0
            elif year_tax_amount - remining_limit > 0:
                if year_tax_amount - remining_limit <= current_month_amount:
                    tax_amount = (year_tax_amount - remining_limit) * tax.tax.rate_gross
                else:
                    tax_amount = current_month_amount * tax.tax.rate_gross
            # print(f"თანამშრომელი <> {tax.employee_id.name} -- წლიური-{year_tax_amount} - თვიური გადასახადი - {current_month_amount} -- დარჩენილი ლიმიტი {remining_limit} -- გადასახადი ჯამური:{tax_amount}")
            vals_list.append(
                self._prepare_transaction_vals(
                    amount=-tax_amount,
                    worksheet_id=employee_worksheet(emp),
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

        ordered_vals = []
        not_reduces_income_tax_base = all_deduction_ids.filtered(lambda d: not d.deduction_id.reduces_income_tax_base
                                                                           and not d.deduction_id.avanse
                                                                           and not d.insurance_pension_linked_earning_id
                                                                 )

        def get_earning_codes():
            earning_code = [rec.link_insurance_ded.id for rec in
                            self.env['prx.payroll.earning'].search([('link_insurance_ded', '!=', False)])]
            return earning_code

        not_reduces_income_tax_base = not_reduces_income_tax_base.filtered(
            lambda d: d.deduction_id.id not in get_earning_codes())

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
                    amount=-amt,
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
        tr.create(vals_list)
        vals_list.clear()
        self.update_proportions_for_existing_transactions(worksheet)
        prx_pension_insurance = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_pension_insurance')
        if prx_pension_insurance:
            self.create_insurance_pension_deductions(worksheet=worksheet)
        return True

    def create_insurance_pension_deductions(self, worksheet):
        """Create pension deductions for EARNINGGs with insurance = True and pension_proportion > 0."""
        """დაზღვევის საპენსიოს ტრანზაქცია"""

        tr = self.env['prx.payroll.transaction'].search([('transferred', '=', False)])
        period_start = self.period.start_date
        period_end = self.period.end_date

        earnings = tr.search([
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False),
            ('pension_proportion', '<', 0.0),
            ('earning_id', '=',
             self.env['prx.payroll.earning'].search([('insurance', '=', True), ('link_insurance_ded', '!=', False)],
                                                    limit=1).id),
            ('period_id', '>=', self.period.id),
        ])
        # for earning in earnings.filtered(lambda d: not d.transferred):
        for earning in earnings:
            pension_amount = -abs(
                earning.amount * earning.position_earning_id.insurance_pension_deduction_id.percentage)
            if pension_amount:
                pension_vals = self._prepare_transaction_vals(
                    worksheet_id=earning.worksheet_id.id,
                    employee_id=earning.employee_id.id,
                    amount=pension_amount,
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

    def update_proportions_for_existing_transactions(self, worksheet):
        """Update tax and pension proportions for all EARNING transactions in worksheet."""
        pension_ids = self.env['prx.payroll.deduction'].search([('pension', '=', True)]).ids
        earnings = self.env['prx.payroll.transaction'].search([
            ('worksheet_id', 'in', worksheet.ids),
            ('transaction_type', '=', 'earning'),
            ('transferred', '=', False)
        ])

        for earning in earnings.filtered(lambda d: not d.transferred):
            base = earning.earning_proportion or 1.0

            # tax ჩანაწერები
            tax_amount = sum(self.env['prx.payroll.transaction'].search([
                ('employee_id', '=', earning.employee_id.id),
                ('worksheet_id', '=', earning.worksheet_id.id),
                ('transaction_type', '=', 'tax'),
                ('transferred', '=', False)
            ]).mapped('amount'))

            pension_amount = sum(self.env['prx.payroll.transaction'].search([
                ('employee_id', '=', earning.employee_id.id),
                ('worksheet_id', '=', earning.worksheet_id.id),
                ('transaction_type', '=', 'deduction'),
                ('deduction_id', 'in', pension_ids),
                ('transferred', '=', False)
            ]).mapped('amount'))

            earning.write({
                'tax_proportion': tax_amount * base,
                'pension_proportion': pension_amount * base,
            })
