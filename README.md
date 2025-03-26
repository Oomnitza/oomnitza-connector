#### * Python3.8 Deprecation Notice:
Since version **2024.11.1** the connector no longer supports Python versions less than 3.12.

The further maintenance, support and development of the versions of Python prior to 3.12 is NOT planned.

Please make sure you have converted ALL custom converters and filters to Python 3.12 syntax before upgrading the connector to version 2024.11.1 or above.
This may require you to create a new virtual environment with the Python 3.12, if so ensure all local changes are saved before upgrading.
The Docker image should have the newest environment once pulled from dockerhub. Check Docker section below for any changes in setup.

# Local connector
Oomnitza’s local connector, built using Python 3.12, is a single application that pulls data from multiple vendor applications and pushes data into your Oomnitza instance. 

The local connector can pull data from the following sources:

* Chef [https://www.chef.io/chef/](https://www.chef.io/chef/)
* Jasper [http://www.jasper.com](http://www.jasper.com/)
* LDAP e.g., [http://www.openldap.org](http://www.openldap.org/), [Active Directory](https://www.microsoft.com)
* MobileIron [http://www.mobileiron.com](http://www.mobileiron.com/)
* Netbox [https://netbox.readthedocs.io/en/stable/](https://netbox.readthedocs.io/en/stable/)
* Open-AudIT [https://www.open-audit.org/](https://www.open-audit.org/)
* SCCM [http://www.microsoft.com](http://www.microsoft.com/en-us/server-cloud/products/system-center-2012-r2-configuration-manager/)
* Tanium [https://www.tanium.com/](https://www.tanium.com/)
* vCenter [https://www.vmware.com](https://www.vmware.com)
* WorkspaceOne [https://www.workspaceone.com](https://www.workspaceone.com)
* Munki Report [https://github.com/munkireport/munkireport-php](https://github.com/munkireport/munkireport-php)
* Insight [https://www.insight.com/en_US/home.html](https://www.insight.com/en_US/home.html)
* Dell Asset Order Status [https://developer.dell.com/apis/9208/versions/2/apiV2.json/definitions/DellOrder](https://developer.dell.com/apis/9208/versions/2/apiV2.json/definitions/DellOrder)
* Plain CSV files

## Before you begin

The local connector can be used to create two types of integrations:
-   [Basic integrations](#basic-integrations)
-   [Extended integrations](#extended-integrations)

## Basic integrations

Basic integrations run on our local connector and can presently pull data from the sources listed above. To create a basic integration, you complete these actions:
-   Download the code for the basic integration from GitHub    
-   Update the configuration file    
-   Push the configuration file to your Oomnitza instance    
-   Map the vendor application’s fields to Oomnitza

## Extended integrations

![integrationtypes_basic_and_extended](https://user-images.githubusercontent.com/106762328/184131676-e1b0fe85-cef1-42db-b484-b73970259098.png)

The initial setup and configuration of extended integrations that use the local connector is similar to that of basic integrations.  However, when an extended integration is pushed to your Oomnitza instance, you can avail of additional features in the Oomnitza UI to:
  - Create and manage schedules
 - Review detailed error logs
 - Easily add mapping fields

To set up an extended integration locally, complete the steps and [set the connector to run in managed mode](#setting-the-connector-to-run-in-managed-mode). Some of the reasons why customers choose to install extended integrations locally are as follows:
 - To access systems that cannot be accessed from the Oomnitza Cloud
 - To store credentials locally. That is, you don’t want to store connection credentials in the Oomnitza Cloud.
 - To connect to systems such as Microsoft Endpoint Configuration Manager (MECM), Lightweight Directory Access Protocol (LDAP), and VMWare VCenter.

Alternatively, you can create extended connector integrations that run in the Oomnitza Cloud. When you run extended integrations in the Oomnitza cloud, you get more more benefits and features such as:

 - The onboarding wizard to set up instances in minutes.
 - The Oomnitza vault with built-in security for storing credentials in the Cloud. See [Adding credentials to the Oomnitza vault](https://oomnitza.zendesk.com/hc/en-us/articles/360058760613-Adding-credentials-to-the-Oomnitza-vault).
 -  More authentication options such as OAuth and AWS.
  - The syncing of SaaS users.
 
 We also have more extended cloud integrations to choose from! 
To view a complete list of our supported extended integrations navigate to **Configuration>Extended>New Integration** in your Oomnitza instance or checkout our [ documentation](https://oomnitza.zendesk.com/hc/en-us/sections/6552754147735-Extended-connector-integrations).

If you can’t find an integration, you can request one.  See how to [request extended integrations](https://oomnitza.zendesk.com/hc/en-us/articles/360056773473-Requesting-custom-extended-integrations).
___

  - [Getting Started](#getting-started)
  - [System Requirements](#system-requirements)
  - [Runtime Environment Setup](#runtime-environment-setup)
    - [Linux Environment](#linux-environment)
    - [Windows Environment](#windows-environment)
    - [OS X Environment](#os-x-environment)
  - [Containerized Environment Setup](#containerized-environment-setup)
    - [Overview](#overview)
    - [Before you start](#before-you-start)
      - [Download the GitHub repository](#download-the-github-repository)
      - [Install the GitHub repository](#install-the-github-repository)
    - [Download and install Docker Desktop](#download-and-install-docker-desktop)
    - [Run the local connector with Docker Compose](#run-the-local-connector-with-docker-compose)
      - [Initial configuration](#initial-configuration) 
      - [Modify the .env file](#modify-the-env-file)
    - [Modify the Docker Image](#modify-the-docker-image)
      - [Run the Local Connector](#run-the-local-connector)
      - [Additional Service Examples](#addtional-service-examples)
    - [Add service examples](#add-service-examples)
      - [LDAP service](#ldap-service)
      - [CSV Assets service](#csv-assets-service)
        - [LDAP Service](#ldap-service)
        - [CSV Assets Service](#csv-assets-service)
  - [Connector Configs](#connector-configs)
    - [Common optional settings](#common-optional-settings)
    - [Oomnitza Configuration](#oomnitza-configuration)
  - [Storage for Connector secrets](#storage-for-connector-secrets)
    - [Common recommendations](#common-recommendations)
    - [Deployment and receiving secrets](#deployment-and-receiving-secrets)
      - [Local KeyRing](#local-keyring)
      - [HashiCorp Vault](#hashicorp-vault)
      - [CyberArk secret storage](#cyberark-secret-storage)
        - [Self-hosted CyberArk installation](#self-hosted-cyberark-installation)
        - [Managing secrets via CyberArk](#managing-secrets-via-cyberark)
        - [Connector configuration](#connector-configuration)
  - [Running the connector server](#running-the-connector-server)
  - [Running the connector client](#running-the-connector-client)
    - [Setting the Connector to Run in Managed Mode](#setting-the-connector-to-run-in-managed-mode)
	    - [Configuration details for managed mode](#configuration-details-for-managed-mode)
      - [SaaS authorization item](#saas-authorization-item)
      - [Oomnitza authorization item](#oomnitza-authorization-item)
      - [Local inputs item](#local-inputs-item)
      - [Setting the export file connector](#setting-the-export-file-connector)
    - [Setting the connector to run in upload mode](#setting-the-connector-to-run-in-upload-mode)
      - [Setting the connector to run as an automated task for upload mode](#setting-the-connector-to-run-as-an-automated-task-for-upload-mode)
      - [CSV Assets Configuration](#csv-assets-configuration)
      - [CSV Users Configuration](#csv-users-configuration)
      - [Chef Configuration](#chef-configuration)
      - [Jasper Configuration](#jasper-configuration)
      - [KACE SMA Configuration](#kace-sma-configuration)
      - [LDAP Users Configuration](#ldap-users-configuration)
      - [LDAP Assets Configuration](#ldap-assets-configuration)
      - [MobileIron Configuration](#mobileiron-configuration)
      - [Netbox Configuration](#netbox-configuration)
      - [Open-AudIT Configuration](#open-audit-configuration)
      - [SCCM Configuration](#sccm-configuration)
      - [Tanium Configuration](#tanium-configuration)
      - [vCenter Configuration](#vcenter-configuration)
      - [WorkspaceOne Configuration](#workspaceone-configuration)
      - [Munki Report Configuration](#munkireport-configuration)
      - [Insight Configuration](#insight-configuration)
      - [Dell Configuration](#dell-configuration)     
  - [Advanced usage](#advanced-usage)
    - [Logging](#logging)
    - [Custom Converters](#custom-converters)
    - [Record Filtering](#record-filtering)
  - [Current limitations](#current-limitations)
    - [Software mapping](#software-mapping)
    - [MS Windows environment](#ms-windows-environment)


## Getting Started
The most current version of this documentation can always be found on
 [GitHub](https://github.com/Oomnitza/oomnitza-connector/blob/master/README.md).

 Use this local connector to run basic integrations and to run extended integrations locally. 
 
To run basic integrations, follow the steps to install and configure the local connector.

To run extended integrations locally, follow the steps to install the local connector and [set the connector to run in managed mode](#setting-the-connector-to-run-in-managed-mode). 

If you would prefer to run extended integrations in the Oomnitza Cloud, refer to [extended integrations](#extended-integrations).

## System Requirements
The Oomnitza Connector supports Linux, Windows, and Mac OS. 
For Linux, we recommend the Ubuntu OS.
Recommended Requirements: 2-4 vCPU, 4-8 GB RAM, 2 GB disk space. 
Overall the Connector has a small footprint and only utilizes CPU and 
RAM during the scheduled synchronization jobs. With log rotation enabled for 
the generated Connector logs, the consumed disk space will remain within limits. 
Depending on the number of integrations and volume of data, 
the Connector can be configured to use additional workers.

## Runtime Environment Setup
You will need to install Python 3.12 as well as the packages which the connector
relies upon. Some of the python packages may require build tools to be installed.

Please visit the sections below related to the build tools before installing the additional modules.

We suggest you setup a [virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/)
 and use `pip` to install the requirements. This can be done as follows (See our
 [documentation](https://wiki.oomnitza.com/wiki/Installing_additional_Python_Modules) on installing
 additional Python modules for use in Oomnitza.):

    cd /path/to/connector
    virtualenv .
    source bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt 

### Linux Environment
On Ubuntu, the build tools are installed using:

    sudo apt-get install build-essential unixodbc unixodbc-dev

### Windows Environment
For MS Windows you have to install Windows C++ compilers as build tools. Please visit the [Python Wiki](https://wiki.python.org/moin/WindowsCompilers)
 To check what is appropriate compiler you have to download and install. 


### OS X Environment
For OS X environment you have to install the build tools using the following command:

    xcode-select --install


## Containerized Environment Setup

### Overview

Before we begin installing the local connector, it is important to think ahead about what data you want to bring in and how you want to store it in Oomnitza. Since Oomnitza is highly customizable, there are many possibilities. Before proceeding to the next steps, take time to think about what information you want, and what Oomnitza fields you want filled out with data. Complete the following steps in your Oomnitza instance: 
 - Click **Configuration > Integrations**.
 - In the **Basic** section for Asset or User Integrations, click the tile corresponding to the integration, such as Workspace ONE.
 - In the **Mappings** section, map the integration fields to the Oomnitza fields.  
- Select a unique identifier for the sync key, which will synchronize the data that is streamed from your integration to Oomnitza.
 
If the fields you want to map to Oomnitza haven’t been created yet, refer to our [Guide to creating custom fields in Oomnitza](https://oomnitza.zendesk.com/hc/en-us/articles/220045028-Creating-custom-fields).

### Before you start

To run the local connector in a docker container, you must:
 - Download and install the GitHub repository
 - Download and install Docker Desktop

#### Download the GitHub repository
 - Go to the [Oomnitza Connector](https://github.com/Oomnitza/oomnitza-connector#connector-configs) page on GitHub.
 - Scroll to the top of the page, click **Code**, and then click **Download Zip**.

#### Install the GitHub repository

You create a directory to download and install the GitHub repository on a local drive.

For example, in Windows, you create a directory called **myconfig** in this file path: `C:\oomnitza\connector\myconfig`

In Linux, you create a directory called **myconfig** in this file path: `/home/myconfig`

#### Download and install Docker Desktop

Click a link to download Docker Desktop:
 - [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
 - [Docker Desktop for Linux](https://hub.docker.com/search?offering=community&operating_system=linux&q=&type=edition)
 - [Docker Desktop for Mac](https://hub.docker.com/editions/community/docker-ce-desktop-mac?utm_source=docker&utm_medium=webreferral&utm_campaign=dd-smartbutton&utm_location=header)

### Run the local connector with Docker Compose

#### Initial configuration

To start the local connector using Docker Compose, you must complete these steps:
1. Have docker installed and running.
2. Download the Oomnitza Connector from Github
3. Either setup a `config.ini` or a `.env` file with the required config, examples can be seen below in [Connector Configs](#connector-configs) section 
   1. Copy `example.env` to `.env` and populate the necessary values
   2. OR copy the necessary configs from Connector Configs to a `config.ini`
4. Open the `docker-compose.yml` file and modify based on target integrations to run. See [Run the Local Connector](#run-the-local-connector) below
   1. There are examples for running ldap, csv_assets and managed as a starting point.
   2. There is an example of running a managed integration with a `config.ini` as this requires a special flag. `ini_only`
      1. See [Run the Local Connector](#run-the-local-connector) for more information.
5. If you need to make changes to the code or other files see [Modify the Docker Image](#modify-the-docker-image) section below.


#### Modify the .env file
 
To set up the local connector for your basic or extended integration, and to connect the local connector to your Oomnitza instance, you can create a `.env` file. The `.env` file tells the local connector which Oomnitza Cloud instance to connect to and which basic or extended integration the local connector should serve up to the Oomnitza Cloud instance.

If you intend to run the local connector solely to connect to systems that are behind a firewall, you only need to maintain the [oomnitza] section and one or more of the managed sections in the `.env` file.
The example below of the oomnitza section (top 3 lines) and the Managed integrations (not all fields are required)
`OOMNITZA_CONNECTOR_SOURCE` should be left as `default`
```dotenv
OOMNITZA_URL=https://<instance>.oomnitza.com
OOMNITZA_API_TOKEN=XXX
OOMNITZA_CONNECTOR_SOURCE=default

MANAGED_ENABLED=False
MANAGED_ID=XXX
MANAGED_SAAS_AUTHORIZATION={"params": {"api-token": "saas-api-token"}, "headers": {"Authorization": "Bearer Example"}}
MANAGED_OOMNITZA_AUTHORIZATION=oomnitza-api-token
MANAGED_LOCAL_INPUTS={"username": "username@example.com", "password": "ThePassword"}
MANAGED_TEST_RUN=false
MANAGED_IS_CUSTOM=false
```

For setup of a basic integration, like Chef, you can configure the following in the `.env`
```dotenv
OOMNITZA_URL=https://<instance>.oomnitza.com
OOMNITZA_API_TOKEN=XXX
OOMNITZA_CONNECTOR_SOURCE=default

CHEF_ENABLED=False
CHEF_URL=https://example.com/organizations/org
CHEF_CLIENT=user
CHEF_KEY_FILE=/path/to/user.pem
CHEF_ATTRIBUTE_EXTENSION=
```

For more information, see [Setting the Connector to Run in Managed Mode](#setting-the-connector-to-run-in-managed-mode)

### Modify the Docker Image.

If you need to modify the underlying code/docker image for testing purposes and need to rebuild the image you can run

`docker build -t oomnitza/oomnitza-connector:latest .`

This will rebuild the image with the same name and tag so you can trial your changes (the trailing dot is important)

> **WARNING**: _This command will replace the current image with the new built one._

If you want to keep changes separated, change the tag after the colon symbol to `beta` i.e. 

`docker build -t oomnitza/oomnitza-connector:beta .`

You will need to change this in the docker-compose.yml file to match the tag.
And will need to change all commands below from `latest` to `beta`

#### Run the Local Connector

Check the `docker-compose.yml` file to see the different ways to configure the On-Prem connector.
Below is an example of the setup required for Managed mode and for ldap local assets (Upload mode) using either `.env` or `config.ini`.
```yml
version: "3"

services:
  oomnitza-connector:
    image: oomnitza/oomnitza-connector:latest
    env_file:
      - .env
    command: ["managed"]
    # volumes:
    #   - /path/config.ini:/app/config.ini
  oomnitza-connector-managed-ini:
    image: oomnitza/oomnitza-connector:latest
    #env_file:
    #  - .env
    command: ["managed", "ini_only"]
    volumes:
      - /path/config.ini:/app/config.ini
  oomnitza-connector-ldap:
    image: oomnitza/oomnitza-connector:latest
    env_file:
      - .env
    command: ["upload", "ldap"]
    # volumes:
    #   - /path/config.ini:/app/config.ini

  oomnitza-connector-ldap-ini:
    image: oomnitza/oomnitza-connector:latest
    #env_file:
    #  - .env
    command: ["upload", "ldap", "ini_only"]
    volumes:
      - /path/config.ini:/app/config.ini
```

Next we need to decide if we want to use a `config.ini` file or the `.env` file setup.<br>
If you're using the `config.ini` file setup, you'll need to comment out `env_file:`, then, uncomment the `volume` section<br> of the docker-compose.yml file
and adjust the `/path/config.ini` before the colon with the system path to your local config.ini

For the `command` section we need to specify what mode we want to run in. A few examples below of the different options.
- If we want to run a managed integration on-prem we need to specify `command: ["managed"]`
- If we want to run a managed integration on-prem with the ini only we change to `command: ["managed", "ini_only"]`
- If we are running a basic integrations like VCenter we can do the following:
  - `command: ["upload", "vcenter"]` to run the integration as normal
  - `command: ["upload", "vcenter", "--testmode"]` to run the basic integration in test mode
  - `command: ["upload", "vcenter", "ini_only"]` to run the basic integration with a config.ini (this is subject to change in the future to make it easier to use)
    - `ini_only`, `--testmode` and other flags are mutually exclusive.

To run the local connector with Docker:

    docker run --env-file .env oomnitza/oomnitza-connector:latest
    docker run --env-file .env oomnitza/oomnitza-connector:latest upload ldap

To run the local connector with Docker Compose, issue the following command:

    docker-compose up oomnitza-connector -d

This will run the docker image in docker desktop.

To run different connectors (listed in the docker-compose.yml) i.e. ldap or managed-ini for example:

    docker-compose up oomnitza-connector-ldap -d
    docker-compose up oomnitza-connector-managed-ini -d

**Result**

The docker container will run in detached mode. That is, as a background process. It can be viewed in Docker Desktop.

### Additional Service Examples

If you need to run extended integrations, you can add a service to the Docker Compose configuration file,  `docker-compose.yml`.

#### LDAP Service

For LDAP, you add:
```yml
    oomnitza-connector-ldap:
      image: oomnitza/oomnitza-connector:latest
      env_file:
        - .env
      command: ["upload", "ldap"]
      # volumes:
      #   - /path/on/local/machine:/home/appuser/config/
```
#### CSV Assets Service

For CSV assets, you add:
```yml
    oomnitza-connector-csv-assets:
      image: oomnitza/oomnitza-connector:latest
      env_file:
        - .env
      command: ["upload", "csv_assets", "--testmode"]
      #volumes:
      #   - /another/path/on/local/machine:/home/appuser/exp/
      #   - /path/on/local/machine:/home/appuser/config/
```
The CSV file that contains the asset records should be stored in a directory on the local machine, the path in the container should be defined in the configuration file. For example, /home/appuser/exp/<file_name>.csv.

Example
```dotenv
CSV_ASSETS_ENABLED=True
CSV_ASSETS_FILENAME=/home/appuser/exp/assets.csv
CSV_ASSETS_DIRECTORY=
CSV_ASSETS_SYNC_FIELD=BARCODE
```
 
#### Important

If you run Docker on a Windows 10 desktop, you might need to enclose the Windows folder path with single or double quotes in the volumes section.


## Connector Configs

Now you should be able to generate a default config file. Running `python connector.py generate-ini` will regenerate
 the `config.ini` file, and create a backup if the file already exists. When you edit this file, it will have one section
 per connection. You can safely remove the section for the connections you will not be using to keep the file small and
 manageable.

If you require multiple different configurations of a single connector, such as the need to pull from two different LDAP OUs,
 additional sections can be added by appending a '.' and a unique identifier to the section name. For example, having both a
 `[ldap]` and `[ldap.Contractors]` section will allow you to pull users from a default and Contractor OU.

An example generated `config.ini` follows.

    [oomnitza]
    url = https://example.oomnitza.com
    api_token = 
    username = oomnitza-sa
    password = ThePassword
    
    [managed.xxx]
    enable = False
    saas_authorization = {"params": {"api-token": "saas-api-token"}, "headers": {"Authorization": "Bearer Example"}}
    oomnitza_authorization = oomnitza-api-token
    local_inputs = {"username": "username@example.com", "password": "ThePassword"}
    test_run = false
    
    [chef]
    enable = False
    url = https://example.com/organizations/org
    client = user
    key_file = /path/to/user.pem
    attribute_extension = {}
    node_mappings = {}
    
    [csv_assets]
    enable = False
    filename = /some/path/to/file/assets.csv
    directory = /some/path/to/files/
    sync_field = 24DCF85294E411E38A52066B556BA4EE
    
    [csv_users]
    enable = False
    filename = /some/path/to/file/users.csv
    directory = /some/path/to/files/
    default_role = 25
    default_position = Employee
    sync_field = USER
    
    [jasper]
    enable = False
    wsdl_path = http://api.jasperwireless.com/ws/schema/Terminal.wsdl
    username = username@example.com
    password = change-me
    api_token = YOUR Jasper API TOKEN
    storage = storage.db
    
    [kace]
    enable = False
    url = https://KACE_SMA
    username = ***
    password = ***
    organization_name = Default
    api_version = 8
    
    [ldap]
    enable = False
    url = ldaps://ldap.com:389
    username = cn=read-only-admin,dc=example,dc=com
    password = 
    base_dn = dc=example,dc=com
    group_dn = 
    protocol_version = 3
    filter = (objectClass=*)
    default_role = 25
    default_position = Employee
    page_criterium = 
    groups_dn = []
    group_members_attr = member
    group_member_filter = 
    
    [ldap_assets]
    enable = False
    url = ldaps://ldap.com:389
    username = cn=read-only-admin,dc=example,dc=com
    password = 
    base_dn = dc=example,dc=com
    group_dn = 
    protocol_version = 3
    filter = (objectClass=*)
    page_criterium = 
    groups_dn = []
    group_members_attr = member
    group_member_filter = 
    sync_field = 24DCF85294E411E38A52066B556BA4EE
    
    [mobileiron]
    enable = False
    url = https://na1.mobileiron.com
    username = username@example.com
    password = change-me
    partitions = ["Drivers"]
    api_version = 1
    include_checkin_devices_only = True
    last_checkin_date_threshold = 129600
    
    [netbox]
    enable = False
    url = https://NETBOX
    auth_token = *******
    
    [open_audit]
    enable = False
    url = http://XXX.XXX.XXX.XXX
    username = 
    password = 
    
    [sccm]
    enable = False
    server = server.example.com
    database = CM_DCT
    username = change-me
    password = change-me
    authentication = SQL Server
    driver = 
    
    [tanium]
    enable = False
    url = https://TANIUM_SERVER
    username = ***
    password = ***
    session_token = 
    domain = 
    view = 

    [vcenter]
    enable = False
    url = https://api_host
    username = administrator@vsphere.local
    password = change-me

    [workspaceone_devicesoftware]
    enable = False
    url = https://tech-dev.workspace.com
    client_id = ***
    client_secret = ***
    region = na
    apps_scope = all
    ignore_apple = False
    default_versioning = False

    [munki_report]
    enable = False
    url = https://munki_report
    username = administrator
    password = change-me
    db_columns = ["extra.column"]

    [insight]
    enable = False
    client_id = 123456
    client_key = 123456789
    client_secret = *******
    order_creation_date_from = YYYY-MM-DD
    order_creation_date_to = YYYY-MM-DD
    tracking_data = X
    
    [dell_asset_order_status]
    enable = False
    client_id = 234234
    client_secret = 34567
    is_dp_id = False
    is_po_numbers = True
    is_order_no_country_code = False
    values = ["PO123", "PO432"]
    country_code = ["US", "EU", "IN"]

The `[oomnitza]` section is where you configure the connector with the URL and login credentials for connecting to
Oomnitza. You can use an existing user’s credentials for username and password, but best practice is to create a
service account using your standard naming convention. See the documentation for [managing user accounts in Oomnitza](https://oomnitza.zendesk.com/hc/en-us/sections/204396587-Managing-people).


The remaining sections each deal with a single connection to an external service. The "enable" field is common to all
connections and if set to "True" will enable this service for processing. Some fields are common to a type of
connection. For example, "default_role" and "default_user" are fields for connections dealing with loading
People into the Oomnitza app.

Each section can end with a list of field mappings. Simple mappings which just copy a field from the external system to
 a field inside Oomnitza can be defined here or in the System Settings within Oomnitza. Simple mappings are as follows:

    mapping.[Oomnitza Field] = {"source": "[external field]"}

For fields which require processing before being brought into Oomnitza must be defined in the INI. These mappings are
 more involved. Please contact [support@oomnitza.com](mailto://support@oomnitza.com) for more information. The format is:

    mapping.[Oomnitza Field] = {"source": "[external field]", "converter": "[converter name]"}

### Common optional settings
`sync_field`: The Oomnitza field (fields) which contains the object's unique identifier. 
We typically recommend username or email for users and serial_number for assets.
Will be loaded from Oomnitza mapping if not set. To create multiple sync field, split it by comma,
for example `sync_field = USER,EMAIL`.
The exceptions to this rule are the LDAP assets & CSV files because there is no way to
set the mapping in Oomnitza for these data sources at the current moment.

`insert_only`: set this to True to only create records in Oomnitza. Records for existing objects will not be updated.

`update_only`: set this to True to only update records in Oomnitza. Records for new objects will not be created.

`insert_only` and `update_only` can not be both of true value.

`verify_ssl`: set to false if the target data source instance is running with a self signed or invalid SSL certificate.

`ssl_protocol` : if the service to be connected to requires a particular SSL protocol version to properly connect, the connection's
 section in the ini file can include a `ssl_protocol` option. The value can be one of:
 `ssl`, `sslv23`, `sslv3`, `tls`, `tls1`.

### Oomnitza Configuration
`url`: the url of the Oomnitza application. For example: `https://example.oomnitza.com`

`username`: the Oomnitza username to use

`password`: the Oomnitza password to use

`api_token`: The API Token belonging to the Oomnitza user. If provided, `username` and `password` will not be used. For further information, refer to [Creating an API token](https://oomnitza.zendesk.com/hc/en-us/articles/360049276794-Creating-an-API-token).

`user_pem_file`: The path to the PEM-encoded certificate containing the both private and public keys of the user. 
Has to be used **_only_** if there is enabled two factor authentication in your environment. The certificate has to be also uploaded to Oomnitza in the "Configuration/ Security/ Certificates" page.

## Storage for Connector secrets

To prevent secrets sprawl and disclosure the Oomnitza Connector uses secret backends to securely store credentials, usernames, API tokens, and passwords.

There are three options:

- local KeyRing;
- external Vault Key Management System by Hashicorp (the Vault KMS);
- external CyberArk Secrets Management

KeyRing (KeyChain) is a secure, encrypted database and the easiest to configure.

The [Vault KMS](https://www.vaultproject.io/intro/index.html) and [CyberArk](https://www.cyberark.com/products/privileged-account-security-solution/application-access-manager/) provide an
 additional layer of security. In this case, all secrets will be stored in the external encrypted system

### Common recommendations

Before adding secrets for Connector, first, follow the instructions and setup the Oomnitza Connector.
Use a technical role with restricted permissions to run the Connector.

### Deployment and receiving secrets

To add secrets use the command line utility which enables an easy way to
   place secrets to the system keyring service.

```sh
$ python strongbox.py --help
usage: strongbox.py [-h] [--version] --connector=CONNECTOR --key=KEY --value

optional arguments:
  -h, --help            show this help message and exit
  --version             Show the vault version.
  --connector CONNECTOR Connector name or vault alias under which secret is saved in vault.
  --key KEY             Secret key name.
  --value VALUE         Secret value. Will be requested.
```

To prevent password disclosure you will be asked to provide your secret value
in the console.

You can add a few secrets to one type of Connector using the different `"key"`

Note the `CONNECTOR` name used in the argument `--connector` must be the same as the name of the section
used to describe the connector, or the same as the `vault_alias` set in the section within configuration file. For example, for the command

    python strongbox.py --connector=<connector_name>.abc --key=api_token --value=
    
we expect the section `[<connector_name>.abc]` exists in the configuration where `<connector_name>` could be tanium, vcenter, etc.

    [<connector_name>.abc]
    enable = True
    ...
    
or the `vault_alias` was set within the section

    [<connector_name>]
    vault_alias = <connector_name>.abc
    enable = True
    ...

There is no validation set for the alias and the section name clash. If both found the alias has the priority.
Another thing to be mentioned is that the `vault_alias` can be any string value and not be relevant to the name of the service it relates to.  
It is OK to set the `vault_alias = I_love_cats` or any other value you want.

#### Local KeyRing

OS Supported:

Ubuntu Linux: [SecretStorage](https://github.com/mitya57/secretstorage) (requires installation of additional packages).

Windows: Windows Credential Manager (by default).

OS X: KeyChain. The encryption is AES 128 in GCM (Galois/Counter Mode).

_OS X Note: the `keyring==8.7` tested on Mac OS X 10.12.6._

1. To use local KeyRing specify `keyring` as the `vault_backend` in config

```ini
[oomnitza]
url = https://example.com
vault_backend = keyring
vault_keys = api_token
```

For Linux, you may have to install **dbus-python** package and configure KeyRing Daemon.

2. Add the secrets:

```sh
python strongbox.py --connector=oomnitza --key=api_token --value=
Your secret: your-secret
```

#### HashiCorp Vault

To use the Vault KMS:

1. Install, initialize and unseal the Vault KMS (use documentation).

2. Mount Key/Value Secret Backend.

3. Write secrets to Key/Value Secret Backend. For example:

```sh
$ vault write secret/<connector_name> \
    system_name=oomnitza_user \
    api_token=123456789ABCD$$$
Success! Data written to: secret/<connector_name>
```
4. Create a json/hcl file with policy:

This section grants all access on __"*secret/<connector_name>**"__. 
Further restrictions can be applied to this broad policy.

```hcl
path "secret/<connector_name>/*" {
  capabilities = ["read", "list"]
}
```

5. To add this policy to the Vault KMS system policies list use the following
   command or API:

```sh
vault write sys/policy/<connector_name>-read policy=@/root/vault/<connector_name>-read.hcl
```

6. To create a token with assigned policy:

```sh
vault token-create -policy=<connector_name>-read -policy=<connector_name>-read -policy=logs
Token: 6c1247-413f-4816-5f=a72-2ertc1d2165e
```

7. To use Hashicorp Vault as a secret backend set "vault_backend = vault" instead of "keyring".

```ini
[<connector_name>]
enable = true
url = https://example.com
vault_backend = vault
vault_keys = api_token username password
```

8. To connect to the Hashicorp Vault the `vault_url` and `vault_token` should
   be added to system keyring via vault cli.

Use `strongbox.py` cli to add `vault_url` and `vault_token` to system keyring

```sh
python strongbox.py --connector=<connector_name> --key=vault_url --value=
Your secret: https://vault.adress.com/v1/secret/<connector_name>

python strongbox.py --connector=<connector_name> --key=vault_token --value=
Your secret: 6c1247-413f-4816-5f=a72-2ertc1d2165e
```

__It is recomended to use read-only token.__

#### CyberArk secret storage

In order to use CyberArk as secret storage:

1. Install and configure CyberArk storage (use self-hosted storage or use
   dedicated storage provided by [CyberArk](https://www.cyberark.com/))

2. Write secrets to CyberArk storage

3. Configure connector to use CyberArk secret backend

##### Self-hosted CyberArk installation

- Use [official documentation](https://docs.conjur.org/Latest/en/Content/Get%20Started/install-open-source.htm) to install and configure CyberArk Conjur service

    ```
    # In your terminal, download the Conjur Open Source quick-start configuration
    curl -o docker-compose.yml https://www.conjur.org/get-started/docker-compose.quickstart.yml

    # Pull all of the required Docker images from DockerHub.
    docker-compose pull

    # Generate a master data key:
    docker-compose run --no-deps --rm conjur data-key generate > data_key

    # Load the data key into the environment:
    export CONJUR_DATA_KEY="$(< data_key)"

    # Run the Conjur server, database, and client:
    docker-compose up -d
    ```

    If you want to confirm that CyberArk was installed properly, you can open a
    browser and go to localhost:8080 and view the included status UI page.

- Create new account (name should be equal to your connector configration
    section)

    ```
    docker-compose exec conjur conjurctl account create <connector_name>
    # API key for admin: <cyberark_api_key>
    ```

- Start a bash shell for the Conjur client CLI

    ```
    docker-compose exec client bash
    ```

- Login into your account

    ```
    conjur init -u conjur -a <connector_name>
    conjur authn login -u admin
    ```

- Create root policy, e.g. [use more complex / nested configuration for
  granular permissions](https://docs.conjur.org/Latest/en/Content/Operations/Policy/PolicyGuideConcepts%20and%20Best%20Practices%20_%20Conjur%20Developer%20Docs.html)

    ```
    $ cat /root/policy/<connector_name>-policy.yml

    ---
    - !variable api_token
    - !variable some_secret_key
    ```

- Apply policy to your account (this allow you manage the specified secrets
    via command line or api)

    ```
    conjur policy load root /root/policy/<connector_name>-policy.yml
    ```

##### Managing secrets via CyberArk

- Push all required secrets into storage

    ```
    conjur variable values add api_token secret-api-token
    conjur variable values add some_secret_key some-secret-value
    ```

##### Connector configuration

- To connect to the CyberArk secret storage - the `vault_url` and `vault_token` should
  be added to system keyring via cli.

Use `strongbox.py` cli to add `vault_url` and `vault_token` to system keyring

```sh
python strongbox.py --connector=<connector_name> --key=vault_url --value=
Your secret: https://cyberark-secret-storage-sever.example.com

python strongbox.py --connector=<connector_name> --key=vault_token --value=
Your secret: <cyberark_api_key>
```

- Update connector configuration to use CyberArk secret storage

```ini
[<connector_name>]
enable = true
url = https://example.com
vault_backend = cyberark
vault_keys = api_token some_secret_key
```

## Running the connector server
It is possible to setup the connector server that will handle webhooks and other requests from external sources and react to them. 
The connector server is [WSGI compliant server](https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface).
The connector server is meant to be run from the command line with following command line arguments:

    $ python server.py -h
    usage: server.py [-h] [--host HOST] [--port PORT]
                     [--show-mappings] [--testmode] [--save-data] [--ini INI]
                     [--logging-config LOGGING_CONFIG]
    
    optional arguments:
      -h, --help            show this help message and exit
      --host HOST
      --port PORT
      --show-mappings       Show the mappings which would be used by the
                            connector.
      --testmode            Run connectors in test mode.
      --save-data           Saves the data loaded from other system.
      --ini INI             Config file to use.
      --logging-config LOGGING_CONFIG
                            Use to override logging config file to use.

The available arguments for the connector server are serving for the same purposes as for the connector client, except 2 new server-specific arguments:

`--host` is used to specify the server's host. Default is 127.0.0.1

`--port` is used to specify the server's port. Default is 8000

The url pointing to the connector server instance should ends with the name of the connector:

Examples:

    https://my-connector-server.com/it/does/not/matter/casper
    https://my-connector-server.com/it/does/not/matter/casper.MDM
    https://my-connector-server.com/it/does/not/matter/casper.1

## Running the connector client
The connector is meant to be run from the command line and as such as multiple command line options:

    $ python connector.py -h
    usage: connector.py [-h] [--record-count RECORD_COUNT] [--workers WORKERS]
                        [--show-mappings] [--testmode] [--save-data] [--ini INI]
                        [--logging-config LOGGING_CONFIG]
                        [--ignore-cloud-maintenance]
                        [{managed,upload,generate-ini,version}]
                        [connectors [connectors ...]]
    
    positional arguments:
      {version,generate-ini,upload,managed}
                            Action to perform.
      connectors            Connectors to run. Relevant only for the `upload` mode
    
    optional arguments:
      -h, --help            show this help message and exit
      --record-count RECORD_COUNT
                            Number of records to pull and process from connection.
                            Relevant only for the `upload` mode
      --workers WORKERS     Number of async IO workers used to pull & push
                            records.
      --ignore-cloud-maintenance
                            Adds special behavior for the managed connectors to
                            ignore the cloud maintenance
      --show-mappings       Show the mappings which would be used by the
                            connector. Relevant only for the `upload` mode
      --testmode            Run connectors in test mode.
      --save-data           Saves the data loaded from other system.
      --ini INI             Config file to use.
      --logging-config LOGGING_CONFIG
                            Use to override logging config file to use.

The available actions are:

* `version`: shows the version of the connector and exit
* `managed`: the default mode for the connector, starts the connector in the "managed-from-cloud" mode, when the configuration, mapping, etc are retrieved from the Oomnitza cloud. Requires to have
only the `[oomnitza]` section to be configured within the .ini file to operate
* `generate-ini`: generate an example `config.ini` file.
* `upload`: uploads the data from the indicated connectors to Oomnitza. The connector values are taken
   from the section names in the ini file.

`--ini` is used to specify which config file to load, if not provided, `config.ini` from the root directory will be used.
   This option can be used with the `generate-ini` action to specify the file to generate.

`--logging-config` is used to specify an alternate logging config file.

`--show-mappings` is used to print out the loaded mappings. These mappings can be a combination of the built-in mappings,
   `config.ini` mappings, and mappings setup via the website.

`--testmode` will print out the records which would have been sent rather than pushing the data to the server. This
   can be used to see what, exactly, is getting sent to the server.

`--record-count` is used to limit the number of records to process. Once this number have been processed, the connector
   will exit. This can be used with `--testmode` to print out a limited number of records then exit cleanly.

`--save-data` is used to save the data loaded from the remote system to disk. These files can then be used to confirm
   the data is being loaded and mapped as expected.

`--workers` is used to setup the number of workers used to push the extracted data to Oomnitza instance. Default is 2. 
   If you will increase this value it will increase the load generated by connector and decrease the time required to finish the full sync.

`--ignore-cloud-maintenance` is used to specify the connector in the managed mode to ignore the cloud maintenance. If enabled the main loop will not be interrupted during the maintenance and the
 connector will continue to work 

### Setting the Connector to Run in Managed Mode

You configure the local connector to run in `managed` mode when you want the local connector to deliver the asset and/or user data for extended integrations. That is, you don’t want to use the cloud connector to manage the delivery of data.

In `managed` mode, the scheduling, mapping, and other parameters are configured in the Oomnitza cloud and the local connector points to them and maintains the credentials. The reasons for running the local connector in `managed` mode are as follows:
 - You want to store credentials locally rather than storing the credentials in the Oomnitza Cloud.
 - You want to access systems behind firewalls or in local data centers that are not accessible from the Oomnitza Cloud.

If you are using docker setup you will need to adjust the docker-compose.yml to use either an `env` file or a `config.ini` file

**Important Note:** For managed integrations, it is essential to separate your basic integrations from your managed integrations. Use separate configuration files like `basic_config.ini` for basic integrations and `managed_config.ini` for managed integrations to avoid integration issues.

**Important Note:** This is also important if you are using `.env` files, having a `managed.env` and a `basic.env` to keep configurations separate will help avoid issues.


#### Configuration details for managed mode

In the configuration file, you must create a section for each of the managed integrations that you want to use. 

The name of each section comprises the combination of the following two strings separated by a period and enclosed in square brackets: 
 - `managed`
 - Integration **ID**

Example: `[managed.268]`

**Note**
You can obtain your Integration ID on the **Configuration>Integrations** page. Open the integration and look for the value for the **ID** parameter in the **URL**. For example, the format of the **URL** is `https://<instance_name>.oomnitza.com/settings/connectors?id=268&type=users&view=integrations`.

When you create a `managed` section, you must provide the credentials that are used when the integration is run. Because of security restrictions, you cannot use the credentials that are stored for the connectors in the Oomnitza Cloud instance. You can only use `basic` and `token based authorizations` that you pass in the header or params section of the API. The local connector does not support `OAuth 2` or `AWS based authentication`.  If you require `OAuth 2` or `AWS based authentication`, you could use the cloud connector  and enable certain routes using Mutual Transport Layer Security (mTLS) to enhance the security of the API calls. 

To configure credentials for a managed connector, the managed section can contain the following items:
 
 - saas_authorization
 - oomnitza_authorization
 - local_inputs

#### SaaS authorization item

The `saas_authorization` item is mandatory. It is a JSON defined dictionary with ready-to-use `HTTP headers` or `HTTP headers` and `query parameters` that are used to authorize with the external data source API or the **ID** of the stored credential in Oomnitza. 

To specify the `header` and `parameters`, the JSON format is as follows: 

    {"headers": <dictionary with the key-value specification of headers>, "params": <dictionary with the key-value specification of headers>}
 
The `headers` or `params` or both `headers` and `params` must be set. 

Let’s say a system must pass a special `authorization token` called `xyz` in the `authorization header` or as a `query parameter` called authorization:

    {"headers": {"authorization": "XYZ"}}                   # OK
    {"headers": {"authorization": "XYZ"}, "params": {}}     # OK
    {"params": {"authorization": "XYZ"}}                    # OK
    {"params": {"authorization": "XYZ"}, "headers": {}}     # OK
    
    {"params": {}, "headers": {}}      # NOT OK - headers and params not set
 
**Exception**

In `session-based authorization` scenarios, `headers` and `parameters` cannot be defined initially because they are automatically generated.

#### Oomnitza authorization item

The `oomnitza_authorization` item is optional. The API token of the user who runs the integration. If it is not set, the user that is defined in the `[oomnitza]` section is used.

#### Local inputs item

The `local_inputs` item is optional unless an integration requires additional secrets that must be passed to the Oomnitza GUI, and you want to store these secrets locally.

**Scenario 1**

The `config.ini` file for an extended integration with an **ID** of 67, which uses an `authorization header`.
 `Authorization: Bearer ABC`:

    [oomnitza]
    url = https://example.oomnitza.com
    api_token = i_am_oomnitza_api_token_1
    
    [managed.67]
    oomnitza_authorization = i_am_oomnitza_api_token_2
    saas_authorization = {"headers": {"Authorization": "Bearer ABC"}}
 
**Scenario 2**

The `config.ini` file for an extended integration with an **ID** of 15 that uses a `session-based authorization` flow and where all the required inputs are stored in the Oomnitza Cloud.

    [oomnitza]
    url = https://example.oomnitza.com
    api_token = i_am_oomnitza_api_token_1
    
    [managed.15]
    oomnitza_authorization = i_am_oomnitza_api_token_2
 
**Scenario 3**

The `config.ini` file for an extended integration with an **ID** of 34 that uses a `session-based authorization` flow and where all the required inputs are stored locally.
    
    [oomnitza]
    url = https://example.oomnitza.com
    api_token = i_am_oomnitza_api_token_1
    
    [managed.34]
    oomnitza_authorization = i_am_oomnitza_api_token_2
    local_inputs = {"username": "john.smith", "password": "supErs3cr3T"}

#### Setting the export file connector

"Export file" connector is the subset of the `managed` connectors. The main difference between the "export file" connector and all the other connectors is that 
it works in an `reverse` mode - it fetches the data from Oomnitza, not brings data to it. The result of sync of the "export file" connector is the .CSV file with the
data from Oomnitza (assets or users).

The configuration for the `managed` connector is the same as as for the regular `managed` connectors except for 2 differences

1) The section name of the "export file" connector is named with the `managed_reports`, not `managed`
2) The section `managed_reports` does not need the `saas_authorization` to be set because there is no SaaS to deal with, we deal only with Oomnitza

The full example of the config.ini file for the stored "export file" integration with **ID** = 68 :

    [oomnitza]
    url = https://example.oomnitza.com
    api_token = i_am_oomnitza_api_token_1

    [managed_reports.68]
    oomnitza_authorization = i_am_oomnitza_api_token_2


### Setting the connector to run in upload mode

The mode `upload` is the main mode for the connector before version 2.2.0. In this mode the connector sync initiated from the client's side.

To run the connector in the `upload` mode you have to start it like this:

    python connector.py upload <data_source_1> <data_source_2> ...

The specified name of the data source (`<data_source_1>`, ...) must match the name of the section within configuration .ini file
Within this section there must be `enable = True` set explicitly

#### Setting the connector to run as an automated task for upload mode
There are many ways to automate the sync, here are a few:

* OS X: http://www.maclife.com/article/columns/terminal_101_creating_cron_jobs
* OS X: http://superuser.com/questions/126907/how-can-i-get-a-script-to-run-every-day-on-mac-os-x
* OS X: http://launched.zerowidth.com/
* Linux: http://www.cyberciti.biz/faq/how-do-i-add-jobs-to-cron-under-linux-or-unix-oses/
* Windows: http://bytes.com/topic/python/answers/32605-windows-xp-cron-scheduler-python

#### CSV Assets Configuration
`filename`: CSV file with assets inside

`directory`: directory with CSV files with assets inside. Note: `filename` and `directory` are mutually exclusive

##### Default Field Mappings
    No default mappings. Everything should be defined in the config


#### CSV Users Configuration
`filename`: CSV file with assets inside

`directory`: directory with CSV files with assets inside. Note: `filename` and `directory` are mutually exclusive

`default_role`: The numeric ID of the role which will be assigned to imported users. For example: `25`.

`default_position`: The position which will be assigned to the user. For example: `Employee`.


##### Default Field Mappings
    No default mapping. Everything should be defined in the config


#### Chef Configuration
The `[chef]` section contains a similar set of preferences.

The identifier section of the `config.ini` file should contain a mapping to a unique field in Oomnitza, which you want to use as the identifier for an asset.

`url`: the full url of the Chef server with organization e.g. https://chef-server/organizations/ORG/

`client`: the Chef username for authentication

`key_file`: the Chef RSA private key for authentication

`attribute_extension`: [optional] dictionary of additional node attributes to extract

`node_mappings`: [optional] dictionary of node mapping to overrides

##### List of currently supported Chef attributes
    'hardware.name'
    'hardware.ip_address'
    'hardware.mac_address'
    'hardware.hostname'
    'hardware.fqdn'
    'hardware.domain'
    'hardware.platform'
    'hardware.platform_version'
    'hardware.serial_number'
    'hardware.model'
    'hardware.total_memory_mb'
    'hardware.total_hdd_mb'
    'hardware.cpu'
    'hardware'cpu_count'
    'hardware.uptime_seconds'

##### Attribute Extension
The connector `config.ini` allows for additional node attributes to be extracted.

Example: `attribute_extension = {"__default__": {"kernel_name": "automatic.kernel.name"}}`

The above example will introduce a new mappable attribute "hardware.kernel_name". If a particular platform does not have this node attribute, it will processed as empty.

`attribute_extension = {
    "mac_os_x": {"machine_name": "automatic.machinename"},
    "windows": {"machine_name": "automatic.foo.bar"}
}`

The above example will introduce a new mappable attribute "hardware.machine_name" for mac_os_x and windows nodes only.

##### Node Mappings
The connector `config.ini` allows Chef overwriting of node lookups.

Example: `node_mappings = {"windows": {"serial_number": "normal.subsystem.hardware.serial_number"}}`

In the above example, we are overwriting where to search for `serial_number` in a Windows node.

The same can be done for Mac with `mac_os_x` and as default with `__default__`

#### Jasper Configuration
`wsdl_path`: The full URL to the Terminal.wsdl. Defaults to: http://api.jasperwireless.com/ws/schema/Terminal.wsdl.

`username`: the Jasper username to use

`password`: the Jasper password to use

`storage`: The path to the storage file used to maintain state about the connector. Defaults to: `storage.db`

`api_token`: The Jasper API Token.

##### Default Field Mappings
    No default mappings

#### LDAP Users Configuration

This is for `[ldap]` section:

`url`: The full URI for the LDAP server.

`username`: the LDAP username to use. Can be a DN, such as `cn=read-only-admin,dc=example,dc=com`.

`password`: the LDAP password to use

`base_dn`: The Base DN to use for the connection.

`group_dn`: Identifies the group to which the users we want to fetch have to belong. _The attribute is a legacy one, see the `groups_dn` attribute below_

`groups_dn`: Identifies the list of groups to which the users we want to fetch have to belong. 

_NOTE: the attributes `base_dn`, `group_dn` and `groups_dn` define the DN where to fetch the data from. 
**And these attributes have a priority**. If the `groups_dn` is defined, the data will be fetched from the mentioned groups and the `group_dn` and `base_dn` will be ignored. 
Next goes the `group_dn` attribute. The lowest priority has the `base_dn`, it will be taken into the account only if `groups_dn` and `group_dn` are empty._

`group_members_attr`: Identifies the name of the attribute in the LDAP linking the record inside the group with the group. 
Default is "member" but can vary in different LDAP systems.

`group_member_filter`: Identifies the additional optional filter used to extract the details of the user in the group. Empty by default.

`protocol_version`: The LDAP Protocol version to use. Defaults to: `3`.

`filter`: The LDAP filter to use when querying for people. For example: `(objectClass=*)` will load all objects. This is a very reasonable default.

`default_role`: The numeric ID of the role which will be assigned to imported users. For example: `25`.

`default_position`: The position which will be assigned to the user. For example: `Employee`.

##### Default Field Mappings
    mapping.USER =           {'source': "uid", 'required': True, 'converter': 'ldap_user_field'},
    mapping.FIRST_NAME =     {'source': "givenName"},
    mapping.LAST_NAME =      {'source': "sn"},
    mapping.EMAIL =          {'source': "mail", 'required': True},
    mapping.PERMISSIONS_ID = {'setting': "default_role"},


#### LDAP Assets Configuration

This is for `[ldap_assets]` section and actually contains the same set of configuration as for `[ldap]` used to fetch the user records.

`url`: The full URI for the LDAP server.

`username`: the LDAP username to use. Can be a DN, such as `cn=read-only-admin,dc=example,dc=com`.

`password`: the LDAP password to use

`base_dn`: The Base DN to use for the connection.

`group_dn`: Identifies the group to which the users we want to fetch have to belong. _The attribute is a legacy one, see the `groups_dn` attribute below_

`groups_dn`: Identifies the list of groups to which the users we want to fetch have to belong. 

_NOTE: the attributes `base_dn`, `group_dn` and `groups_dn` define the DN where to fetch the data from. 
**And these attributes have a priority**. The highest priority is for `groups_dn`, the data will be fetched from the mentioned groups and the `group_dn` and `base_dn` will be ignored. 
Next goes the `group_dn` attribute. The lowest priority has the `base_dn`, it will be taken into the account only if `groups_dn` and `group_dn` are empty._

`group_members_attr`: Identifies the name of the attribute in the LDAP linking the record inside the group with the group. 
Default is "member" but can vary in different LDAP systems.

`group_member_filter`: Identifies the additional optional filter used to extract the details of the user in the group. Empty by default.

`protocol_version`: The LDAP Protocol version to use. Defaults to: `3`.

`filter`: The LDAP filter to use when querying for people. For example: `(objectClass=*)` will load all objects. This is a very reasonable default.

##### Default Field Mappings
    No default mappings


#### MobileIron Configuration
`url`: The full URI for the MobileIron server. For example: `https://na1.mobileiron.com`

`username`: The MobileIron username to use.

`password`: The MobileIron password to use.

`partitions`: The MobileIron partitions to load. For example: `["Drivers"]` or `["PartOne", "PartTwo"]`. Used for API v1 and ignored for API v2.

`api_version`: The version of MobileIron API used to fetch the records. Available options are `1` and `2`.
The cloud instances are using v1 by default. For the CORE instances (on-premise installations) you have to use v2.

`include_checkin_devices_only`: If this is True, the MobileIron connector only processes the devices that have been checked in.

`last_checkin_date_threshold`: If the setting `include_checkin_devices_only` is True, the MobileIron connector only sends the devices that last check-in date is within the past X days. The threshold needs to be in seconds e.g. 604800 is 7 days in seconds.

##### Default Field Mappings
    No default mappings


#### Netbox Configuration
`url`: The full URI for the Netbox server.

`auth_token`: the authorization token to use.

##### Default Field Mappings
    No default mappings


#### Open-AudIT Configuration
`url`: The full URI for the Open-AudIT server. For example: `http://192.168.111.145`

`username`: The Open-AudIT username used to connect to the API.

`password`: The Open-AudIT password used to connect to the API.

##### Default Field Mappings
    No default mappings

##### List of currently supported Open-AudIT attributes
    'hardware.name'
    'hardware.ip'
    'hardware.dbus_identifier'
    'hardware.description'
    'hardware.dns_hostname'
    'hardware.domain'
    'hardware.end_of_life'
    'hardware.end_of_service'
    'hardware.environment'
    'hardware.first_seen'
    'hardware.form_factor'
    'hardware.fqdn'
    'hardware.hostname'
    'hardware.identification'
    'hardware.last_seen'
    'hardware.mac_vendor'
    'hardware.mac'
    'hardware.manufacturer'
    'hardware.memory_count'
    'hardware.model'
    'hardware.os_bit'
    'hardware.os_family'
    'hardware.os_group'
    'hardware.os_installation_date'
    'hardware.os_name'
    'hardware.os_version'
    'hardware.processor_count'
    'hardware.purchase_invoice'
    'hardware.purchase_order_number'
    'hardware.serial_imei'
    'hardware.serial_sim'
    'hardware.serial'
    'hardware.storage_count'
    'hardware.uptime_formatted'
    'hardware.uptime'
    'hardware.uuid'
    'hardware.warranty_expires'


#### SCCM Configuration
The account used to connect to the SCCM database requires at least read-only access.

`server`: The server hosting the SCCM database.

`database`: The SCCM database from which to pull data.

`username`: The username to use when connecting to the server using `SQL Server` authentication. This user
requires read-only access to the DB. Ignored when using `Windows` authentication.

`password`: The password to use when connecting to the server using `SQL Server` authentication.
Ignored when using `Windows` authentication.

`driver`: The driver name used to communicate with SCCM database. In most of the cases has to be left empty; if left empty the connector will try to use the most recent driver. 

In Windows environment there is always should be at least one legacy driver named "SQL Server". In other environments you may have to explicitly install drivers ([download drivers](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)). 

Please refer to this [page](https://github.com/mkleehammer/pyodbc/wiki/Connecting-to-SQL-Server-from-Windows) for the list of currently supported drivers.

`authentication`: Sets the type of authentication to use when connecting to the server.
Options are `SQL Server` or `Windows`. The default is to use SQL Server Authentication.
When using `Windows` authentication, the `username` and `password` fields are ignored and the credentials
for the currently logged in user will be used when making the connection to the SCCM database.


##### Default Field Mappings
    No default mappings

#### Tanium Configuration
`url`: The URL for the Tanium instance

Choose between user/password or session_token authorization:

- `username`: The username used to authorize. Please note, the account should have the "Asset Report Read" permission

- `password`: The password used to authorize.

- `session_token`: The session_token provided by the Tanium As A Service console.

`domain`: The domain of the account, used for authorization. Optional, can be empty.

`view`: The numeric ID of the view used to fetch the assets. Optional, can be empty; if empty, all the available attributes of the assets will be retrieved. 
**WARNING**: the view usage may limit the set of attributes fetched from Tanium system and not all the attributes visible on the Web UI mapping will be actually available. 
If these not available attributes will be mapped on UI, null values will be pushed to Oomnitza.


##### Default Field Mappings
    No default mappings


#### vCenter Configuration
`url`: The API host. For example: `https://{api_host}`

`username`: The username used to create a session to make vCenter REST API requests. 

`password`: The password used to create a session to make vCenter REST API requests. <br>

`use_legacy_apis`: Defaulted to True to use apis up to and including v7.0 U2. If False, support has been
 added for new apis after v7.0 U2 (up to version v8.0 U1)


##### Default Field Mappings
    No default mappings


#### WorkspaceOne Configuration
`client_id`: The WorkspaceOne Client ID, used to fetch access token.

`client_secret`: The WorkspaceOne Client Secret, used to fetch access token.

`region`: The WorkspaceOne region. ie. na, apac, emer or uat

`url`:  The url of the WorkspaceOne including https:// and top level domain (.com, .ie, etc)

`apps_scope`:  The Scope of the WorkspaceOne API calls. Default to **all**

    Acceptable values are: managed, device or all
        managed: Only sync managed apps from Workspace one.
        installed: Only sync device apps from Workspace one.
        all: Sync both managed and device apps from Workspace one.

`ignore_apple`:  Ignore Apple software that starts with com.apple.* Defaulted to False<br>
(False = do not ignore)

`default_versioning`:  If Software is found with no version, we default the version to _0.0_. Default to False<br>
(False = do not sync software with no version)


##### Default Field Mappings
    No default mappings

#### Munki Report Configuration
`url`: The Munki Report Url, used to fetch csrf token and assets.

`username`: The Munki Report Username, used to login.

`password`: The Munki Report password, used to login.

`db_columns`:  The Munki Report DB column names in a list. Example ["machine.serial_number", "machine.hostname"]


##### Default Field Mappings
    List default mapped Munki Report Database Columns.
    [
        "machine.serial_number",
        "machine.hostname",
        "machine.machine_desc",
        "reportdata.timestamp",
        "reportdata.console_user",
        "machine.os_version",
        "reportdata.remote_ip",
        "munkireport.manifestname"
    ]

#### Insight Configuration

This configuration provides the ability to retrieve the status of orders. You can filter by date range and tracking data. 

`client_id`: The Insight Client ID.

`client_key`: The Insight Client Key.

`client_secret`: The Insight Client Secret.

`order_creation_date_from`: Specify the order creation from date in the format YYYY-MM-DD

`order_creation_date_to`:  Specify the order creation to date in the format YYYY-MM-DD

`tracking_data`:  Include any tracking data for the order (Defaults to "X" if no specific tracking data is available)

#### Dell Configuration

This configuration provides the ability to retrieve Dell order status information for all order types. You need to provide the order numbers, DPIDs, or PO numbers associated with the order you wish to track.

`client_id`: The Dell Client ID.

`client_secret`: The Dell Client Secret.

`is_dp_id`: Set to True to input DPIDs.

`is_po_numbers`:  Set to True to input PO Numbers.

`is_order_no_country_code`: Set to True to input Order Numbers and country code.

`values`:  Enter the PO Numbers, DPIDs, or Order Numbers you want to retrieve using the format ["PO123", "PO432"].

`country_code`:  If you choose to input Order Numbers, include an ISO two-digit country code using the format ["GB", "FR", "IN"]. For a list of approved country codes, see [Dell Order Status Pull_API](https://developer.dell.com/apis/9208/versions/2/apiV2.json) 

## Advanced usage

### Logging
The Oomnitza Connector uses the standard python `logging` module. This modules is configured via the `logging.json` file.
 This file can be edited, or copied to a new file, to change the logging behavior of the connector. Please see the
 [python docs](https://docs.python.org/3/library/logging.html) for information of configuring python logging.

### Custom Converters
It is possible to create a completely custom complex converter that will be used to convert values extracted from external system to before pushing them to the Oomnitza.
 To use this option you have to define the name of this converter in the mapping, like this
    
    mapping.MY_AWESOME_FIELD =  {"source": "name", "converter": "my_custom_converter"}
 
 next you have to define new `[converters]` section in the config with the `my_custom_converter:`. Under this converter name you have to define a valid Python 3.12 function,
 that has to return some value - this value is a result of the converter. In the converter function a "record" object is available, it is the whole record extracted from external system as Python [dict](https://docs.python.org/2/library/stdtypes.html#dict) object.
 Example:

    [ldap]
    
    ... here goes config ... 
    
    mapping.POSITION = {"source": "position", "converter": "my_custom_converter"}
    
    [converters]
    my_custom_converter:
        return record.get("position", "Unknown position")
 If an exception is raised inside the custom converter's code, a None value is returned as the result

### Record Filtering
Support has been added for filtering the records passed from the connector to Oomnitza. By default, all records from the
 remote system will be sent to Oomnitza for processing. To limit the records based on values in those records, a special
 `recordfilter` value can be added to a connector section in the ini file. This filter is written using the Python
 programming language.

For example, the following filter will only  process records with the `asset_type` field set to "`computer`":

    recordfilter:
        return record.asset_type == "computer"

This is a very new feature, with many options, and we are still working on the documentation. If you are interested in
 using this feature, please contact [support@oomnitza.com](mailto://support@oomnitza.com) for assistance.


## Current limitations

### Software mapping
There is no possibility to set the mapping for the software info associated with IT assets (SCCM, JAMF). The only thing can be done is to disable the mapping at all. 
To do this set the following custom mapping in your `config.ini` file:

    mapping.APPLICATIONS = {"hardcoded": []}

### MS Windows environment
In MS Windows environment the "Task Scheduler" is the natural tool to schedule the connector execution. Please note that in different version of Windows there can be different ways to specify the
 "working directory" of connector executable. One of the reliable way to solve this is to also set the path to the configuration files via the command line arguments.
