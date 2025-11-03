from odoo import models, fields, api
from odoo.exceptions import UserError


class PRXPayrollCreateWorksheetWizard(models.TransientModel):
    _name = "prx.payroll.create.worksheet.wizard"
    _description = "Worksheet wizard"

    date = fields.Date(string="თარიღი", required=True)
    earning_id = fields.Many2one('prx.payroll.earning', string="ანაზღაურება",required=True)
    department_id = fields.Many2one('hr.department', string="დეპარტამენტი")

    count_not_created = fields.Integer(string="რაოდენობა(შესაქმნელი)", compute="_compute_amount_totals")
    count_created = fields.Integer(string="რაოდენობა(შექმნილი)", compute="_compute_amount_totals")

    @api.depends('line_ids_not_created', 'line_ids_created')
    def _compute_amount_totals(self):
        for wizard in self:
            wizard.count_not_created = len(wizard.line_ids_not_created)
            wizard.count_created = len(wizard.line_ids_created)

    line_ids_not_created = fields.One2many(
        'prx.payroll.create.worksheet.wizard.line',
        'wizard_id',
        string="შესაქმნელი"
    )

    line_ids_created = fields.One2many(
        'prx.payroll.create.worksheet.wizard.line',
        'wizard_created_id',
        string="შექმნილი"
    )

    @api.onchange('date', 'earning_id', 'department_id')
    def onchange_filter_data(self):
        """ეს onchange იძახება მხოლოდ ფორმის UI-ზე"""
        self.line_ids_not_created = [(5, 0, 0)]
        self.line_ids_created = [(5, 0, 0)]

        if not self.date or not self.earning_id:
            return

        access_employees = self.env['prx.payroll.worksheet.manager'].search(
            [('worksheet_manager_id', '=', self.env.user.employee_id.id)]
        ).line_ids.mapped('employee_id')

        earnings = self.env['prx.payroll.position.earning'].search([
            ('start_date', '<=', self.date),
            '|',
            ('end_date', '=', False),
            ('end_date', '>=', self.date),
            ('exception', '=', False),
            ('earning_id', '=', self.earning_id.id),
        ])

        if not self.env.user.has_group('prx_payroll.prx_payroll_administrator'):
            earnings = earnings.filtered(lambda c: c.employee_id in access_employees)

        if self.department_id:
            earnings = earnings.filtered(lambda c: c.employee_id.department_id == self.department_id)

        periods = self.env['prx.payroll.period'].search([
            ('start_date', '<', self.date),
            ('end_date', '>', self.date)
        ])
        earning_lines = self.env['prx.payroll.worksheet.line']
        lines_not_created, lines_created = [], []
        for earning in earnings:
            worksheet = self.env['prx.payroll.worksheet'].search([
                ('period_id', 'in', periods.ids),
                ('worker_id', '=', earning.employee_id.id),
                ('status', '=', 'open'),
                ('salary_type', '=', 'standard'),
            ], limit=1)

            if not worksheet:
                continue

            moved = bool(self._get_moved(
                earning=earning,
                worksheet=worksheet
            ))
            line_vals = {
                'moved': moved,
                'employee_id': earning.employee_id.id,
                'department_id': earning.employee_id.department_id.id,
                'worksheet': worksheet.id,
                'period_id': worksheet.period_id.id,
                'employee_earning_id': earning.id,
            }
            if not moved:
                lines_not_created.append((0, 0, line_vals | {'moved': False, 'wizard_id': self.id}))
            earning_lines += self._get_moved(earning=earning,worksheet=worksheet)

        for line in earning_lines:
            line_vals = {
                'moved': False,
                'employee_id': line.earning_id.employee_id.id,
                'department_id': line.earning_id.employee_id.department_id.id,
                'worksheet': line.worksheet_id.id,
                'period_id': periods.id,
                'employee_earning_id': line.earning_id.id,
                'quantity': line.quantity
            }
            lines_created.append((0, 0, line_vals | {'moved': True, 'wizard_created_id': self.id}))
        self.line_ids_not_created = [(5, 0, 0)] + lines_not_created
        self.line_ids_created = [(5, 0, 0)] + lines_created


    def _get_moved(self,earning, worksheet):
        lines = self.env['prx.payroll.worksheet.line'].search(
            [
                ('employee_id', '=', earning.employee_id.id),
                ('worksheet_id', '=', worksheet.id),
                ('wizard_date', '=', self.date),
                ('earning_id', '=', earning.id),
            ]
        )
        return lines

    def action_confirm(self):
        for line in self.line_ids_not_created.filtered(lambda l: l.selected):
            if not line.quantity:
                raise UserError(f'შეავსე {line.employee_id.name} თანამშრომელზე რაოდენობა')
            self.env['prx.payroll.worksheet.line'].create({
                'date': self.date,
                'earning_id': line.employee_earning_id.id,
                'quantity': line.quantity,
                'worksheet_id': line.worksheet.id,
                'amount': line.employee_earning_id.amount * line.quantity,
                'rate': line.employee_earning_id.amount,
                'wizard_date': self.date
            })

class PRXPayrollCreateWorksheetWizardLine(models.TransientModel):
    _name = "prx.payroll.create.worksheet.wizard.line"
    _description = "Position earning wizard line"

    selected = fields.Boolean(string="მონიშნული")
    employee_id = fields.Many2one('hr.employee', string="თანამშრომელი")
    worksheet = fields.Many2one('prx.payroll.worksheet')
    period_id = fields.Many2one('prx.payroll.period')
    quantity = fields.Integer(string="რაოდენობა")
    department_id = fields.Many2one('hr.department',string='დეპარტამენტი')
    employee_earning_id = fields.Many2one('prx.payroll.position.earning',string='ანაზღაურება')
    earning_unit = fields.Selection(related='employee_earning_id.earning_id.earning_unit',string='ანაზღაურების ერთეული')

    wizard_id = fields.Many2one('prx.payroll.create.worksheet.wizard', string="Wizard (Not Created)")
    wizard_created_id = fields.Many2one('prx.payroll.create.worksheet.wizard', string="Wizard (Created)")

    moved = fields.Boolean()
