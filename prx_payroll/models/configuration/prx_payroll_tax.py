from odoo import models, fields, api

class PRXPayrollTax(models.Model):
    _name = 'prx.payroll.tax'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll Tax'
    _rec_name = 'tax'

    tax = fields.Char(string='გადასახადი', translate=True, required=True,tracking=True)
    description = fields.Char(string='აღწერა',tracking=True,translate=True)
    rate_gross = fields.Float(string='გროს განაკვეთი',digits=(19, 2),tracking=True)
    rate_net = fields.Float(string='ნეტ განაკვეთი',digits=(19, 2),tracking=True)
    rate_base = fields.Float(string='საბაზისო განაკვეთი', digits=(19, 2),tracking=True)
    code = fields.Char(string="კოდი")
    report_name = fields.Char(compute="_compute_report_name", string="რეპორტის დასახელება", store=True,compute_sudo=True)

    @api.depends('code', 'tax')
    def _compute_report_name(self):
        for rec in self:
            rec.report_name = "{}.{}".format(rec.code,rec.tax)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.tax)