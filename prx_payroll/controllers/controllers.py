from odoo import http
from odoo.http import request
import base64, json, urllib.parse

class PayslipReportController(http.Controller):

    @http.route('/report/payslip/view', type='http', auth='user')
    def view_pdf_popup(self, data=None, **kwargs):
        if not data:
            return request.not_found()
        try:
            decoded = base64.b64decode(data)
            payload = json.loads(decoded)
        except Exception:
            return request.not_found()

        form = payload.get("form")
        if not form:
            return request.not_found()
        report = request.env.ref('prx_payroll.prx_payroll_payslip_report_pdf_action').with_context(lang="en_US")
        pdf_bytes, _ = report._render_qweb_pdf(
            report.report_name,
            res_ids=None,
            data={'form': form},
        )
        safe_name = f"{form.get('fullName','')}_{form.get('period','')}_Payslip.pdf"
        fallback  = "Payslip.pdf"
        quoted    = urllib.parse.quote(safe_name)

        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition',
             f'inline; filename="{fallback}"; filename*=UTF-8\'\'{quoted}'),
            ('Content-Length', str(len(pdf_bytes))),
        ]
        return request.make_response(pdf_bytes, headers=headers)