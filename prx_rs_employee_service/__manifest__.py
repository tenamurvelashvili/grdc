# -*- coding: utf-8 -*-
{
    'name': "Prx RS Employee Service",

    'summary': "Prx RS Employee Service",

    'description': """Prx RS EMPLOYEE SERVICE""",

    'author': "Proxima Solutions LTD",
    'website': "https://www.proxima.solutions",

    'category': 'Proxima',
    'version': '0.1',
    'depends': ['base','hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/configuration.xml',
        'views/prx_res_users_auth.xml',
        'views/prs_rs_employee_ext.xml',
        'views/prx_rs_employee_list.xml',
        'wizard/prx_rs_employee_wizard.xml',
        'wizard/prx_payroll_rs_employee_wizard.xml',
        'views/ir_act_window.xml',
        'views/prx_rs_menu.xml',
    ],
    'demo': [
    ],
}

