"""python-for-android recipe for the project's Pygame CE runtime."""

from os import pathsep
from os.path import join

import sh
from pythonforandroid.logger import shprint
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class PygameCERecipe(CompiledComponentsPythonRecipe):
    """Build Pygame CE against python-for-android's SDL2 libraries."""

    name = "pygame-ce"
    version = "2.5.8"
    url = "https://github.com/pygame-community/pygame-ce/archive/{version}.tar.gz"
    site_packages_name = "pygame-ce"
    depends = [
        "sdl2",
        "sdl2_image",
        "sdl2_mixer",
        "sdl2_ttf",
        "setuptools",
        "jpeg",
        "png",
    ]
    call_hostpython_via_targetpython = False
    install_in_hostpython = False
    hostpython_prerequisites = ["Cython==3.3.0"]

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            setup_template = open("buildconfig/Setup.Android.SDL2.in").read()
            environment = self.get_recipe_env(arch)
            environment["ANDROID_ROOT"] = join(self.ctx.ndk.sysroot, "usr")

            png = self.get_recipe("png", self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), ".libs")
            png_include_dir = png.get_build_dir(arch)
            jpeg = self.get_recipe("jpeg", self.ctx)
            jpeg_include_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            image_recipe = self.get_recipe("sdl2_image", self.ctx)
            image_includes = "".join(
                f"-I{path} " for path in image_recipe.get_include_dirs(arch)
            )
            mixer_recipe = self.get_recipe("sdl2_mixer", self.ctx)
            mixer_includes = "".join(
                f"-I{path} " for path in mixer_recipe.get_include_dirs(arch)
            )
            setup = setup_template.format(
                sdl_includes=(
                    " -I"
                    + join(self.ctx.bootstrap.build_dir, "jni", "SDL", "include")
                    + " -L"
                    + join(self.ctx.bootstrap.build_dir, "libs", str(arch))
                    + f" -L{png_lib_dir} -L{jpeg_lib_dir}"
                    + f" -L{arch.ndk_lib_dir_versioned}"
                ),
                sdl_ttf_includes="-I"
                + join(self.ctx.bootstrap.build_dir, "jni", "SDL2_ttf"),
                sdl_image_includes=image_includes,
                sdl_mixer_includes=mixer_includes,
                jpeg_includes="-I" + jpeg_include_dir,
                png_includes="-I" + png_include_dir,
                freetype_includes="",
            )
            with open("Setup", "w") as setup_file:
                setup_file.write(setup)

    def get_recipe_env(self, arch):
        environment = super().get_recipe_env(arch)
        source_dir = self.get_build_dir(arch.arch)
        environment["PYTHONPATH"] = source_dir + pathsep + environment.get(
            "PYTHONPATH", ""
        )
        environment["USE_SDL2"] = "1"
        environment["PYGAME_CROSS_COMPILE"] = "TRUE"
        environment["PYGAME_ANDROID"] = "TRUE"
        return environment

    def install_python_package(self, arch):
        environment = self.get_recipe_env(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            hostpython = sh.Command(self.hostpython_location)
            shprint(hostpython, "setup.py", "build_py", _env=environment)
            shprint(
                hostpython,
                "setup.py",
                "install",
                "--install-lib",
                self.ctx.get_python_install_dir(arch.arch),
                "--skip-build",
                "--force",
                _env=environment,
            )


recipe = PygameCERecipe()
