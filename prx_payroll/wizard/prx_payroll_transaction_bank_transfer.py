from odoo import api, fields, models
from odoo.exceptions import UserError
from ..models.configuration.prx_enum_selection import SalaryType
from datetime import datetime
import uuid
import json
import base64


class PRXPayrollTransactionTransfer(models.TransientModel):
    _name = 'prx.payroll.transaction.transfer'
    _description = 'Payroll Transaction Transfer'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    bank = fields.Selection([('bog', 'საქართველოს ბანკი'), ('tbc', 'თიბისი ბანკი')], string='ბანკი')
    period_id = fields.Many2one('prx.payroll.period', string="პერიოდი")
    transaction_type = fields.Selection(
        [('earning', 'ანაზღაურება'), ('tax', 'გადასახადი'), ('deduction', 'დაქვითვა'), ('pension', 'საპენსიო'),
         ('all', 'ყველა')],
        string='ტრანზაქციის ტიპი')
    creditor_ids = fields.Many2many('res.partner', string='კრდიტორი')
    employee_id = fields.Many2many('hr.employee', string='თანამშრომელი')
    salary_type = fields.Selection(SalaryType.selection() + [('all', 'ყველა')], string='გადახდის ტიპი')
    attach_type = fields.Selection([('by_record', 'ერთი ჩანაწერი'), ('by_file', 'ჯგუფური გადარიცხვა')],
                                   string='ბანკში ატვირთვის ტიპი')
    file_name = fields.Char(string='ფაილის დასახელება')

    def generate_transfer_document(self):
        self.generate_bank_data()

    def generate_bank_data(self):
        domain = [('period_id', '=', self.period_id.id), ('transaction_type', '!=', 'transfer'),('transferred', '=', False)]

        if self.employee_id:
            domain.append(('employee_id', 'in', self.employee_id.ids))
        if self.salary_type != 'all':
            domain.append(
                ('worksheet_id', 'in', self.env['prx.payroll.worksheet'].search([('salary_type', '=', self.salary_type),
                                                                                 ('period_id', '=',self.period_id.id)]).ids))
        values = {'bog': [], 'tbc': []}
        if self.transaction_type in ['earning', 'all']:
            """აქ ვანგარიშობ ანაზღაურები,ავანსი და ბონუსი"""
            main_domain = domain + [('earning_id', '!=', False), ('earning_id', 'not in',
                                                                  self.env['prx.payroll.earning'].search(
                                                                      [('insurance', '=', True)]).ids)]
            transactions = self.env['prx.payroll.transaction'].search(main_domain)

            for tran in transactions:
                employee = tran.employee_id
                if not employee.bank_account_id or not employee.bank_account_id.acc_number:
                    raise UserError(f'{employee.name} ბანკის ანგარიში არ არის მითითებული!')
                earning_amount = sum(self.env['prx.payroll.transaction'].search(
                    [('worksheet_id', '=', tran.worksheet_id.sequence), ('employee_id', '=', employee.id)]).mapped(
                    'amount'))
                if self.attach_type == 'by_file':
                    transfer = self.generate_bank_schemas(
                        bank=self.bank,
                        tabel_name=tran.worksheet_id.sequence,
                        employee=employee,
                        earning=tran.earning_id,
                        amount=earning_amount
                    )
                    values.get(self.bank).append(transfer)
                if self.attach_type == 'by_record':
                    purpose_text = ''
                    if tran.earning_id.salary_type in ['standard', 'avanse']:
                        purpose_text = 'Salary'
                    if tran.earning_id.salary_type == 'one_time':
                        purpose_text = 'Bonus'

                    self.create_bank_request_transaction(
                        partner=employee.user_partner_id,
                        salary=True,
                        amount=earning_amount,
                        purpose=purpose_text,
                        recipientBankAccount=employee.bank_account_id,
                        accountType='salary',
                        employee=employee
                    )

        # გადასახადი საშემოსავლო
        if self.transaction_type in ['tax', 'all']:
            treasury_amount = abs(sum(
                self.env['prx.payroll.transaction'].search(domain + [('transaction_type', '=', 'tax')]).mapped(
                    'amount')))
            treasury_partner = self.env['res.partner'].search([('treasury', '=', True)], limit=1)
            if not treasury_partner or not treasury_partner.bank_ids:
                raise UserError("მიუთითეთ ხაზინის ანგარიში!")
            treasury_acc = treasury_partner.bank_ids.filtered(lambda l: l.is_default)
            if not treasury_acc:
                raise UserError("სახაზინო ანგარიში კონტაქტებში ვერ მოიძებნა !")
            purpose_text = f"Treasury Payment"

            self.create_bank_request_transaction(
                partner=treasury_partner,
                salary=False,
                amount=treasury_amount,
                purpose=purpose_text,
                recipientBankAccount=treasury_acc,
                accountType='treasury'
            )
        # საპენსიო
        if self.transaction_type in ['pension', 'all']:
            pension_amount = abs(
                sum(self.env['prx.payroll.transaction'].search(domain + [('transaction_type', '=', 'deduction')]
                                                               ).filtered(lambda l: l.deduction_id.pension).mapped('amount')))
            if pension_amount:
                pension_partner = self.env['prx.payroll.deduction'].search([('pension', '=', True)], limit=1).creditor
                if not pension_partner or not pension_partner.bank_ids:
                    raise UserError("მიუთითეთ საპენსიოს ანგარიში!")
                pension_acc = pension_partner.bank_ids.filtered(lambda l: l.is_default)
                if not pension_acc:
                    raise UserError("საპენსიო ანგარიში კონტაქტებში ვერ მოიძებნა !")
                purpose_text = f"საპენსიო"

                self.create_bank_request_transaction(
                    partner=pension_partner,
                    salary=False,
                    amount=pension_amount * 2,
                    purpose=purpose_text,
                    recipientBankAccount=pension_acc,
                    accountType='payroll'
                )
        # დაქვითვა
        if self.transaction_type in ['deduction', 'all']:
            """ალიმენტი და ყველა გადახდა საპენსიოს და საშემოსავლოს გარდა"""
            domain = domain + [('transaction_type', '=', 'deduction')]
            if not self.creditor_ids:
                domain += [('creditor', '!=', False)]
            else:
                domain += [('creditor', 'in', self.creditor_ids.ids)]

            deduction_transaction = self.env['prx.payroll.transaction'].search(domain)
            deduction_transaction = deduction_transaction.filtered(
                lambda l: not l.deduction_id.pension and not l.deduction_id.avanse)
            for tran in deduction_transaction:
                if self.attach_type == 'by_record':
                    self.create_bank_request_transaction(
                        partner=tran.creditor,
                        salary=False,
                        amount=tran.amount,
                        purpose=tran.deduction_id.payment_description,
                        recipientBankAccount=tran.creditor.bank_ids.filtered(lambda l: l.is_default),
                        accountType='payroll',
                    )
                if self.attach_type == 'by_file':
                    transfer = self.generate_bank_schemas(
                        bank=self.bank,
                        tabel_name=tran.worksheet_id.sequence,
                        amount=tran.amount,
                        transaction=tran,
                        deduction=True
                    )
                    values.get(self.bank).append(transfer)
        if self.attach_type == 'by_file':
            """ფაილის შექმნა"""
            if values[self.bank]:
                self.action_export_json(
                    data=values[self.bank],
                    fileName=self.file_name + '.json'
                )

    def generate_bank_schemas(self, bank, tabel_name, amount, employee=False, earning=False, deduction=False,
                              transaction=False):
        """
            საქართველოს/თიბის ბანკის სქემა რომელსაც ვიყენებ ფაილის დაგენერირებისას რომელიც შემდეგ იგზავნება ბანკში
            საქართველოა ბანკში შემთვევაში უნდა გაიგზავნოს ფაილი ფორმატით CSV
            თიბისი ბანკის შემთხვევაში უნდა გაიგზავნოს ერთიან რექუესტად და არა ბეჩ ფაილად
        """
        purpose = ''
        payer = self.env.user.company_id
        IsSalary = False

        if earning:
            if earning.salary_type in ['standard', 'avanse']:
                purpose = 'Earning'
                IsSalary = True
            if earning.salary_type == 'one_time':
                purpose = 'Bonus'
                IsSalary = True
        if deduction:
            if not transaction.deduction_id.payment_description:
                raise UserError(
                    f"დაქვითების კონფიგურაციაში არის შევსებული 'გადარიცხვის დანიშნულება' - > {transaction.deduction_id.deduction}")
            purpose = transaction.deduction_id.payment_description or ''

        prx_payroll_acc_id = int(self.env['ir.config_parameter'].sudo().get_param('prx_payroll.prx_payroll_acc'))
        prx_payroll_acc = self.env['res.partner.bank'].browse(prx_payroll_acc_id)
        BeneficiaryAccountNumber = employee.bank_account_id.prx_sanitized_acc if not deduction else transaction.creditor.bank_ids.filtered(
            lambda l: l.is_default).prx_sanitized_acc
        BeneficiaryBankCode = employee.bank_account_id.bank_id.bic if not deduction else transaction.creditor.bank_ids.filtered(
            lambda l: l.is_default).bank_id.bic
        BeneficiaryInn = employee.identification_id if not deduction else transaction.creditor.vat
        BeneficiaryName = employee.name if not deduction else transaction.creditor.name
        payload = {}

        if bank == 'bog':
            payload = {
                "Nomination": purpose,
                "PayerInn": payer.vat,
                "PayerName": payer.name,
                # MT103 ინდივიდუალური გადარიცხვა.
                # BULK - სტანდარტული გადარიცხვა. შესაძლებელია მხოლოდ 10 000 ლარამდე.
                "DispatchType": 'MT103' if amount > 99_999 else 'BULK',
                "ValueDate": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                "IsSalary": IsSalary,
                "UniqueId": str(uuid.uuid4()),
                "Amount": abs(amount),
                "DocumentNo": tabel_name,
                "SourceAccountNumber": prx_payroll_acc.prx_sanitized_acc,
                "BeneficiaryAccountNumber": BeneficiaryAccountNumber,
                "BeneficiaryBankCode": BeneficiaryBankCode,
                "BeneficiaryInn": BeneficiaryInn,
                "CheckInn": False,
                "BeneficiaryName": BeneficiaryName,
                "AdditionalInformation": purpose
            }
        if bank == 'tbc':
            payload = {
                'accountNumber': BeneficiaryAccountNumber,
                'documentNumber': int('22'+tabel_name[3:]),
                'amount': abs(amount),
                'currency': "GEL",
                'additionalDescription': purpose,
                'description': purpose,
                'beneficiaryName': BeneficiaryName,
                'beneficiaryTaxCode': BeneficiaryInn,
                'PayloadType': 'TBC_ACCOUNT_OTHER_BANK_NATI0NAL_CURRENCY' if 'TBC' not in BeneficiaryName else 'TBC_WITHIN_BANK_PAYMENT_PAYLOAD'
            }
        return payload

    def create_bank_request_transaction(self, partner, salary, amount, purpose, recipientBankAccount, accountType,
                                        employee=False):
        """return bank.transfer.request values for create by line"""
        icp = self.env['ir.config_parameter'].sudo()
        payroll_acc_id = icp.get_param('prx_payroll.prx_payroll_acc')
        if not payroll_acc_id:
            raise UserError("დააკონფიგურირეთ კომპანიის გადახდის საბანკო ანგარიში.")
        payroll_acc = self.env['res.partner.bank'].browse(int(payroll_acc_id))
        if not payroll_acc or not payroll_acc.exists():
            raise UserError("ფეიროლის მოდულში არსებული კომპანიის ანგარიში, არასწორია ან ვერ მოიძებნა.")
        vals = {
            'company_id': self.company_id.id,
            'transaction_providers': None,
            'currency_id': self.env.company.currency_id.id,
            'account_type': accountType,
            'purpose': purpose,
            'additional_information': purpose,
            'is_salary': salary,
            'dispatch_type': 'MT103',  # ინდივიდუალური გადარიცხვა
            'payment_amount': abs(amount),
            'partner_id': partner.id,  # ხაზინის კონტაქტი
            'recipient_inn': partner.vat if accountType != 'salary' else employee.identification_id,
            'recipient_bank_account_number': recipientBankAccount.id,
            'value_date': fields.Datetime.now(),

            # === Payer (company) ===
            'payer_name': self.env.user.company_id.name,
            'payer_inn': self.env.user.company_id.vat,
            'source_account_number': payroll_acc.id,
            'source_account_number_text': payroll_acc.prx_sanitized_acc,

            'recipient_bank_account_number_text': recipientBankAccount.prx_sanitized_acc,
            'recipient_bank_code': recipientBankAccount.bank_id.bic,
            'recipient_account_holder': recipientBankAccount.acc_holder_name,
        }
        if accountType == 'salary':
            vals['employee_id'] = employee.id
        transfer_model = self.env['bank.transfer.request'].sudo()
        if self.bank == 'bog':
            bog_bic = icp.get_param('prx_bog_api_service.prx_bog_swift_code_bic')
            provider = self.env['res.bank'].search([('bic', '=', bog_bic)], limit=1)
            vals['transaction_providers'] = provider.id

            transfer_model.create(vals)

        if self.bank == 'tbc':
            tbc_bic = icp.get_param('prx_tbc_api_service.prx_tbc_bank_swift_code_bic')
            provider = self.env['res.bank'].search([('bic', '=', tbc_bic)], limit=1)
            vals['transaction_providers'] = provider.id
            transfer_model.create(vals)

    def action_export_json(self, data, fileName):
        """this method creates bank.transfer.request attachment in JSON content"""

        if not data:
            raise UserError('ბანკის დასაგენერირებელი ტრანზაქციები ვერ მოიძებნა!')
        line_cmds = []
        for idx, record in enumerate(data, start=1):
            if self.bank == 'tbc':
                record['position'] = str(idx)

            if self.bank == 'bog':
                line_cmds.append(
                    (0, 0, {
                        'document_number': record['DocumentNo'],
                        'amount': record['Amount'],
                        'description': record['Nomination'],
                        'additional_description': record['AdditionalInformation'],
                        'beneficiary_name': record['BeneficiaryName'],
                        'beneficiary_tax_code': record['BeneficiaryInn'],
                        'beneficiary_account_number': record['BeneficiaryAccountNumber'],
                        'beneficiary_bank_code': record['BeneficiaryBankCode'],
                        'source_account_number': record['SourceAccountNumber'],
                        'unique_id': record['UniqueId'],
                    })
                )

            if self.bank == 'tbc':
                line_cmds.append(
                    (0, 0, {
                        'beneficiary_account_number': record['accountNumber'],
                        'document_number': record['documentNumber'],
                        'amount': record['amount'],
                        'currency': record['currency'],
                        'additional_description': record['additionalDescription'],
                        'position': record['position'],
                        'description': record['description'],
                        'beneficiary_name': record['beneficiaryName'],
                        'beneficiary_tax_code': record['beneficiaryTaxCode'],
                        'payload_type': record['beneficiaryTaxCode'],
                    })
                )

        json_string = json.dumps(data, ensure_ascii=False, indent=4)
        json_base64 = base64.b64encode(json_string.encode('utf-8'))

        target_record = self.env['bank.transfer.request'].sudo().create({
            'account_type': 'file',
            'file': json_base64,
            'file_filename': fileName,
            'currency_id': self.env["res.currency"].sudo().search([('name', '=', 'GEL')], limit=1).id,
            'line_ids': line_cmds,
        })

        return target_record

    def get_bank_swift(self):
        """return swift code"""
        icp = self.env['ir.config_parameter'].sudo()
        if self.bank == 'bog':
            bog_bic = icp.get_param('prx_bog_api_service.prx_bog_swift_code_bic')
            return bog_bic
        elif self.bank == 'tbc':
            tbc_bic = icp.get_param('prx_tbc_api_service.prx_tbc_bank_swift_code_bic')
            return tbc_bic
        else:
            return UserError('პროვაიდერი ბანკი ვერ მოიძებნა!')
