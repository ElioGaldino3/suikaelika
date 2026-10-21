"""python-for-android recipe for the Pymunk version used by Suika Elika."""

import sh
from pythonforandroid.logger import shprint
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class PymunkRecipe(CompiledComponentsPythonRecipe):
    """Cross-compile Pymunk and its Chipmunk CFFI extension for Android."""

    name = "pymunk"
    version = "7.3.1"
    url = "https://files.pythonhosted.org/packages/source/p/pymunk/pymunk-{version}.tar.gz"
    depends = ["cffi", "setuptools"]
    hostpython_prerequisites = ["cffi==2.0.0"]
    call_hostpython_via_targetpython = False

    def get_recipe_env(self, arch):
        environment = super().get_recipe_env(arch)
        environment["LDFLAGS"] += " -llog -lm"
        return environment

    def install_python_package(self, arch):
        environment = self.get_recipe_env(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            shprint(
                sh.Command(self.hostpython_location),
                "setup.py",
                "install",
                "--install-lib",
                self.ctx.get_python_install_dir(arch.arch),
                "--skip-build",
                "--force",
                _env=environment,
            )


recipe = PymunkRecipe()
