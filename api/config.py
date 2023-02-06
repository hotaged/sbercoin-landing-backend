import os
from dynaconf import Dynaconf

print(os.getcwd())

settings = Dynaconf(
    envvar_prefix="SCL",  # envvar_prefix = "SBERCOIN_LANDING"\
    settings_files=['settings.toml', '.secrets.toml'],
)

print(settings.winpay)
print(settings.__dict__)
