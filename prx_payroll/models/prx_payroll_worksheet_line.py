from odoo import models, fields, api,_
from odoo.exceptions import UserError,ValidationError
from markupsafe import Markup

class PRXPayrollWorksheetLine(models.Model):
    _name = 'prx.payroll.worksheet.line'
    _description = 'Payroll worksheet line'
    _order = "date asc,earning_id"
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    worksheet_id = fields.Many2one('prx.payroll.worksheet',ondelete="cascade", string="ტაბელი")
    employee_id = fields.Many2one(related='worksheet_id.worker_id') #დეტალებისთვის
    date = fields.Date(string="თარიღი",required=True,tracking=True)
    earning_domain_ids = fields.One2many('prx.payroll.position.earning',compute='_domain_ids')
    earning_id = fields.Many2one('prx.payroll.position.earning',string="ანაზღაურება",required=True,tracking=True)
    earning_amount = fields.Float(related='earning_id.amount',string="ანაზრაურების თანხა",digits=(19, 2),readonly=True,tracking=True)
    rate = fields.Float(compute="_calculate_earning_rate",tracking=True,string="განაკვეთი",digits=(16, 10),readonly=False,required=True,store=True)
    amount = fields.Float(compute='_calculate_earning',string="თანხა",digits=(16, 10),readonly=False,store=True,tracking=True)
    quantity = fields.Float(string="რაოდენობა",digits=(16, 4),required=True,tracking=True)
    over_time_earning_rate = fields.Float(string="ზეგანაკვეთურის განაკვეთი",digits=(16, 10),tracking=True)
    over_time_qty = fields.Float(string="ზეგანაკვეთის რაოდენობა",digits=(16, 2))
    over_time_amount = fields.Float(string="ზეგანაკვეთის თანხა",digits=(16, 10))
    absence_trans_id = fields.Integer(string="გაცდენის კოდი")
    source = fields.Selection([('system','system'),('manual','manual')],string="წყარო",default='manual',readonly=True)
    is_production_base = fields.Boolean(related='earning_id.earning_id.production_base')
    time_of_type = fields.Many2one('hr.leave.type', string="Time Off Type")
    kind_of_time_type = fields.Selection(related='time_of_type.time_type', string="Kind of Time Off")
    earning_unit = fields.Selection(related='earning_id.earning_id.earning_unit',string="გამომუშავების ტიპი")
    wizard_date = fields.Date()

    payroll_admin = fields.Boolean(compute="_is_payroll_admin")
    def _is_payroll_admin(self):
        self.payroll_admin = bool(self.env.user.has_group('prx_payroll.prx_payroll_administrator'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.earning_id.earning_id.earning)

    @api.model_create_multi
    def create(self, vals):
        line = super(PRXPayrollWorksheetLine, self).create(vals)
        if line.worksheet_id:
            line.worksheet_id._update_payroll_worksheet_details()
        return line

    def write(self, vals):
        tracked_fields = set(vals.keys())
        old_data = {
            rec.id: {f: rec[f] for f in tracked_fields}
            for rec in self
        }

        res = super(PRXPayrollWorksheetLine, self).write(vals)
        for line in self:
            if line.worksheet_id:
                line.worksheet_id._update_payroll_worksheet_details()

        for rec in self:
            print(old_data.get(rec.id, {}))
            rec._post_change_diff(old_vals=old_data.get(rec.id, {}), new_vals=vals, action='updated')
        return res

    def _post_change_diff(self, old_vals, new_vals, action):
        lines = []

        def _safe_val(val):
            """Return comparable and readable value."""
            if hasattr(val, 'id'):
                return val.id
            return val

        def _display_val(val):
            """Return display name if record, else raw."""
            if hasattr(val, 'display_name'):
                return val.display_name
            return val if val is not None else _('(unset)')

        field_labels = {f: self._fields[f].string for f in new_vals}
        if action == 'created':
            lines.append(Markup("<li><strong>New line created</strong></li>"))

        for field, new in new_vals.items():
            old = old_vals.get(field)
            if action == 'updated' and _safe_val(old) == _safe_val(new):
                continue
            label = field_labels.get(field, field)
            lines.append(Markup("<li>") + f"{label}: {_display_val(old)} → {_display_val(new)}" + Markup("</li>"))

        if not lines:
            return
        body = Markup("<b>Line {}</b><ul>").format(_('changes')) + Markup().join(lines) + Markup("</ul>")
        self.worksheet_id.message_post(body=body, message_type='comment')

    def unlink(self):
        worksheet_ids = self.mapped('worksheet_id')
        res = super(PRXPayrollWorksheetLine, self).unlink()
        if worksheet_ids:
            worksheet_ids._update_payroll_worksheet_details()
        return res

    @api.onchange('earning_id')
    def _calculate_earning_rate(self):
        for rec in self:
            rec.rate = rec.earning_id.amount

    @api.depends('earning_id','quantity','rate')
    def _calculate_earning(self):
        for rec in self:
            if rec.quantity or rec.rate:
                rec.amount = (rec.rate or 1) * rec.quantity
            else:
                rec.amount = rec.earning_id.amount

    @api.depends('earning_id', 'worksheet_id', 'date')
    def _domain_ids(self,on_date=False):
        for rec in self:
            domain_ids = []
            if len(self) == 1:
                earnings = self.env['prx.payroll.position.earning'].search([
                    ('employee_id', '=', rec.worksheet_id.worker_id.id)
                ])
                for earn in earnings:
                    if self.date and self.date >= earn.start_date and not earn.end_date:
                        domain_ids.append(earn.id)
                        continue
                    if not earn.start_date:
                        continue
                    for dt in self:
                        if not on_date:
                            if dt.date and earn.end_date >= dt.worksheet_id.period_id.start_date:
                                domain_ids.append(earn.id)
                        else:
                            if earn.end_date and dt.date and earn.end_date >= dt.date:
                                domain_ids.append(earn.id)
            rec.earning_domain_ids = [(6, 0, domain_ids)] if domain_ids else None


    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            self._domain_ids(on_date=True)