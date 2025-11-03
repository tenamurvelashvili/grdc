from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError

class PRXPayrollTaxReportCategory(models.Model):
    _name = 'prx.payroll.tax.report.category'
    _description = 'Payroll tax report category'

    code = fields.Char(string=_('კოდი'),required=True)
    description = fields.Char(string = _('შემოსავლის მიმღებ პირთა კატეგორია'),translate=True,required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'კოდი უნიკალური უნდა იყოს!')
    ]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.code)
