# Changelog

## [2025.04.1]

### Updated

- Adding GET and POST to the HttpAdapters allowed list
- Adding 429 Http error code to the HttpAdapters Retry list

# Changelog

## [2025.03.2]

### Fixed

- Fixed issue where config parsing was failing on empty `enable` values.

## [2025.03.1]

### Fixed

- Fixed some issues with docker setup around config.ini files.
- Fixed a write permission in the docker container for the docker user.

### Updated

- Update the .env file to and entrypoint scripts to ensure we can use either `config.ini` or `.env` files.
  - `ini_only` is used to run docker with a config.ini file instead of the new .env flow.
- Updated the README.md to reflect the correct state of the docker setup for on-prem integrations.
- Additional examples of services added to the docker-compose.yml

## [2024.11.1]

### Announcement
The Connector's versioning number has been change from digits to a YYYY.MM.Release candidate.
This will allow Oomnitza to easily track when a version was released.

The Connector python version has been upgraded from Python 3.8 to Python 3.12
Consult the README.md for more information.
Older version of the connector may still work with older version of Python, but these are no longer supported by Oomnitza
For the latest changes and security patches we recommend moving to this Release or greater.

### Added

- Cisco DNA: Added Cisco DNA to pull in network devices
- Docker entrypoint.sh script to simplify the docker commands

### Fixed

- Removed params from urls in log messages

### Updated

- Update the requirements.txt to reflect the change to Python 3.12
- Update Constants and helper functions to dedicated files for easier reuse.
  - Updated code files that require helper functions.
- Updated Dockerfile and docker-compose.yml to use simplified commands.

## [2.5.1]

### Fixed

- Fixed url creation issue on Windows machine.

## [2.5.0]

### Deprecated

- Deprecated Meraki Network Devices: Will be removed in next major release.
- Deprecated Netbox: Will be removed in next major release.

### Added

- Added the ability to cancel running connectors from the webui in Local mode.
- Added functionality for multiple list api calls.
- Chef: Added the ability to map extra node fields from the ini (See README.md for more information)

### Fixed

- Fixed some wording around log lines.
- Fixed Meraki Network Devices token issue with new Oomnitza release.
- Fixed MobileIron token issue with new Oomnitza release.

### Updated

- Update the requirements.txt to reflect the removal of old, unused connectors and their packages.
- Update the README.md to reflect current released connectors and information.
- Dell Asset Order Status: Updated to use Version 3
- MobileIron updated to streamline fetching assets. Removed redundant code.
- Updated checks for AWS Connector to reduce complexity of code.

### Removed

- Google Chrome Devices: This can be created from the Oomnitza webui in local mode and run via a managed mode on-prem.
- SimpleMDM Configuration: This can be created from the Oomnitza webui in local mode and run via a managed mode on-prem.
- Removed old connector files that can no longer be run and tracked from the webui, removed for maintainability reasons as well.
  - Airwatch, AzureUsers, BambooHR, Chromebooks, MerakiSM, Okta, OneLogin, Workday and Zendesk
- Removed the *Shim-Service* due to performance issues and no longer being required.

## [2.4.6]

### Updated

- WorkspaceOne Device Software Connector: Incorrect id used for device software api call

## [2.4.5]

### Updated

- WorkspaceOne Device Software Connector: Reduced the expiry time of the access token to 55 minutes to avoid edge condition where api call was made on the hour mark and failed with 401.

## [2.4.4]

### Fixed

- WorkspaceOne Device Software Connector: Updated installed apps api to exit on empty `app_items` list. All other apis finish on a 204 response.

## [2.4.3]

### Fixed

- WorkspaceOne Device Software Connector: Updated Api call to use the correct device uuid instead of id.
- Connector respecting `--testmode` flag and only processing 10 records.

## [2.4.2]

### Updated

- WorkspaceOne Device Software Connector
  - Added filter option to ignore **_com.apple._*** software bundles.
  - Added filter option to default software with no version to a version of _**0.0**_
  - Added functionality to sync either managed or installed software. Or to sync all.

### Fixed

- Fixed issue where the `verify_ssl` flag was being ignored as part of a request session resulting in SSL errors

## [2.4.1]

### Removed

- Removed the following deprecated assets basic connectors:
  - Airwatch
  - Chromebooks
  - Google Mobile Devices
  - Jamf (Casper)
  - Jamf Mobile
  - MerakiSM
  - SimpleMDM
- Removed the following deprecated users basic connectors:
  - Azure Users
  - BambooHR
  - Okta
  - OneLogin
  - Zendesk

## [2.4.0]

### Changed

- Starting from version 2.4.0 the connector project is migrated to the python 3.8.x. There is NO
 fallback support for the python2 or earlier version of python3

## [2.3.14]

### Added

- Adding Insight Order Status Asset connector
- Adding Dell Asset Order Status connector

### Updated

- Updated Tanium with session_token setting to support basic auth or token authorization.
- Updated the launch options to skip running the Shim-Service with `--skip-shim`. Runs by default.
- Updated vCenter to allow use of the new api versions from >v7.0U2 to v8.0U1 and legacy apis.

## [2.3.13]

### Updated

- Updated Munki Report with db_columns setting to enable the retrieval of extra columns.

## [2.3.12]

### Added

- Adding Munki Report asset load connector.
- Added the Shim-Service
- Updated some Connectors to Take advantage of the new service

## [2.3.11]

### Fixed

- Processing of ManageEngine Integration

## [2.3.10]

### Added

- Support processing of multiple AWS Regions
- Process initial AWS Credentials altogether with AWS IAM

