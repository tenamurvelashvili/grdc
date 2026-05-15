# -*- coding: utf-8 -*-
{
    'name': "XRateService",
    'summary': "Update currencies rate from NBG",
    'description': """
Update currencies rate from NBG
    """,

    'author': "Proxsima Solutions",
    'website': "https://proxima.solutions",
    'category': 'Proxima',
    'version': '18.0.1.0',

    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'jobs/update_res_currency_rate.xml',
        'view/settings.xml',
    ],
    # only loaded in demonstration mode
    'demo': [

    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3"
}

