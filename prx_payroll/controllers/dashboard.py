from datetime import datetime
from odoo.http import route, request, Controller
from odoo import fields
import calendar
from collections import OrderedDict
from collections import Counter
from collections import defaultdict
from dateutil.relativedelta import relativedelta


class PayrollDashboardController(Controller):

    @route('/prx_payroll/get_last_3_months_summary', type='json', auth='user')
    def get_last_3_months_summary(self):
        Transaction = request.env['prx.payroll.transaction'].sudo()
        today = datetime.today()
        this_month_start = today.replace(day=1)
        this_month_end_day = calendar.monthrange(today.year, today.month)[1]
        this_month_end = today.replace(day=this_month_end_day)

        # შევამოწმოთ მიმდინარე თვეში არის თუ არა გატარება
        this_month_records = Transaction.search_count([
            ('start_date', '>=', this_month_start.date()),
            ('start_date', '<=', this_month_end.date())
        ])

        months = []
        if this_month_records:
            months.append(this_month_start)

        while len(months) < 3:
            prev_month = (months[0] if months else this_month_start) - relativedelta(months=1)
            months.insert(0, prev_month)

        # შეკრიბე თითო თვე
        summaries = []
        for month_date in months:
            year = month_date.year
            month = month_date.month
            start_date = month_date.replace(day=1)
            end_day = calendar.monthrange(year, month)[1]
            end_date = month_date.replace(day=end_day)

            records = Transaction.read_group(
                domain=[
                    ('start_date', '>=', start_date.date()),
                    ('start_date', '<=', end_date.date())
                ],
                fields=['amount', 'transaction_type'],
                groupby=['transaction_type']
            )

            record_ids = []
            for rec in records:
                if '__domain' in rec:
                    matched_ids = Transaction.search(rec['__domain']).ids
                    record_ids.extend(matched_ids)

            summary = {
                'record_ids': list(set(record_ids)),
                'month': start_date.strftime('%B'),
                'year': year,
                'earning': 0,
                'tax': 0,
                'deduction': 0
            }

            for r in records:
                ttype = r['transaction_type']
                if ttype in summary:
                    summary[ttype] = r['amount']

            summaries.append(summary)
        demo = [{'month': 'Apr', 'year': 2025, 'earning': 7000, 'tax': 0, 'deduction': 0},
                {'month': 'May', 'year': 2025, 'earning': 5000, 'tax': 80, 'deduction': 752},
                {'month': 'Jun', 'year': 2025, 'earning': 1500, 'tax': 300, 'deduction': 600}]

        return summaries
    @route('/prx_payroll/get_last_month_project_summary', type='json', auth='user')
    def get_last_month_project_summary(self):
        # მოძებნე ბოლო გამოყენებული პერიოდი
        grouped_periods = request.env['prx.payroll.transaction.cost.report'].read_group(
            domain=[('period_id', '!=', False)],
            fields=['period_id'],
            groupby=['period_id'],
        )

        period_ids = [g['period_id'][0] for g in grouped_periods if g.get('period_id')]
        periods = request.env['prx.payroll.period'].browse(period_ids).filtered(lambda p: p.start_date)
        periods_sorted = sorted(periods, key=lambda p: p.start_date, reverse=True)
        last_period = periods_sorted[0] if periods_sorted else None

        if not last_period:
            return []

        model = request.env['prx.payroll.transaction.cost.report']

        records = model.search([
            ('period_id', '=', last_period.id),
            ('cost_unit_id', '!=', False)
        ])

        grouped = defaultdict(lambda: {"amount": 0.0, "ids": [], "id": None})

        for rec in records:
            key = rec.cost_unit_id.name
            grouped[key]["amount"] += rec.cost_amount or 0.0
            grouped[key]["id"] = rec.cost_unit_id.id
            grouped[key]["ids"].append(rec.id)

        result = [
            {
                "name": name,
                "y": round(data["amount"], 2),
                "id": data["id"],
                "record_ids": data["ids"],
            }
            for name, data in grouped.items()
        ]

        # უსახელო ჩანაწერები
        unnamed_recs = model.search([
            ('cost_unit_id', '=', False),
            ('period_id', '=', last_period.id)
        ])

        if unnamed_recs:
            result.append({
                "name": "უსახელო",
                "y": sum(unnamed_recs.mapped("cost_amount")),
                "id": None,
                "record_ids": unnamed_recs.ids,
            })

        demo_data = [
            {"name": "პროექტი A", "y": 12000},
            {"name": "პროექტი B", "y": 8500},
            {"name": "პროექტი C", "y": 4200},
            {"name": "პროექტი D", "y": 3100},
            {"name": "უსახელო", "y": 1500},
        ]
        return result

    def get_last_two_period_comparison(self):
        Transaction = request.env['prx.payroll.transaction'].sudo()

        all_txns = Transaction.search(
            [('start_date', '!=', False), ('end_date', '!=', False)],
            order='end_date desc'
        )

        periods = OrderedDict()
        for txn in all_txns:
            key = (txn.start_date, txn.end_date)
            if key not in periods:
                periods[key] = []
            periods[key].append(txn)

        periods_list = list(periods.items())

        if len(periods_list) < 1:
            return {
                'current_month': '',
                'previous_month': '',
                'current_amount': 0.0,
                'previous_amount': 0.0,
                'growth_percent': 0.0,
                'is_positive': False,
            }

        current_period_key, current_txns = periods_list[0]
        current_amount = sum(txn.amount for txn in current_txns)
        current_month = current_period_key[0].strftime('%B %Y') if current_period_key[0] else ''

        if len(periods_list) > 1:
            previous_period_key, previous_txns = periods_list[1]
            previous_amount = sum(txn.amount for txn in previous_txns)
            previous_month = previous_period_key[0].strftime('%B %Y') if previous_period_key[0] else ''
        else:
            previous_amount = 0.0
            previous_month = ''

        if previous_amount == 0:
            growth_percent = 0.0
        else:
            growth_percent = round(((current_amount - previous_amount) / previous_amount) * 100, 2)

        return {
            'current_month': current_month,
            'previous_month': previous_month,
            'current_amount': current_amount,
            'previous_amount': previous_amount,
            'growth_percent': growth_percent,
            'is_positive': growth_percent > 0,
        }

    def get_last_yoy_transaction_info(self):
        Transaction = request.env['prx.payroll.transaction'].sudo()

        latest_tx = Transaction.search(
            [('end_date', '!=', False)],
            order='end_date desc',
            limit=1
        )

        if not latest_tx:
            return {
                'current_period': '',
                'current_amount': 0.0,
                'compare_amount_last_year_current_month': 0.0,
                'previous_amount': 0.0,
                'previous_period': '',
                'yoy_period_start': '',
                'yoy_period_end': '',
                'is_positive': False,
            }

        latest_date = latest_tx.end_date
        current_year = latest_date.year
        current_month = latest_date.month
        current_start = latest_date.replace(day=1)
        current_end = latest_date.replace(day=calendar.monthrange(current_year, current_month)[1])

        current_month_tx = Transaction.search([
            ('end_date', '>=', current_start),
            ('end_date', '<=', current_end)
        ])
        current_amount = sum(current_month_tx.mapped('amount'))

        last_year_start = current_start.replace(year=current_year - 1)
        last_year_end = current_end.replace(year=current_year - 1)

        last_year_tx = Transaction.search([
            ('end_date', '>=', last_year_start),
            ('end_date', '<=', last_year_end)
        ])
        prev_amount = sum(last_year_tx.mapped('amount'))

        if prev_amount == 0:
            growth = 0.0
            is_positive = False
        else:
            growth = round(((current_amount - prev_amount) / prev_amount) * 100, 2)
            is_positive = growth > 0

        return {
            'current_period': current_start.strftime("%B %Y"),
            'current_amount': current_amount,
            'compare_amount_last_year_current_month': growth,
            'previous_amount': prev_amount,
            'previous_period': last_year_start.strftime("%B %Y"),
            'yoy_period_start': last_year_start.strftime("%B %Y"),
            'yoy_period_end': last_year_end.strftime("%B %Y"),
            'is_positive': is_positive,
        }

    def get_last_period_worksheet_status_summary(self):
        grouped = request.env['prx.payroll.worksheet'].read_group(
            [('period_id', '!=', False)],
            ['period_id'],
            ['period_id'],
        )

        period_ids = [g['period_id'][0] for g in grouped if g.get('period_id')]
        periods = request.env['prx.payroll.period'].browse(period_ids).filtered(lambda p: p.start_date)
        periods_sorted = sorted(periods, key=lambda p: p.start_date, reverse=True)

        last_period = periods_sorted[0] if periods_sorted else None

        if not last_period:
            return {
                'payroll_month_label': '',
                'open_count': 0,
                'closed_count': 0,
                'posted_count': 0,
                'canceled_count': 0,
                'tabel_period_id': 0,
            }

        worksheets = request.env['prx.payroll.worksheet'].search([
            ('period_id', '=', last_period.id)
        ])

        statuses = Counter(worksheets.mapped('status'))

        return {
            'payroll_month_label': last_period.start_date.strftime('%B %Y') if last_period.start_date else '',
            'open_count': statuses.get('open', 0),
            'closed_count': statuses.get('closed', 0),
            'posted_count': statuses.get('posted', 0),
            'canceled_count': statuses.get('cancelled', 0),
            'tabel_period_id': last_period.id,
        }
    
    @route('/prx_payroll/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self):
        transaction = request.env['prx.payroll.transaction'].search([], order='start_date desc', limit=1)
        last_transactions = request.env['prx.payroll.transaction'].search([
            ('start_date', '=', transaction.start_date),
            ('end_date', '=', transaction.end_date),
        ])

        total_amount = sum(last_transactions.mapped('amount'))
        employee_ids = last_transactions.mapped('employee_id')
        employee_count = len(set(employee_ids))
        avg_amount = total_amount / employee_count if employee_count else 0
        transaction_mont = transaction[0].start_date.strftime('%B %Y') if transaction else ''
        # MoM
        compare_amount_last_two_period_dict = self.get_last_two_period_comparison()
        compare_amount_last_two_period = compare_amount_last_two_period_dict['growth_percent']
        mom_period_start = compare_amount_last_two_period_dict['previous_month']
        mom_period_end = compare_amount_last_two_period_dict['current_month']
        #YoY
        yoy = self.get_last_yoy_transaction_info()

        #tabel
        last_worksheets = self.get_last_period_worksheet_status_summary()

        return {
            'payroll_transaction_ids': last_transactions.ids,
            'payroll_month': transaction_mont,
            'total_amount': total_amount,
            'employee_count': employee_count,
            'average_amount': avg_amount,
            'compare_amount_last_two_period': compare_amount_last_two_period,
            'mom_period_start': mom_period_start,
            'mom_period_end': mom_period_end,

            'compare_amount_last_year_current_month': yoy['compare_amount_last_year_current_month'],
            'yoy_period_start': yoy['yoy_period_start'],
            'yoy_period_end': yoy['yoy_period_end'],
            'tabel_period_id': last_worksheets['tabel_period_id'],
            'total_tabel_open': last_worksheets['open_count'],
            'total_tabel_closed': last_worksheets['closed_count'],
            'total_tabel_posted': last_worksheets['posted_count'],
            'total_tabel_canceled': last_worksheets['canceled_count'],
            'tabel_month': last_worksheets['payroll_month_label'],

        }

    @route('/payroll/department_expenses', type='json', auth='user')
    def get_department_expenses(self):
        Transaction = request.env['prx.payroll.transaction'].sudo()

        latest_tx = Transaction.search(
            [('start_date', '!=', False), ('end_date', '!=', False)],
            order='end_date desc',
            limit=1
        )

        if not latest_tx:
            return []

        start_date = latest_tx.start_date
        end_date = latest_tx.end_date

        records = Transaction.read_group(
            domain=[
                ('organization_unit_id', '!=', False),
                ('start_date', '=', start_date),
                ('end_date', '=', end_date)
            ],
            fields=['amount:sum', 'organization_unit_id'],
            groupby=['organization_unit_id']
        )

        chart_data = []
        for rec in records:
            label = rec['organization_unit_id'][1] if rec.get('organization_unit_id') else 'უცნობი დეპარტამენტი'
            amount = rec['amount']
            tx_ids = Transaction.search(rec['__domain']).ids
            chart_data.append({
                'label': label,
                'y': round(amount, 2),
                'tx_ids': tx_ids,
            })

        return chart_data


    @route('/prx_payroll/get_last_transactions_by_code', type='json', auth='user')
    def get_last_transactions_by_code(self):
        Transaction = request.env['prx.payroll.transaction'].sudo()

        last_tx = Transaction.search([
            ('start_date', '!=', False),
            ('end_date', '!=', False)
        ], order='end_date desc', limit=1)

        if not last_tx:
            return []

        start_date = last_tx.start_date
        end_date = last_tx.end_date

        transactions = Transaction.search([
            ('start_date', '>=', start_date),
            ('end_date', '<=', end_date),
            ('earning_id', '!=', False),
        ])

        grouped = defaultdict(lambda: {'amount': 0.0, 'record_ids': []})
        for tx in transactions:
            grouped[tx.code]['amount'] += tx.amount or 0.0
            grouped[tx.code]['record_ids'].append(tx.id)

        result = []
        for code, data in grouped.items():
            result.append({
                'code': code,
                'amount': round(data['amount'], 2),
                'record_ids': data['record_ids'],
            })

        return result

# demo = {
#     'payroll_month': date.today().strftime('%B %Y'),
#     'total_amount': 15500.75,
#     'employee_count': 25,
#     'average_amount': 620.03,
#     'compare_amount_last_two_period': 4.3,
#     'compare_amount_last_year_current_month': -2.1,
#     'total_tabel_open': 10,
#     'total_tabel_closed': 12,
#     'total_tabel_posted': 3,
#     'tabel_month': date.today().strftime('%B %Y'),
#     'mom_period_start': '01.06.2025',
#     'mom_period_end': '30.06.2025',
#     'yoy_period_start': '01.07.2024',
#     'yoy_period_end': '31.07.2024',
# }
