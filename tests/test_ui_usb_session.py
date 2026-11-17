"""USB sessions opened by the GUI must be released.

Over libusb (macOS, Linux) a claimed USB interface is exclusive: a printer
object left open makes the next one fail, and the GUI reports "Printer is
unreachable or offline". Seen on an Epson L375 (ET-2500) on macOS: "Printer
status" worked, then every "Get" failed until the app was closed.
"""
from typing import Dict, Iterator, List

import black
import pytest

import ui


class FakeUsbPrinter:
    """Stands in for the epson_usb_bridge printer: records close() calls."""

    instances: List["FakeUsbPrinter"] = []
    stats_error: Exception = None

    def __init__(self, **kwargs: object) -> None:
        self.model = kwargs.get("model")
        self.closed = False
        FakeUsbPrinter.instances.append(self)

    def stats(self) -> Dict[str, str]:
        if FakeUsbPrinter.stats_error is not None:
            raise FakeUsbPrinter.stats_error
        return {"ready": "yes"}

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def fresh_fake_printers() -> Iterator[None]:
    FakeUsbPrinter.instances = []
    FakeUsbPrinter.stats_error = None
    yield
    FakeUsbPrinter.instances = []
    FakeUsbPrinter.stats_error = None


class FailingCloseUsbPrinter:
    """A printer whose close() raises, as a vanished USB device can."""

    def close(self) -> None:
        raise OSError("LIBUSB_ERROR_NO_DEVICE")


class FakeTkVariable:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class FakeTreeview:
    def tag_configure(self, *args: object, **kwargs: object) -> None:
        pass

    def heading(self, *args: object, **kwargs: object) -> None:
        pass

    def get_children(self) -> List[str]:
        return []

    def delete(self, *items: str) -> None:
        pass


class FakeStatusWindow:
    """The few EpsonPrinterUI attributes printer_status() touches."""

    def __init__(self) -> None:
        self.model_var = FakeTkVariable("ET-2500")
        self.ip_var = FakeTkVariable("")
        self.conf_dict: Dict[str, object] = {}
        self.replace_conf = False
        self.mode = black.Mode(line_length=200, magic_trailing_comma=False)
        self.tree = FakeTreeview()
        self.errors: List[Exception] = []
        self.printer: object = None

    def printer_class(self) -> type:
        return FakeUsbPrinter

    def usb_mode(self) -> bool:
        return True

    def _connection_ready(self, address: str) -> bool:
        return True

    def show_status_text_view(self) -> None:
        pass

    def show_treeview(self) -> None:
        pass

    def populate_treeview(self, *args: object) -> None:
        pass

    def expand_all(self, tree: FakeTreeview) -> None:
        pass

    def handle_printer_error(self, error: Exception) -> None:
        self.errors.append(error)

    def config(self, **kwargs: object) -> None:
        pass

    def update_idletasks(self) -> None:
        pass


def test_printer_status_closes_its_usb_session() -> None:
    window = FakeStatusWindow()

    ui.EpsonPrinterUI.printer_status(window, cursor=False)

    assert window.errors == []
    assert len(FakeUsbPrinter.instances) == 1
    assert FakeUsbPrinter.instances[0].closed


def test_printer_status_closes_its_session_when_reading_fails() -> None:
    FakeUsbPrinter.stats_error = TimeoutError("USB: no answer")
    window = FakeStatusWindow()

    ui.EpsonPrinterUI.printer_status(window, cursor=False)

    assert len(window.errors) == 1
    assert FakeUsbPrinter.instances[0].closed


def test_printer_status_releases_the_main_printer_first() -> None:
    # "Get" leaves self.printer holding the interface (it opens lazily and
    # stays open); "Printer status" must release it before opening its own.
    window = FakeStatusWindow()
    main_printer = FakeUsbPrinter()
    window.printer = main_printer

    ui.EpsonPrinterUI.printer_status(window, cursor=False)

    assert main_printer.closed
    assert window.errors == []


def test_close_printer_session_closes_the_printer() -> None:
    printer = FakeUsbPrinter()

    ui.close_printer_session(printer)

    assert printer.closed


def test_close_printer_session_ignores_missing_or_network_printers() -> None:
    ui.close_printer_session(None)
    ui.close_printer_session(object())  # SNMP printer: no close() method


def test_close_printer_session_swallows_close_errors() -> None:
    ui.close_printer_session(FailingCloseUsbPrinter())
