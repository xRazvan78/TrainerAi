//! Windows Graphics Capture (WGC) screen capture module.
//!
//! Exposes:
//! - [`CapturedFrame`] — a single captured frame encoded as JPEG/base64 with a perceptual hash.
//! - [`ahash`] — 8×8 average-hash of a `DynamicImage`.
//! - [`hamming`] — Hamming distance between two `u64` hashes.
//! - [`find_autocad_hwnd`] — enumerate visible windows to find AutoCAD.
//! - [`capture_window_frame`] — WGC capture of one frame from an HWND.

use base64::Engine as _;
use image::imageops::FilterType;
use std::sync::mpsc;
use std::time::Duration;
use windows::Win32::Foundation::{BOOL, HWND, LPARAM};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetWindowTextW, IsWindowVisible,
};
use windows_capture::capture::GraphicsCaptureApiHandler;
use windows_capture::frame::Frame;
use windows_capture::graphics_capture_api::InternalCaptureControl;
use windows_capture::settings::{
    ColorFormat, CursorCaptureSettings, DirtyRegionSettings, DrawBorderSettings,
    MinimumUpdateIntervalSettings, SecondaryWindowSettings, Settings,
};
use windows_capture::window::Window;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// A single captured frame, downscaled 50%, JPEG-encoded and base64-encoded.
pub struct CapturedFrame {
    pub jpeg_b64: String,
    pub hash: u64,
    pub width: u32,
    pub height: u32,
}

// ---------------------------------------------------------------------------
// Perceptual hashing
// ---------------------------------------------------------------------------

/// 8×8 average-hash of `img`.
///
/// Resize to 8×8 nearest-neighbour, convert to luma, compute mean, set bit i
/// when pixel[i] >= mean.
pub fn ahash(img: &image::DynamicImage) -> u64 {
    let small = img.resize_exact(8, 8, FilterType::Nearest);
    let luma = small.to_luma8();
    let pixels: Vec<u8> = luma.into_raw();

    let mean = pixels.iter().map(|&p| p as u32).sum::<u32>() / 64;

    let mut hash: u64 = 0;
    for (i, &p) in pixels.iter().enumerate() {
        if p as u32 >= mean {
            hash |= 1u64 << i;
        }
    }
    hash
}

/// Hamming distance between two hashes.
pub fn hamming(a: u64, b: u64) -> u32 {
    (a ^ b).count_ones()
}

// ---------------------------------------------------------------------------
// Window enumeration
// ---------------------------------------------------------------------------

/// Walk visible top-level windows and return the first whose title contains
/// "AutoCAD" (case-sensitive).
///
/// TODO: gate DWM-cloaked windows behind an additional `DwmGetWindowAttribute`
/// check if ghost windows become a problem.
pub fn find_autocad_hwnd() -> Option<HWND> {
    let mut result: Option<HWND> = None;

    unsafe extern "system" fn enum_cb(hwnd: HWND, lparam: LPARAM) -> BOOL {
        // Skip invisible windows.
        if !IsWindowVisible(hwnd).as_bool() {
            return BOOL(1); // continue
        }

        let mut buf = [0u16; 256];
        let len = GetWindowTextW(hwnd, &mut buf);
        if len <= 0 {
            return BOOL(1);
        }

        let title = String::from_utf16_lossy(&buf[..len as usize]);
        if title.contains("AutoCAD") {
            let out = &mut *(lparam.0 as *mut Option<HWND>);
            *out = Some(hwnd);
            return BOOL(0); // stop enumeration
        }

        BOOL(1)
    }

    // SAFETY: `result` lives for the duration of `EnumWindows`.
    let _ = unsafe {
        EnumWindows(
            Some(enum_cb),
            LPARAM(std::ptr::addr_of_mut!(result) as isize),
        )
    };

    result
}

// ---------------------------------------------------------------------------
// WGC single-frame capture
// ---------------------------------------------------------------------------

/// Payload sent from the WGC callback thread to the caller.
struct RawFrame {
    data: Vec<u8>,
    width: u32,
    height: u32,
}

/// Internal capture handler that grabs one frame and stops.
struct OneShot {
    tx: Option<mpsc::SyncSender<RawFrame>>,
}

impl GraphicsCaptureApiHandler for OneShot {
    type Flags = mpsc::SyncSender<RawFrame>;
    type Error = Box<dyn std::error::Error + Send + Sync>;

    fn new(
        ctx: windows_capture::capture::Context<Self::Flags>,
    ) -> Result<Self, Self::Error> {
        Ok(Self { tx: Some(ctx.flags) })
    }

    fn on_frame_arrived(
        &mut self,
        frame: &mut Frame,
        capture_control: InternalCaptureControl,
    ) -> Result<(), Self::Error> {
        let w = frame.width();
        let h = frame.height();

        // Pull BGRA8 bytes out of the frame (may have row padding).
        let mut frame_buffer = frame.buffer()?;
        let raw = frame_buffer.as_nopadding_buffer()?;

        // Clone so we own the bytes before stopping the session.
        let owned = raw.to_vec();

        if let Some(tx) = self.tx.take() {
            let _ = tx.send(RawFrame { data: owned, width: w, height: h });
        }

        capture_control.stop();
        Ok(())
    }

