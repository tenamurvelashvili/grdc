# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command
import requests
import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def get_nbg_rates(self, currency: str):
        """GET NBG currencies"""
        url = f'https://api.businessonline.ge/api/rates/nbg/{currency}'

        headers = {}
        response = requests.request("GET", url, headers=headers)

        if response.status_code == 200:
            _logger.info(f"Successfully got {currency} rate {float(response.content)}")
            print(float(response.content))
            return float(response.content)

    def update_currency_rates_nbg(self):
        """Update 'res.currency.rate' model rates"""

        for rec in self.search([('name', '!=', 'GEL')]):
            if rec.rate_ids and rec.rate_ids[-1].name == fields.Date.today():
                rec.rate_ids[-1].write({'rate': 1 / self.get_nbg_rates(rec.name)})
                continue
            if self.env.company.currency_id.id == rec.id:
                continue
            rate = self.get_nbg_rates(rec.name)
            if rate:

                rec.rate_ids = [
                    Command.create(
                        {'name': fields.Date.today(),
                         'rate': 1 / self.get_nbg_rates(rec.name)
                         }
                    ),
                ]

