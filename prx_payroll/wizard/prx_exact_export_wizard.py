import logging
from datetime import date, timedelta

from odoo import fields, models
from odoo.exceptions import UserError

from ..models.prx_MSSQL_connector import MSSQLConnector

_logger = logging.getLogger(__name__)


class PrxExactExportWizard(models.TransientModel):
    _name = 'prx.exact.export.wizard'
    _description = 'Export Payroll to Exact'
    OPERATOR_ID = 1

    period_id = fields.Many2one('prx.payroll.period', string='Period', required=True)
    dagbknr = fields.Char(
        string='Exact Journal',
        required=True,
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param('mssql.exact_journal', '064'),
    )

    def action_export(self):
        data = self._get_export_data()
        if not data:
            raise UserError('No payroll transactions found for the selected period.')

        try:
            with MSSQLConnector(self.env) as conn:
                self._export_to_exact(conn, data)
        except Exception as e:
            _logger.error('Exact Export Failed: %s', str(e))
            raise UserError(f'Export failed: {str(e)}')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Payroll data successfully exported to Exact.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_export_data(self):
        sql = """
        WITH georgian_map(src, dst) AS (
            VALUES
                ('ა', 'a'), ('ბ', 'b'), ('გ', 'g'), ('დ', 'd'), ('ე', 'e'),
                ('ვ', 'v'), ('ზ', 'z'), ('თ', 't'), ('ი', 'i'), ('კ', 'k'),
                ('ლ', 'l'), ('მ', 'm'), ('ნ', 'n'), ('ო', 'o'), ('პ', 'p'),
                ('ჟ', 'zh'), ('რ', 'r'), ('ს', 's'), ('ტ', 't'), ('უ', 'u'),
                ('ფ', 'p'), ('ქ', 'k'), ('ღ', 'gh'), ('ყ', 'q'), ('შ', 'sh'),
                ('ჩ', 'ch'), ('ც', 'ts'), ('ძ', 'dz'), ('წ', 'ts'), ('ჭ', 'ch'),
                ('ხ', 'kh'), ('ჯ', 'j'), ('ჰ', 'h')
        )
        SELECT
            EXTRACT(YEAR FROM p.end_date) AS Year,
            EXTRACT(MONTH FROM p.end_date) AS Period,
            eal.exact_account AS Account,
            concat(emp_name.name_en, ' ', e.earning_exact, ' ', tr.transaction_type) AS Description,
            creditor.crdnr AS Crdnr,
            '' AS CC,
            '' AS CU,
            CASE
                WHEN eal.debit_percent = 100 THEN tr.amount
                WHEN eal.credit_percent = 100 THEN -tr.amount
                ELSE tr.amount
            END AS Amount
        FROM prx_payroll_transaction tr
        INNER JOIN prx_payroll_period p ON p.id = tr.period_id
        INNER JOIN prx_payroll_earning e ON tr.earning_id = e.id AND e.earning_exact != 'avansi'
        LEFT OUTER JOIN prx_payroll_earning_account_line eal ON eal.earning_id = e.id
        LEFT OUTER JOIN hr_employee emp ON emp.id = tr.employee_id
        LEFT OUTER JOIN prx_exact_creditor creditor ON creditor.id = emp.creditor_id
        LEFT OUTER JOIN LATERAL (
            SELECT string_agg(coalesce(gm.dst, s.ch), '' ORDER BY s.ord) AS name_en
            FROM regexp_split_to_table(emp.name, '') WITH ORDINALITY AS s(ch, ord)
            LEFT OUTER JOIN georgian_map gm ON gm.src = s.ch
        ) emp_name ON true
        WHERE p.end_date = %s and creditor.crdnr is not null  

        UNION ALL

        -- tax: DEBIT (and any non-creditor) lines, one row per account line
        SELECT
            EXTRACT(YEAR FROM p.end_date) AS Year,
            EXTRACT(MONTH FROM p.end_date) AS Period,
            tal.exact_account AS Account,
            concat(emp_name.name_en, ' ', t.tax_exact, ' ', tr.transaction_type) AS Description,
            creditor.crdnr AS Crdnr,
            '' AS CC,
            '' AS CU,
            CASE
                WHEN tal.debit_percent = 100 THEN -tr.amount
                WHEN tal.credit_percent = 100 THEN tr.amount
                ELSE tr.amount
            END AS Amount
        FROM prx_payroll_transaction tr
        INNER JOIN prx_payroll_period p ON p.id = tr.period_id
        INNER JOIN prx_payroll_tax t ON tr.tax_id = t.id
        INNER JOIN prx_payroll_tax_account_line tal
               ON tal.tax_id = t.id AND COALESCE(tal.use_transaction_creditor, false) = false
        LEFT OUTER JOIN hr_employee emp ON emp.id = tr.employee_id
        LEFT OUTER JOIN prx_exact_creditor creditor ON creditor.id = emp.creditor_id
        LEFT OUTER JOIN LATERAL (
            SELECT string_agg(coalesce(gm.dst, s.ch), '' ORDER BY s.ord) AS name_en
            FROM regexp_split_to_table(emp.name, '') WITH ORDINALITY AS s(ch, ord)
            LEFT OUTER JOIN georgian_map gm ON gm.src = s.ch
        ) emp_name ON true
        LEFT OUTER JOIN prx_payroll_worksheet w ON tr.worksheet_id = w.id AND w.type != ''
        WHERE p.end_date = %s and creditor.crdnr is not null

        UNION ALL

        -- tax: consolidated CREDITOR line, one row per creditor per period.
        -- crdnr comes from the tax creditor's res_partner.exact_crdnr_code field.
        SELECT
            EXTRACT(YEAR FROM p.end_date) AS Year,
            EXTRACT(MONTH FROM p.end_date) AS Period,
            tal.exact_account AS Account,
            concat('TAX ', tp.exact_crdnr_code) AS Description,
            tp.exact_crdnr_code AS Crdnr,
            '' AS CC,
            '' AS CU,
            SUM(
                CASE
                    WHEN tal.debit_percent = 100 THEN -tr.amount
                    WHEN tal.credit_percent = 100 THEN tr.amount
                    ELSE tr.amount
                END
            ) AS Amount
        FROM prx_payroll_transaction tr
        INNER JOIN prx_payroll_period p ON p.id = tr.period_id
        INNER JOIN prx_payroll_tax t ON tr.tax_id = t.id
        INNER JOIN prx_payroll_tax_account_line tal
               ON tal.tax_id = t.id AND COALESCE(tal.use_transaction_creditor, false) = true
        LEFT OUTER JOIN res_partner tp ON tp.id = t.creditor
        LEFT OUTER JOIN hr_employee emp ON emp.id = tr.employee_id
        LEFT OUTER JOIN prx_exact_creditor creditor ON creditor.id = emp.creditor_id
        WHERE p.end_date = %s and creditor.crdnr is not null and tp.exact_crdnr_code is not null
        GROUP BY
            EXTRACT(YEAR FROM p.end_date),
            EXTRACT(MONTH FROM p.end_date),
            tal.exact_account,
            tp.exact_crdnr_code

        UNION ALL

        -- deduction: DEBIT (and any non-creditor) lines, one row per account line
        SELECT
            EXTRACT(YEAR FROM p.end_date) AS Year,
            EXTRACT(MONTH FROM p.end_date) AS Period,
            dal.exact_account AS Account,
            concat(emp_name.name_en, ' ', d.deduction_exact, ' ', tr.transaction_type) AS Description,
            creditor.crdnr AS Crdnr,
            '' AS CC,
            '' AS CU,
            CASE
                WHEN dal.debit_percent = 100 THEN -tr.amount
                WHEN dal.credit_percent = 100 THEN tr.amount
                ELSE tr.amount
            END AS Amount
        FROM prx_payroll_transaction tr
        INNER JOIN prx_payroll_period p ON p.id = tr.period_id
        INNER JOIN prx_payroll_deduction d ON tr.deduction_id = d.id AND d.deduction_exact != 'avansi'
        INNER JOIN prx_payroll_deduction_account_line dal
               ON dal.deduction_id = d.id AND COALESCE(dal.use_transaction_creditor, false) = false
        LEFT OUTER JOIN hr_employee emp ON emp.id = tr.employee_id
        LEFT OUTER JOIN prx_exact_creditor creditor ON creditor.id = emp.creditor_id
        LEFT OUTER JOIN LATERAL (
            SELECT string_agg(coalesce(gm.dst, s.ch), '' ORDER BY s.ord) AS name_en
            FROM regexp_split_to_table(emp.name, '') WITH ORDINALITY AS s(ch, ord)
            LEFT OUTER JOIN georgian_map gm ON gm.src = s.ch
        ) emp_name ON true
        WHERE p.end_date = %s and creditor.crdnr is not null

        UNION ALL

        -- deduction: consolidated CREDITOR line, one row per creditor per period.
        -- crdnr comes from the deduction creditor's res_partner.exact_crdnr_code field.
        SELECT
            EXTRACT(YEAR FROM p.end_date) AS Year,
            EXTRACT(MONTH FROM p.end_date) AS Period,
            dal.exact_account AS Account,
            concat('DEDUCTION ', dp.exact_crdnr_code) AS Description,
            dp.exact_crdnr_code AS Crdnr,
            '' AS CC,
            '' AS CU,
            SUM(
                CASE
                    WHEN dal.debit_percent = 100 THEN -tr.amount
                    WHEN dal.credit_percent = 100 THEN tr.amount
                    ELSE tr.amount
                END
            ) AS Amount
        FROM prx_payroll_transaction tr
        INNER JOIN prx_payroll_period p ON p.id = tr.period_id
        INNER JOIN prx_payroll_deduction d ON tr.deduction_id = d.id AND d.deduction_exact != 'avansi'
        INNER JOIN prx_payroll_deduction_account_line dal
               ON dal.deduction_id = d.id AND COALESCE(dal.use_transaction_creditor, false) = true
        LEFT OUTER JOIN res_partner dp ON dp.id = d.creditor
        LEFT OUTER JOIN hr_employee emp ON emp.id = tr.employee_id
        LEFT OUTER JOIN prx_exact_creditor creditor ON creditor.id = emp.creditor_id
        WHERE p.end_date = %s and creditor.crdnr is not null and dp.exact_crdnr_code is not null
        GROUP BY
            EXTRACT(YEAR FROM p.end_date),
            EXTRACT(MONTH FROM p.end_date),
            dal.exact_account,
            dp.exact_crdnr_code
        ORDER BY Year, Period
        """
        self.env.cr.execute(sql, (
            self.period_id.end_date,  # earning branch
            self.period_id.end_date,  # tax debit / non-creditor lines
            self.period_id.end_date,  # tax consolidated creditor line
            self.period_id.end_date,  # deduction debit / non-creditor lines
            self.period_id.end_date,  # deduction consolidated creditor line
        ))
        return self.env.cr.dictfetchall()

    def _export_to_exact(self, conn, rows):
        m_year, m_per = None, None
        bkstnr, volgnr5 = None, None
        regel = 1

        for row in rows:
            if m_year != row['year'] or m_per != row['period']:
                m_year, m_per = row['year'], row['period']
                bkstnr = self._get_new_bkstnr(conn, m_year, self.dagbknr)
                volgnr5 = self._get_new_volgnr5(conn, m_year, m_per, self.dagbknr)

                if not bkstnr or not volgnr5:
                    raise UserError('Could not generate BKSTNR/VOLGNR5 from Exact stored procedures.')

                volgnr5 = self._format_volgnr5(volgnr5)

                docdate = self._get_period_docdate(m_year, m_per)
                period = self._format_period(m_per)
                self._insert_amutak_entry(conn, m_year, period, docdate, bkstnr, volgnr5)
                regel = 1

            line_sql = """
                           INSERT INTO amutas (bkjrcode, periode, dagbknr, bkstnr, volgnr5, reknr, oms25, crdnr, \
                                               bedrag, val_bdr, exvalbdr, datum, docdate, faktuurnr, docnumber, \
                                               btw_code, valcode, verschil, betwijze, kredbep, exvalcode, levverw, \
                                               betcond, \
                                               regel, entryorigin, transsubtype, res_id, syscreator, sysmodifier)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, \
                                   %s, %s, %s, %s, %s, %s, %s, \
                                   '0  ', 'GEL', 0, 'B', 'K', 'GEL', 'L', '00', \
                                   %s, 'N', 'W', %s, %s, %s) \
                           """

            docdate = self._get_period_docdate(m_year, m_per)
            conn.execute_dml(line_sql, (
                    m_year,  # bkjrcode
                    self._format_period(m_per),  # periode (char(3), e.g. '  1')
                    self.dagbknr,  # dagbknr (journal, e.g. '064')
                    bkstnr,  # bkstnr (entry number)
                    volgnr5,  # volgnr5 (sequence number, width 5)
                    row.get('account'),  # reknr (Exact account)
                    (row.get('description') or '')[:25],  # oms25 (description, max 25 chars)
                    row.get('crdnr'),  # crdnr (creditor number)
                    row.get('amount'),  # bedrag
                    row.get('amount'),  # val_bdr
                    row.get('amount'),  # exvalbdr
                    docdate,  # datum (datetime, e.g. 2026-04-30 00:00:00.000)
                    docdate,  # docdate (same as datum)
                    bkstnr,  # faktuurnr (must equal bkstnr)
                    bkstnr,  # docnumber (must equal bkstnr)
                    str(int(regel)).rjust(4),  # regel (line no, 4 chars)
                    self.OPERATOR_ID,  # res_id
                    self.OPERATOR_ID,  # syscreator
                    self.OPERATOR_ID,  # sysmodifier
                ))
            regel += 1

    @staticmethod
    def _get_period_docdate(year, period):
        return (date(int(year), int(period), 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    @staticmethod
    def _format_period(period):
        return str(int(period)).rjust(3)

    @staticmethod
    def _format_volgnr5(volgnr5):
        return str(int(str(volgnr5).strip())).rjust(5)

    def _insert_amutak_entry(self, conn, year, period, docdate, bkstnr, volgnr5):
        calls = [
            (
                """
                    EXEC [EXSERVER].[070].[dbo].[usp_InsertAmutakEntry]
                        @bkjrcode=%s,
                        @dagbknr=%s,
                        @docdate=%s,
                        @periode=%s,
                        @bkstnr=%s,
                        @volgnr5=%s;
                """,
                (year, self.dagbknr, docdate, period, bkstnr, volgnr5),
            ),
            (
                """
                    EXEC [EXSERVER].[070].[dbo].[usp_InsertAmutakEntry]
                        @bkjrcode=%s,
                        @dagbknr=%s,
                        @docdate=%s,
                        @period=%s,
                        @bkstnr=%s,
                        @volgnr5=%s;
                """,
                (year, self.dagbknr, docdate, period, bkstnr, volgnr5),
            ),
            (
                """
                    EXEC [EXSERVER].[070].[dbo].[usp_InsertAmutakEntry]
                        @bkjrcode=%s,
                        @dagbknr=%s,
                        @docdate=%s,
                        @periode=%s,
                        @bkstnr=%s,
                        @volgnr5=%s,
                        @entryorigin='N',
                        @syscreator=%s,
                        @sysmodifier=%s,
                        @betwijze='B',
                        @kredbep='K',
                        @oorsprong='A',
                        @status='E',
                        @Division=70;
                """,
                (year, self.dagbknr, docdate, period, bkstnr, volgnr5, self.OPERATOR_ID, self.OPERATOR_ID),
            ),
        ]

        last_error = None
        for sql, params in calls:
            try:
                conn.execute_dml(sql, params)
                return
            except Exception as err:
                if 'too many arguments' in str(err).lower() or 'expects parameter' in str(err).lower():
                    last_error = err
                    continue
                raise

        if last_error:
            raise last_error

    def _get_new_bkstnr(self, conn, year, journal):
        sql = """
            DECLARE @newBKSTNR char(8);
            EXEC [EXSERVER].[070].[dbo].[PrxGetNewBKSTNR]
                @Year=%s,
                @JournalN=%s,
                @newBKSTNR=@newBKSTNR OUTPUT;
            SELECT @newBKSTNR AS new_val;
        """
        res = conn.execute_query(sql, (year, journal))
        return res[0]['new_val'] if res else None

    def _get_new_volgnr5(self, conn, year, period, journal):
        sql = """
            DECLARE @newVolgnr5 char(5);
            EXEC [EXSERVER].[070].[dbo].[PrxGetNewVolgnr5]
                @bkjrcode=%s,
                @period=%s,
                @dagbknr=%s,
                @newVolgnr5=@newVolgnr5 OUTPUT;
            SELECT @newVolgnr5 AS new_val;
        """
        res = conn.execute_query(sql, (year, self._format_period(period), journal))
        return res[0]['new_val'] if res else None
