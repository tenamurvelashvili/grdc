from odoo import models, fields, api
from odoo.exceptions import UserError
from lxml import etree


class WorkerTax(models.Model):
    _name = 'prx.payroll.employee.tax'
    _description = 'PRX Payroll Employee Tax'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    active = fields.Boolean(string='Active', default=True)
    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', required=True)
    identification_number = fields.Char(string='პირადი ნომერი', related='employee_id.identification_id', readonly=True,
                                        store=False)
    tax = fields.Many2one('prx.payroll.tax', string='გადასახადი', required=True)
    start_date = fields.Date(string='საწყისი თარიღი', required=True)
    end_date = fields.Date(string='საბოლოო თარიღი')
    used_tax_amount = fields.Float(string='მიღებამდე გამოყენებული შეღავათი', digits=(19, 2),tracking=True)
    exception = fields.Boolean(string="გამონაკლისი")
    open_contract_ids = fields.Many2many(
        comodel_name='hr.employee',
        string="Employee's Open Contracts",
        compute='_compute_open_emp_ids',
    )

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            if isinstance(arch, str):
                doc = etree.fromstring(arch)
            else:
                doc = arch
            for field in doc.xpath(".//field"):
                field.set('readonly', '1')
            sheet_list = doc.xpath(".//sheet")
            if sheet_list:
                sheet = sheet_list[0]
                parent = sheet.getparent()
                if parent is not None and not doc.xpath('.//chatter'):
                    index = list(parent).index(sheet)
                    chatter = etree.Element('chatter')
                    parent.insert(index + 1, chatter)
        return arch, view

    @api.depends('employee_id.contract_ids', 'employee_id','exception')
    def _compute_open_emp_ids(self):
        for rec in self:
            if rec.exception:
                rec.open_contract_ids = self.env['hr.employee'].search([]).contract_ids.filtered(
                    lambda c: c.state == 'close').mapped('employee_id')
            else:
                rec.open_contract_ids = self.env['hr.employee'].search([]).contract_ids.filtered(
                    lambda c: c.state == 'open').mapped('employee_id')

    @api.onchange('exception')
    def clear_exception(self):
        if not self.exception:
            self.employee_id = None

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.tax.tax)

    @api.constrains('start_date', 'end_date', 'employee_id')
    def _check_date_and_contract(self):
        for record in self:
            if record.start_date:
                if record.end_date and record.start_date >= record.end_date:
                    raise UserError('საწყისი თარიღი არშეიძლება საბოლოო თარიღზე მეტი')
                if not record.exception:
                    overlapping = self.search([
                        ('employee_id', '=', record.employee_id.id),
                        ('id', '!=', record.id),
                    ])
                    for overlap in overlapping:
                        if overlap.end_date and overlap.start_date and overlap.start_date <= record.start_date <= overlap.end_date:
                            raise UserError('მსგავსი ჩანაწერი უკვე არსებობს')
                        if not overlap.end_date and overlap.start_date and overlap.start_date <= record.start_date:
                            raise UserError('მსგავსი ჩანაწერი უკვე არსებობს')
                        if not overlap.end_date and not record.end_date and overlap.start_date and overlap.start_date >= record.start_date:
                            raise UserError('მსგავსი ჩანაწერი უკვე არსებობს')
                        if not overlap.end_date and record.end_date and overlap.start_date and overlap.start_date <= record.end_date:
                            raise UserError('მსგავსი ჩანაწერი უკვე არსებობს')
