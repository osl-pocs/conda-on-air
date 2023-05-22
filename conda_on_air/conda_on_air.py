"""Main module."""
from pathlib import Path
import tempfile

import sh
import yaml


class CondaOnAirSpec:
    spec: dict = {
        '1.0.0': {
            'name': {
                'help': (
                    'The conda environment name to be used. '
                    'You can use `--name` to override that.'
                ),
                'required': True,
                'type': 'string',
            },
            'packages': {
                'help': (
                    'A dictionary with the packages that will be'
                    'built and installed.'
                ),
                'type': 'dict',
                'required': True,
                '__items__': {
                    '__key__': 'name',
                    '__value__': {
                        'url': {
                            'help': 'The URL to the feedstock repository.',
                            'required': True,
                            'type': 'string',
                        },
                        'rev': {
                            'help': (
                                'The revision tag or commit ID for the given '
                                'repository.'
                            ),
                            'required': 'True',
                            'type': 'string',
                        },
                        'version': {
                            'help': 'The package version.',
                            'required': True,  # maybe it could be optional
                            'type': 'string',
                        },
                    },
                },
            },
        }
    }


class CondaOnAir(CondaOnAirSpec):
    config_path: Path = Path('./.conda-on-air.yaml')
    config_data: dict = {}

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config_data = self.read_config(config_path)
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="condaonair_"))

    def verify_config(self, config_data):
        if not config_data.get("version"):
            raise Exception("Version spec not found.")
        if not self.spec.get(config_data.get("version")):
            raise Exception(
                "The version defined in the configuration file is not valid."
            )
        # TODO: check if the config_data is correct according to the specs
        return True

    def read_config(self, config_path: Path):
        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        if self.verify_config(config_data):
            return config_data

        return {}

    def clone(self):
        env_name = self.config_data.get("name")
        patches_path = Path(self.config_data.get("path")) / "patches"
        pkgs = self.config_data.get("packages")

        for pkg_name, pkg_data in pkgs.items():
            url = pkg_data.get("url")
            rev = pkg_data.get("rev")
            version = pkg_data.get("version")
            pkg_dir_path = str(self.tmp_dir / pkg_name)

            sh.rm("-rf", pkg_dir_path)
            sh.git("clone", url, pkg_dir_path)

            with sh.pushd(pkg_dir_path):
                sh.git("checkout", rev)

    def build(self):
        env_name = self.config_data.get("name")
        patches_path = Path(self.config_data.get("path")) / "patches"
        pkgs = self.config_data.get("packages")

        for pkg_name, pkg_data in pkgs.items():
            pkg_dir_path = str(self.tmp_dir / pkg_name)

            with sh.pushd(pkg_dir_path):
                sh.git("conda", "build")

    def install(self):
        ...

    def remove_tmp_dir(self):
        # sh.rm("-rf", str(self.tmp_dir))
        ...

    def teardown(self):
        self.remove_tmp_dir()

    def run(self):
        self.clone()
        self.build()
        self.install()
        self.teardown()
