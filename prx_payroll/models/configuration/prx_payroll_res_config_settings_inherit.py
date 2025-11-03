from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    prx_manual = fields.Boolean(string='Manual', config_parameter='prx_payroll.prx_manual_not_unlink')
    prx_system = fields.Boolean(string='System', config_parameter='prx_payroll.prx_system_not_unlink')
    prx_earning = fields.Boolean(string='გამომუშავებით', config_parameter='prx_payroll.prx_earning_not_unlink')
    prx_pension_insurance = fields.Boolean(string='დაზღვევა საპენსიოს',
                                           config_parameter='prx_payroll.prx_pension_insurance')
    bonus_salary = fields.Selection([('month','გადაცემული თვეების მიხევით'), ('worked_month','ნამუშევარი თვეების მიხედვით')],
                                    string='ბონუსის დაანგარიშება',
                                    config_parameter='prx_payroll.prx_bonus_salary_type'
                                    )
    prx_bonus_terminated_employee = fields.Boolean(string='ბონუსი განთავისუფლებულ თანამშრომელზე',
                                                   config_parameter='prx_payroll.prx_bonus_terminated_employee',
                                                   help='ბონუსი განთავისუფლებულ თანამშრომელზე',
                                                   )
    prx_base_calculation = fields.Selection([('start_earn', 'საწყისი ანაზღაურება'), ('end_earn', 'საბოლოო ანაზღაურება')],
                                            string='კალკულაციის წყარო',
                                            help='თანამშრომლის პოზიციის ანაზრაურებიდან თვის საწყისი თანხით დაითვალოს თუ საბოლოო თარიღით',
                                            config_parameter='prx_payroll.prx_base_calculation'
                                            )

    prx_payroll_acc = fields.Many2one(
        'res.partner.bank',
        string="სახელფასო ანგარიში",
        config_parameter='prx_payroll.prx_payroll_acc'
    )
    close_tabel = fields.Boolean(string='ტაბელის ავტომატური დახურვა', config_parameter='prx_payroll.prx_close_tabel')