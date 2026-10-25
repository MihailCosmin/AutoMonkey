struct App(egui_target::TargetApp);

impl eframe::App for App {
    fn ui(&mut self, ui: &mut eframe::egui::Ui, _frame: &mut eframe::Frame) {
        self.0.ui(ui)
    }
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([800.0, 700.0])
            .with_title("AutoMonkey egui target"),
        ..Default::default()
    };
    eframe::run_native(
        "AutoMonkey egui target",
        options,
        Box::new(|_cc| Ok(Box::new(App(Default::default())))),
    )
}
