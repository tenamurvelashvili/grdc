from odoo import models, fields
from datetime import datetime
from .prx_rs_enum import WorkTypeList, EmployeeStatusSelectionList, GenderList,Gender
from odoo.exceptions import UserError
import time


class PrxRsEmployee(models.Model):
    _name = 'prx.rs.service.employee'
    _description = 'PRX RS Registered Employees'

    external_ref = fields.Char(string="ID", required=True, index=True)
    tin = fields.Char(string="TIN", required=True, index=True)
    org_tin = fields.Char(string="Organization TIN", index=True)
    org_fullname = fields.Char(string="Organization Full Name")
    citizenship = fields.Char(string="Citizenship")
    fullname = fields.Char(string="Full Name", required=True)
    phone = fields.Char(string="Phone")
    gender = fields.Selection(Gender.selection(), string="Gender")
    gender_txt = fields.Char(string="Gender")
    birth_date = fields.Date(string="Birth Date")
    create_date = fields.Datetime(string="Create Date")
    activate_date = fields.Datetime(string="Activate Date")
    cancel_date = fields.Datetime(string="Cancel Date")
    work_type = fields.Char(string="Work Type")
    work_type_txt = fields.Char(string="Work Type")
    status = fields.Char(string="Status")
    status_txt = fields.Char(string="Status")
    is_foreigner = fields.Boolean(string="Is Foreigner")
    is_corrected = fields.Boolean(string="Is Corrected")
    is_corrected_icon = fields.Binary(string="Corrected Icon")
    is_corrected_txt = fields.Char(string="Is Corrected")
    citizen_country_id = fields.Many2one('prx.tax.report.country', string="Citizen Country")
    last_change_date = fields.Datetime(string="Last Change Date")
    suspend_date = fields.Datetime(string="Suspend Date")
    last_change_by = fields.Char(string="Last Changed By")

    def open_employee_wizards(self):
        action = self.env.ref('prx_rs_employee_service.action_prx_rs_employee_wizard').read()[0]
        return action

    def create_rs_employee(self, tin=False):
        raw = self.env['prx.rs.employee.integration']._get_rs_employee_list(tin=tin)
        data_block = raw.get('Data') or {}
        header_fields = data_block.get('Fields') or []
        rows = data_block.get('Rows') or []

        if not header_fields or not rows:
            return

        def parse_date(date_str):
            if not date_str:
                return False
            try:
                return datetime.strptime(date_str, '%d-%m-%Y').date()
            except Exception:
                return False

        def parse_datetime(dt_str):
            if not dt_str:
                return False
            try:
                dt = datetime.strptime(dt_str, '%d-%m-%Y')
                return dt.strftime('%Y-%m-%d 00:00:00')
            except ValueError:
                try:
                    dt = datetime.strptime(dt_str, '%d-%m-%Y %H:%M:%S')
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    return False

        country_model = self.env['prx.tax.report.country']

        for row in rows:
            if len(row) != len(header_fields):
                continue

            record_data = dict(zip(header_fields, row))

            raw_country_id = record_data.get('CITIZEN_COUNTRY_ID')
            country_id = False
            if raw_country_id:
                try:
                    cid = int(raw_country_id)
                    country_rec = country_model.browse(cid)
                    if country_rec.exists():
                        country_id = cid
                except (ValueError, TypeError):
                    country_id = False

            vals = {
                'external_ref': str(int(record_data.get('ID'))) if record_data.get('ID') else False,
                'tin': record_data.get('TIN') or False,
                'org_tin': record_data.get('ORG_TIN') or False,
                'org_fullname': record_data.get('ORG_FULLNAME') or False,
                'citizenship': record_data.get('CITIZENSHIP') or False,
                'fullname': record_data.get('FULLNAME') or False,
                'phone': record_data.get('PHONE') or False,
                'gender': str(int(record_data.get('GENDER'))) if record_data.get('GENDER') else False,
                'gender_txt': record_data.get('GENDER_TXT') or False,
                'birth_date': parse_date(record_data.get('BIRTH_DATE')),
                'create_date': parse_datetime(record_data.get('CREATE_DATE')),
                'activate_date': parse_datetime(record_data.get('ACTIVATE_DATE')),
                'cancel_date': parse_datetime(record_data.get('CANCEL_DATE')),
                'work_type': record_data.get('WORK_TYPE') or False,
                'work_type_txt': record_data.get('WORK_TYPE_TXT') or False,
                'status': str(int(record_data.get('STATUS'))) if record_data.get('STATUS') is not None else False,
                'status_txt': record_data.get('STATUS_TXT') or False,
                'is_foreigner': bool(int(record_data.get('IS_FOREIGNER', 0))),
                'is_corrected': bool(int(record_data.get('IS_CORRECTED', 0))),
                'is_corrected_icon': record_data.get('IS_CORRECTED_ICON') or False,
                'is_corrected_txt': record_data.get('IS_CORRECTED_TXT') or False,
                'citizen_country_id': country_id,
                'last_change_date': parse_datetime(record_data.get('LAST_CHANGE_DATE')),
                'suspend_date': parse_datetime(record_data.get('SUSPEND_DATE')),
                'last_change_by': record_data.get('LAST_CHANGE_BY') or False,
            }

            try:
                self.env['prx.rs.service.employee'].create(vals)
            except Exception as e:

                continue


