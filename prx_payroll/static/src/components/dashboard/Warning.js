/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart} from "@odoo/owl";


export class PRXPayrollDashboardActionBox extends Component {
    static template = "prx_payroll.ActionBox";
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.orm = useService('orm');
        this.state = useState({
            loading: true,
            warnings: {},
        })
        onWillStart(() => {
          this.orm.call('prx.payroll.dashboard.warning', 'get_dashboard_warnings').then(data => {
              this.state.warnings = data;
              this.state.loading = false;
            }
          )
          return Promise.resolve(true);
        })
    }
}
