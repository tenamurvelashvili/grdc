from odoo import models, api,fields
from odoo.exceptions import ValidationError

class PrxSequenceGeneration(models.Model):
    _name = 'prx.sequence.generation'
    _description = 'PRX sequence generation'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    name = fields.Char('მიმდევრობის დასახელება',required=True)
    model_model = fields.Many2one('ir.model', string='მოდული')
    prefix = fields.Char(string='პრეფიქსი',required=True)
    len_prefix = fields.Integer(string='პრეფიქსის სიგრძე',default=10)
    visualize_sequence = fields.Char('მიმდევრობა')
    sequence_id = fields.Many2one('ir.sequence')
    generated = fields.Boolean(string="გენერირებული მიმდევრობა")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{}".format(rec.name or ' ')

    def create_procurement_group_sequence(self,):
        seq_obj = self.env['ir.sequence']
        seq = seq_obj.search([('code', '=', self.model_model.model)], limit=1)
        if not seq:
            seq = seq_obj.create({
                'name': f'{self.name}',
                'code': f'{self.model_model.model}',
                'prefix': f'{self.prefix}',
                'padding': f'{self.len_prefix}',
                'number_next': 0,
                'number_increment': 1,
            })
            self.visualize_sequence = f'{self.prefix + '0'*self.len_prefix}'[:-1] + '1'
            self.sequence_id = seq.id
            self.generated = True
            self.env.cr.commit()
        else:
            raise ValidationError('ეს მიმდევრობა უკვე არსებობს')

    def unlink(self):
        self.env['ir.sequence'].browse(self.sequence_id.id).unlink()
        return super().unlink()



