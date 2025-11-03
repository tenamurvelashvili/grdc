from odoo import models, fields, api

class PRXTaxReportCountry(models.Model):
    _name = 'prx.tax.report.country'
    _description = 'tax report country'
    _rec_name = 'country'
    _order = 'country'

    code = fields.Char(string = 'კოდი',required=True)
    country = fields.Char(string = 'ქვეყნის დასახელება',translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Code must be unique!')
    ]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.country)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|',
                ('country', operator, name),
                ('code',    operator, name),
            ]
        records = self.search(domain + args, limit=limit)
        return records.name_get()

    def name_get(self):
        result = []
        for rec in self:
            label = f"[{rec.code}] {rec.country}"
            result.append((rec.id, label))
        return result

