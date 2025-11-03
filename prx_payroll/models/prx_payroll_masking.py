import hashlib
import random
import re
from odoo import fields, models
from odoo.exceptions import UserError


def hash_field_value(value: str) -> str:
    if value in [None, False, True]:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(val) -> bool:
    if not isinstance(val, str):
        return False
    return bool(re.fullmatch(r"[A-Fa-f0-9]{64}", val))


class PrxPayrollMasking(models.Model):
    _name = 'prx_payroll.masking'
    _description = 'Payroll information masking'

    name = fields.Char(required=True)

    def hash_model_logs(self, fields_names, model_name, hashing=False, recompute=0.0):
        model = self.env['ir.model'].search([('model', '=', model_name)])
        if model:
            ir_field_ids = self.env['ir.model.fields'].search(
                [('name', 'in', fields_names), ('model_id', '=', model.id)]).ids
            print(ir_field_ids)
            for log in self.env['mail.tracking.value'].search([('field_id', 'in', ir_field_ids)]):
                if hashing:
                    if not _is_sha256(log.old_value_char):
                        log.old_value_char = hash_field_value(log.old_value_char) if hashing else log.old_value_char * recompute
                    if not _is_sha256(log.new_value_char):
                        log.new_value_char = hash_field_value(log.new_value_char) if hashing else log.new_value_char * recompute
                if recompute:
                    log.old_value_float = log.old_value_float * recompute
                    log.new_value_float = log.new_value_float * recompute

        self.create({
            'name': f'{model_name} Log Masking Done'
        })

    def action_mask_employee_info(self):

        employees = self.env['hr.employee'].search([])

        for employee in employees:
            if not _is_sha256(employee.identification_id):
                employee.identification_id = hash_field_value(employee.identification_id)
            if not _is_sha256(employee.passport_id):
                employee.passport_id = hash_field_value(employee.passport_id)
            if not _is_sha256(employee.private_street):
                employee.private_street = hash_field_value(employee.private_street)
            if not _is_sha256(employee.private_street2):
                employee.private_street2 = hash_field_value(employee.private_street2)
            if not _is_sha256(employee.private_city):
                employee.private_city = hash_field_value(employee.private_city)
            if not _is_sha256(employee.private_zip):
                employee.private_zip = hash_field_value(employee.private_zip)
            if not _is_sha256(employee.private_state_id.name):
                employee.private_state_id.name = hash_field_value(employee.private_state_id.name)
            if not _is_sha256(employee.private_country_id.name):
                employee.private_country_id.name = hash_field_value(employee.private_country_id.name)
            if not _is_sha256(employee.private_email):
                employee.private_email = hash_field_value(employee.private_email)
            if not _is_sha256(employee.private_phone):
                employee.private_phone = hash_field_value(employee.private_phone)
            if not _is_sha256(employee.bank_account_id.acc_number):
                employee.bank_account_id.acc_number = hash_field_value(employee.bank_account_id.acc_number)
            if not _is_sha256(employee.ssnid):
                employee.ssnid = hash_field_value(employee.ssnid)

        self.create({
            'name': 'Employee Info Masking Done'
        })

        for rec in self.env['prx.payroll.transaction'].search([]):
            rec.personal_number = hash_field_value(rec.personal_number)

        for rec in self.env['prx.payroll.employee.deduction.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        for rec in self.env['prx.payroll.employee.tax.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        for rec in self.env['prx.payroll.position.earning.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        self.env.cr.commit()

        model_employees_fields = [
            'identification_id',
            'passport_id',
            'private_street',
            'private_street2',
            'private_city',
            'private_zip',
            'private_email',
            'ssnid',
            'private_phone']

        model_res_partner_bank_fields = [
            'acc_number',
            'sanitized_acc_number'
        ]

        model_fields = {
            'hr.employee': model_employees_fields,
            'res.partner.bank': model_res_partner_bank_fields
        }

        for key, value in model_fields.items():
            self.hash_model_logs(
                hashing=True,
                model_name=key,
                fields_names=value
            )

    def action_mask_payroll_info(self):
        self.env['prx.payroll.import.wizard'].sudo().search([]).unlink()

        self.env.cr.execute("""
            UPDATE prx_payroll_position_earning t
            SET amount = round((t.amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_position_earning
            ) r
            WHERE r.id = t.id and t.id
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_employee_deduction t
            SET amount = round((t.amount * r.rate)::numeric, 10),
                limit_amount = round((t.limit_amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_employee_deduction
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_worksheet_line t
            SET amount = round((t.amount * r.rate)::numeric, 10),
                rate = round((t.rate * r.rate)::numeric, 10),
                over_time_amount = round((t.over_time_amount * r.rate)::numeric, 10),
                over_time_earning_rate = round((t.over_time_earning_rate * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_worksheet_line
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_worksheet_detail t
            SET amount = round((t.amount * r.rate)::numeric, 10),
                rate = round((t.rate * r.rate)::numeric, 10),
                earning_amount = round((t.earning_amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_worksheet_detail
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_position_earning_import t
            SET amount = round((t.amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_position_earning_import
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_position_earning_import t
            SET amount = round((t.amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_position_earning_import
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_transaction t
            SET amount = round((t.amount * r.rate)::numeric, 2),
                rate   = round((t.rate * r.rate)::numeric, 2)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_transaction
            ) r
            WHERE r.id = t.id;
        """)

        self.env.cr.execute("""
            UPDATE prx_payroll_employee_tax t
            SET used_tax_amount = round((t.used_tax_amount * r.rate)::numeric, 10)
            FROM (
                SELECT id, (random() * 19 + 1) AS rate
                FROM prx_payroll_employee_tax
            ) r
            WHERE r.id = t.id;
        """)

        self.create({
            'name': 'Payroll Info Masking Done'
        })

        # recompute logs values
        model_fields = {
            'prx.payroll.employee.deduction': ['percentage', 'amount'],
            'prx.payroll.employee.tax': ['used_tax_amount'],
            'prx.payroll.position.earning': ['amount']
        }
        for key, value in model_fields.items():
            rate = round(random.uniform(1, 20), 2)
            self.hash_model_logs(
                recompute=rate,
                model_name=key,
                fields_names=value
            )
