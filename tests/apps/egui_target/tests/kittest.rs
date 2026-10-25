use egui_kittest::{kittest::Queryable, Harness};
use egui_target::TargetApp;

fn new_harness() -> Harness<'static, TargetApp> {
    Harness::new_ui_state(|ui, app: &mut TargetApp| app.ui(ui), TargetApp::default())
}

#[test]
fn increment_button_updates_count() {
    let mut harness = new_harness();

    harness.get_by_label("Increment").click();
    harness.run();
    harness.get_by_label("Increment").click();
    harness.run();

    assert_eq!(harness.state().count, 2);
    harness.get_by_label("Count: 2");
}

#[test]
fn about_window_opens_and_closes() {
    let mut harness = new_harness();

    harness.get_by_label("About").click();
    harness.run();

    harness.get_by_label("AutoMonkey egui target v1");

    harness.get_by_label("OK").click();
    harness.run();

    assert!(harness.query_by_label("AutoMonkey egui target v1").is_none());
    assert_eq!(harness.state().last_action, "About closed");
}

#[test]
fn enabled_checkbox_toggles() {
    let mut harness = new_harness();

    harness.get_by_label("Enabled").click();
    harness.run();

    assert!(harness.state().enabled);
}
