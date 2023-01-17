
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="SCL",  # envvar_prefix = "SBERCOIN_LANDING"
    settings_files=['settings.toml', '.secrets.toml'],
)
