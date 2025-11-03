import base64
import io
from openpyxl import Workbook
from odoo import api, fields, models
from ..models.configuration.prx_enum_selection import BankReports,BankTransactionReportType,SalaryType
from odoo.exceptions import UserError
from openpyxl.styles import numbers


class PRXPayrollBankReports(models.TransientModel):
    _name = 'prx.payroll.bank.reports'
    _description = 'Period bank reports wizard'

    period_id = fields.Many2one('prx.payroll.period', string="პერიოდი", required=True)
    bank = fields.Selection(BankReports.selection(), string='ბანკი', required=True)
    transaction_type = fields.Selection(BankTransactionReportType.selection(), string='ტრანზაქციის ტიპი', default='all',required=True)
    process_type = fields.Selection(SalaryType.selection(), string='პროცესის ტიპი',required=True)
    file_download = fields.Binary("File", readonly=True)
    file_name = fields.Char("Filename")

    def action_generate_bank_reports(self):
        self.ensure_one()
        wb = Workbook()
        ws = wb.active
        ws.title = "ბანკის ფაილი"
        if self.bank == 'bog':
            header, values = self.get_bog_excel_header_and_values()
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions['B'].width = 45
            ws.column_dimensions['C'].width = 25
            ws.column_dimensions['D'].width = 20
            ws.column_dimensions['E'].width = 25
            ws.column_dimensions['F'].width = 55
            ws.append(header)
        elif self.bank == 'tbc':
            header, values = self.get_tbc_excel_header_and_values()
            ws.column_dimensions['A'].width = 20
            ws.column_dimensions['B'].width = 30
            ws.column_dimensions['C'].width = 10
            ws.column_dimensions['D'].width = 20
            ws.append(header[0])
            ws.append(header[1])
        else:
            raise UserError('აირჩიე ბანკი!')

        for value in values:
            ws.append(value)

        for row in range(2, ws.max_row + 1):
            ws["{}{}".format("C" if self.bank == 'tbc' else "E" , row)].number_format = numbers.FORMAT_NUMBER_00
            ws["{}{}".format( "D", row)].number_format = numbers.FORMAT_TEXT

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        self.file_download = base64.b64encode(bio.read())
        self.file_name = f"Bank_Reports_{self.period_id.period+'_'+self.bank}.xlsx"
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


    def get_bog_excel_header_and_values(self):
        header = ['მიმღების ანგარიშის ნომერი',
                  'მიმღები ბანკის კოდი(არასავალდებულო)',
                  'მიმღების დასახელება',
                  'დანიშნულება',
                  'გადასარიცხი თანხა',
                  'მიმღების საიდენტიფიკაციო კოდი(არასავალდებულო)']
        domain = [('period_id', '=', self.period_id.id),('code','!=',False),('worksheet_id.salary_type','=',self.process_type)]
        if self.transaction_type == 'non_transferred':
            domain += [('transferred','=',False)]
        if self.transaction_type == 'transferred':
            domain += [('transferred', '=', True)]

        txs = self.env['prx.payroll.transaction'].read_group(
            domain,
            ['employee_id','amount:sum(amount)',],
            ['employee_id'])

        values=[]
        employee_model = self.env['hr.employee']
        for empl in txs:
            employee = employee_model.browse(empl['employee_id'][0])
            values.append([
                employee.bank_account_id.acc_number or '',
                employee.bank_account_id.bank_id.bic or '',
                employee.name or '',
                'ხელფასი',
                empl['amount'] or 0.0,
                employee.identification_id or '',
                ])
        return header, values

    def get_tbc_excel_header_and_values(self):
        header_geo = ['მიმღების ანგარიში','მიმღების სახელი და გვარი','თანხა','დანიშნულება']
        header_eng = ['Account Number',"Employee's Name",'Amount','Description']
        header = [header_geo,header_eng]

        domain = [('period_id', '=', self.period_id.id),('code','!=',False),('worksheet_id.salary_type','=',self.process_type)]
        if self.transaction_type == 'non_transferred':
            domain += [('transferred','=',False)]
        if self.transaction_type == 'transferred':
            domain += [('transferred', '=', True)]


        txs = self.env['prx.payroll.transaction'].read_group(
            domain,
            ['employee_id','amount:sum(amount)',],
            ['employee_id'])

        values=[]
        employee_model = self.env['hr.employee']
        for empl in txs:
            employee = employee_model.browse(empl['employee_id'][0])
            values.append([
                employee.bank_account_id.acc_number or '',
                employee.name or '',
                empl['amount'] or 0.0,
                'ხელფასი',
                ])

        return header,values