/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PayrollDashboard } from "@prx_payroll/components/dashboard/PayrollDashboard";

registry.category("actions").add("PayrollDashboard", PayrollDashboard);
