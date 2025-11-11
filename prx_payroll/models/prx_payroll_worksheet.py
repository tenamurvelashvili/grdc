from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from .configuration.prx_enum_selection import WorksheetType, WorksheetStatus, SalaryType
from datetime import date
from calendar import monthrange


class PRXPayrollWorksheet(models.Model):
    _name = 'prx.payroll.worksheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll worksheet'
    _rec_name = 'sequence'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    active = fields.Boolean(default=True)
    transferred = fields.Boolean(string="გადარიცხულია")
    sequence = fields.Char(string="დოკ.ნომერი", readonly=True, default='New')
    worker_id = fields.Many2one('hr.employee', string='თანამშრომელი', required=True)
    period_id = fields.Many2one('prx.payroll.period', string='პერიოდი', required=True)
    status = fields.Selection(WorksheetStatus.selection(), string="სტატუსი", default='open')
    type = fields.Selection(WorksheetType.selection(), string='ტიპი', default='generated_by_user')
    note = fields.Text(string='კომენტარი')
    worksheet_line_ids = fields.One2many('prx.payroll.worksheet.line', 'worksheet_id', string="დეტალები")
    worksheet_detail_ids = fields.One2many('prx.payroll.worksheet.detail', 'worksheet_id', string="ანაზღაურება")
    readonly_worksheet = fields.Boolean(compute='_readonly_fields')
    cost_line_ids = fields.One2many('prx_payroll.worksheet.cost.line', 'worksheet_id', string="დეტალები")
    salary_type = fields.Selection(SalaryType.selection(), required=True, default='standard', string="პროცესის ტიპი")

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('sequence', operator, name), ('worker_id', operator, name)]
        records = self.search(domain + args, limit=limit)
        return records.name_get()

    def name_get(self):
        result = []
        for rec in self:
            label = f"{rec.sequence} - {rec.worker_id.name} - {rec.period_id.period}"
            result.append((rec.id, label))
        return result

    @api.constrains('period_id', 'worker_id')
    def _check_period_id(self):
        for rec in self:
            if not rec.period_id or not rec.worker_id:
                continue
            domain = [
                ('period_id', '=', rec.period_id.id),
                ('worker_id', '=', rec.worker_id.id),
                ('id', '!=', rec.id),
                ('salary_type', '=', rec.salary_type)
            ]
            existing = self.search(domain, limit=1)
            if existing:
                raise ValidationError(f'{rec.worker_id.name}, ამ პერიოდზე ტაბელი {rec.sequence} უკვე არსებობს!')

    def unlink(self):
        not_open = self.filtered(lambda ws: ws.status != 'open')
        if not_open:
            raise UserError("ტაბელის წაშლა შესაძლებელი არის სტატუსზე: 'ღია'")
        for rec in self:
            if rec.transferred:
                raise UserError("გადარიცხული ტრანზაქციის წაშლა შეუძლებელია!")
            tx_exists = self.env['prx.payroll.transaction'].search_count([
                ('worksheet_id', '=', rec.id)
            ])
            if tx_exists:
                raise UserError(f"ტაბელი {rec.display_name} გამოიყენება ტრანზაქციებში და ვერ წაიშლება.")
        return super(PRXPayrollWorksheet, self).unlink()

    def write(self, vals):
        if 'active' in vals and vals.get('active') is False:
            forbidden = self.filtered(lambda ws: ws.status in ('open', 'posted'))
            if forbidden:
                raise UserError("ტაბელის დაარქივება შესაძლებელია სტატუსზე: 'ღია' ან 'დაპოსტილი'")
        if self.filtered(lambda ws: ws.transferred):
            raise UserError("გადარიცხული ტაბელის შეცვლა/დახურვა შეუძლებელია.")
        res = super(PRXPayrollWorksheet, self).write(vals)
        self.get_grouped_sums()
        return res

    def get_grouped_sums(self):
        grouped_data = self.cost_line_ids._read_group(
            domain=[('worksheet_id', '=', self.id)],
            aggregates=['rate:sum'],
            groupby=["cost_center_id"],
        )
        for group in grouped_data:
            if group[1] != 1:
                raise ValidationError('The rate value must be equal to 1 in all grouped records.')

        return grouped_data

    def document_open(self):
        for rec in self:
            if rec.status == 'closed':
                rec.write({'status': 'open'})

    def document_post(self):
        for rec in self:
            if rec.status == 'closed':
                rec.write({'status': 'posted'})

    def document_cancel(self):
        for rec in self:
            if rec.status == 'posted':
                rec.write({'status': 'cancelled'})

    def document_close(self):
        for rec in self:
            if rec.status == 'open':
                rec.write({'status': 'closed'})

    def _readonly_fields(self):
        self.readonly_worksheet = bool(self.worksheet_detail_ids)

    def action_view_worksheet_lines(self):
        action = self.env.ref('prx_payroll.action_prx_worksheet_line_act_window').read()[0]
        action['domain'] = [('worksheet_id', '=', self.id)]
        return action

    def action_view_worksheet_earning(self):
        action = self.env.ref('prx_payroll.action_prx_payroll_worksheet_detail').read()[0]
        action['domain'] = [('worksheet_id', '=', self.id)]
        return action

    def _update_payroll_worksheet_details(self):
        detail = self.env['prx.payroll.worksheet.detail']
        for worksheet in self:
            worksheet.worksheet_detail_ids.unlink()
            grouped_data = {}
            for line in worksheet.worksheet_line_ids:
                key = line.earning_id.id
                if key not in grouped_data:
                    grouped_data[key] = {
                        'position': line.earning_id.contract_id.job_id.name,
                        'earning_id': line.earning_id.id,
                        'earning_amount': line.earning_amount,
                        'rate': line.rate,
                        'quantity': line.quantity,
                        'amount': line.amount,
                        'date': [line.date],
                    }
                else:
                    grouped_data[key]['quantity'] += line.quantity
                    grouped_data[key]['amount'] += line.amount
                    grouped_data[key]['date'].append(line.date)
            for key, data in grouped_data.items():
                last_date = max(data['date']) if data['date'] else False
                data.update({'worksheet_id': worksheet.id, 'date': last_date})
                detail.create(data)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PRXPayrollWorksheet, self).create(vals_list)
        for rec in res:
            rec.sequence = self.env['ir.sequence'].next_by_code('prx.payroll.worksheet')

            ''' cost line-ების დამატება '''
            cost_document_lines = self.env['prx_payroll.employee.cost.document.line'].search([
                ('ref_employee_id', '=', rec.worker_id.id)
            ])

            cost_line_model = self.env['prx_payroll.worksheet.cost.line']
            line_list = []
            for line in cost_document_lines:
                line_list.append({
                    'worksheet_id': rec.id,
                    'document_id': line.employee_cost_document_id.id,
                    'cost_document_line_id': line.id,
                    'cost_unit_id': line.cost_unit_id.id,
                    'cost_center_id': line.ref_cost_center_id.id,
                    'is_init_record': True,
                    'rate': line.rate,
                })

            cost_line_model.create(line_list)
        return res

    def delete_lines(self):
        """delete worksheet lines"""
        if self.status == 'open':
            self.worksheet_line_ids.unlink()

    def generate_worksheet(self):
        prx_manual_not_unlink = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_manual_not_unlink')
        prx_system_not_unlink = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_system_not_unlink')
        prx_earning_not_unlink = self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_earning_not_unlink')

        def configuration_unlink(tabel=self):
            """აქ კონფიგურაციის მიხედვით ვშლი ჩანაწერებს ტაბელის ლაინებიდან"""
            if tabel.status == 'open':
                if not prx_manual_not_unlink:
                    tabel.worksheet_line_ids.filtered(
                        lambda record: record.source == 'manual' and not record.is_production_base).unlink()
                if not prx_system_not_unlink:
                    tabel.worksheet_line_ids.filtered(lambda record: record.source == 'system').unlink()
                if not prx_earning_not_unlink:
                    tabel.worksheet_line_ids.filtered(lambda record: record.is_production_base).unlink()
        if self.status != 'open':
            raise UserError("დეტალების გენერაცია შესაძლებელი არის მხოლოდ 'ღია' სტატუსში!")

        configuration_unlink()
        active_earning = self.env['prx.payroll.position.earning'].search([
            ('employee_id', '=', self.worker_id.id),
            ('start_date', '<=', self.period_id.end_date),
            ('salary_type', '=', self.salary_type),
            '|',
            ('end_date', '>=', self.period_id.start_date),
            ('end_date', '=', False),
        ])
        earning_record_by_one = active_earning.filtered(
            lambda record: record.earning_id.record_type in ('single_record_by_calendar',
                                                             'single_record_by_workday')
                           and not record.earning_id.production_base and self.salary_type == record.earning_id.salary_type)

        if earning_record_by_one:
            single_line = []
            for earning in earning_record_by_one:
                last_working_days = self.env['prx.organisation.calendar'].get_last_working_days(
                    self.period_id.end_date,
                    earning.contract_id.resource_calendar_id)
                date_by_record = self.period_id.end_date if earning.earning_id.record_type == 'single_record_by_calendar' else last_working_days
                if earning.end_date:
                    "თუ ანაზღაურების დასრულების თარიღი მეტია მაშინ date = earning.end_date მნიშველობას"
                    if date_by_record > earning.end_date:
                        date_by_record = earning.end_date
                line = self.env['prx.payroll.worksheet.line'].create({
                    'worksheet_id': self.id,
                    'date': date_by_record,
                    'earning_id': earning.id,
                    'quantity': 1,
                    'rate': earning.amount,
                    'source': 'system'
                })
                single_line.append((4, line.id, 0))
            self.write({'worksheet_line_ids': single_line})

        earning_by_many_record = active_earning.filtered(
            lambda record: record.earning_id.record_type in ('divide_work_day', 'divide_work_calendar')
                           and not record.earning_id.production_base
                           and self.salary_type == record.earning_id.salary_type)

        if earning_by_many_record:
            generate_period_days = sorted([self.period_id.start_date + timedelta(days=rec) for rec in
                                           range((self.period_id.end_date - self.period_id.start_date).days + 1)])
            for earning in earning_by_many_record:
                earning_date = self.get_date_range(earning, self.period_id)
                if not earning_date:
                    continue
                start, end = earning_date['start'], earning_date['end']
                generate_range = sorted([start + timedelta(days=rec) for rec in
                                         range((end - start).days + 1)])  # ამდენი ჩანაწერი უნდა იყოს

                if earning.earning_id.record_type == 'divide_work_calendar':
                    len_period_moth_days = (self.period_id.end_date - self.period_id.start_date).days + 1
                    single_line = []
                    if earning.earning_id.earning_unit == 'day':
                        for lin_record in generate_range:
                            line = self.env['prx.payroll.worksheet.line'].create({
                                'worksheet_id': self.id,
                                'date': lin_record,
                                'earning_id': earning.id,
                                'quantity': 1,
                                'rate': earning.amount / len_period_moth_days,
                                'source': 'system'
                            })
                            single_line.append((4, line.id, 0))
                    if earning.earning_id.earning_unit == 'hour':
                        calendar_hours_per_day = earning.contract_id.resource_calendar_id.hours_per_day
                        total_period_hours = calendar_hours_per_day * len_period_moth_days
                        hour_rate = (earning.amount / total_period_hours) if total_period_hours else 0.0

                        for lin_record in generate_range:
                            line = self.env['prx.payroll.worksheet.line'].create({
                                'worksheet_id': self.id,
                                'date': lin_record,
                                'earning_id': earning.id,
                                'quantity': calendar_hours_per_day,
                                'rate': hour_rate,
                                'source': 'system'
                            })
                            single_line.append((4, line.id, 0))
                    self.write({'worksheet_line_ids': single_line})
                if earning.earning_id.record_type == 'divide_work_day':
                    end_date_earning_period = generate_range[-1]
                    work_days_set = set()
                    working_days_period_full = set()

                    for days in generate_period_days:
                        is_workday = self.env['prx.organisation.calendar'].is_working_day(
                            days,
                            earning.contract_id.resource_calendar_id,
                        )
                        if is_workday:
                            working_days_period_full.add(days)

                        check_day = self.env['prx.organisation.calendar'].get_next_working_days(
                            days,
                            earning.contract_id.resource_calendar_id,
                            contains=True
                        )
                        if check_day:
                            if days in generate_range:
                                if check_day <= end_date_earning_period:
                                    work_days_set.add(check_day)
                    work_days = sorted(work_days_set)
                    single_line = []
                    if earning.earning_id.earning_unit == 'day':
                        for work_day in work_days:
                            line = self.env['prx.payroll.worksheet.line'].create({
                                'worksheet_id': self.id,
                                'date': work_day,
                                'earning_id': earning.id,
                                'quantity': 1,
                                'rate': (earning.amount / len(working_days_period_full)) if working_days_period_full else 0.0,
                                'source': 'system',
                            })
                            single_line.append((4, line.id, 0))
                    if earning.earning_id.earning_unit == 'hour':
                        calendar = earning.contract_id.resource_calendar_id
                        hours_map = self.env['prx.organisation.calendar'].get_day_work_hours(
                            working_days_period_full,
                            calendar
                        )  # მაგ: {2025-09-01: 8.0, 2025-09-02: 7.5, ...}
                        print(len(hours_map))
                        total_hours = sum(hours_map.values())
                        if not total_hours:
                            fallback_hours = float(calendar.hours_per_day)
                            hours_map = {d: fallback_hours for d in work_days}
                            total_hours = fallback_hours * len(working_days_period_full)

                        hour_rate = earning.amount / total_hours  # ერთ საათზე გადასანაწილებელი თანხა
                        for work_day in work_days:
                            day_hours = float(hours_map.get(work_day, calendar.hours_per_day))
                            line = self.env['prx.payroll.worksheet.line'].create(
                                {
                                    'worksheet_id': self.id,
                                    'date': work_day,
                                    'earning_id': earning.id,
                                    'quantity': day_hours,  # რამდენი საათი იმუშავა ამ დღეს
                                    'rate': hour_rate,  # ერთი საათის ფასი
                                    'source': 'system',
                                }
                            )
                            single_line.append((4, line.id, 0))

                    self.write({'worksheet_line_ids': single_line})
        self.update_time_off(employee=self.worker_id)

    def update_time_off(self, employee):
        period_start = self.period_id.start_date
        period_end = self.period_id.start_date
        start_month = date(period_start.year, period_start.month, 1)
        end_month = date(period_end.year, period_end.month, monthrange(period_end.year, period_end.month)[1])

        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('request_date_to', '>=', start_month),
            ('request_date_from', '<=', end_month),
        ])
        active_earning = self.env['prx.payroll.position.earning'].search([
            ('employee_id', '=', self.worker_id.id),
            ('start_date', '<=', self.period_id.end_date),
            ('salary_type', '=', self.salary_type),
            '|',
            ('end_date', '>=', self.period_id.start_date),
            ('end_date', '=', False),
            ('earning_id', 'in', self.env['prx.payroll.earning'].search(
                [('record_type', 'in', ['divide_work_calendar', 'divide_work_day'])]).ids),
        ])
        if not active_earning:
            return
        calendar = active_earning.contract_id.resource_calendar_id
        if not calendar:
            return

        for leave in leaves:
            leave_start = max(leave.request_date_from, start_month)
            leave_end = min(leave.request_date_to, end_month)

            working_leave_days = set()
            current_day = leave_start
            while current_day <= leave_end:
                working = self.env['prx.organisation.calendar'].get_length_of_workdays_range(
                    start_date=current_day,
                    end_date=current_day,
                    resource=calendar,
                    return_days=True
                )
                if working:
                    working_leave_days.update([d for d in working if isinstance(d, date)])
                    # working_leave_days.update(working) TODO ES iyo Tu aria es brunetteT

                current_day += timedelta(days=1)

            if working_leave_days:
                lines = self.worksheet_line_ids.search([
                    ('employee_id', '=', employee.id),
                    ('date', 'in', list(working_leave_days))
                ])
                lines.write({
                    'time_of_type': leave.holiday_status_id.id
                })
                if leave.holiday_status_id.time_type == 'leave':
                    lines.write({
                        'amount': 0.0,
                        'quantity': 0.0,
                    })
                lines.env.cr.commit()

    @staticmethod
    def get_date_range(earning, period):
        date_range = {}
        if (earning.end_date and earning.start_date <= period.start_date and earning.end_date > period.end_date) or (
                not earning.end_date and earning.start_date <= period.start_date):
            """ხელფასის სტარტი ნაკლებიია პერიოდის სტარტზე და ხელფასის ენდ მეტია პერიოდის ენდზე"""
            date_range['start'] = period.start_date
            date_range['end'] = period.end_date

        if earning.end_date and earning.start_date <= period.start_date and earning.end_date < period.end_date:
            """ხელფასის სტარტი ნაკლებია პერიოდის სტარტზე და ხელფასის ენდ ნაკლებია პერიოდის ენდზე"""
            date_range['start'] = period.start_date
            date_range['end'] = earning.end_date

        if earning.end_date and period.start_date <= earning.start_date < period.end_date < earning.end_date:
            """ხელფასის სტარტი მეტია პერიოდის სტარტზე და ხელფასის ენდ მეტია პერიოდის ენდზე"""
            date_range['start'] = earning.start_date
            date_range['end'] = period.end_date

        if earning.end_date and earning.start_date >= period.start_date and earning.end_date <= period.end_date:
            """ხელფასის სტარტი მეტია პერიოდის სტარტზე და ხელფასის ენდ ნაკლებია პერიოდის ენდზე"""
            date_range['start'] = earning.start_date
            date_range['end'] = earning.end_date

        if not earning.end_date and earning.start_date >= period.start_date < period.end_date:
            date_range['start'] = earning.start_date
            date_range['end'] = period.end_date

        return date_range
