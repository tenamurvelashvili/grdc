from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import SQL, clean_context



class HrApplicant(models.Model):
    _inherit = 'hr.applicant'
    
    first_name = fields.Char(string='First Name', compute='_compute_fr_ls', groups="hr.group_hr_user")
    last_name = fields.Char(string='Last Name',compute='_compute_fr_ls',  groups="hr.group_hr_user")
    
    
    
    @api.depends('candidate_id')
    def _compute_fr_ls(self):
        for applicant in self:
            applicant.first_name = applicant.candidate_id.first_name
            applicant.last_name = applicant.candidate_id.last_name

                
                
    # @api.onchange('first_name', 'last_name')
    # def _onchange_name(self):
    #     for applicant in self:
    #         fn = applicant.first_name or ''
    #         ln = applicant.last_name or ''
    #         applicant.partner_name = (fn + ' ' + ln).strip()
            
    def write(self, vals):
        if 'first_name' in vals or 'last_name' in vals:
            for rec in self:
                fn = vals.get('first_name', rec.first_name) or ''
                ln = vals.get('last_name',  rec.last_name)  or ''
                vals['partner_name'] = (fn + ' ' + ln).strip()
        return super().write(vals)
    
    # @api.onchange('first_name', 'last_name')
    # def _onchange_applicant_name(self):
    #     for applicant in self:
    #         fn = applicant.first_name or ''
    #         ln = applicant.last_name or ''
    #         applicant.partner_name = (fn + ' ' + ln).strip()
            
            
    def create_employee_from_applicant(self):
        self.ensure_one()
        action = self.candidate_id.create_employee_from_candidate()
        employee = self.env['hr.employee'].browse(action['res_id'])
        employee.write({
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name': self.first_name + ' ' + self.last_name,
            'job_id': self.job_id.id,
            'job_title': self.job_id.name,
            'department_id': self.department_id.id,
            'work_email': self.department_id.company_id.email or self.email_from, # To have a valid email address by default
            'work_phone': self.department_id.company_id.phone,
        })
        return action
    


class HrCandidateEXT(models.Model):
    _inherit = 'hr.candidate'
    
    first_name = fields.Char(string='First Name', groups="hr.group_hr_user")
    last_name = fields.Char(string='Last Name', groups="hr.group_hr_user")
    
    @api.onchange('first_name', 'last_name')
    def _onchange_name(self):
        for candidate in self:
            fn = candidate.first_name or ''
            ln = candidate.last_name or ''
            candidate.partner_name = (fn + ' ' + ln).strip()
            
    def write(self, vals):
        if 'first_name' in vals or 'last_name' in vals:
            for rec in self:
                fn = vals.get('first_name', rec.first_name) or ''
                ln = vals.get('last_name',  rec.last_name)  or ''
                vals['partner_name'] = (fn + ' ' + ln).strip()
        return super().write(vals)