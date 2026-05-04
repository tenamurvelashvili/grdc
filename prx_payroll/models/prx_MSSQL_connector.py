import logging
import pymssql

_logger = logging.getLogger(__name__)


class MSSQLConnector:
    """
    Reusable MS SQL Server connector.
    Credentials are loaded from Odoo system parameters.

    Usage:
        with MSSQLConnector(self.env) as conn:
            rows = conn.execute_query("SELECT * FROM MyTable WHERE id=%s", (1,))
            conn.execute_sp("sp_MyProc", (param1, param2))
    """

    def __init__(self, env):
        get = env['ir.config_parameter'].sudo().get_param
        self._host = get('mssql.host')
        self._port = int(get('mssql.port') or 1433)
        self._user = get('mssql.user')
        self._password = get('mssql.password')
        self._database = get('mssql.database')
        self._conn = None
        self._connect()

    def _connect(self):
        try:
            self._conn = pymssql.connect(
                server=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                as_dict=True,
                timeout=30,
                charset='UTF-8',
                tds_version='7.0',  # try 7.0, 7.1, 7.2, 7.3, 7.4
            )
            _logger.info("MS SQL connected to %s/%s", self._host, self._database)
        except Exception as e:
            _logger.error("MS SQL connection failed: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  SELECT queries                                                       #
    # ------------------------------------------------------------------ #
    def execute_query(self, sql, params=None):
        """
        Run any SELECT statement.
        Returns a list of dicts.
        params must be a tuple, e.g. (value1, value2)
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
        except Exception as e:
            _logger.error("MS SQL query error: %s | SQL: %s", e, sql)
            raise
        finally:
            cursor.close()

    # ------------------------------------------------------------------ #
    #  Stored Procedures                                                    #
    # ------------------------------------------------------------------ #
    def execute_sp(self, sp_name, params=None, fetch=True):
        """
        Execute a stored procedure.
        params: tuple of positional args, e.g. ('GEO', 2024)
        fetch:  True  → return result rows (list of dicts)
                False → commit write-SP, return None
        """
        placeholders = ", ".join(["%s"] * len(params)) if params else ""
        sql = f"EXEC {sp_name} {placeholders}"
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or ())
            if fetch:
                return cursor.fetchall()
            self._conn.commit()
            return None
        except Exception as e:
            _logger.error("MS SQL SP error: %s | SP: %s", e, sp_name)
            raise
        finally:
            cursor.close()

    # ------------------------------------------------------------------ #
    #  DML helpers                                                          #
    # ------------------------------------------------------------------ #
    def execute_dml(self, sql, params=None):
        """INSERT / UPDATE / DELETE. Auto-commits."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or ())
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            _logger.error("MS SQL DML error: %s", e)
            raise
        finally:
            cursor.close()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------ #
    #  Context manager support                                              #
    # ------------------------------------------------------------------ #
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
