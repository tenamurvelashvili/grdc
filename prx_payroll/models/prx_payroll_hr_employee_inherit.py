from odoo import models, fields,api
from odoo.exceptions import UserError,ValidationError

class Employee(models.Model):
    _inherit = 'hr.employee'

    have_running_contract = fields.Boolean(compute='_compute_have_running_contract')
    first_name = fields.Char(string='First Name', groups="hr.group_hr_user")
    last_name = fields.Char(string='Last Name', groups="hr.group_hr_user")
    tax_country = fields.Many2one('prx.tax.report.country', string='Tax Country', groups="hr.group_hr_user")
    tax_category = fields.Many2one('prx.tax.report.category', string='Tax Category', groups="hr.group_hr_user")
    county_code = fields.Char(string='County Code', related='country_id.code', readonly=True, groups="hr.group_hr_user")
    bonus_category = fields.Many2one('prx.payroll.bonus.category',string='ბონუსის კატეგორია')

    def create(self, vals):
        if 'first_name' in vals or 'last_name' in vals:
            fn = vals.get('first_name', '') or ''
            ln = vals.get('last_name', '')  or ''
            vals['name'] = (fn + ' ' + ln).strip()
        return super().create(vals)

    def write(self, vals):
        if 'first_name' in vals or 'last_name' in vals:
            for rec in self:
                fn = vals.get('first_name', rec.first_name) or ''
                ln = vals.get('last_name',  rec.last_name)  or ''
                vals['name'] = (fn + ' ' + ln).strip()
        return super().write(vals)

    def _compute_have_running_contract(self):
        for rec in self:
            rec.have_running_contract = bool(rec.contract_ids.filtered(lambda c: c.state == 'open'))

    def action_open_worksheets(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'ტაბელები',
            'res_model': 'prx.payroll.worksheet',
            'view_mode': 'list,form',
            'domain': [('worker_id','=',self.id)],
            'context': {'search_default_open_status': 1},
            'target': 'new',
            'search_view_id': self.env.ref('prx_payroll.view_prx_payroll_worksheet_search').id,
        }

    def action_open_position_earning(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'პოზიციის ანაზღაურება',
            'res_model': 'prx.payroll.position.earning',
            'view_mode': 'list,form',
            'domain': [('employee_id','=',self.id)],
            'context': {'search_default_active': 1},
            'target': 'new',
            'search_view_id': self.env.ref('prx_payroll.view_prx_payroll_position_earning_search').id,
        }

    def action_add_employee_line(self):
        header_id = self.env.context.get('header_id')
        for record in self:
            self.env['prx.payroll.worksheet.manager.line'].create(
                {
                    'header_id': header_id,
                    'employee_id': record.id,
                },
            )