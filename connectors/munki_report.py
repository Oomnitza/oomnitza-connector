import logging

from lib.connector import AssetsConnector, response_to_object


class Connector(AssetsConnector):
    MappingName = 'munki_report'
    Settings = {
        'url':              {'order': 1, 'example': 'https://Munki_Report', 'default': ''},
        'username':         {'order': 2, 'example': '***', 'default': ''},
        'password':         {'order': 3, 'example': '***', 'default': ''}
    }

    munki_report_db_columns = [
        "machine.serial_number",
        "machine.hostname",
        "machine.machine_desc",
        "reportdata.timestamp",
        "reportdata.console_user",
        "machine.os_version",
        "reportdata.remote_ip",
        "munkireport.manifestname"
    ]

    FieldMappings = {}

    def __init__(self, *args, **kwargs):
        super(Connector, self).__init__(*args, **kwargs)
        self.settings['url'] = self.settings['url'].rstrip('/') + '/index.php'
        self.csrf_token = ""

    def login(self):
        """Login to the Munki Report system"""
        auth_url = f"{self.settings['url']}?/auth/login"
        self.logger.info(f"Attempting to login to {auth_url}")

        # The response doesn't matter here, it's a welcome page. We just need the session cookies and the token.
        _ = self._get_session().post(
            auth_url,
            data={
                'login': self.settings['username'],
                'password': self.settings['password']
            },
        )

        self.csrf_token = self.get_cookie_token("CSRF-TOKEN")

    def get_headers(self):
        if not self.csrf_token:
            self.login()

        return {'x-csrf-token': self.csrf_token}

    def get_cookie_token(self, token_name):
        token_value = self._get_session().cookies.get(token_name)
        if token_value:
            return token_value
        else:
            self.logger.error(f"No {token_name} found in cookies.")

    def generate_query(self):
        return {f"columns[{str(i)}][name]": c for i, c in enumerate(self.munki_report_db_columns)}

    def get_munki_report_field_names(self, sql_query):
        columns = sql_query.split("FROM")[0].strip()
        dirty_column_names = columns.split(",")
        field_values = [n.split(".")[1].replace("`", "") for n in dirty_column_names]

        return field_values

    def extract_data_from_response(self, dict_response):
        if type(dict_response) is not dict:
            self.logger.error(f"Response was not of type dict, further procession was not possible:"
                      f" Actual type {type(dict_response)},"
                      f" The Response {dict_response}")
            return [], ""

        data = dict_response.get('data', [])
        sql_query = dict_response.get('sql', '')  # Determines the order of values in the list.
        errors = dict_response.get('error', '')  # An error could have occurred on the sql side but a 200 was returned

        if errors:
            self.logger.info(f"Error occurred within the request: {errors}")
            return [], ""

        return data, sql_query

    def get_assets(self):
        query_url = f"{self.settings['url']}?/datatables/data"
        
        self.logger.info("Issuing POST %s", query_url)

        query_data = self._get_session().post(query_url, data=self.generate_query(), headers=self.get_headers())

        self.logger.debug('Response code [%s]', query_data.status_code)

        mapped_item = {}
        if query_data.status_code != 200:
            self.logger.warning(f"Retrieving assets failed with status code {query_data.status_code}")
            return mapped_item

        dict_response = response_to_object(query_data.text)
        data, sql_query = self.extract_data_from_response(dict_response)

        if not data or not sql_query:
            self.logger.warning("There was no response data or the sql query was empty.")
            return mapped_item

        field_names = self.get_munki_report_field_names(sql_query)

        for d in data:
            for i, item in enumerate(d):
                mapped_item[field_names[i]] = item
            yield mapped_item

    def _load_records(self, options):
        for asset in self.get_assets():
            yield asset
