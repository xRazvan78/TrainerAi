// src/renderer/app.rs
use dioxus::prelude::*;

pub fn app() -> Element {
    rsx! {
        div { class: "container",
            h1 { "AutoCAD Trainer AI" }
            p { "Dioxus interface is working!" }
        }
    }
}