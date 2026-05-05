import os
import sys
import json
import queue
import threading
import importlib.util
import urllib.request
import tkinter as tk
from tkinter import ttk

# Ensure playwright is importable from dynamically loaded plugins when frozen
import playwright
import playwright.sync_api

if getattr(sys, 'frozen', False):
    # Point playwright's driver at the bundled node.exe inside _internal/
    _driver = os.path.join(sys._MEIPASS, "playwright", "driver", "node.exe")
    os.environ.setdefault("PLAYWRIGHT_DRIVER_PATH", _driver)

GITHUB_USER   = "griff85"
GITHUB_REPO   = "maki-money"
GITHUB_BRANCH = "main"
GITHUB_RAW    = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR  = os.path.join(BASE_DIR, "plugins")
MANIFEST     = os.path.join(BASE_DIR, "manifest.json")


class MakiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MakiBot")
        self.root.resizable(True, True)
        self.root.minsize(500, 400)

        self._log_queue = queue.Queue()
        self._apply_dark_theme()
        self._build_ui()
        self._set_icon()
        self._poll_log()

        threading.Thread(target=self._update_then_load, daemon=True).start()

    def _apply_dark_theme(self):
        BG      = "#141414"
        BG2     = "#2d2d2d"
        BG3     = "#3c3c3c"
        FG      = "#d4d4d4"
        BORDER  = "#1a2a4a"
        ACCENT  = "#2a4a7a"

        self.root.configure(bg=BG)

        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".",
            background=BG, foreground=FG,
            bordercolor=BORDER, darkcolor=BG, lightcolor=BG2,
            troughcolor=BG3, focuscolor=ACCENT, insertcolor=FG,
        )
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TLabelframe", background=BG, foreground=FG, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BG, foreground=FG)
        style.configure("TButton", background=BG3, foreground=FG,
                        bordercolor=BORDER, relief="flat", padding=4)
        style.map("TButton",
            background=[("active", BG2), ("disabled", "#1e1e1e")],
            foreground=[("disabled", "#4a4a4a")],
            bordercolor=[("disabled", "#2a3a5a")],
        )
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TEntry", fieldbackground=BG3, foreground=FG,
                        bordercolor=BORDER, insertcolor=FG)
        style.configure("TSpinbox", fieldbackground=BG3, foreground=FG,
                        bordercolor=BORDER, arrowcolor=FG, background=BG3)
        style.configure("TCombobox", fieldbackground=BG3, foreground=FG,
                        bordercolor=BORDER, arrowcolor=FG, background=BG3,
                        selectbackground=BG3, selectforeground=FG)
        style.map("TCombobox",
            fieldbackground=[("readonly", BG3)],
            selectbackground=[("readonly", BG3)],
        )
        style.configure("TNotebook", background=BG, bordercolor=BORDER)
        style.configure("TNotebook.Tab", background="#252525", foreground="#888888",
                        bordercolor=BORDER, padding=[12, 4])
        style.map("TNotebook.Tab",
            background=[("selected", "#272727")],
            foreground=[("selected", "#b0b0b0")],
            bordercolor=[("selected", "#1a2a4a")],
            lightcolor=[("selected", "#272727")],
            darkcolor=[("selected", "#272727")],
        )

        style.configure("Vertical.TScrollbar",
            background="#2e2e2e", troughcolor="#1a1a1a",
            arrowcolor="#555555", bordercolor="#1a1a1a",
            darkcolor="#2e2e2e", lightcolor="#2e2e2e", relief="flat",
        )
        style.map("Vertical.TScrollbar",
            background=[("active", "#3d3d3d"), ("pressed", "#4a4a4a")],
        )

        # Style the combobox dropdown listbox (plain tk widget, not ttk)
        self.root.option_add("*TCombobox*Listbox.background", BG3)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", BG)

    def _set_icon(self):
        try:
            icon_path = os.path.join(BASE_DIR, "small_maki_money.png")
            icon = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, icon)
        except Exception:
            pass

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        text_container = tk.Frame(log_frame, bg="black")
        text_container.pack(fill="both", expand=True, padx=4, pady=4)

        scrollbar = ttk.Scrollbar(text_container, orient="vertical",
                                  style="Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")

        self.log_box = tk.Text(
            text_container, width=62, height=10, state="disabled",
            wrap="word", font=("Consolas", 9),
            bg="black", fg="#00ff00", insertbackground="#00ff00",
            relief="flat", borderwidth=0,
            yscrollcommand=scrollbar.set,
        )
        self.log_box.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_box.yview)

    def _log(self, message):
        self._log_queue.put(message)

    def _poll_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self.log_box.config(state="normal")
                self.log_box.insert("end", msg + "\n")
                self.log_box.see("end")
                self.log_box.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    # ── Updater ───────────────────────────────────────────────────────────────

    def _update_then_load(self):
        self._run_updater()
        self.root.after(0, self._load_plugins)

    def _run_updater(self):
        try:
            with urllib.request.urlopen(f"{GITHUB_RAW}/manifest.json", timeout=5) as r:
                remote = json.loads(r.read())

            try:
                with open(MANIFEST) as f:
                    local = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                local = {"plugins": []}

            local_versions = {p["file"]: p["version"] for p in local.get("plugins", [])}

            os.makedirs(PLUGINS_DIR, exist_ok=True)
            updated = []
            for plugin in remote.get("plugins", []):
                fname = plugin["file"]
                rver  = plugin["version"]
                if local_versions.get(fname) != rver:
                    url = f"{GITHUB_RAW}/plugins/{fname}"
                    with urllib.request.urlopen(url, timeout=10) as r:
                        content = r.read()
                    with open(os.path.join(PLUGINS_DIR, fname), "wb") as f:
                        f.write(content)
                    updated.append(fname)
                    self._log(f"[Updater] Updated {fname} → v{rver}")

            with open(MANIFEST, "w") as f:
                json.dump(remote, f, indent=2)

            if updated:
                self._log(f"[Updater] {len(updated)} plugin(s) updated")
            else:
                self._log("[Updater] All plugins up to date")

        except Exception as e:
            self._log(f"[Updater] GitHub unreachable — loading local plugins ({type(e).__name__})")

    # ── Plugin loader ─────────────────────────────────────────────────────────

    def _load_plugins(self):
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        loaded = 0
        for fname in sorted(os.listdir(PLUGINS_DIR)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(PLUGINS_DIR, fname)
            try:
                spec = importlib.util.spec_from_file_location(fname[:-3], path)
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "TAB_NAME") and hasattr(mod, "build_tab"):
                    frame = ttk.Frame(self.notebook)
                    self.notebook.add(frame, text=mod.TAB_NAME)
                    mod.build_tab(frame, self._log)
                    loaded += 1
                    self._log(f"[Loader] Loaded plugin: {mod.TAB_NAME}")
            except Exception as e:
                self._log(f"[Loader] Failed to load {fname}: {e}")

        if loaded == 0:
            self._log("[Loader] No plugins found in plugins/")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    root = tk.Tk()
    app  = MakiApp(root)
    root.mainloop()
