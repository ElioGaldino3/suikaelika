"""python-for-android Python recipe tuned for Android TV compatibility."""

from os.path import join

from pythonforandroid.recipes.python3 import Python3Recipe as UpstreamPython3Recipe


class AndroidPython3Recipe(UpstreamPython3Recipe):
    """Disable optional remote debugging, whose syscalls need Android API 24+."""

    configure_args = list(UpstreamPython3Recipe.configure_args) + [
        "--without-remote-debug",
          # CPython 3.14 still schedules this module when remote debug is off.
          "py_cv_module__remote_debugging=n/a",
    ]

    def get_recipe_dir(self):
        """Keep using the upstream patch files while overriding its build args."""
        return join(self.ctx.root_dir, "recipes", "python3")


recipe = AndroidPython3Recipe()
