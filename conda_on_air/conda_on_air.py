"""Main module."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import sh
import yaml
from colorama import Fore

from conda_on_air.errors import CondaOnAirError


class PrintPlugin:
    def _print_error(self, message: str):
        print(Fore.RED, message, Fore.RESET, file=sys.stderr)

    def _print_info(self, message: str):
        print(Fore.BLUE, message, Fore.RESET, file=sys.stdout)

    def _print_warning(self, message: str):
        print(Fore.YELLOW, message, Fore.RESET, file=sys.stdout)


class CondaOnAirSpec:
    spec: dict = {
        '1.0': {
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
                        'patches': {
                            'help': (
                                'A list of patches to apply to the original '
                                'feedstock files.'
                            ),
                            'required': False,
                            'type': 'list',
                            '__items__': {
                                '__value__': {
                                    'help': 'A list of patches files.',
                                    'type': 'class',
                                    '__value__': {
                                        'original-file': {
                                            'help': (
                                                'The path to the original file'
                                            ),
                                            'type': 'string',
                                            'required': True,
                                        },
                                        'patch-file': {
                                            'help': (
                                                'The path to the patch file'
                                            ),
                                            'type': 'string',
                                            'required': True,
                                        },
                                    },
                                }
                            },
                        },
                    },
                },
            },
        }
    }


class CondaOnAir(CondaOnAirSpec, PrintPlugin):
    config_path: Path = Path('./.conda-on-air.yaml')
    config_data: dict = {}

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config_data = self.read_config(config_path)
        self.tmp_dir = Path(tempfile.mkdtemp(prefix='condaonair_'))

        use_mamba_install = self.check_tool_exist('mamba')
        use_mamba_build = use_mamba_install and self.check_tool_exist('boa')
        self.conda_app = 'mamba' if use_mamba_install else 'conda'
        self.conda_build_app = (
            'conda mambabuild' if use_mamba_build else 'conda build'
        )

    def check_tool_exist(self, name: str):
        """Check whether `name` is on PATH and marked as executable."""
        return shutil.which(name) is not None

    def shell_app(self, *args):
        sh_args = dict(
            _in=sys.stdin,
            _out=sys.stdout,
            _err=sys.stderr,
            _bg=True,
            _bg_exc=False,
            _no_err=True,
            _env=os.environ,
            _new_session=True,
        )
        cmd_list = list(args)
        exe = cmd_list.pop(0)
        p = getattr(sh, exe)(*cmd_list, **sh_args)

        try:
            p.wait()
        except sh.ErrorReturnCode as e:
            self._print_error(str(e))
            os._exit(CondaOnAirError.SH_ERROR_RETURN_CODE.value)
        except KeyboardInterrupt:
            pid = p.pid
            p.kill_group()
            self._print_error(f'[EE] Process {pid} killed.')
            os._exit(CondaOnAirError.SH_KEYBOARD_INTERRUPT.value)

    def verify_config(self, config_data):
        if not config_data.get('version'):
            raise Exception('Version spec not found.')
        if not self.spec.get(config_data.get('version')):
            raise Exception(
                'The version defined in the configuration file is not valid.'
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
        pkgs = self.config_data.get('packages')

        for pkg_name, pkg_data in pkgs.items():
            url = pkg_data.get('url')
            rev = pkg_data.get('rev')
            pkg_dir_path = str(self.tmp_dir / pkg_name)

            self.shell_app('rm', '-rf', pkg_dir_path)
            self.shell_app(
                'git',
                'clone',
                url,
                pkg_dir_path,
            )

            with sh.pushd(pkg_dir_path):
                self.shell_app(
                    'git',
                    'checkout',
                    rev,
                )

    def _apply_patch(self, name: str, patches: list):
        for patch in patches:
            original_file = str(
                self.tmp_dir / name / patch.get('original-file')
            )
            patch_file = str(Path(patch.get('patch-file')).resolve())

            assert original_file
            assert patch_file

            self.shell_app('patch', original_file, '-i', patch_file)

    def build(self):
        pkgs = self.config_data.get('packages')

        for pkg_name, pkg_data in pkgs.items():
            pkg_dir_path = str(self.tmp_dir / pkg_name)

            self._apply_patch(pkg_name, pkg_data.get('patches', list()))

            with sh.pushd(pkg_dir_path):
                self.shell_app(
                    *self.conda_build_app.split(' '),
                    '.',
                )

    def install(self):
        env_name = self.config_data.get('name')
        pkgs = self.config_data.get('packages')

        extra_args = []
        if os.getenv('CONDA_DEFAULT_ENV') == 'base':
            extra_args.extend(['--name', env_name])

        for pkg_name, pkg_data in pkgs.items():
            self.shell_app(
                self.conda_app, 'install', '--use-local', '-y', pkg_name
            )

    def remove_tmp_dir(self):
        # self.shell_app('rm', '-rf', str(self.tmp_dir))
        ...

    def teardown(self):
        self.remove_tmp_dir()

    def run(self):
        self.clone()
        self.build()
        self.install()
        self.teardown()
