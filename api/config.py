from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="SCL",
    settings_files=['settings.toml', '.secrets.toml'],
)
