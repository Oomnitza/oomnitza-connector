# -*- mode: python -*-
import certifi
a = Analysis(['./connector.py'],
             pathex=None,
             hiddenimports=['connectors.airwatch', 'connectors.bamboohr', 'connectors.casper',
                            'connectors.jasper', 'connectors.ldap', 'connectors.mobileiron',
                            'connectors.okta', 'connectors.onelogin', 'connectors.zendesk',
                            'connectors.oomnitza',
                            'converters.casper_extension_attribute',
                            'converters.date_format',
                            'converters.first_from_full',
                            'converters.last_from_full',
                            'converters.ldap_user_field',
                            'converters.mac_model_from_sn',
                            'converters.split',
                            'converters.split_email',
                            'converters.uber_position',
                            'xmltodict'],
             hookspath=['./connectors', './converters'],
             runtime_hooks=None)

a.datas += [('connectors/airwatch.py', './connectors/airwatch.py', 'DATA')]
a.datas += [('connectors/bamboohr.py', './connectors/bamboohr.py', 'DATA')]
a.datas += [('connectors/casper.py', './connectors/casper.py', 'DATA')]
a.datas += [('connectors/jasper.py', './connectors/jasper.py', 'DATA')]
a.datas += [('connectors/ldap.py', './connectors/ldap.py', 'DATA')]
a.datas += [('connectors/mobileiron.py', './connectors/mobileiron.py', 'DATA')]
a.datas += [('connectors/okta.py', './connectors/okta.py', 'DATA')]
a.datas += [('connectors/onelogin.py', './connectors/onelogin.py', 'DATA')]
a.datas += [('connectors/zendesk.py', './connectors/zendesk.py', 'DATA')]
a.datas += [('connectors/oomnitza.py', './connectors/oomnitza.py', 'DATA')]
a.datas += [('connector_gui/styles/darwin.json', './connector_gui/styles/darwin.json', 'DATA')]
a.datas += [('connector_gui/styles/windows.json', './connector_gui/styles/windows.json', 'DATA')]
a.datas += [('connector_gui/styles/metadata.json', './connector_gui/styles/metadata.json', 'DATA')]
a.datas += [('connector_gui/images/collapsed.png', './connector_gui/images/collapsed.png', 'DATA')]
a.datas += [('connector_gui/images/disabled.png', './connector_gui/images/disabled.png', 'DATA')]
a.datas += [('connector_gui/images/enabled.png', './connector_gui/images/enabled.png', 'DATA')]
a.datas += [('connector_gui/images/oomnitza_logo.png', './connector_gui/images/oomnitza_logo.png', 'DATA')]
a.datas += [('connector_gui/images/scheduled.png', './connector_gui/images/scheduled.png', 'DATA')]
a.datas += [('connector_gui/images/expanded.png', './connector_gui/images/expanded.png', 'DATA')]
a.datas += [('connector_gui/images/connector.ico', './connector_gui/images/connector.ico', 'DATA')]
a.datas += [('cacert.pem', certifi.where(), 'DATA')]
a.datas += [('logging.json', './logging.json', 'DATA')]
a.datas += [('connector_gui/templates/task_scheduler.xml', './connector_gui/templates/task_scheduler.xml', 'DATA')]

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='connector',
          debug=False,
          strip=None,
          upx=True,
          console=False)
app = BUNDLE(exe,
             name='connector.app',
             icon='./connector_gui/images/connector.icns')
