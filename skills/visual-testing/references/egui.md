# egui: headless tests with egui_kittest (layer 1)

`egui_kittest` drives an egui UI without a window: it finds widgets through the
AccessKit tree, clicks them, types, presses keys, checks state and compares pixel
snapshots. It cannot test real OS input, the real window manager, DPI scaling, the fonts
on the user's machine, native dialogs (`rfd`), or drags between windows. Those belong to
the AutoMonkey pass (layer 2).

Everything below is checked against **egui / eframe / egui_kittest 0.37**. egui changed
its API in 0.37; older examples you may remember (`TopBottomPanel`, `App::update(ctx)`,
`Harness::new_state(ctx, ..)`) no longer compile.

A working example lives in AutoMonkey: `tests/apps/egui_target/` (app) and
`tests/apps/egui_target/tests/kittest.rs` (tests).

## Setup

```toml
[dev-dependencies]
egui_kittest = "0.37"                                              # queries, clicks, keys
# egui_kittest = { version = "0.37", features = ["snapshot", "wgpu"] }  # + pixel snapshots
```

Snapshots render with wgpu, so they need a GPU or a software adapter: WARP on Windows
CI, mesa lavapipe on Linux CI (`mesa-vulkan-drivers`). Keep query tests free of the
snapshot feature so they run anywhere.

## Structure the app for testing

In 0.37 the app draws into a root `&mut egui::Ui`. Put the drawing in the library crate
on a state struct; the binary only wraps it.

```rust
// src/lib.rs
pub use eframe::egui;

#[derive(Default)]
pub struct TargetApp { pub count: u32, pub name: String, pub show_about: bool }

impl TargetApp {
    pub fn ui(&mut self, ui: &mut egui::Ui) {
        egui::Panel::top("menu_bar").show(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("Help", |ui| {
                    if ui.button("About").clicked() { self.show_about = true; ui.close(); }
                });
            });
        });
        egui::CentralPanel::default().show(ui, |ui| {
            if ui.button("Increment").clicked() { self.count += 1; }
            ui.label(format!("Count: {}", self.count));
            ui.add(egui::TextEdit::singleline(&mut self.name).hint_text("Name"));
        });
        if self.show_about {
            egui::Window::new("About").show(ui.ctx(), |ui| {
                if ui.button("OK").clicked() { self.show_about = false; }
            });
        }
    }
}

// src/main.rs
struct App(my_app::TargetApp);
impl eframe::App for App {
    fn ui(&mut self, ui: &mut eframe::egui::Ui, _frame: &mut eframe::Frame) { self.0.ui(ui) }
}
```

## Tests

```rust
use egui_kittest::{kittest::Queryable, Harness};
use my_app::TargetApp;

fn harness() -> Harness<'static, TargetApp> {
    Harness::new_ui_state(|ui, app: &mut TargetApp| app.ui(ui), TargetApp::default())
}

#[test]
fn increment_twice() {
    let mut h = harness();
    h.get_by_label("Increment").click();
    h.run();                                   // let egui process the event and repaint
    h.get_by_label("Increment").click();
    h.run();
    assert_eq!(h.state().count, 2);
    h.get_by_label("Count: 2");                // panics if the label is missing
}

#[test]
fn about_dialog_opens_and_closes() {
    let mut h = harness();
    h.get_by_label("Help").click();
    h.run();
    h.get_by_label("About").click();
    h.run();
    h.get_by_label("OK").click();
    h.run();
    assert!(h.query_by_label("OK").is_none());
}
```

Useful calls (0.37):

| Want | Call |
|---|---|
| find by visible text | `get_by_label("Save")`, `query_by_label(..)` → `Option`, `get_by_label_contains(..)` |
| find by kind | `get_by_role(egui::accesskit::Role::TextInput)`, `get_by_role_and_label(Role::Button, "OK")` |
| find by current value | `get_by_value("abc")` |
| act on a node | `.click()`, `.click_secondary()`, `.click_modifiers(Modifiers::CTRL)`, `.hover()`, `.focus()`, `.type_text("hello")` |
| read a node | `.value()`, `.is_focused()`, `.rect()` |
| keyboard | `h.key_press(egui::Key::Enter)`, `h.key_press_modifiers(Modifiers::COMMAND, Key::S)`, `h.key_combination(&[..])` |
| raw pointer | `h.hover_at(pos)`, `h.drag_at(pos)` |
| frames | `h.run()` (until settled), `h.step()` (one frame) |
| size | `Harness::builder().with_size(egui::vec2(800.0, 600.0)).build_ui_state(..)` |
| state | `h.state()`, `h.state_mut()` |

`get_*` panics with a readable message when nothing (or more than one node) matches;
use `query_*` when absence is the expected result.

## Pixel snapshots

```rust
#[test]
fn main_view_snapshot() {
    let mut h = Harness::builder()
        .with_size(egui::vec2(800.0, 600.0))           // fixed size = stable images
        .build_ui_state(|ui, app: &mut TargetApp| app.ui(ui), TargetApp::default());
    h.run();
    h.snapshot("main_view");                           // tests/snapshots/main_view.png
}
```

- First run writes `tests/snapshots/<name>.png`; later runs compare. On a mismatch the
  test fails and writes `<name>.new.png` and `<name>.diff.png` next to it.
- Accept intended changes: `UPDATE_SNAPSHOTS=1 cargo test` (`force` rewrites all). Look at
  every `.diff.png` before accepting.
- Commit the `.png` snapshots; git-ignore `*.new.png`, `*.diff.png`, `*.old.png`.
- Thresholds and the output folder: `kittest.toml` in the workspace root
  (`output_path`, `threshold`, per-OS `[windows]` / `[linux]` / `[mac]` sections).
- Snapshot both themes (`ctx.set_theme(egui::Theme::Dark/Light)`) and a narrow size to
  catch clipping and overlapping widgets.

## What to cover in layer 1

- Every button and menu item has a label (otherwise neither kittest nor AutoMonkey can
  find it) and changes state as intended.
- Dialogs/windows open and close; Escape and Enter behave.
- Keyboard shortcuts; disabled states (`ui.add_enabled(false, ..)`) do nothing.
- Empty, very long and non-ASCII text in snapshots (clipping, wrapping).

## AccessKit is also what layer 2 uses

eframe exposes the same AccessKit tree to the operating system (UI Automation on
Windows, AT-SPI on Linux) through its default `accesskit` feature. That is how
AutoMonkey's `controls`, `click_control` and `tab_order` see egui widgets. Keep the
feature enabled, and give icon-only buttons a text label, or they are invisible in the
tree.

## CI

`cargo test --workspace` (add `--all-features` for snapshots). Upload
`tests/snapshots/*.diff.png` and `*.new.png` as artifacts when the job fails.
