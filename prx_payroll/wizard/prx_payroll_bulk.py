from odoo import models, fields, api

class BulkUpdateWizard(models.TransientModel):
    _name = 'prx.payroll.bulk.wizard'
    _description = 'Bulk Update Currency & End Date'

    end_date = fields.Date(string="End Date", required=True)
    currency_id = fields.Many2one('res.currency', string="Currency")

    def action_apply(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return

        records = self.env[self.env.context.get('active_model')].browse(active_ids)
        data_set = {
            'end_date': self.end_date,
        }
        if self.currency_id:
            data_set['currency_id'] = self.currency_id.id,
        records.write(data_set)
