from odoo import models

class HrContract(models.Model):
    _inherit = "hr.contract"

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            if ("date_end" in vals and rec.state in ["close", "cancel"]) or (vals.get('state',False) in ["close", "cancel"]):
                if rec.date_end:
                    earnings = self.env['prx.payroll.position.earning'].search([
                        ('contract_id', '=', rec.id)
                    ])
                    for earning in earnings:
                        try:
                            if not earning.end_date:
                                earning.end_date = rec.date_end
                            elif earning.end_date and rec.date_end and earning.end_date > rec.date_end:
                                earning.end_date = rec.date_end
                        except Exception as e:
                            continue
        return res
