# Changelog

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