### Updated

- Actualize README.md

### Fixed

- Multiply AWS IAM fixes

## [2.3.9]

### Added

- Support of AWS IAM flow
- Show error in the UI when max exceptions count are reached

### Updated

- python-ldap library 3.2.0 -> 3.4.0 version
- Get rid of enum34 library

### Fixed

- Chef Integration handle empty nodes gracefully
- Rogue Integration running forever issue

## [2.3.8]

### Added

- WorkspaceOne Connector for devices with apps/software
- Support of 'completed with empty response' status

### Updated

- README.md to respect new system wordings

### Fixed

- Updated certifi version to fix certificate verify failed error
- CSV Export issue that leads to the incorrect file processing


## [2.3.7]

### Removed

- Deprecated connectors (docs)

## [2.3.6]

### Added

- VMware vCenter devices connector

## [2.3.5]

### Added 

- Docker image for containerized environment setup.

## [2.3.4]

### Added

- Added Cisco Meraki Network Devices support. Sync all network and inventory devices under an Organization.

### Fixed

- LDAP utf-8 encoding/decoding issues 

## [2.3.3]

### Added

- `as_is` jinja filter allows to disable input data evaluation to native
    python types for the `managed` connector.
- Added two settings `include_checkin_devices_only` and `last_checkin_date_threshold` for the MobileIron connector

## [2.3.2]

### Added

- the support for the arbitrary importable modules in the connector mapping for the `managed` connectors
- the better fatal errors representation with the traceback logged within sync sessions for the `managed` connectors
- the basic SaaS <> User integration support for the `managed` users connectors

## [2.3.1]

### Added

- the `managed` connectors support the software processing for the asset-based connectors now.
- support for `--ignore-cloud-maintenance` command line argument to ignore the cloud maintenance in the main loop

### Fixed

- the `managed` connectors now guess the type of the values to send to Oomnitza instead of mindlessly pushing them as strings. 
- errors during the configuration processing for the `managed` connector will be logged in the cloud as the regular errors in the appropriate sync session and will not break the connector execution
 if this is suitable

## [2.3.0]

### Added

- support for the new session-based auth flow (the systems like VCenter, KACE, SolarWinds supports this flow) for the managed connectors
in case of on-premise deployments. 
- support the extra local inputs `local_inputs` for the managed connectors in case these inputs have to be filled with some secrets and these
secrets have to be stored using some local secret storage
- the failed request attempt to the external service will be logged in the cloud as the separate sync session with the failed state

## [2.2.1]

### Fixed

- Zendesk authentication issue 

## [2.2.0]

### Added

- support for the new `managed` mode and new generic `managed` connector module.
- `managed` mode is now the default mode for the connector

### Removed

- support for the `env_password` removed from the codebase; the local credentials have to be stored within the .ini file or within the secret storage 

## [2.1.3]

### Added 

- support `vault_alias` for the custom secret's alias

## [2.1.2]

### Fixed

- BambooHR authentication issue 

## [2.1.1]

### Changed

- Updated the README for the Chromebook connector
- Updated the requirements.txt

## [2.1.0]

### Changed

- Starting from version 2.1.0 the connector project is migrated to the python 3.6.x (or above). There is NO
 fallback support for the python2

## [2.0.1]

### Removed

- Attribute `missingAppsCount` was removed from the set of attributes requested by Meraki connector.

## [2.0.0]

### Added 

- support `update_only` and `insert_only` optional settings for all data sources.

### Changed

- `sync_field` is now optional field for all the data sources except `csv_assets`, `csv_users`, `ldap_assets`.
- if set the `sync_field` could be of multiple fields. To define multiple values split it with commas: `sync_field = USER,EMAIL`
- using a new Oomnitza API: payload and params have been changed as well.

### Removed

- `normal_position` option is no more the valid setting value for the user-specific connectors. Use the
regular mapping options with the configurable mapping rules to define the behavior for the `POSITION` user's attribute.

## [1.9.21]

### Added

- Added Netbox support.

## [1.9.20]

### Added

- Added the "Primary User" extraction for the SCCM connector.

## [1.9.19]

### Changed

- Altered logic for ServiceNow: pull more computer-specific attributes and custom "alm_hardware" attributes.

## [1.9.18]

### Changed

- Altered logic for ServiceNow: pull more computer-specific attributes.

## [1.9.17]

### Changed

- Altered logic for ServiceNow: pull all the assets, not only the "hardware" ones.

## [1.9.16]

### Added

- Added ServiceNow support.

## [1.9.15]

### Fixed

- Handle the Tanium API empty installed software issue

## [1.9.14]

### Added

- Added Workday support (via RaaS).

## [1.9.13]

### Added

- Added Tanium support.

## [1.9.12]

### Added

- Added KACE SMA support.

## [1.9.11]

### Added

- Added SimpleMDM support.

## [1.9.10]

### Added

- Added possibility to set up the mapping for the Jamf (Casper) mobile connector on the Oomnitza Portal side. This feature is supported by Oomnitza Portal starting from version 4.4.9.

## [1.9.9]

### Changed

- User-specific connectors now have the possibility to specify the sync_field, as it is for the asset-specific ones. The fallback support is added and if there is no `sync_field` explicitly defined in 
the settings the default one `USER` will be used. This feature is supported by Oomnitza Portal starting from version 4.4.8, the older versions of Oomnitza will ignore the custom `sync_field` and use 
the default `USER`.

### Removed

- Removed the support for the Azure devices integration (Intune MDM) because it is migrated completely to the Oomnitza web portal and has to be enabled and configured there. 
