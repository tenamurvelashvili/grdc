/** @odoo-module **/

import { Component, onMounted, useRef,useState,onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { PayrollDashboardTodo } from "@prx_payroll/components/todo_list/todo_list";
import { PRXPayrollDashboardActionBox } from "./Warning.js";
import { user } from '@web/core/user';

export class PayrollDashboard extends Component {
    static template = "prx_payroll.PayrollDashboard";
    static components = {
        PayrollDashboardTodo,
        PRXPayrollDashboardActionBox,
    };

    setup() {
        this.chart1Ref = useRef("chart1");
        this.chart2Ref = useRef("chart2");
        this.chart3Ref = useRef("chart3");
        this.chart4Ref = useRef("chart4");

        this.rpc = rpc;
        this.orm = useService('orm');
        this.user = user;

        this.tax = useState({ value: 0 });
        this.deduction = useState({ value: 0 });
        this.earning = useState({ value: 0 });

        // start payroll
        this.payrollMonth = useState({ value: 0 });
        this.payrollTotalAmount = useState({ value: 0 });
        this.payrollEmployeeCount = useState({ value: 0 });
        this.payrollAverageAmount = useState({ value: 0 });
        this.payrollTransactionIDS = useState({ value: 0 });


        this.compareAmountLastTwoPeriod = useState({ value: 0 });
        this.compareAmountLastYearCurrentMonth = useState({ value: 0 });

        this.totalTabelOpen = useState({ value: 0 });
        this.totalTabelClosed = useState({ value: 0 });
        this.totalTabelPosted = useState({ value: 0 });
        this.totalTabelCanceled = useState({ value: 0 });

        this.tabelMonth = useState({ value: 0 });
        this.tabel_period_id = useState({ value: 0 });

        this.momPeriodStart = useState({ value: 0 });
        this.momPeriodEnd = useState({ value: 0 });
        this.yoyPeriodStart = useState({ value: 0 });
        this.yoyPeriodEnd = useState({ value: 0 });


        this.lastClickTime = 0; // ქლიქს ვიტვლი აქ

        onMounted(async () => {
            await this.loadChartData();  // ვტვირთავ დეფაულ დატას ჩაეტზე
            this.renderCharts();
        });
        const stored = localStorage.getItem('prx_payroll_notes_collapsed');
        const defaultCollapsed = stored === 'true';
        this.state = useState({
            isPayrollAdmin: false,
            isWorksheetManager: false,
            isCollapsed: defaultCollapsed,
        });

        onWillStart(async () => {
            // აქ მინდა ჩავტვირთო დატა სანამ ფორმა გაიხსნება
            const data = await this.rpc("/prx_payroll/dashboard_data", {});
            this.payrollMonth.value = data.payroll_month;
            this.payrollTotalAmount.value = data.total_amount;
            this.payrollEmployeeCount.value = data.employee_count;
            this.payrollAverageAmount.value = data.average_amount;
            this.payrollTransactionIDS.value = data.payroll_transaction_ids;
            //MoM
            this.momPeriodStart.value = data.mom_period_start;
            this.momPeriodEnd.value = data.mom_period_end;
            this.compareAmountLastTwoPeriod.value = data.compare_amount_last_two_period;
            //YoY
            this.compareAmountLastYearCurrentMonth.value = data.compare_amount_last_year_current_month;
            this.yoyPeriodStart.value = data.yoy_period_start;
            this.yoyPeriodEnd.value = data.yoy_period_end;
            //tabel
            this.tabelMonth.value = data.tabel_month;
            this.tabel_period_id.value = data.tabel_period_id;
            this.totalTabelOpen.value = data.total_tabel_open;
            this.totalTabelClosed.value = data.total_tabel_closed;
            this.totalTabelPosted.value = data.total_tabel_posted;
            this.totalTabelCanceled.value = data.total_tabel_canceled;

            // Access
            this.state.isPayrollAdmin = await this.user.hasGroup("prx_payroll.prx_payroll_administrator");
            this.state.isWorksheetManager = await this.user.hasGroup("prx_payroll.prx_payroll_worksheet_manager");

        });
    }

      toggleCollapse() {
        this.state.isCollapsed = !this.state.isCollapsed;
        localStorage.setItem('prx_payroll_notes_collapsed', this.state.isCollapsed);
          window.location.reload();
//          this.renderCharts();
      }


    async loadChartData() {
        // გადასახადი დაქვითვა ანაზღაურება
        const data = await this.rpc('/prx_payroll/get_last_3_months_summary');
        console.log(data)
        this.chartData = data;
        // დეფაულტად 3 თვისას ჩავწერ
        let total_tax = 0;
        let total_deduction = 0;
        let total_earning = 0;

        for (const item of data) {
            total_tax += item.tax || 0;
            total_deduction += item.deduction || 0;
            total_earning += item.earning || 0;
        }

        this.tax.value = total_tax;
        this.deduction.value = total_deduction;
        this.earning.value = total_earning;

        this.renderColumnChart(data);
    }


    renderCharts() {
        this.renderColumnChart();
        this.renderDoughnutChart();
        this.renderBarChart()
        this.renderColumnChart2()
    }

    renderColumnChart() {
        if (!this.chart1Ref.el || !this.chartData) return;

        const chart1 = new CanvasJS.Chart(this.chart1Ref.el, {
            exportEnabled: false,
            animationEnabled: true,
            axisY: { title: "Amount" },
            data: [{
                type: "column",
                dataPoints: this.chartData.map(item => ({
                    label: item.month,
                    y: item.earning,
                    toolTipContent:
                        `<strong>${item.month}</strong><br/>` +
                        `გადასახადი ${item.tax?.toFixed(2) || 0}<br/>` +
                        `დაქვითვა ${item.deduction?.toFixed(2) || 0}<br/>` +
                        `ანაზღაურება ${item.earning?.toFixed(2) || 0}`
                })),
                click: (e) => this.onBarClick(e.dataPoint.label),
            }]
        });

        chart1.render();
    }

    onBarClick(monthLabel) {
        const monthData = this.chartData.find(item => item.month === monthLabel);
        if (monthData) {
            this.tax.value = monthData.tax || 0;
            this.deduction.value = monthData.deduction || 0;
            this.earning.value = monthData.earning || 0;
        }

        const now = new Date().getTime();
        const timeDiff = now - this.lastClickTime;
        this.lastClickTime = now;

        if (timeDiff < 500) {
            const record_ids = monthData.record_ids;
            if (!record_ids || !record_ids.length) {
                console.warn("record_ids ვერ მოიძებნა", monthLabel);
                return;
            }

            this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'prx.payroll.transaction',
                name: 'Project Cost',
                target: 'new',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', record_ids]],
                context: { create: false }
            });
        }
    }


    async renderDoughnutChart() {
        if (!this.chart2Ref.el) return;

        // წამოიღე პროექტების ხარჯის მონაცემები ბოლო თვისთვის
        const projectData = await this.rpc('/prx_payroll/get_last_month_project_summary');

        const chart2 = new CanvasJS.Chart(this.chart2Ref.el, {
            exportEnabled: false,
            animationEnabled: true,
            legend: {
                cursor: "pointer",
                itemclick: function (e) {
                    e.dataSeries.dataPoints[e.dataPointIndex].exploded =
                        !e.dataSeries.dataPoints[e.dataPointIndex].exploded;
                    e.chart.render();
                }
            },
            data: [{
                type: "doughnut",
                innerRadius: 40,
                showInLegend: true,
                toolTipContent: "<b>{name}</b>: ₾{y} (#percent%)",
                indexLabel: "{name} - #percent%",
                dataPoints: projectData,
                click: this.onProjectChartClick.bind(this),
            }]
        });

        chart2.render();
    }

    onProjectChartClick(e) {
        const now = new Date().getTime();
        const timeDiff = now - this.lastClickTime;
        this.lastClickTime = now;

        // თუ დაჭერებს შორის განსხვავება ნაკლებია 500ms-ზე, ჩავთვალოთ double click
        if (timeDiff < 500) {
            const record_ids = e.dataPoint.record_ids;
            if (!record_ids || !record_ids.length) {
                console.warn("record_ids ვერ მოიძებნა", e);
                return;
            }

            this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'prx.payroll.transaction.cost.report',
                name: 'Project Cost',
                target: 'new',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', record_ids]],
                context: { create: false }
            });
        }
    }


    onClickStatusFromElement(ev) {
      const status = ev.currentTarget.dataset.status;
      if (!status) return;
      this.env.services.action.doAction({
          type: 'ir.actions.act_window',
          name: 'ტაბელები',
          res_model: 'prx.payroll.worksheet',
          view_mode: 'list,form',
          views: [[false, 'list'], [false, 'form']],
          domain: [['status', '=', status],['period_id','=',this.tabel_period_id.value]],
          target: 'new',
          context:{'create':false}
      });
    }

      async openPayrollTransactions() {
        await this.env.services.action.doAction({
          type: "ir.actions.act_window",
          name: "Payroll Transactions",
          res_model: "prx.payroll.transaction",
          view_mode: "list,form",
          views: [[false, 'list'], [false, 'form']],
          target: "new",
          context:{'create':false},
          domain: [['id','in',this.payrollTransactionIDS.value]],
        });
      }


    async renderBarChart() {
        if (!this.chart3Ref.el) return;
        const result = await this.rpc("/payroll/department_expenses");

        if (!Array.isArray(result)) return;

        result.sort((a, b) => b.y - a.y);

        const chart3 = new CanvasJS.Chart(this.chart3Ref.el, {
            theme: "white",
            animationEnabled: true,
            exportEnabled: false,
            axisX: {
                includeZero: true,
                labelFontSize: 12,
                titleFontSize: 14,
                gridThickness: 0,
                labelPlacement: "inside",
                tickPlacement: "outside",
            },
            axisY: {
                labelFontSize: 13,
                labelFontColor: "#555",
                gridThickness: 0,
            },
            data: [{
                type: "bar",
                toolTipContent: "<b>{label}</b><br>ხარჯი: {y} ₾",
                dataPoints: result,
                click: this.onDepartmentBarClick.bind(this),
            }]
        });

        chart3.render();
    }

    onDepartmentBarClick(e) {
        const tx_ids = e.dataPoint.tx_ids;
        if (tx_ids && tx_ids.length) {
            this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'prx.payroll.transaction',
                views: [[false, 'list']],
                domain: [['id', 'in', tx_ids]],
                target: 'new',
                context:{'create':false,'export': 1,},
            });
        } else {
            console.warn("ID-ები ვერ მოიძებნა ან ცარიელია");
        }
    }


    async renderColumnChart2() {
        if (!this.chart4Ref.el) return;

        const data = await this.rpc("/prx_payroll/get_last_transactions_by_code");

        const chart4 = new CanvasJS.Chart(this.chart4Ref.el, {
            exportEnabled: false,
            animationEnabled: true,
            axisY: {
                title: "თანხა (₾)",
                gridThickness: 0
                },
            axisX: {
                title: "კოდი",
                gridThickness: 0
                },
            data: [{
                type: "column",
                dataPoints: data.map(item => ({
                    label: item.code || "უცნობი",
                    y: item.amount,
                    record_ids: item.record_ids,
                    toolTipContent:
                        `<strong>კოდი:</strong> ${item.code || "უცნობი"}<br/>` +
                        `<strong>თანხა:</strong> ₾${item.amount.toFixed(2)}<br/>` +
                        `<strong>ჩანაწერები:</strong> ${item.record_ids.length} ერთეული`
                })),
                click: (e) => {
                    const ids = e.dataPoint.record_ids;
                    if (ids?.length) {
                        this.env.services.action.doAction({
                            type: 'ir.actions.act_window',
                            res_model: 'prx.payroll.transaction',
                            name: 'Filtered Transactions',
                            target: 'new',
                            views: [[false, 'list']],
                            domain: [['id', 'in', ids]],
                            context: { 'create': false }
                        });
                    }
                }
            }]
        });

        chart4.render();
    }


}

registry.category("actions").add("prx_payroll.dashboard", PayrollDashboard);