    fn on_closed(&mut self) -> Result<(), Self::Error> {
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

fn bgra_to_rgba(mut buf: Vec<u8>) -> Vec<u8> {
    for chunk in buf.chunks_exact_mut(4) {
        chunk.swap(0, 2); // B↔R
    }
    buf
}

fn encode_jpeg(img: &image::DynamicImage) -> Option<Vec<u8>> {
    let mut bytes = Vec::new();
    let mut encoder =
        image::codecs::jpeg::JpegEncoder::new_with_quality(&mut bytes, 75);
    encoder.encode_image(img).ok()?;
    Some(bytes)
}

// ---------------------------------------------------------------------------
// Public capture entry point
// ---------------------------------------------------------------------------

/// Capture one frame from `hwnd` using Windows Graphics Capture.
///
/// Returns `None` on any failure or if no frame arrives within 250 ms.
pub fn capture_window_frame(hwnd: HWND) -> Option<CapturedFrame> {
    let (tx, rx) = mpsc::sync_channel::<RawFrame>(1);

    let wc_window = Window::from_raw_hwnd(hwnd.0);

    let settings = Settings::new(
        wc_window,
        CursorCaptureSettings::WithoutCursor,
        DrawBorderSettings::Default,
        SecondaryWindowSettings::Default,
        MinimumUpdateIntervalSettings::Default,
        DirtyRegionSettings::Default,
        ColorFormat::Bgra8,
        tx,
    );

    let _control = OneShot::start_free_threaded(settings).ok()?;
    let raw = rx.recv_timeout(Duration::from_millis(250)).ok()?;
    finish_frame(raw)
}

fn finish_frame(raw: RawFrame) -> Option<CapturedFrame> {
    let RawFrame { data: buf, width: w, height: h } = raw;

    // windows-capture with ColorFormat::Bgra8 gives BGRA bytes.
    // Swap R and B channels to produce RGBA so the `image` crate is happy.
    let rgba = bgra_to_rgba(buf);

    let img = image::RgbaImage::from_raw(w, h, rgba).map(image::DynamicImage::ImageRgba8)?;

    // Perceptual hash (ahash uses internal 8×8 reduction, unaffected by resolution).
    let hash = ahash(&img);

    // JPEG encode at quality 75. Full resolution is required so that EasyOCR can
    // read the AutoCAD command line text (~14px tall at 1080p, illegible at 50% scale).
    let bytes = encode_jpeg(&img)?;

    let jpeg_b64 =
        base64::engine::general_purpose::STANDARD.encode(&bytes);

    Some(CapturedFrame {
        jpeg_b64,
        hash,
        width: w,
        height: h,
    })
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// A solid white 8×8 image: every pixel == 255, mean == 255.
    /// Each pixel >= mean (255 >= 255), so all 64 bits are set → u64::MAX.
    #[test]
    fn ahash_solid_white() {
        let img = image::DynamicImage::ImageRgba8(image::RgbaImage::from_pixel(
            8,
            8,
            image::Rgba([255u8, 255, 255, 255]),
        ));
        assert_eq!(ahash(&img), u64::MAX);
    }

    /// A solid black 8×8 image: every pixel == 0, mean == 0.
    /// Each pixel >= mean (0 >= 0), so all 64 bits are set → u64::MAX.
    /// Known limitation: uniform-colour images (all pixels equal) always hash
    /// to u64::MAX because every pixel equals the mean.
    #[test]
    fn ahash_solid_black() {
        let img = image::DynamicImage::ImageRgba8(image::RgbaImage::from_pixel(
            8,
            8,
            image::Rgba([0u8, 0, 0, 255]),
        ));
        assert_eq!(ahash(&img), u64::MAX);
    }

    #[test]
    fn ahash_uniform_collision() {
        // Known limitation: solid black and solid white both hash to u64::MAX
        // because every pixel equals the mean in both cases.
        // A black→white transition is therefore invisible to the hash diff.
        let black = image::DynamicImage::ImageRgba8(image::RgbaImage::from_pixel(
            8, 8, image::Rgba([0u8, 0, 0, 255]),
        ));
        let white = image::DynamicImage::ImageRgba8(image::RgbaImage::from_pixel(
            8, 8, image::Rgba([255u8, 255, 255, 255]),
        ));
        assert_eq!(hamming(ahash(&black), ahash(&white)), 0);
    }

    #[test]
    fn hamming_identity() {
        let x: u64 = 0xDEAD_BEEF_CAFE_1234;
        assert_eq!(hamming(x, x), 0);
    }

    #[test]
    fn hamming_all_bits() {
        assert_eq!(hamming(0u64, !0u64), 64);
    }
}
