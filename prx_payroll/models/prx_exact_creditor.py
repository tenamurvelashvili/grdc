import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.osv import expression
from .prx_MSSQL_connector import MSSQLConnector

_logger = logging.getLogger(__name__)


class PrxExactCreditor(models.Model):
    _name = 'prx.exact.creditor'
    _description = 'Exact Creditor'
    _rec_name = 'full_name'

    crdnr = fields.Char(string='Credit Number', required=True, index=True)
    cmp_name = fields.Char(string='Company Name')
    cmp_code = fields.Char(string='Company Code')
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)
    _sql_constraints = [
        ('crdnr_unique', 'UNIQUE(crdnr)', 'Credit Number must be unique.'),
    ]



    @api.depends('crdnr', 'cmp_name')
    def _compute_full_name(self):
        for rec in self:
            name = rec.crdnr or ""
            if rec.cmp_name:
                name = f"{rec.cmp_name} - {name}"
            rec.full_name = name

    # Keep display_name consistent with the new field
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.full_name



    # ------------------------------------------------------------------ #
    #  Sync from MS SQL                                                     #
    # ------------------------------------------------------------------ #
    def action_sync_from_mssql(self):
        sql = """
              SELECT ZVSalaryCredit.crdnr    AS crdnr,
                     ZVSalaryCredit.cmp_name AS cmp_name,
                     ZVSalaryCredit.cmp_code AS cmp_code
              FROM ZVSalaryCredit \
              """
        try:
            with MSSQLConnector(self.env) as conn:
                rows = conn.execute_query(sql)
        except Exception as e:
            raise UserError(f"MS SQL connection failed: {e}")

        if not rows:
            raise UserError("No data returned from ZVSalaryCredit.")

        # Load all existing crdnr values in one query — avoids N+1 searches
        existing_crdnrs = set(
            self.search([]).mapped('crdnr')
        )

        inserted = 0
        skipped = 0

        for row in rows:
            crdnr = row.get('crdnr')
            if not crdnr:
                continue

            if crdnr in existing_crdnrs:
                skipped += 1
                continue

            self.create({
                'crdnr': crdnr,
                'cmp_name': row.get('cmp_name'),
                'cmp_code': row.get('cmp_code'),
            })
            existing_crdnrs.add(crdnr)  # prevent duplicate inserts within same batch
            inserted += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': f'{inserted} inserted, {skipped} skipped (already exist).',
                'type': 'success',
                'sticky': False,
            },
        }
