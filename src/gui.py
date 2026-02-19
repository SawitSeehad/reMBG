# ==========================================================
# pvBG - Private Background Removal
# Copyright (C) 2026 Saw it See had
# Licensed under the MIT License
# ==========================================================

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import threading
import os
import sys

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

from engine import Engine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

PREVIEW_SIZE = 380

def make_checkerboard(width: int, height: int, tile: int = 12) -> Image.Image:
    """
    Generate a checkerboard pattern image (used as background
    for the result preview so transparency is visible).
    """
    img = Image.new("RGB", (width, height), (220, 220, 220))
    dark = (170, 170, 170)
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if (x // tile + y // tile) % 2 == 0:
                for py in range(tile):
                    for px in range(tile):
                        if x + px < width and y + py < height:
                            img.putpixel((x + px, y + py), dark)
    return img

def composite_on_checker(rgba_image: Image.Image) -> Image.Image:
    """
    Composite an RGBA image onto a checkerboard background
    so that transparent areas are visually distinguishable.
    """
    checker = make_checkerboard(rgba_image.width, rgba_image.height)
    checker.paste(rgba_image, mask=rgba_image.split()[3])
    return checker

class App(TkinterDnD.Tk if DND_AVAILABLE else ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("pvBG v1.0.0 — Private Background Removal (Offline)")
        self.geometry("1000x680")
        self.minsize(800, 580)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.configure(bg="#1a1a2e")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir  = os.path.join(current_dir, '..', 'assets')
        try:
            self.iconbitmap(os.path.join(assets_dir, 'icon.ico'))
        except Exception:
            pass

        model_path = os.path.join(current_dir, '..', 'models', 'pvBG.onnx')
        try:
            self.engine      = Engine(model_path)
            self.status_text = "✅  System ready. Select or drop an image to begin."
        except Exception as e:
            self.engine      = None
            self.status_text = f"❌  Engine error: {e}"

        self.current_result   = None   
        self._orig_photo_ref  = None   
        self._res_photo_ref   = None

        self._build_ui()

        if DND_AVAILABLE:
            self._setup_dnd()

    def _build_ui(self):
        """Build all UI widgets."""

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 6))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="pvBG",
            font=ctk.CTkFont(family="Arial", size=32, weight="bold"),
            text_color="#4fc3f7"
        ).grid(row=0, column=0)

        ctk.CTkLabel(
            header_frame,
            text="Private Background Removal — Offline & Private",
            font=ctk.CTkFont(family="Arial", size=12),
            text_color="gray"
        ).grid(row=1, column=0)

        self.frame_left  = self._make_panel("Original Image")
        self.frame_left.grid(row=1, column=0, padx=(16, 8), pady=8, sticky="nsew")

        self.frame_right = self._make_panel("Result")
        self.frame_right.grid(row=1, column=1, padx=(8, 16), pady=8, sticky="nsew")

        # Image labels inside panels
        self.lbl_orig = ctk.CTkLabel(
            self.frame_left,
            text="No image selected.\n\nDrop an image here\nor use the button below.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
            wraplength=340
        )
        self.lbl_orig.pack(expand=True, fill="both", padx=8, pady=8)

        self.lbl_res = ctk.CTkLabel(
            self.frame_right,
            text="Result will appear here\nafter processing.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
            wraplength=340
        )
        self.lbl_res.pack(expand=True, fill="both", padx=8, pady=8)

        if DND_AVAILABLE:
            self._drop_hint_left = ctk.CTkLabel(
                self.frame_left,
                text="⬇  Drop image here",
                font=ctk.CTkFont(size=11),
                text_color="#555577"
            )
            self._drop_hint_left.place(relx=0.5, rely=0.96, anchor="s")

        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 4))
        ctrl_frame.grid_columnconfigure(0, weight=1)
        ctrl_frame.grid_columnconfigure(1, weight=1)
        ctrl_frame.grid_columnconfigure(2, weight=1)

        self.btn_open = ctk.CTkButton(
            ctrl_frame,
            text="📂  Select Image",
            command=self.open_image,
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10
        )
        self.btn_open.grid(row=0, column=0, padx=10, pady=8, sticky="ew")

        self.btn_process = ctk.CTkButton(
            ctrl_frame,
            text="▶  Remove Background",
            command=self._trigger_process,
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10,
            state="disabled",
            fg_color="#1565c0",
            hover_color="#1976d2"
        )
        self.btn_process.grid(row=0, column=1, padx=10, pady=8, sticky="ew")

        self.btn_save = ctk.CTkButton(
            ctrl_frame,
            text="💾  Save as PNG",
            command=self.save_image,
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10,
            state="disabled",
            fg_color="#2e7d32",
            hover_color="#388e3c"
        )
        self.btn_save.grid(row=0, column=2, padx=10, pady=8, sticky="ew")

        self.lbl_info = ctk.CTkLabel(
            self,
            text=self.status_text,
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=900
        )
        self.lbl_info.grid(row=3, column=0, columnspan=2, pady=(2, 10))

    def _make_panel(self, title: str) -> ctk.CTkFrame:
        """Create a titled preview panel frame."""
        outer = ctk.CTkFrame(self, corner_radius=12)
        ctk.CTkLabel(
            outer,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#90caf9"
        ).pack(pady=(10, 0))
        ctk.CTkFrame(outer, height=1, fg_color="#333355").pack(fill="x", padx=12, pady=4)
        return outer

    def _setup_dnd(self):
        """Register drag-and-drop targets on both panels and the window."""
        for widget in (self, self.frame_left, self.lbl_orig):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        """Handle a file drop event."""
        raw  = event.data.strip()
        # tkinterdnd2 wraps paths with spaces in braces: {/path/with spaces/file.png}
        path = raw.strip("{}").split("} {")[0]
        if os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXT):
            self._load_image(path)
        else:
            self._set_status("⚠️  Unsupported file type. Please drop a JPG, PNG, WEBP, or BMP image.")

    def open_image(self):
        """Open file manager dialog and load the selected image."""
        if not self.engine:
            messagebox.showerror("Engine Error", "pvBG model is not loaded. Check the models folder.")
            return
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("All files", "*.*")
            ]
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str):
        """
        Load an image from disk, display a preview in the Original panel,
        and reset the Result panel — without running inference yet.

        Args:
            path (str): Absolute path to the image file.
        """
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            self._set_status(f"❌  Failed to open image: {e}")
            return

        self._current_input_path = path

        thumb = img.copy()
        thumb.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)

        photo = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
        self._orig_photo_ref = photo   # prevent garbage collection

        self.lbl_orig.configure(image=photo, text="")

        self.lbl_res.configure(image=None, text="Ready to process.\nClick ▶ Remove Background.")
        self._res_photo_ref  = None
        self.current_result  = None
        self.btn_save.configure(state="disabled")

        self.btn_process.configure(state="normal")

        filename = os.path.basename(path)
        w, h     = img.size
        self._set_status(f"📂  Loaded: {filename}  ({w} × {h} px) — Click ▶ Remove Background to process.")

    def _trigger_process(self):
        """Start background removal in a separate thread."""
        if not self.engine:
            messagebox.showerror("Engine Error", "pvBG model is not loaded.")
            return
        if not hasattr(self, '_current_input_path') or not self._current_input_path:
            return

        # Disable controls while processing
        self.btn_process.configure(state="disabled", text="⏳  Processing...")
        self.btn_open.configure(state="disabled")
        self.btn_save.configure(state="disabled")
        self.lbl_res.configure(image=None, text="⏳  Removing background...\nPlease wait.")
        self._set_status("⏳  pvBG is processing the image. Please wait...")

        threading.Thread(
            target=self._run_inference,
            args=(self._current_input_path,),
            daemon=True
        ).start()

    def _run_inference(self, path: str):
        """
        Run pvBG inference on a background thread, then schedule
        the UI update back on the main thread.

        Args:
            path (str): Path to the input image.
        """
        try:
            result = self.engine.remove_background(path)
            self.current_result = result
            self.after(0, self._show_result)
        except Exception as e:
            self.after(0, lambda: self._on_inference_error(str(e)))

    def _show_result(self):
        """Display the processed result image and re-enable controls."""
        if self.current_result is None:
            self._on_inference_error("Engine returned no result.")
            return

        # Composite result on checkerboard to visualise transparency
        composited = composite_on_checker(self.current_result)
        thumb      = composited.copy()
        thumb.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)

        photo = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
        self._res_photo_ref = photo   # prevent garbage collection

        self.lbl_res.configure(image=photo, text="")
        self.btn_save.configure(state="normal")
        self.btn_process.configure(state="normal", text="▶  Remove Background")
        self.btn_open.configure(state="normal")

        w, h = self.current_result.size
        self._set_status(f"✅  Done!  Output: {w} × {h} px — Click 💾 Save as PNG to export.")

    def _on_inference_error(self, message: str):
        """Handle inference errors and restore UI state."""
        self.lbl_res.configure(image=None, text="❌  Processing failed.")
        self.btn_process.configure(state="normal", text="▶  Remove Background")
        self.btn_open.configure(state="normal")
        self._set_status(f"❌  Error: {message}")

    def save_image(self):
        """Save the result RGBA image as a PNG file."""
        if not self.current_result:
            return
        path = filedialog.asksaveasfilename(
            title="Save result as PNG",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")]
        )
        if path:
            try:
                self.current_result.save(path, format="PNG")
                messagebox.showinfo("Saved", f"Image saved successfully!\n{path}")
                self._set_status(f"💾  Saved to: {path}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save image:\n{e}")

    def _set_status(self, text: str):
        """Update the status bar label."""
        self.lbl_info.configure(text=text)

if __name__ == "__main__":
    app = App()
    app.mainloop()