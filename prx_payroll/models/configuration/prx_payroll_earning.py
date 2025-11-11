from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError
from .prx_enum_selection import EarningUnit,RecordType,SalaryType


class PRXPayrollEarning(models.Model):
    _name = 'prx.payroll.earning'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll earning'

    earning = fields.Char(string = 'ანაზღაურება',required=True,tracking=True,translate=True)
    earning_type = fields.Many2one('prx.payroll.earning.type',string = 'ანაზღაურების ტიპი',tracking=True)
    earning_group = fields.Many2one('prx.payroll.earning.group',string = 'ანაზღაურების ჯგუფი',tracking=True)
    no_material = fields.Boolean(string='არაფულადი სარგებელი',tracking=True)
    earning_unit = fields.Selection(EarningUnit.selection(),string = 'ანაზღაურების ერთეული',required=True,tracking=True)
    record_type = fields.Selection(RecordType.selection(),string = 'ჩანაწერის რაოდენობა',required=True,tracking=True)
    production_base = fields.Boolean(string='გამომუშავებით',tracking=True)
    tax_report = fields.Many2one('prx.tax.report.earning.type',string = 'განაცემის სახე',tracking=True)
    another_income = fields.Boolean(string='სხვა ფულადი შემოსავალი')
    salary_type = fields.Selection(SalaryType.selection(),required=True,default='standard',string="პროცესის ტიპი")
    code = fields.Char(string="კოდი")
    report_name = fields.Char(compute="_compute_report_name", string="რეპორტის დასახელება", store=True,compute_sudo=True)
    insurance = fields.Boolean(string='დაზღვევა',tracking=True)
    bonus = fields.Boolean(string='მონაწილეობს ბონუსი',help='მიიღოს ბუნუსის დაანგარიშებაში მონაწილეობა')
    link_insurance_ded = fields.Many2one('prx.payroll.deduction',string="დაქვითვა",domain=[('deduction_calc_type','=','percentage')])
    
    pension_check = fields.Boolean(compute='_compute_pension_check', store=False, compute_sudo=True)    

    @api.constrains('production_base','earning_unit')
    def _validate_earning_unit(self):
        if not self.production_base and self.earning_unit in ('unit','shift','half_time'):
            raise ValidationError(f"ანაზღაურების ერთეული '{dict(self._fields['earning_unit'].selection).get(self.earning_unit)}' შესაძლებელია მხოლოდ გამომუშავებითზე!")

    @api.onchange('insurance')
    def _onchange_insurance(self):
        if not self.insurance:
            self.link_insurance_ded = False

    def write(self, vals):
        if 'insurance' in vals and not vals.get('insurance'):
            vals['link_insurance_ded'] = False
        return super().write(vals)

    @api.depends('code', 'earning')
    def _compute_report_name(self):
        for rec in self:
            rec.report_name = "{}.{}".format(rec.code,rec.earning)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.earning)
            
    def _compute_pension_check(self):
        config_param = self.env['ir.config_parameter'].sudo()
        for rec in self:
            value = config_param.get_param('prx_payroll.prx_pension_insurance')
            rec.pension_check = bool(value and value not in ['False', '0'])