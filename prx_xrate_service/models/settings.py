from odoo import models, fields, api, Command
from odoo.exceptions import UserError
import requests
import logging
import json

_logger = logging.getLogger(__name__)


class NBGHistoricalRates(models.TransientModel):
    _name = 'nbg.currency.rate'
    _description = 'National Currency Rate'

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    currency_id = fields.Many2one(comodel_name='res.currency')

    def get_rates_with_range(self, params: dict):
        """GET BOG API CURRENCY params:currency,start_date,end_date"""

        currency = params.get('currency')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        url = f'https://api.businessonline.ge/api/rates/nbg/{currency}/{start_date}/{end_date}'

        headers = {}
        response = requests.request("GET", url, headers=headers)

        if response.status_code == 200:
            _logger.info(f"Successfully got {currency} rate with {start_date} - {end_date} range method")
            return json.loads(response.content)

    def get_nbg_currency(self):
        if self.env.company.currency_id.name != 'GEL':
            raise UserError('Company currency must be GEL!')
        if self.currency_id.id == self.env.company.currency_id.id:
            raise UserError('You can not update this currency because this is company currency!')
        nbg_data = self.get_rates_with_range(
            {'start_date': self.start_date, 'end_date': self.end_date, 'currency': self.currency_id.name})
        currency = self.env['res.currency'].search([('name', '=', self.currency_id.name)])
        domain = [('name', '>=', self.start_date), ('name', '<=', self.end_date),
                  ('currency_id', '=', self.currency_id.id)]
        check = self.env['res.currency.rate'].search(domain)
        if check:
            raise UserError('Please check currency date ranges, because this currency rate in dates already exists!')
        vals = []
        for record in nbg_data:
            vals.append(Command.create({'name': record['Date'], 'rate': 1 / record['Rate']}), )

        currency.rate_ids = vals
