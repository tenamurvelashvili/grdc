import base64
import io
import pandas as pd
from openpyxl import Workbook
from odoo import api, fields, models
from odoo.exceptions import UserError
from openpyxl.styles import numbers,Font, Alignment, PatternFill, Side

class PRXPayrollDeclarationWizard(models.TransientModel):
    _name = 'prx.payroll.declaration.wizard'
    _description = 'Payroll declaration report wizard'

    period_id = fields.Many2one('prx.payroll.period', string="პერიოდი", required=True)
    file_download = fields.Binary("File", readonly=True)
    file_name = fields.Char("Filename")

    def action_generate_declaration(self):
        self.ensure_one()

        txs = self.env['prx.payroll.transaction'].search([
            ('period_id', '=', self.period_id.id),
        ])

        data = []
        for t in txs:
            earning_amount = sum(r.amount for r in txs if r.transaction_type == 'earning' and r.earning_id and r.employee_id.id == t.employee_id.id)
            another_benefit = 0.0
            for rec in txs.search([('transaction_type','=','tax'),('employee_id','=',t.employee_id.id),('period_id','=',self.period_id.id)]):
                var_s = sum(txs.search([('employee_id','=',t.employee_id.id),('include_tax_base','=',True),('period_id','=',self.period_id.id)]).mapped('amount'))
                if rec.tax_id.rate_base > 0:
                    if rec.tax_id and rec.amount == 0:
                        """ქეისი როცა ტრანზაქციებში არის 0 საშემოსავლო ტრანზაქციებში ვწერთ [გაითვალისწინოს გადასახადის დასაანგარიშებლად ჯამი]"""
                        another_benefit = var_s
                    else:
                        another_benefit = (rec.amount / rec.tax_id.rate_gross) + var_s

            tax_code = t.earning_id.tax_report.code if t.earning_id.tax_report else ''
            emp_tax = txs.search([('employee_id','=',t.employee_id.id),('transaction_type','=','tax'),('period_id', '=', self.period_id.id)],limit=1)
            emp_rate_gross = emp_tax.tax_id.rate_gross * 100 if emp_tax else 0.0
            info = self.env['prx.payroll.report']._get_employee_create_vals(t.employee_id)

            data.append({
                'employee_id': t.employee_id.id,
                'period_id': self.period_id.id,
                'personal_number': t.personal_number or '',
                'first_name': t.employee_id.first_name,
                'last_name': t.employee_id.last_name,
                'private_street': info['private_street'],
                'resident_country': t.employee_id.tax_country.code or '',
                'tax_category': t.employee_id.tax_category.code or '',
                'tax_report': tax_code,
                'amount': t.amount or 0.0,
                'rate_gross': emp_rate_gross,
                'earning_amount':earning_amount,
                'another_benefit':another_benefit,
                'payment_date': t.period_id.payment_date,
            })
        df = pd.DataFrame(data)
        if df.empty:
            raise UserError('ჩანაწერი არ მოიძებნა!')
        grouped = (
            df.groupby(['employee_id','period_id'],dropna=False, as_index=False)
            .agg(
                earning_amount=('earning_amount', 'first'),
                first_name=('first_name', 'first'),
                last_name=('last_name', 'first'),
                tax_report=('tax_report', 'first'),
                private_street=('private_street', 'first'),
                resident_country=('resident_country', 'first'),
                tax_category=('tax_category', 'first'),
                rate_gross=('rate_gross', 'first'),
                personal_number=('personal_number', 'first'),
                another_benefit=('another_benefit', 'first'),
                payment_date=('payment_date','first')
            )
            .reset_index()
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "საშემოსავლო დეკლარაცია"

        header = [
            "საიდენტიფიკაციო ნომერი (პირადი ნომერი)",
            "თანხის მიმღების სახელი/სამართლებრივი ფორმა",
            "თანხის მიმღების გვარი/დასახელება",
            "მისამართი",
            "პირის რეზიდენტობა (ქვეყანა)",
            "შემოსავლის მიმღებ პირთა კატეგორია",
            "განაცემის სახე",
            "განაცემი თანხა (ლარი)",
            "სხვა შეღავათი",
            "გაცემის თარიღი",
            "წყაროსთან დასაკავებელი გადასახადის განაკვეთი",
            "საერთაშორისო ხელშეკრულების საფუძველზე გათავისუფლებას დაქვემდებარებული გადასახადის თანხა (ლარი)",
            "ორმაგი დაბეგვრის თავიდან აცილების შესახებ ხელშეკრულების საფუძველზე ჩათვლას დაქვემდებარებული, უცხო ქვეყანაში გადახდილი გადასახადის თანხა / შესამცირებელი საშემოსავლო გადასახადი (ლარი)"
        ]
        ws.append(header)
        header_fill = PatternFill(fill_type="solid", fgColor="EEECE1")
        thin_side = Side(border_style="thin", color="000000")
        for col in range(1, len(header) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(size=11)
            cell.fill = header_fill
            cell.border = thin_side
            cell.alignment = Alignment(
                wrap_text=True,
                horizontal="center",
                vertical="center",
                textRotation=0
            )
            # 3) ვრცელი სვეტის სიგანე
            letter = cell.column_letter
            ws.column_dimensions[letter].width = 25

        ws.row_dimensions[1].height = 168

        ws.freeze_panes = "A2"

        for _, r in grouped.iterrows():
            ws.append([
                r['personal_number'],
                r['first_name'],
                r['last_name'],
                r['private_street'],
                r['resident_country'],
                r['tax_category'],
                r['tax_report'],
                r['earning_amount'],
                r['another_benefit'],
                r['payment_date'],
                r['rate_gross'],
                0,
                0,
            ])

        for row in range(2, ws.max_row + 1):
            ws["{}{}".format("H", row)].number_format = numbers.FORMAT_NUMBER_00
            ws["{}{}".format("I", row)].number_format = numbers.FORMAT_NUMBER_00
            ws["{}{}".format("M", row)].number_format = numbers.FORMAT_NUMBER_00
            # ws["{}{}".format("J", row)].number_format = numbers.FORMAT_DATE_DDMMYY

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        self.file_download = base64.b64encode(bio.read())
        self.file_name = f"Declaration_{self.period_id.period}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
