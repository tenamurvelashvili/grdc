from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta
from .prx_rs_API import EmployeeAPIClient
from .prx_rs_enum import AuthMethod


class Users(models.Model):
    _inherit = 'res.users'

    prx_res_employee = fields.One2many('prx.rs.employee.users', inverse_name='user_id')

class PRXRSEmployeeUsers(models.Model):
    _name = 'prx.rs.employee.users'
    _description = 'RS User authorisation'

    company_id = fields.Many2one(string='Company', comodel_name='res.company', required=True,
                                 default=lambda self: self.env.company)
    auth_id = fields.Char('Auth Name')
    auth_passw = fields.Char('Auth Password')
    user_id = fields.Many2one('res.users')
    api_auth_type = fields.Selection(AuthMethod.selection(), default="0", string='Auth Type')
    api_device_code = fields.Char(string='Device Code')
    active_status = fields.Boolean('Active')
    token = fields.Char(string='Token')
    token_end = fields.Datetime(string='Token End Date')

    @api.constrains('active_status')
    def check_account(self):
        for rec in self:
            if rec.active_status and len(self.search([('company_id', '=', rec.company_id.id),
                                                      ('active_status', '=', True),
                                                      ('id', '!=', rec.id),
                                                      ('user_id', '=', rec.user_id.id)])) > 0:
                raise UserError('This access must be unique!')

    def update_token(self, token):
        now = fields.Datetime.now()
        parameter_key = 'prx_rs_employee_service.rs_employee_api_token_expired_time'
        token_valid = self.env['ir.config_parameter'].sudo().get_param(parameter_key)
        expiration_time = now + timedelta(seconds=int(token_valid))
        self.write(
            {
                'token': token,
                'token_end': expiration_time,
                'active_status': True
            })

    def get_credentials(self):
        credentials = self.sudo().search([('active_status', '=', True), ('user_id', '=', self.env.user.id)])
        return credentials.auth_id, credentials.auth_passw

    def get_stored_token(self):
        token = self.sudo().search([('active_status', '=', True), ('user_id', '=', self.env.user.id)])
        return token.token_end, token.token

    def _auth(self):
        token_end, token = self.get_stored_token()
        if token_end and token_end > fields.Datetime.now():
            return token
        employee_user = self.env['prx.rs.employee.users'].sudo().search(
            [('user_id', '=', self.env.user.id), ('active_status', '=', True)])
        if not employee_user:
            raise UserError('User credentials not found!')
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'prx_rs_employee_service.rs_employee_api_base_url'
        )
        client = EmployeeAPIClient(
            base_url=base_url,
            username=employee_user.auth_id,
            password=employee_user.auth_passw,
            auth_type=0,  # self.api_auth_type,
            device_code=None,  # self.api_device_code
        )
        status, data = client.authenticate()
        if status != 200:
            raise UserError(f"{status, data['STATUS']['TEXT']}")
        employee_user.update_token(data['ACCESS_TOKEN'])
        return data['ACCESS_TOKEN']
