import os
import sys
import json
import queue
import threading
import importlib.util
import urllib.request
import tkinter as tk
from tkinter import ttk, scrolledtext

if getattr(sys, 'frozen', False):
    _base = os.path.dirname(sys.executable)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(_base, "browsers"))

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
        self.root.resizable(False, False)

        self._log_queue = queue.Queue()
        self._build_ui()
        self._set_icon()
        self._poll_log()

        threading.Thread(target=self._update_then_load, daemon=True).start()

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

        self.log_box = scrolledtext.ScrolledText(
            log_frame, width=62, height=10, state="disabled",
            wrap="word", font=("Consolas", 9),
            bg="black", fg="#00ff00", insertbackground="#00ff00",
        )
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)

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
    root = tk.Tk()
    app  = MakiApp(root)
    root.mainloop()
