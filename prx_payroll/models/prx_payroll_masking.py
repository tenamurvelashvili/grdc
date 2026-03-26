import hashlib
import random
import re
from odoo import fields, models
from odoo.exceptions import UserError

def _random_rate():
    return round(random.uniform(1, 20), 10)

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

        silent_ctx = dict(self.env.context or {})
        silent_ctx.update({
            'tracking_disable': True,
            'mail_notrack': True,
            'mail_create_nolog': True,
            'mail_post_autofollow': False,
            'mail_auto_subscribe_no_notify': True,
            'mail_notify_force_send': False,
        })
        silent_env = self.env(context=silent_ctx)

        employees = silent_env['hr.employee'].search([])
        for employee in employees:
            if not _is_sha256(employee.name):
                employee.name = hash_field_value(employee.name)
            if not _is_sha256(employee.first_name):
                employee.first_name = hash_field_value(employee.first_name)
            if not _is_sha256(employee.last_name):
                employee.last_name = hash_field_value(employee.last_name)
            if not _is_sha256(employee.contract_id.name):
                employee.contract_id.name = hash_field_value(employee.contract_id.name)
            if not _is_sha256(employee.work_email):
                employee.work_email = hash_field_value(employee.work_email)
            if not _is_sha256(employee.work_phone):
                employee.work_phone = hash_field_value(employee.work_phone)
            if not _is_sha256(employee.mobile_phone):
                employee.mobile_phone = hash_field_value(employee.mobile_phone)
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

        self.with_env(silent_env).create({
            'name': 'Employee Info Masking Done'
        })

        users_model = silent_env['res.users']
        users = users_model.search([])
        users_has_work_email = 'work_email' in users_model._fields
        users_has_work_phone = 'work_phone' in users_model._fields
        users_has_mobile_phone = 'mobile_phone' in users_model._fields
        for user in users:
            if not _is_sha256(user.name):
                user.name = hash_field_value(user.name)
            if users_has_work_email and not _is_sha256(user.work_email):
                user.work_email = hash_field_value(user.work_email)
            if users_has_work_phone and not _is_sha256(user.work_phone):
                user.work_phone = hash_field_value(user.work_phone)
            if users_has_mobile_phone and not _is_sha256(user.mobile_phone):
                user.mobile_phone = hash_field_value(user.mobile_phone)

        self.with_env(silent_env).create({
            'name': 'User Info Masking Done'
        })

        for rec in silent_env['prx.payroll.transaction'].search([]):
            rec.personal_number = hash_field_value(rec.personal_number)

        for rec in silent_env['prx.payroll.employee.deduction.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        for rec in silent_env['prx.payroll.employee.tax.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        for rec in silent_env['prx.payroll.position.earning.import'].search([]):
            rec.identification_number = hash_field_value(rec.identification_number)

        silent_env.cr.commit()

        model_employees_fields = [
            'name',
            'first_name',
            'last_name',
            'contract_id',
            'work_email',
            'work_phone',
            'mobile_phone',
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

        model_users_fields = ['name']
        if users_has_work_email:
            model_users_fields.append('work_email')
        if users_has_work_phone:
            model_users_fields.append('work_phone')
        if users_has_mobile_phone:
            model_users_fields.append('mobile_phone')

        model_fields = {
            'hr.employee': model_employees_fields,
            'res.partner.bank': model_res_partner_bank_fields,
            'res.users': model_users_fields
        }

        for key, value in model_fields.items():
            self.with_env(silent_env).hash_model_logs(
                hashing=True,
                model_name=key,
                fields_names=value
            )



    def action_mask_payroll_info(self):
            self.env['prx.payroll.import.wizard'].sudo().search([]).unlink()
            
            rand_rate_calc = _random_rate()

            self.env.cr.execute("""
                UPDATE prx_payroll_position_earning
                SET amount = round((amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_employee_deduction
                SET amount = round((amount * %(rand_rate)s)::numeric, 10),
                    limit_amount = round((limit_amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_worksheet_line
                SET amount = round((amount * %(rand_rate)s)::numeric, 10),
                    rate = round((rate * %(rand_rate)s)::numeric, 10),
                    over_time_amount = round((over_time_amount * %(rand_rate)s)::numeric, 10),
                    over_time_earning_rate = round((over_time_earning_rate * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_worksheet_detail
                SET amount = round((amount * %(rand_rate)s)::numeric, 10),
                    rate = round((rate * %(rand_rate)s)::numeric, 10),
                    earning_amount = round((earning_amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_position_earning_import
                SET amount = round((amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_position_earning_import
                SET amount = round((amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_transaction
                SET amount = round((amount * %(rand_rate)s)::numeric, 2),
                    rate   = round((rate * %(rand_rate)s)::numeric, 2)
            """, {'rand_rate': rand_rate_calc})

            self.env.cr.execute("""
                UPDATE prx_payroll_employee_tax
                SET used_tax_amount = round((used_tax_amount * %(rand_rate)s)::numeric, 10)
            """, {'rand_rate': rand_rate_calc})

            self.create({
                'name': 'Payroll Info Masking Done'
            })

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
