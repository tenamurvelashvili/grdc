from odoo import models
from odoo.exceptions import UserError
from ..models.prx_MSSQL_connector import MSSQLConnector
import logging

_logger = logging.getLogger(__name__)


class PrxSyncWizard(models.TransientModel):
    _name = 'prx.sync.wizard'
    _description = 'Sync Exact Creditors from MS SQL'

    def action_sync(self):
        self.env['prx.exact.creditor'].action_sync_from_mssql()
        return {'type': 'ir.actions.act_window_close'}
