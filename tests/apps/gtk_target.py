"""GTK target app for the AT-SPI side of the AI layer (atspi_tree.py): a menu bar with a
submenu, a combo box, a check button, an entry, buttons, a dialog, a label whose text is
ellipsized, and the tab order entry -> combo -> check -> Increment -> Open dialog.

    python tests/apps/gtk_target.py          # GTK 3
    python tests/apps/gtk_target.py --gtk4   # GTK 4 (PopoverMenuBar instead of GtkMenuBar)

Window title: "AutoMonkey GTK target" (GTK 3) / "AutoMonkey GTK4 target" (GTK 4).
Needs python3-gi with gir1.2-gtk-3.0 (or gir1.2-gtk-4.0). GTK apps expose AT-SPI when
toolkit-accessibility is on, or always (GTK 4, and GTK 3 with the atk-bridge loaded).
"""
import sys

import gi

GTK4 = "--gtk4" in sys.argv
gi.require_version("Gtk", "4.0" if GTK4 else "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

LONG = "ready - all systems operational, waiting for the next command"
CHOICES = ["Red", "Green", "Blue"]


class State:
    def __init__(self):
        self.count = 0
        self.status = None
        self.window = None

    def set_status(self, text):
        self.status.set_text(text)


def _widgets(state):
    """The form shared by both GTK versions; returns the box and the widgets in tab order."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(12)

    name = Gtk.Entry()
    name.set_placeholder_text("Your name")
    name.connect("changed", lambda e: state.set_status(f"Hello, {e.get_text()}"))

    combo = Gtk.ComboBoxText()
    for c in CHOICES:
        combo.append_text(c)
    combo.set_active(0)
    combo.connect("changed", lambda c: state.set_status(f"Colour: {c.get_active_text()}"))

    check = Gtk.CheckButton(label="Enable notifications")
    check.connect("toggled", lambda b: state.set_status(f"Notifications {'on' if b.get_active() else 'off'}"))

    inc = Gtk.Button(label="Increment")

    def increment(_b):
        state.count += 1
        state.set_status(f"Count: {state.count}")
    inc.connect("clicked", increment)

    dlg = Gtk.Button(label="Open dialog")
    dlg.connect("clicked", lambda _b: open_dialog(state))

    status = Gtk.Label(label=LONG)
    status.set_ellipsize(3)  # Pango.EllipsizeMode.END
    status.set_max_width_chars(18)
    status.set_xalign(0)
    status.set_halign(Gtk.Align.START)  # take the natural width: max_width_chars, so the text is cut
    state.status = status

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    order = [name, combo, check, inc, dlg]
    for w in (name, combo, check):
        _add(box, w)
    for w in (inc, dlg):
        _add(row, w)
    _add(box, row)
    _add(box, status)
    return box, order


def _add(box, widget):
    if GTK4:
        box.append(widget)
    else:
        box.pack_start(widget, False, False, 0)


def open_dialog(state):
    if GTK4:
        d = Gtk.Window(title="Settings", transient_for=state.window, modal=True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.append(Gtk.Label(label="Apply the settings?"))
        ok = Gtk.Button(label="OK")
        ok.connect("clicked", lambda _b: (state.set_status("Settings applied"), d.destroy()))
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: d.destroy())
        inner.append(ok)
        inner.append(cancel)
        d.set_child(inner)
        d.present()
        return
    d = Gtk.Dialog(title="Settings", transient_for=state.window, modal=True)
    d.add_button("Cancel", Gtk.ResponseType.CANCEL)
    d.add_button("OK", Gtk.ResponseType.OK)
    d.get_content_area().add(Gtk.Label(label="Apply the settings?"))
    d.show_all()
    if d.run() == Gtk.ResponseType.OK:
        state.set_status("Settings applied")
    d.destroy()


def gtk3():
    state = State()
    win = Gtk.Window(title="AutoMonkey GTK target")
    state.window = win
    win.set_default_size(420, 320)
    win.connect("destroy", Gtk.main_quit)
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    bar = Gtk.MenuBar()

    def menu(title, items):
        top = Gtk.MenuItem(label=title)
        sub = Gtk.Menu()
        for label, action in items:
            if isinstance(action, list):
                item = Gtk.MenuItem(label=label)
                inner = Gtk.Menu()
                for l2, a2 in action:
                    i2 = Gtk.MenuItem(label=l2)
                    i2.connect("activate", lambda _i, a=a2: a())
                    inner.append(i2)
                item.set_submenu(inner)
            else:
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda _i, a=action: a())
            sub.append(item)
        top.set_submenu(sub)
        bar.append(top)

    menu("File", [("Open...", lambda: open_dialog(state)),
                  ("Recent", [("first.txt", lambda: state.set_status("Opened first.txt")),
                              ("second.txt", lambda: state.set_status("Opened second.txt"))]),
                  ("Quit", Gtk.main_quit)])
    menu("Help", [("About", lambda: state.set_status("AutoMonkey GTK target 1.0"))])
    outer.pack_start(bar, False, False, 0)
    box, order = _widgets(state)
    outer.pack_start(box, True, True, 0)
    win.add(outer)
    win.show_all()
    order[0].grab_focus()
    Gtk.main()


def gtk4():
    app = Gtk.Application(application_id="org.automonkey.GtkTarget4")

    def activate(app):
        state = State()
        win = Gtk.ApplicationWindow(application=app, title="AutoMonkey GTK4 target")
        state.window = win
        win.set_default_size(420, 320)
        for name, cb in [("open", lambda: open_dialog(state)),
                         ("first", lambda: state.set_status("Opened first.txt")),
                         ("second", lambda: state.set_status("Opened second.txt")),
                         ("about", lambda: state.set_status("AutoMonkey GTK4 target 1.0")),
                         ("quit", app.quit)]:
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda _a, _p, cb=cb: cb())
            app.add_action(act)
        model = Gio.Menu()
        file_menu = Gio.Menu()
        file_menu.append("Open...", "app.open")
        recent = Gio.Menu()
        recent.append("first.txt", "app.first")
        recent.append("second.txt", "app.second")
        file_menu.append_submenu("Recent", recent)
        file_menu.append("Quit", "app.quit")
        help_menu = Gio.Menu()
        help_menu.append("About", "app.about")
        model.append_submenu("File", file_menu)
        model.append_submenu("Help", help_menu)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(Gtk.PopoverMenuBar.new_from_model(model))
        box, order = _widgets(state)
        outer.append(box)
        win.set_child(outer)
        win.present()
        GLib.idle_add(order[0].grab_focus)

    app.connect("activate", activate)
    app.run([sys.argv[0]])


if __name__ == "__main__":
    gtk4() if GTK4 else gtk3()
