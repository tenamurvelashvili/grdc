import requests
import json
import datetime

class EmployeeAPIClient:

    def __init__(self,base_url: str,token: str=None, username: str = None, password: str = None, auth_type: int = 0, device_code: str = None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.auth_type = auth_type
        self.device_code = device_code
        self.access_token = token

    def _headers(self, include_auth: bool = False):
        headers = {"Content-Type": "application/json"}
        if include_auth and self.access_token:
            headers["Authorization"] = f"bearer {self.access_token}"
        return headers

    def authenticate(self):
        url = f"{self.base_url}/Users/Authenticate"
        payload = {
            "USERNAME": self.username,
            "PASSWORD": self.password,
            "AUTH_TYPE": self.auth_type,
            "DEVICE_CODE": self.device_code or ""
        }
        resp = requests.post(url, headers=self._headers(False), json=payload)
        if resp.status_code == 200:

            data = resp.json().get("DATA", {})

            if "ACCESS_TOKEN" in data and data["ACCESS_TOKEN"]:
                self.access_token = data["ACCESS_TOKEN"]
                return resp.status_code, data

            if "PIN_TOKEN" in data:
                return resp.status_code,data

            return resp.status_code, resp.json().get("STATUS", {})
        return resp.status_code,resp.text

    def authenticate_pin(self, pin_token: str, pin: int, device_code: str = None, address: str = None,
                         browser: str = None, oper_system: str = None):

        url = f"{self.base_url}/Users/AuthenticatePin"
        payload = {
            "PIN_TOKEN": pin_token,
            "PIN": pin,
            "DEVICE_CODE": device_code or None,
            "ADDRESS": address or None,
            "BROWSER": browser or None,
            "OPER_SYSTEM": oper_system or None
        }
        resp = requests.post(url, headers=self._headers(False), json=payload)
        resp.raise_for_status()
        data = resp.json().get("DATA", {})
        if "ACCESS_TOKEN" in data and data["ACCESS_TOKEN"]:
            self.access_token = data["ACCESS_TOKEN"]
            return data
        raise RuntimeError(f"Unexpected response from AuthenticatePin: {resp.text}")

    def sign_out(self):
        if not self.access_token:
            raise RuntimeError("No access token.")
        url = f"{self.base_url}/Users/SignOut"
        resp = requests.post(url, headers=self._headers(True), json={})
        resp.raise_for_status()
        self.access_token = None
        return resp.json().get("STATUS", {}).get('ID', {})


    def get_countries(self, country_name: str = "", country_id: str = ""):
        if not self.access_token:
            raise RuntimeError("Not authenticated.")
        url = f"{self.base_url}/Employees/GetCountries"
        payload = {
            "COUNTRY_NAME": country_name,
            "COUNTRY_ID": country_id
        }
        resp = requests.post(url, headers=self._headers(True), json=payload)
        resp.raise_for_status()
        return resp.json().get("DATA", {}).get("COUNTRIES", {})

    def get_employee(self, id: int):
        if not self.access_token:
            raise RuntimeError("Not authenticated.")
        url = f"{self.base_url}/Employees/GetEmployee"
        payload = {"ID": id}
        resp = requests.post(url, headers=self._headers(True), json=payload)
        resp.raise_for_status()
        return resp.json().get("DATA", {})

    def save_employee(self, employee_data: dict):
        if not self.access_token:
            raise "Not authenticated."
        url = f"{self.base_url}/Employees/SaveEmployee"

        # Ensure all dates/datetimes are converted to ISO strings
        serializable_data = {
            key: (value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) else value)
            for key, value in employee_data.items()
        }

        resp = requests.post(url, headers=self._headers(True), json=serializable_data)
        print(resp.status_code)
        if resp.status_code == 200:
            return resp.status_code, resp.json().get("DATA", {})
        return resp.status_code, resp.json()

    def list_employees(self, tin: str = None):
        if not self.access_token:
            raise RuntimeError("Not authenticated")
        url = f"{self.base_url}/Employees/ListEmployees"
        payload = {}
        if tin:
            payload = {"TIN": tin}
        resp = requests.post(url, headers=self._headers(True), json=payload)
        resp.raise_for_status()
        return resp.status_code, resp.json().get("DATA", {})

# if __name__ == "__main__":
#     USERNAME = "tbilisi"
#     PASSWORD = "123456"
#     AUTH_TYPE = 0
#     DEVICE_CODE = None
#
#     client = EmployeeAPIClient(
#         base_url="https://eapi.rs.ge",
#         username=USERNAME,
#         password=PASSWORD,
#         auth_type=AUTH_TYPE,
#         device_code=DEVICE_CODE,
#         # token="f7d9eadb-da43-44f1-8511-138020cf4c14-05062025023543"
#     )
#
#     auth_data = client.authenticate()
#     print("Authenticate response DATA:", json.dumps(auth_data, indent=2))
#
#     countries = client.get_countries(country_name="რეს", country_id="032")
#     print("GetCountries DATA:",countries)
#     #
#     # single_emp = client.get_employee(id=3260028)
#     # print("GetEmployee DATA:", single_emp)
#
#     # new_emp_payload = {
#     #     "ID": 0,
#     #     "IS_FOREIGNER": 1,
#     #     "TIN": "12345628910",
#     #     "FULLNAME": "dff dd",
#     #     "GENDER": "1",
#     #     "CITIZEN_COUNTRY_ID": "040",
#     #     "STATUS": 1,
#     #     "PHONE": "5000980004",
#     #     "WORK_TYPE": 1,
#     #     "BIRTH_DATE": "19-10-1990"
#     # }
#     # saved_emp = client.save_employee(new_emp_payload)
#     # print("SaveEmployee DATA:", saved_emp)
#
#     emp_list = client.list_employees()
#     print("ListEmployees DATA:", emp_list)
#
#     # signout_status = client.sign_out()
#     # print("SignOut STATUS:", json.dumps(signout_status, indent=2))
