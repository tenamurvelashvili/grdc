# -*- coding: utf-8 -*-
{
    'name': "prx_payroll",

    'summary': "Proxima solution payroll",

    'description': """Proxima solution payroll""",

    'author': "Proxima Solutions",
    'website': "https://www.proxima.solutions",

    'category': 'Proxima',
    'version': '0.1',

    'depends': [
        'base',
        'hr_contract',
        'hr_holidays',
        'resource',
        'prx_calendar',
        'prx_income_tax',
        'prx_rs_employee_service'
    ],

    'data': [
        'security/ir_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/prx_payroll_dashboard_warning.xml',
        'data/prx_payroll_default_records.xml',
        'views/prx_payroll_period.xml',
        'wizard/prx_generate_period_wizard.xml',
        'wizard/prx_payroll_bulk.xml',
        'views/prx_payroll_earning_group_and_type.xml',
        'views/prx_payroll_earning.xml',
        'views/prx_payroll_tax.xml',
        'views/prx_payroll_deduction.xml',
        'views/prx_payroll_employee_deduction.xml',
        'views/prx_payroll_employee_tax.xml',
        'wizard/prx_payroll_earning_bonus_wizard.xml',
        'wizard/prx_payroll_create_employee_earning.xml',
        'views/prx_payroll_position_earning.xml',
        'views/prx_sequence_generation.xml',
        'wizard/prx_payroll_create_worksheet_wizard.xml',
        'views/prx_payroll_worksheet.xml',
        'views/prx_payroll_calculation.xml',
        'views/prx_payroll_hr_employee_inherit.xml',
        'views/prx_payroll_worksheet_line_and_earnings.xml',
        'views/prx_payroll_transaction.xml',
        'views/prx_payroll_excel_import.xml',
        'views/prx_payroll_employee_ext.xml',
        'views/prx_payroll_worksheet_manager.xml',
        'wizard/prx_payroll_payslip_report_wizard.xml',
        'wizard/prx_payroll_declaration_wizard.xml',
        'wizard/prx_payroll_bank_reports.xml',
        'wizard/prx_payroll_transaction_reports.xml',
        'wizard/prx_payroll_tabel_report.xml',
        'wizard/prx_payroll_pension_alimony.xml',
        'wizard/prx_payroll_creditor_wizard.xml',
        'wizard/prx_payroll_transaction_bank_transfer.xml',
        'wizard/prx_payroll_bulk_close_transaction.xml',
        'reports/prx_payroll_payslip_pdf.xml',
        'views/prx_payroll_cost_center.xml',
        'views/prx_payroll_cost_unit.xml',
        'views/prx_payroll_employee_cost_document.xml',
        'views/prx_payroll_employee_cost_document_lines.xml',
        'views/prx_payroll_transaction_cost.xml',
        'views/prx_payroll_masking.xml',
        'wizard/prx_payroll_earning_amount_calculator.xml',
        'views/prx_payroll_dashboard_warning.xml',
        # 'views/neutralize_banner.xml',

        'views/prx_payroll_actions.xml',
        'views/prx_payroll_res_config_settings.xml',
        'views/prx_payroll_menu.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'prx_payroll/static/src/css/Payroll.scss',
            'prx_payroll/static/src/components/dashboard/lib/*',
            'prx_payroll/static/src/components/dashboard/PayrollDashboardIndex.js',
            'prx_payroll/static/src/components/dashboard/PayrollDashboard.js',
            'prx_payroll/static/src/components/dashboard/PayrollDashboard.xml',
            # warning
            'prx_payroll/static/src/components/dashboard/Warning.js',
            'prx_payroll/static/src/components/dashboard/Warning.xml',
            # TODOLIST
            'prx_payroll/static/src/components/todo_list/todo_list.js',
            'prx_payroll/static/src/components/todo_list/todo_list.xml',
            'prx_payroll/static/src/components/todo_list/todo_list.scss',
        ],
    },

}
