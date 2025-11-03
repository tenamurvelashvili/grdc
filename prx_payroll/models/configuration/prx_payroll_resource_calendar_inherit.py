from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError

class ResourceCalendar(models.Model):
    _inherit ='resource.calendar'

    def create_organisation_calendar(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Organisation Calendar',
            'res_model': 'prx.organisation.calendar',
            'view_mode': 'form',
            'view_id': self.env.ref('prx_payroll.view_prx_organisation_calendar_wizard').id,
            'context':{'default_schedule_type_id':self.id},
            'target': 'new',
        }