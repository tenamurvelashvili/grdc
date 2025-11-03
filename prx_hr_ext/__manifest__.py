# -*- coding: utf-8 -*-
{
    'name': "PRX HR Additions",

    'summary': "PRX HR additions functionalities",

    'description': """PRX HR additions functionalities""",

    'author': "Proxima Solutions",
    'website': "https://proxima.solutions",

    'category': 'Proxima',
    'version': '0.1',

    'depends': ['base','hr','prx_calendar','hr_holidays'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/prx_hr_tabel_report.xml',
        'views/prx_time_off_code.xml',
        'views/prx_hr_leave_type_ext.xml',
        'data/prx_time_off_code.xml',
        'views/actions.xml',
        'views/menu.xml',
    ],
    'demo': [
    ],
}

