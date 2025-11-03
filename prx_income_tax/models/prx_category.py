from odoo import models, fields, api

class PRXTaxReportCategory(models.Model):
    _name = 'prx.tax.report.category'
    _description = 'Tax report category'
    _rec_name = 'description'

    code = fields.Char(string = 'კოდი',required=True)
    description = fields.Char(string = 'შემოსავლის მიმღებ პირთა კატეგორია',translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Code must be unique!')
    ]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.description)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|',
                ('code', operator, name),
                ('description', operator, name),
            ]
        records = self.search(domain + args, limit=limit)
        return records.name_get()

    def name_get(self):
        result = []
        for rec in self:
            label = f"[{rec.code}] {rec.description}"
            result.append((rec.id, label))
        return result

