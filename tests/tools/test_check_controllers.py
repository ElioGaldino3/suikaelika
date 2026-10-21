"""Native enumeration excludes keyboard; partial failures remain visible."""

from types import SimpleNamespace

from tools import check_controllers


class Joystick:
    def __init__(self, index):
        self.index = index
        self.closed = False

    def init(self):
        pass

    def quit(self):
        self.closed = True

    def get_instance_id(self):
        return 50 + self.index

    def get_name(self):
        return "Controle igual"

    def get_guid(self):
        return "same-guid"

    def get_numaxes(self):
        return 4

    def get_numbuttons(self):
        return 10

    def get_numhats(self):
        return 1


def test_report_counts_same_model_pads_separately_and_releases_devices(monkeypatch):
    pads = [Joystick(0), Joystick(1)]
    closed = []
    pygame = SimpleNamespace(
        display=SimpleNamespace(init=lambda: None, quit=lambda: closed.append("display")),
        joystick=SimpleNamespace(
            init=lambda: None,
            quit=lambda: closed.append("joystick"),
            get_count=lambda: 2,
            Joystick=lambda index: pads[index],
        ),
        event=SimpleNamespace(pump=lambda: None),
        version=SimpleNamespace(ver="test"),
        get_sdl_version=lambda: (2, 32, 0),
        error=RuntimeError,
    )
    api = SimpleNamespace(
        init=lambda: None,
        quit=lambda: closed.append("controller"),
        is_controller=lambda index: index == 0,
    )
    monkeypatch.setattr(check_controllers.importlib, "import_module", lambda _: api)
    report = check_controllers.collect_controllers(pygame)
    assert report["joystick_count"] == report["opened_count"] == 2
    assert not report["keyboard_counted"]
    assert [device["instance_id"] for device in report["devices"]] == [50, 51]
    assert "índice 1" in check_controllers.format_text(report)
    assert all(pad.closed for pad in pads)
    assert closed == ["controller", "joystick", "display"]


def test_controller_read_error_produces_partial_report(monkeypatch):
    pad = Joystick(0)

    def joystick(index):
        if index == 1:
            raise RuntimeError("removido durante enumeração")
        return pad

    def unavailable(_):
        raise ImportError("no mapped API")

    pygame = SimpleNamespace(
        display=SimpleNamespace(init=lambda: None, quit=lambda: None),
        joystick=SimpleNamespace(
            init=lambda: None, quit=lambda: None, get_count=lambda: 2, Joystick=joystick
        ),
        event=SimpleNamespace(pump=lambda: None),
        version=SimpleNamespace(ver="test"),
        get_sdl_version=lambda: (2, 32, 0),
        error=RuntimeError,
    )
    monkeypatch.setattr(check_controllers.importlib, "import_module", unavailable)
    report = check_controllers.collect_controllers(pygame)
    assert report["joystick_count"] == 2 and report["opened_count"] == 1
    assert "removido" in report["errors"][0]
    assert pad.closed and report["devices"][0]["sdl_mapped"] is None
