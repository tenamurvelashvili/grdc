from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError

class PRXPayrollWorksheetManager(models.Model):
    _name = 'prx.payroll.worksheet.manager'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll worksheet manager'
    _check_company_auto = True

    @api.constrains('worksheet_manager_id', 'company_id')
    def _check_unique_manager(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('worksheet_manager_id', '=', rec.worksheet_manager_id.id),
                ('company_id', '=', rec.company_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError("მენეჯერი უკვე არსებობს ამ კომპანიისთვის.")

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        required=True, readonly=True,
    )
    worksheet_manager_id = fields.Many2one('hr.employee', string="მენეჯერი",required=True)
    line_ids = fields.One2many(
        'prx.payroll.worksheet.manager.line',
        'header_id', string="თანამშრომელი",
        required=True
    )

    def action_open_manager_lines(self):
        self.ensure_one()
        list_view_id = self.env.ref('prx_payroll.view_hr_employee_tree_prx').id
        return {
            'type': 'ir.actions.act_window',
            'name':'თანამშრომელი',
            'res_model': 'hr.employee',
            'view_mode': 'list',
            'context': {'header_id': self.id},
            'views': [(list_view_id, 'list')],
            'target': 'new',
            'help': '<p class="o_view_nocontent_smiling_face">ჩანაწერები ვერ მოიძებნა</p>',
        }

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.worksheet_manager_id.name)

    @api.model_create_multi
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_managed_employees()
        return rec

    def write(self, vals):
        res = super().write(vals)
        self._sync_managed_employees()
        return res

    def _sync_managed_employees(self):
        for rec in self:
            user = rec.worksheet_manager_id.user_id
            if user:
                employee_ids = rec.line_ids.mapped('employee_id')
                user.managed_employee_ids = [(6, 0, employee_ids.ids)]


class PRXPayrollWorksheetManagerLine(models.Model):
    _name = 'prx.payroll.worksheet.manager.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll worksheet manager line'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    header_id = fields.Many2one(
        'prx.payroll.worksheet.manager',
        string="მენეჯერი",
        ondelete='cascade',
        required=True,
    )
    employee_id = fields.Many2one('hr.employee', string="თანამშრომელი")

    @api.constrains('employee_id', 'company_id')
    def _check_unique_employee(self):
        for rec in self:
            if not rec.employee_id:
                continue
            domain = [
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('company_id', '=', rec.company_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError("ამ თანამშრომელზე ჩანაწერი უკვე არსებობს.")

    position_id = fields.Many2one(
        'hr.job',
        string='პოზიცია',
        compute='_compute_position',
        store=True,
    )
    department = fields.Many2one(
        'hr.department',
        string="დეპარტამენტი",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )

    active_contract = fields.Boolean(compute="_compute_employee_contract",string="ატიური კონტრაქტი")
    @api.depends('employee_id')
    def _compute_employee_contract(self):
        for rec in self:
            rec.active_contract = bool(self.env['hr.contract'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'open')
            ]))

    @api.depends('employee_id')
    def _compute_position(self):
        for rec in self:
            rec.position_id = rec.employee_id.job_id