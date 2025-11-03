from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from collections import defaultdict


def count_months_inclusive(d1, d2):
    """თვეების რაოდენობა (ინკლუზიურად): 2025-01..2025-01 => 1"""
    if not d1 or not d2:
        return 0
    if d1 > d2:
        d1, d2 = d2, d1  # უსაფრთხოება, რომ არ დაბრუნდეს 0 არასწორი მიმდევრობისას
    diff = relativedelta(d2, d1)
    return diff.years * 12 + diff.months + 1

class PRXPayrollEarningBonusWizard(models.TransientModel):
    _name = 'prx.payroll.earning.bonus.wizard'
    _description = 'Payroll Earning Bonus Wizard'

    start_period = fields.Many2one('prx.payroll.period', string="საწყიდი პერიოდი", required=True)
    end_period = fields.Many2one('prx.payroll.period', string="საბოლოო პერიოდი", required=True)
    accrual_date = fields.Date(string='დარიცხვის თარიღი', required=True)
    calc_type = fields.Selection([('transaction', 'ტრანზაციები'),
                                  ('tabel', 'ტაბელი'),
                                  ('earning', 'თანამშრომლის პოზიციის ანაზღაურება')],
                                 string='თანხის დაანგარიშების წყარო', required=True)
    bonus_value = fields.Float(string='ბონუსის კოეფიციენტი', default=1.0, required=True)
    bonus_category = fields.Many2one('prx.payroll.bonus.category', string='ბონუსის კატეგორია')
    earning_id = fields.Many2one('prx.payroll.earning', string='ანაზღაურების კოდი', required=True)
    bonus_salary = fields.Selection(
        [('month', 'გადაცემული თვეების მიხევით'), ('worked_month', 'ნამუშევარი თვეების მიხედვით')],
        string='ბონუსის დაანგარიშება',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_bonus_salary_type')
    )
    employee_ids = fields.Many2many('hr.employee', string="თანამშრომელი")

    @api.constrains("start_period", "end_period")
    def _check_period_range(self):
        for rec in self:
            if rec.start_period and rec.end_period:
                if rec.start_period.start_date > rec.end_period.start_date:
                    raise ValidationError("საწყისი პერიოდი ვერ იქნება საბოლოო პერიოდზე მეტი!")


    def create_bonus_line(self,
                          employee,
                          contract,
                          amount,
                          ):
        exception = False if contract.state == 'open' else True

        self.env['prx.payroll.position.earning'].create({
            'employee_id': employee.id,
            'contract_id': contract.id,
            'position_id': contract.job_id.id,
            'start_date': self.accrual_date,
            'end_date': self.accrual_date,
            'earning_id': self.earning_id.id,
            'currency_id': contract.company_id.currency_id.id,
            'amount': amount,
            'exception': exception
        })

    def generate_bonus(self):

        if not self.bonus_salary:
            raise UserError('მიუთითე ბონუსის დათვლის კონფიგურაცია')

        earning_model = self.env['prx.payroll.earning']
        prx_base_calculation = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_base_calculation')
        include_terminated = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_bonus_terminated_employee')
        employee_model = self.env['hr.employee']
        print("AQ SHEMOVIDA")
        if self.employee_ids:
            employees = self.employee_ids
        else:
            if include_terminated:
                employees = employee_model.search([])
            else:
                employees = employee_model.search([]).filtered(lambda e:e.contract_id.state == 'open')

        if self.bonus_category:
            employees = employees.filtered(lambda e: e.bonus_category == self.bonus_category)

        if not employees:
            raise UserError('თანამშრომელი ვერ მოიძებნა!')

        if self.calc_type == 'transaction':
            transactions = self.env['prx.payroll.transaction'].sudo().search(
                [
                    ('start_date', '>=', self.start_period.start_date),
                    ('end_date', '<=', self.end_period.end_date),
                    ('employee_id', 'in', employees.ids),
                    ('earning_id', 'in', earning_model.sudo().search([('bonus','=',True)]).ids),
                    ('position_earning_id','!=',False)
                ]
            )
            for emp in employees:
                emp_transactions = transactions.filtered(lambda e: e.employee_id == emp)
                if not emp_transactions:
                    continue
                bonus_multiply = count_months_inclusive(self.end_period.end_date, self.start_period.start_date) if self.bonus_salary == 'month' else len(set(emp_transactions.mapped('period_id').ids))
                amount = sum(emp_transactions.mapped('amount')) / bonus_multiply
                last_tx = emp_transactions.sorted('end_date', reverse=True)[:1][0] # ბოლო ტრანზაქციის კონტრაქტი მჭირდება
                contract = last_tx.position_earning_id.contract_id
                self.create_bonus_line(
                    employee=emp,
                    contract=contract,
                    amount=amount
                )

        if self.calc_type == 'tabel':
            period_ids = self.env['prx.payroll.period'].sudo().search([
                ('start_date', '>=', self.start_period.start_date),
                ('end_date', '<=', self.end_period.end_date),
            ])
            worksheets = self.env['prx.payroll.worksheet'].sudo().search([
                ('period_id', 'in', period_ids.ids),
                ('worker_id', 'in', employees.ids),
                ('status', 'in', ('closed', 'posted')),
            ])

            details = self.env['prx.payroll.worksheet.detail'].search([
                ('worksheet_id', 'in', worksheets.ids),
                ('earning_id', 'in',
                 self.env['prx.payroll.position.earning'].search([('employee_id','in',employees.ids)]).filtered(lambda e: e.earning_id.bonus == True).ids),
            ])
            tabel = details.mapped('worksheet_id')

            for emp in employees:
                emp_tabel = tabel.filtered(lambda e: e.worker_id == emp)
                if not emp_tabel:
                    continue
                bonus_salary = count_months_inclusive(self.end_period.end_date, self.start_period.start_date) if self.bonus_salary == 'month' else len(set(emp_tabel.mapped('period_id').ids))
                amount = sum(emp_tabel.mapped('worksheet_detail_ids.amount')) / bonus_salary
                if not amount:
                    continue
                contract = emp_tabel.mapped('worksheet_detail_ids.earning_id.contract_id').sorted('date_end', reverse=True)[:1][0]  # bolo kontraqtze minda gavide tabelebidan
                self.create_bonus_line(
                    employee=emp,
                    contract=contract,
                    amount=amount,
                )
        if self.calc_type == 'earning':
            print("SHENI DEDA")

            year = self.start_period.start_date.year
            position_earning = self.env['prx.payroll.position.earning'].sudo().search([('employee_id','in',employees.ids),
                                                                                       '|',
                                                                                       ('end_date','>',self.start_period.start_date),
                                                                                       ('end_date','=',False),
                                                                                       ('earning_id', 'in',earning_model.sudo().search([('bonus', '=',True)]).ids),
                                                                                       ])

            for emp in employees:
                emp_earning = position_earning.filtered(lambda s: s.employee_id == emp)
                need_earnings = self.env['prx.payroll.position.earning']
                for earn in emp_earning:
                    if earn.start_date.year == year or (earn.start_date.year != year and earn.end_date.year == year):
                        earning_months = self.get_earning_month(earn)
                        print(earning_months)
                        if not earning_months:
                            continue
                        need_earnings |= earn
                emp_need_earn = need_earnings.filtered(lambda d:d.employee_id == emp)
                if emp_need_earn:
                    bonus_salary = count_months_inclusive(self.end_period.end_date,self.start_period.start_date,) if self.bonus_salary == 'month' \
                        else len(set().union(*[self.get_earning_month(e) for e in emp_need_earn])) # ნამუშევარი თვეების რაოდენობა
                    amount = self.identity_bonus_amount(emp_need_earn)
                    print(amount,"Earning Amount Total",emp.name)
                    contract = self.env['hr.contract'].search([('employee_id','=',emp.id)],order='date_start desc, id desc', limit=1)
                    self.create_bonus_line(
                        employee=emp,
                        contract=contract,
                        amount=amount,
                    )
                    print(emp_need_earn,emp.name)
            # raise UserError("FUCK")

    def get_earning_month(self,earn):
        """ანაზღაუერბის თვეების რაოდება"""
        start_period = self.start_period
        end_period = self.end_period
        # თუ earn.start_date უფრო პატარაა, მაშინ ავიღოთ start_period.start_date
        start_m = max(earn.start_date, start_period.start_date).month

        if earn.end_date:
            # თუ ბოლომდე ცდება, მაშინ ავიღოთ end_period.end_date
            if earn.end_date > end_period.end_date:
                end_m = end_period.end_date.month
            else:
                end_m = earn.end_date.month
        else:
            # თუ საერთოდ არ აქვს end_date → ვსვამთ end_period.end_date
            end_m = end_period.end_date.month

        if start_m == end_m:
            return [start_m]
        print(list(range(start_m, end_m + 1)),"ANA")
        return list(range(start_m, end_m + 1))

    def _month_slices(self, rec):
        """ rec-ს ვჭრით თვეების მიხედვით და ვაბრუნებთ [(y,m,s,e), ...]
            s,e უკვე დაქლიპულია wizard-ის period-ით.
        """
        s = max(rec.start_date, self.start_period.start_date) if rec.start_date else self.start_period.start_date
        e = rec.end_date or self.end_period.end_date
        e = min(e, self.end_period.end_date)
        if s > e:
            return []

        cur = s.replace(day=1)
        last = e.replace(day=1)

        out = []
        while cur <= last:
            # ამ თვეს ბოლო დღე
            next_month = (cur + relativedelta(months=1)).replace(day=1)
            month_end = next_month - relativedelta(days=1)
            seg_start = max(s, cur)
            seg_end = min(e, month_end)
            out.append((cur.year, cur.month, seg_start, seg_end))
            cur = next_month
        return out

    def identity_bonus_amount(self, emp_need_earn):
        """
        თუ ჩანაწერი თვეებს სცდება, ვჭრით თვეებზე; თითო თვეზე ვირჩევთ start_earn ან end_earn ჩანაწერის amount-ს
        და საბოლოოდ ვთვლით საშუალოს თვეებზე.
        """
        prx_base_calculation = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_base_calculation')
        pick_first = (prx_base_calculation == 'start_earn')
        pick_last = (prx_base_calculation == 'end_earn')

        # 1) ვაგენერიროთ (y,m) -> იმ თვეში მყოფი რეალურად გადაფარული ჩანაწერები
        by_month = defaultdict(lambda: self.env['prx.payroll.position.earning'])
        for rec in emp_need_earn:
            for (y, m, seg_s, seg_e) in self._month_slices(rec):
                by_month[(y, m)] |= rec

        if not by_month:
            return 0.0

        # 2) თითო თვეზე ავიღოთ შესაბამისი ჩანაწერი (პირველი/ბოლო) start_date-ის მიხედვით
        month_amounts = []
        for (y, m), recs in by_month.items():
            # ამოიღე ვალიდური start_date-ები
            recs = recs.filtered(lambda r: r.start_date)
            if not recs:
                continue
            if pick_first:
                # მინიმალური start_date-ის ჩანაწერი
                smin = min(recs.mapped('start_date'))
                chosen = recs.filtered(lambda r: r.start_date == smin)[:1]
            elif pick_last:
                smax = max(recs.mapped('start_date'))
                chosen = recs.filtered(lambda r: r.start_date == smax)[:1]
            else:
                # დეფოლტად ავიღოთ ბოლო
                smax = max(recs.mapped('start_date'))
                chosen = recs.filtered(lambda r: r.start_date == smax)[:1]

            month_amounts.append(float(chosen.amount or 0.0) if chosen else 0.0)

        # 3) საშუალო თვეებზე (DB-ში არაფერი იწერება)
        if not month_amounts:
            return 0.0

        avg_amount = sum(month_amounts) / (float(len(month_amounts)) if self.bonus_salary == 'worked_month' else count_months_inclusive(self.end_period.end_date,self.start_period.start_date,))

        return avg_amount