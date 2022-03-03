"""Deploy the evaluation_system / core."""
import argparse
from configparser import ConfigParser, ExtendedInterpolation
import logging
import hashlib
import os
from os import path as osp
from pathlib import Path
import re
import shlex
import sys
from subprocess import CalledProcessError, PIPE, run
import urllib.request
from tempfile import TemporaryDirectory


MINICONDA_URL = "https://repo.anaconda.com/miniconda/"
ANACONDA_URL = "https://repo.anaconda.com/archive/"
CONDA_PREFIX = os.environ.get("CONDA", "Anaconda3-2021.11")
CONDA_VERSION = "{conda_prefix}-{arch}.sh"

logging.basicConfig(format="%(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__file__)

MODULE = """#%Module1.0#####################################################################
##
## FREVA - Free Evaluation System Framework modulefile
##
#
### BEGIN of config part ********
#define some variables
set shell [module-info shell]
set modName [module-info name]
set toolName evaluation_system
set curMode [module-info mode]
module-whatis   "evaluation_system {version}"
proc ModulesHelp {{ }} {{
    puts stderr "Load the free evaluation system framework {project}"
}}
if {{ $curMode eq "load" }} {{
    if {{ $shell == "fish" }} {{
        puts "{fish}"
    }} elseif {{ $shell == "csh" }} {{
        puts "{csh}"
    }} elseif {{ $shell == "tcsh" }} {{
        puts "{tcsh}"
    }} elseif {{ $shell == "zsh" }} {{
        puts "{zsh}"
    }} elseif {{ $shell == "bash" }} {{
        puts "{bash}"
    }} else {{
        puts "{sh}"
    }}
}}
prepend-path PATH {root_dir}/bin
setenv EVALUATION_SYSTEM_CONFIG_FILE {eval_conf_file}
"""


def get_activate_string(shell, root_dir):
    """Get the activate command for a given shell."""
    try:
        return dict(
            fish=(
                f"\\. {root_dir}/etc/fish/conf.d/conda.fish && "
                f"\\. {root_dir}/share/fish/completions/freva.fish"
            ),
            tcsh=(
                f"\\. {root_dir}/etc/profile.d/conda.csh && "
                f"\\. {root_dir}/share/tcsh-completion/completion/freva"
            ),
            csh=(f"\\. {root_dir}/etc/profile.d/conda.csh"),
            zsh=(
                f"\\. {root_dir}/etc/profile.d/conda.sh && "
                f"\\. {root_dir}/share/zsh/site-functions/source.zsh"
            ),
            bash=(
                f"\\. {root_dir}/etc/profile.d/conda.sh && "
                f"\\. {root_dir}/share/bash-completion/completions/freva"
            ),
        )[shell]
    except KeyError:
        return f"\\. {root_dir}/etc/profile.d/conda.sh"


def get_script_path():
    return osp.dirname(osp.realpath(sys.argv[0]))


def read(*parts):
    return open(osp.join(get_script_path(), *parts)).read()


def find_files(path, glob_pattern="*"):
    return [str(f) for f in Path(path).rglob(glob_pattern)]


def find_version(*parts):
    vers_file = read(*parts)
    match = re.search(r'^__version__ = "(\d+.\d+)"', vers_file, re.M)
    if match is not None:
        return match.group(1)
    raise RuntimeError("Unable to find version string.")


def reporthook(count, block_size, total_size):
    if count == 0:
        return
    frac = count * block_size / total_size
    percent = int(100 * frac)
    bar = "#" * int(frac * 40)
    msg = "Downloading: [{0:<{1}}] | {2}% Completed".format(bar, 40, round(percent, 2))
    print(msg, end="\r", flush=True)
    if frac >= 1:
        print()


def parse_args(argv=None):
    """Consturct command line argument parser."""

    ap = argparse.ArgumentParser(
        prog="deploy_freva",
        description="""This Programm installs the evaluation_system package.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument(
        "install_prefix", type=Path, help="Install prefix for the environment."
    )
    ap.add_argument(
        "--packages",
        type=str,
        nargs="*",
        help="Pacakges that are installed",
        default=Installer.default_pkgs,
    )
    ap.add_argument(
        "--channel", type=str, default="conda-forge", help="Conda channel to be used"
    )
    ap.add_argument("--shell", type=str, default="bash", help="Shell type")
    ap.add_argument(
        "--arch",
        type=str,
        default="Linux-x86_64",
        choices=[
            "Linux-aarch64",
            "Linux-ppc64le",
            "Linux-s390x",
            "Linux-x86_64",
            "MacOSX-x86_64",
        ],
        help="Choose the architecture according to the system",
    )
    ap.add_argument("--python", type=str, default="3.9", help="Python Version")
    ap.add_argument(
        "--pip",
        type=str,
        nargs="*",
        default=Installer.pip_pkgs,
        help="Additional packages that should be installed using pip",
    )
    ap.add_argument(
        "--develop",
        action="store_true",
        default=False,
        help="Use the develop flag when installing the evaluation_system package",
    )
    ap.add_argument(
        "--no_conda",
        "--no-conda",
        action="store_true",
        default=False,
        help="Do not create conda environment",
    )
    ap.add_argument(
        "--run_tests",
        action="store_true",
        default=False,
        help="Run unittests after installation",
    )
    ap.add_argument(
        "--silent",
        "-s",
        action="store_true",
        default=False,
        help="Minimize writing to stdout",
    )
    args = ap.parse_args()
    return args


class Installer:

    default_pkgs = sorted(
        [
            "cdo",
            "conda",
            "configparser",
            "distributed",
            "django",
            "ffmpeg",
            "git",
            "gitpython",
            "dask",
            "ipython",
            "imagemagick",
            "libnetcdf",
            "humanize",
            "mamba",
            "mysqlclient",
            "nco",
            "netcdf4",
            "numpy",
            "pandas",
            "pip",
            "pillow",
            "pymysql",
            "pypdf2",
            "pytest",
            "pytest-env",
            "cartopy",
            "pytest-cov",
            "pytest-html",
            "python-cdo",
            "xarray",
            "pandoc",
            "pint",
        ]
    )
    pip_pkgs = sorted(["pytest-html", "python-git", "python-swiftclient"])

    @property
    def conda_name(self):

        return self.install_prefix.name

    def run_cmd(self, cmd, **kwargs):
        """Run a given command."""
        verbose = kwargs.pop("verbose", False)
        kwargs["check"] = False
        if self.silent and not verbose:
            kwargs["stdout"] = PIPE
            kwargs["stderr"] = PIPE
        res = run(shlex.split(cmd), **kwargs)
        if res.returncode != 0:
            try:
                print(res.stderr.decode())
            except AttributeError:
                # stderr wasn't piped
                pass
            raise CalledProcessError(res.returncode, cmd)

    def create_conda(self):
        """Create the conda environment."""
        with TemporaryDirectory(prefix="conda") as td:
            conda_script = Path(td) / "anaconda.sh"
            tmp_env = Path(td) / "env"
            logger.info(f"Downloading {CONDA_PREFIX} script")
            kwargs = {"filename": str(conda_script)}
            if self.silent is False:
                kwargs["reporthook"] = reporthook
            urllib.request.urlretrieve(
                self.conda_url
                + CONDA_VERSION.format(arch=self.arch, conda_prefix=CONDA_PREFIX),
                **kwargs,
            )
            self.check_hash(conda_script)
            conda_script.touch(0o755)
            cmd = f"{self.shell} {conda_script} -p {tmp_env} -b -f"
            logger.info(f"Installing {CONDA_PREFIX}:\n{cmd}")
            self.run_cmd(cmd)
            cmd = (
                f"{tmp_env / 'bin' / 'conda'} create -c {self.channel} "
                f"-q -p {self.install_prefix} python={self.python} "
                f"{' '.join(self.packages)} -y"
            )
            logger.info(f"Creating conda environment:\n{cmd}")
            self.run_cmd(cmd)

    def check_hash(self, filename):
        archive = urllib.request.urlopen(self.conda_url).read().decode()
        md5sum = ""
        for line in archive.split("</tr>"):
            if CONDA_VERSION.format(arch=self.arch, conda_prefix=CONDA_PREFIX) in line:
                md5sum = line.split("<td>")[-1].strip().strip("</td>")
        md5_hash = hashlib.md5()
        with filename.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
        if md5_hash.hexdigest() != md5sum:
            raise ValueError("Download failed, md5sum mismatch: {md5sum} ")

    def pip_install(self):
        """Install additional packages using pip."""

        cmd = f"{self.python_prefix} -m pip install .[test]"
        logger.info(f"Installing additional packages\n{cmd}")
        self.run_cmd(cmd)
        pip_opts = ""
        if self.develop:
            pip_opts = "-e"
        cmd = f"{self.python_prefix} -m pip install {pip_opts} ."
        logger.info("Installing evaluation_system packages")
        self.run_cmd(cmd)

    def __init__(
        self,
        install_prefix,
        no_conda=False,
        packages=["conda"],
        channel="conda-forge",
        shell="bash",
        arch="Linux-x86_64",
        python="3.10",
        pip=[],
        develop=False,
        run_tests=False,
        silent=False,
    ):
        self.run_tests = run_tests
        self.install_prefix: Path = Path(install_prefix).expanduser().absolute()
        self.packages = set(packages + ["conda"])
        self.channel = channel
        self.arch = arch
        self.python = python
        self.pip = pip
        self.silent = silent
        self.shell = shell
        self.develop = develop
        if self.silent:
            logger.setLevel(logging.ERROR)
        self.conda_url = ANACONDA_URL
        if "miniconda" in CONDA_PREFIX.lower():
            self.conda_url = MINICONDA_URL
        self.conda = no_conda is False

    def create_loadscript(self):
        """Create the load-script for this installation."""

        config_parser = ConfigParser(interpolation=ExtendedInterpolation())
        eval_conf_file = Path(
            os.environ.get(
                "EVALUATION_SYSTEM_CONFIG_FILE",
                self.install_prefix / "freva" / "evaluation_system.conf",
            )
        )
        for key in (
            "preview_path",
            "project_data",
            "base_dir_location",
            "scheduler_output_dir",
        ):
            with eval_conf_file.open("r") as fp:
                config_parser.read_file(fp)
                path = Path(config_parser["evaluation_system"][key])
                if path:
                    try:
                        path.mkdir(exist_ok=True, parents=True)
                    except PermissionError:
                        pass
        eval_conf_file.parent.mkdir(parents=True, exist_ok=True)
        module_format = dict(
            version=find_version("src/evaluation_system", "__init__.py"),
            root_dir=self.install_prefix,
            eval_conf_file=eval_conf_file,
            project=config_parser["evaluation_system"]["project_name"],
        )
        for shell in ("zsh", "fish", "csh", "tcsh", "sh", "bash", "ksh"):
            if shell != "ksh":
                module_format[shell] = get_activate_string(shell, self.install_prefix)
            if shell in ("csh", "tcsh"):
                set_env = (
                    f"setenv PATH $PATH\\:{self.install_prefix / 'bin'}\n"
                    f"setenv EVALUATION_SYSTEM_CONFIG_FILE {eval_conf_file}"
                )
            else:
                set_env = (
                    f"export PATH=$PATH:{self.install_prefix / 'bin'}\n"
                    f"export EVALUATION_SYSTEM_CONFIG_FILE={eval_conf_file}"
                )
            with (eval_conf_file.parent / f"activate_{shell}").open("w") as f:
                f.write(get_activate_string(shell, self.install_prefix))
                f.write(f"\n{set_env}")

        with (eval_conf_file.parent / "loadfreva.modules").open("w") as f:
            f.write(MODULE.format(**module_format))

    def unittests(self):
        """Run unittests."""
        logger.info("Running unittests:")
        env = os.environ.copy()
        env["PATH"] = f'{self.install_prefix / "bin"}:{env["PATH"]}'
        env["FREVA_ENV"] = str(self.install_prefix / "bin")
        self.run_cmd("make test", verbose=True, env=env)

    @property
    def python_prefix(self):
        """Get the path of the new conda evnironment."""
        return self.install_prefix / "bin" / "python3"


if __name__ == "__main__":
    args = parse_args(sys.argv)
    Inst = Installer(
        install_prefix=args.install_prefix,
        no_conda=args.no_conda,
        packages=args.packages,
        channel=args.channel,
        shell=args.shell,
        arch=args.arch,
        python=args.python,
        pip=args.pip,
        develop=args.develop,
        run_tests=args.run_tests,
        silent=args.silent,
    )
    if Inst.conda:
        Inst.create_conda()
        Inst.pip_install()
    Inst.create_loadscript()
    if Inst.run_tests:
        Inst.unittests()
