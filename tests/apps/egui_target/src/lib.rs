pub use eframe::egui;

#[derive(Default)]
pub struct TargetApp {
    pub count: u32,
    pub name: String,
    pub enabled: bool,
    pub strokes: Vec<Vec<egui::Pos2>>,
    pub show_about: bool,
    pub last_action: String,
}

impl TargetApp {
    pub fn ui(&mut self, ui: &mut egui::Ui) {
        egui::Panel::top("menu_bar").show(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("New").clicked() {
                        self.count = 0;
                        self.name.clear();
                        self.strokes.clear();
                        self.last_action = "New".to_owned();
                        ui.close();
                    }
                    if ui.button("Quit").clicked() {
                        ui.ctx().send_viewport_cmd(egui::ViewportCommand::Close);
                        ui.close();
                    }
                });
                ui.menu_button("Help", |ui| {
                    if ui.button("About").clicked() {
                        self.show_about = true;
                        ui.close();
                    }
                });
            });
        });

        egui::CentralPanel::default().show(ui, |ui| {
            ui.heading("AutoMonkey egui target");

            if ui.button("Increment").clicked() {
                self.count += 1;
                self.last_action = "Increment".to_owned();
            }

            ui.label(format!("Count: {}", self.count));

            ui.horizontal(|ui| {
                ui.label("Name:");
                ui.add(egui::TextEdit::singleline(&mut self.name).hint_text("Name"));
            });

            if !self.name.is_empty() {
                ui.label(format!("Hello, {}!", self.name));
            }

            ui.checkbox(&mut self.enabled, "Enabled");

            if ui.button("About").clicked() {
                self.show_about = true;
            }

            let (response, painter) =
                ui.allocate_painter(egui::vec2(400.0, 250.0), egui::Sense::drag());
            let rect = response.rect;
            painter.rect_filled(rect, 0.0, egui::Color32::LIGHT_GRAY);
            painter.rect_stroke(
                rect,
                0.0,
                egui::Stroke::new(1.0, egui::Color32::DARK_GRAY),
                egui::StrokeKind::Inside,
            );

            if response.drag_started() {
                self.strokes.push(Vec::new());
            }
            if response.dragged() {
                if let Some(pos) = response.interact_pointer_pos() {
                    if let Some(stroke) = self.strokes.last_mut() {
                        stroke.push(pos);
                    }
                }
            }

            for points in &self.strokes {
                if points.len() >= 2 {
                    painter.line(points.clone(), egui::Stroke::new(2.0, egui::Color32::BLACK));
                }
            }

            let total_points: usize = self.strokes.iter().map(|s| s.len()).sum();
            ui.label(format!(
                "Strokes: {}, points: {}",
                self.strokes.len(),
                total_points
            ));

            ui.label(format!("Last action: {}", self.last_action));
        });

        if self.show_about {
            egui::Window::new("About")
                .collapsible(false)
                .resizable(false)
                .show(ui.ctx(), |ui| {
                    ui.label("AutoMonkey egui target v1");
                    if ui.button("OK").clicked() {
                        self.show_about = false;
                        self.last_action = "About closed".to_owned();
                    }
                });
        }
    }
}
