from odoo import models, fields, api
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class PRXPayrollPositionEarningWizard(models.TransientModel):
    _name = "prx.payroll.position.earning.wizard"
    _description = "Position earning wizard"

    period_id = fields.Many2one('prx.payroll.period', string="პერიოდი", required=True)
    earning_id = fields.Many2one('prx.payroll.earning', string="ანაზღაურება")
    department_id = fields.Many2one('hr.department', string="დეპარტამენტი")

    amount_total_not_created = fields.Float(
        string="ჯამი",
        compute="_compute_amount_totals",
    )
    count_not_created = fields.Integer(string="რაოდენობა(შესაქმნელი)",compute="_compute_amount_totals")
    count_created = fields.Integer(string="რაოდენობა(შექმნილი)",compute="_compute_amount_totals")
    amount_total_created = fields.Float(
        string="ჯამი",
        compute="_compute_amount_totals",
    )

    @api.depends('line_ids_not_created.amount', 'period_id', 'department_id', 'earning_id', 'line_ids_created')
    def _compute_amount_totals(self):
        for wizard in self:
            wizard.amount_total_not_created = sum(
                wizard.line_ids_not_created.mapped('amount')
            )
            wizard.amount_total_created = sum(
                wizard.line_ids_created.mapped('amount')
            )
            wizard.count_not_created = len(wizard.line_ids_not_created)
            wizard.count_created = len(wizard.line_ids_created)

    line_ids_not_created = fields.One2many(
        'prx.payroll.position.earning.wizard.line',
        'wizard_id',
        string="შესაქმნელი"
    )

    line_ids_created = fields.One2many(
        'prx.payroll.position.earning.wizard.line',
        'wizard_created_id',
        string="შექმნილი"
    )

    @api.onchange('period_id', 'department_id','earning_id')
    def _onchange_period_id(self):
        self.line_ids_not_created = False
        self.line_ids_created = False

        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('date_start', '<=', self.period_id.end_date),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', self.period_id.start_date),
        ])

        if self.department_id:
            contracts = contracts.filtered(lambda c: c.employee_id.department_id == self.department_id)

        if self.env.user.has_group('prx_payroll.prx_payroll_administrator'):
            access_employees = self.env['prx.payroll.worksheet.manager'].search([]).line_ids.mapped('employee_id')
        else:
            access_employees = self.env['prx.payroll.worksheet.manager'].search(
                [('worksheet_manager_id', '=', self.env.user.employee_id.id)]
            ).line_ids.mapped('employee_id')

        lines_not_created, lines_created = [], []

        for contract in contracts:
            start_date = self.period_id.start_date
            end_date = self.period_id.end_date

            if self.period_id.start_date < contract.date_start:
                start_date = contract.date_start
            if contract.date_end and contract.date_end < self.period_id.end_date:
                end_date = contract.date_end

            if contract.employee_id not in access_employees:
                continue

            exists = self.env['prx.payroll.position.earning'].search([
                ('from_wizard', '=', True),
                ('wizard_period_id', '=', self.period_id.id),
                ('employee_id', '=', contract.employee_id.id),
            ])

            if self.department_id:
                exists = exists.filtered(lambda c: c.employee_id.department_id == self.department_id)

            base_vals = {
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'start_date': start_date,
                'end_date': end_date,
                'currency_id': contract.company_id.currency_id.id,
            }

            if self.earning_id:
                exists_for_earning = exists.filtered(lambda r: r.earning_id == self.earning_id)
                if exists_for_earning:
                    for existing in exists_for_earning:
                        line_vals = base_vals | {
                            'earning_id': existing.earning_id.id,
                            'amount': existing.amount,
                            'start_date': existing.start_date,
                            'end_date': existing.end_date,
                            'currency_id': existing.currency_id.id,
                            'moved': True,
                            'wizard_created_id': self.id,
                        }
                        lines_created.append((0, 0, line_vals))
                else:
                    new_vals = base_vals | {
                        'earning_id': self.earning_id.id,
                    }
                    lines_not_created.append((0, 0, new_vals | {'moved': False, 'wizard_id': self.id}))
            else:
                line_vals = base_vals | {'moved': False, 'wizard_id': self.id}
                lines_not_created.append((0, 0, line_vals))

        self.line_ids_not_created = lines_not_created
        self.line_ids_created = lines_created


    def action_confirm(self):
        _logger.info("==================ACTION CONFIRM==================")
        _logger.info(self.line_ids_not_created)

        for line in self.line_ids_not_created.filtered(lambda l: l.selected):
            _logger.info(line)
            _logger.info(line.contract_id)
            contract = line.contract_id

            start_date = self.period_id.start_date
            end_date = self.period_id.end_date
            #
            if self.period_id.start_date < contract.date_start:
                start_date = contract.date_start

            if contract.date_end and contract.date_end < self.period_id.end_date:
                end_date = contract.date_end

            if not line.amount:
                raise UserError(f'{contract.employee_id.name} შეიყვანე ანაზღაურების თანხა')

            data_create = self.env['prx.payroll.position.earning'].create({
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'position_id': contract.job_id.id,
                'start_date': start_date,
                'end_date': end_date,
                'earning_id': line.earning_id.id,
                'currency_id': contract.company_id.currency_id.id,
                'amount': line.amount,
                'from_wizard': True,
                'wizard_period_id': self.period_id.id,
            })
            _logger.info("=================== ENDING IN CREATE ======================")
            _logger.info(data_create)

class PRXPayrollPositionEarningWizardLine(models.TransientModel):
    _name = "prx.payroll.position.earning.wizard.line"
    _description = "Position earning wizard line"

    wizard_id = fields.Many2one('prx.payroll.position.earning.wizard', string="Wizard (Not Created)")
    wizard_created_id = fields.Many2one('prx.payroll.position.earning.wizard', string="Wizard (Created)")

    selected = fields.Boolean(string="მონიშნული")
    moved = fields.Boolean()
    employee_id = fields.Many2one('hr.employee', string="თანამშრომელი", required=True)
    contract_id = fields.Many2one('hr.contract', string="კონტრაქტი", required=True)
    position_id = fields.Many2one(related='contract_id.job_id', string="პოზიცია", store=False, readonly=True)
    identification_number = fields.Char(related='employee_id.identification_id', string="პირადი ნომერი", readonly=True)
    earning_id = fields.Many2one('prx.payroll.earning', string="ანაზღაურება")

    start_date = fields.Date(string="საწყისი თარიღი")
    end_date = fields.Date(string="საბოლოო თარიღი")
    amount = fields.Float(string="თანხა", required=True, digits=(19, 2))
    currency_id = fields.Many2one(
        'res.currency',
        string="ვალუტა",
        default=lambda self: self.env.company.currency_id.id
    )

    @api.depends('contract_id')
    def _onchange_contract_id(self):
        for rec in self:
            if rec.contract_id:
                rec.employee_id = rec.contract_id.employee_id


    def create(self,vals):
        return super().create(vals)