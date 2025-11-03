# -*- coding: utf-8 -*-
{
    'name': "Prx Income Tax",

    'summary': "Prx Income Tax",

    'description': """Prx Income Tax""",

    'author': "Proxima Solutions",
    'website': "https://www.proxima.solutions",

    'category': 'Proxima',
    'version': '0.1',
    'depends': ['base','account'],
    'data': [
        'security/ir.model.access.csv',
        'views/prx_tax_report_country.xml',
        'views/prx_category.xml',
        'views/prx_tax_report_earning_type.xml',
        'views/ir_act_window.xml',
        'views/prx_account_configuration_settings_ext.xml',

    ],
    'demo': [
    ],
}

