# Changelog

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