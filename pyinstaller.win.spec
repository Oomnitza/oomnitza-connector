# -*- mode: python -*-
a = Analysis(['./oomnitza-connector-master/connector.py'],
             pathex=None,
             hiddenimports=['connectors.airwatch', 'connectors.bamboohr', 'connectors.casper',
                            'connectors.jasper', 'connectors.ldap', 'connectors.mobileiron',
                            'connectors.okta', 'connectors.onelogin', 'connectors.zendesk',
                            'connectors.sccm', 'connectors.oomnitza',
                            'converters.casper_extension_attribute',
                            'converters.date_format',
                            'converters.first_from_full',
                            'converters.last_from_full',
                            'converters.ldap_user_field',
                            'converters.mac_model_from_sn',
                            'converters.split',
                            'converters.split_email',
                            'converters.uber_position',
                            'xmltodict',
			    'ctypes.wintypes',
			    'pyodbc'],
             hookspath=['./oomnitza-connector-master/connectors', './oomnitza-connector-master/converters'],
             runtime_hooks=None)

for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break

a.datas += [('connectors/airwatch.py', './oomnitza-connector-master/connectors/airwatch.py', 'DATA')]
a.datas += [('connectors/bamboohr.py', './oomnitza-connector-master/connectors/bamboohr.py', 'DATA')]
a.datas += [('connectors/casper.py', './oomnitza-connector-master/connectors/casper.py', 'DATA')]
a.datas += [('connectors/jasper.py', './oomnitza-connector-master/connectors/jasper.py', 'DATA')]
a.datas += [('connectors/ldap.py', './oomnitza-connector-master/connectors/ldap.py', 'DATA')]
a.datas += [('connectors/mobileiron.py', './oomnitza-connector-master/connectors/mobileiron.py', 'DATA')]
a.datas += [('connectors/okta.py', './oomnitza-connector-master/connectors/okta.py', 'DATA')]
a.datas += [('connectors/onelogin.py', './oomnitza-connector-master/connectors/onelogin.py', 'DATA')]
a.datas += [('connectors/zendesk.py', './oomnitza-connector-master/connectors/zendesk.py', 'DATA')]
a.datas += [('connectors/sccm.py', './oomnitza-connector-master/connectors/sccm.py', 'DATA')]
a.datas += [('connectors/oomnitza.py', './oomnitza-connector-master/connectors/oomnitza.py', 'DATA')]
a.datas += [('connector_gui/styles/darwin.json', './oomnitza-connector-master/connector_gui/styles/darwin.json', 'DATA')]
a.datas += [('connector_gui/styles/windows.json', './oomnitza-connector-master/connector_gui/styles/windows.json', 'DATA')]
a.datas += [('connector_gui/styles/metadata.json', './oomnitza-connector-master/connector_gui/styles/metadata.json', 'DATA')]
a.datas += [('connector_gui/images/collapsed.png', './oomnitza-connector-master/connector_gui/images/collapsed.png', 'DATA')]
a.datas += [('connector_gui/images/disabled.png', './oomnitza-connector-master/connector_gui/images/disabled.png', 'DATA')]
a.datas += [('connector_gui/images/enabled.png', './oomnitza-connector-master/connector_gui/images/enabled.png', 'DATA')]
a.datas += [('connector_gui/images/oomnitza_logo.png', './oomnitza-connector-master/connector_gui/images/oomnitza_logo.png', 'DATA')]
a.datas += [('connector_gui/images/scheduled.png', './oomnitza-connector-master/connector_gui/images/scheduled.png', 'DATA')]
a.datas += [('connector_gui/images/expanded.png', './oomnitza-connector-master/connector_gui/images/expanded.png', 'DATA')]
a.datas += [('connector_gui/images/connector.ico', './oomnitza-connector-master/connector_gui/images/connector.ico', 'DATA')]
a.datas += [('cacert.pem', 'C:/Python27/lib/site-packages/certifi/cacert.pem', 'DATA')]
a.datas += [('logging.json', './oomnitza-connector-master/logging.json', 'DATA')]
a.datas += [('connector_gui/templates/task_scheduler.xml', './oomnitza-connector-master/connector_gui/templates/task_scheduler.xml', 'DATA')]

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='connector.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False,
          icon='./oomnitza-connector-master/connector_gui/images/connector.ico' )



