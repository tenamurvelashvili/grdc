from odoo import models, fields, api
from odoo.exceptions import UserError
from .prx_rs_API import EmployeeAPIClient
from .prx_rs_enum import Gender, EmployeeStatus
import logging

_logger = logging.getLogger(__name__)

class PRXRSEmployeeService(models.AbstractModel):
    _name = 'prx.rs.employee.integration'
    _description = 'RS Integration'

    def _get_token(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'prx_rs_employee_service.rs_employee_api_base_url'
        )
        rs_user = self.env['prx.rs.employee.users'].sudo().search([('user_id', '=', self.env.user.id)])
        token = rs_user._auth()
        if not token:
            raise UserError('Token can not be generated!')
        return token,base_url

    def _create_employee(self, employee_id,status,validate=True,payload=False):
        """
            employee_id: hr.employee
            status: statuses of EmployeeStatus
        """
        is_foreigner = bool(employee_id.tax_country.code != "268")
        if not payload:
            payload = {
                "ID": 0 if not employee_id.rs_employee_id else employee_id.rs_employee_id,
                "IS_FOREIGNER": 1 if is_foreigner else 0,
                "TIN": employee_id.identification_id,
                "FULLNAME": employee_id.name if is_foreigner else None,
                "GENDER": str(Gender.selection()[employee_id.gender]) if employee_id.gender and employee_id.gender in ['male','female'] else None,
                "CITIZEN_COUNTRY_ID": employee_id.tax_country.code if is_foreigner else None,
                "STATUS": status,
                "PHONE": employee_id.private_phone,
                "WORK_TYPE": int(employee_id.work_type),
                "BIRTH_DATE": employee_id.birthday if is_foreigner and employee_id.birthday else None
            }
        token,base_url = self._get_token()
        client = EmployeeAPIClient(
            base_url=base_url,
            token=token,
        )
        status, data = client.save_employee(payload)
        _logger.info(f"RS Payload:{payload}")
        _logger.info(f"RS request:{data} --- {status}")
        if status != 200:
            if not validate:
                return f"{status, data['STATUS']['TEXT']}"
            raise UserError(f"{status, data['STATUS']['TEXT']}")
        employee_id.write(
            {
                'rs_employee_id': data['ID'],
                'rs_employee_status': str(payload['STATUS'])
            })
        self.env.cr.commit()

    def _get_rs_employee_list(self,tin=False):
        token, base_url = self._get_token()
        client = EmployeeAPIClient(
            base_url=base_url,
            token=token,
        )

        status, payload = client.list_employees(tin=tin if tin else None)
        if status != 200:
            raise UserError(f"{status, payload['STATUS']['TEXT']}")
        return payload