# -*- coding: utf-8 -*-
{
    'name': "prx_calendar",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "Proxima Solutions",
    'website': "https://www.proxima.solutions",

    'category': 'Proxima',
    'version': '0.1',

    'depends': ['base','hr_contract','resource'],

    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/prx_organisation_calendar.xml',
        'views/prx_calendar_act_window.xml',
    ],
    'demo': [

    ],
}