class PRXRsEmployeeRequest(models.Model):
    _name = 'prx.rs.employee.request'
    _description = 'Custom Person from External JSON'

    employee_id = fields.Many2one('hr.employee', string='Employees')
    rs_employee_id = fields.Integer(string='RS ID')
    is_foreigner = fields.Boolean(string='Is Foreigner')
    tin = fields.Char(string='TIN')
    fullname = fields.Char(string='Full Name')
    gender = fields.Selection(GenderList.selection(), string='Gender')
    status = fields.Selection(EmployeeStatusSelectionList.selection(), string='Status')
    citizen_country_id = fields.Many2one('prx.tax.report.country')
    phone = fields.Char(string='Phone')
    work_type = fields.Selection(WorkTypeList.selection(), string='Work Type')
    birth_date = fields.Date(string='Birth Date')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.fullname)

    def _get_rs_employee_status(self):
        employees = {'active': [], 'cancel': []}

        base_employee = self.env['hr.employee'].search([])
        with_open = base_employee.filtered(lambda e: any(c.state == 'open' for c in e.contract_ids))

        employees['active'] = with_open.filtered(
            lambda e: not e.rs_employee_status or ( e.rs_employee_id and e.rs_employee_status == '0')
        )

        with_cancel = base_employee.filtered(lambda e: any(c.state != 'open' for c in e.contract_ids))
        employees['cancel'] = with_cancel.filtered(
            lambda e: e.rs_employee_id and e.rs_employee_status == '1'
        )
        return employees

    def generate_employees(self):
        employees = self._get_rs_employee_status()
        if any([employees['active'], employees['cancel']]):
            for employee in employees['active']:
                self.create(
                    {
                        'employee_id': employee.id,
                        'rs_employee_id': employee.rs_employee_id,
                        'is_foreigner': bool(employee.tax_country.code != "268"),
                        'tin': employee.identification_id,
                        'fullname': employee.name,
                        'gender': str(Gender.selection()[employee.gender]) if employee.gender else None,
                        'status': '1',
                        'citizen_country_id': employee.tax_country.code if employee.tax_country.code != "268" else None,
                        'phone': employee.private_phone,
                        'birth_date': employee.birthday,
                        'work_type': str(employee.work_type) if employee.work_type else None
                    }
                )
            for employee in employees['cancel']:
                self.create(
                    {
                        'employee_id': employee.id,
                        'rs_employee_id': employee.rs_employee_id,
                        'is_foreigner': bool(employee.tax_country.code != "268"),
                        'tin': employee.identification_id,
                        'fullname': employee.name,
                        'gender': str(Gender.selection()[employee.gender]) if employee.gender else None,
                        'status': '0',
                        'citizen_country_id': employee.tax_country.code if employee.tax_country.code != "268" else None,
                        'phone': employee.private_phone,
                        'birth_date': employee.birthday or None,
                        'work_type': str(employee.work_type) if employee.work_type else None
                    }
                )

    def request_employee_rs(self):

        results = []
        for rec in self:
            is_foreigner = bool(rec.citizen_country_id.code != "268")
            payload = {
                "ID": 0 if not rec.rs_employee_id else rec.rs_employee_id,
                "IS_FOREIGNER": 0 if is_foreigner else 1,
                "TIN": rec.tin,
                "FULLNAME": rec.fullname if is_foreigner else None,
                "GENDER": int(rec.gender) if is_foreigner and rec.gender else None,
                "CITIZEN_COUNTRY_ID": rec.citizen_country_id.code or None if is_foreigner else None,
                "STATUS": int(rec.status),
                "PHONE": rec.phone,
                "WORK_TYPE": int(rec.work_type) if rec.work_type else None,
                "BIRTH_DATE": rec.birth_date or None if is_foreigner else None
            }
            status_code = int(rec.status)
            time.sleep(1)
            response = self.env['prx.rs.employee.integration']._create_employee(
                employee_id=rec.employee_id,
                status=status_code,
                validate=False,
                payload=payload
            )

            outcome = 'Success' if not response else response
            results.append({'name': rec.fullname or rec.employee_id.name,
                            'status': outcome})
        summary_lines = [f"{item['name']}: {item['status']}" for item in results]
        summary_text = '\n'.join(summary_lines)
        self.env.cr.commit()
        raise UserError(f"\n{summary_text}")
