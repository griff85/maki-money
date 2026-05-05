import os
import sys
import re
import time
import random
import json
import threading
import tkinter as tk
from tkinter import ttk

from playwright.sync_api import Playwright, sync_playwright

TAB_NAME = "Tile Game"

ROWS = 6
COLS = 6
AURA_SWITCH_TO_AURA = 1

ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.json")

_READ_BOARD_JS = r'''() => {
    for (const div of document.querySelectorAll('div')) {
        const btns = [...div.children].filter(e => e.tagName === 'BUTTON');
        if (btns.length === 36) {
            return btns.map(b =>
                (b.innerText || '').replace(/️|︎/g, '').trim()
            );
        }
    }
    return null;
}'''

_TAG_GRID_JS = r'''() => {
    for (const div of document.querySelectorAll('div')) {
        const btns = [...div.children].filter(e => e.tagName === 'BUTTON');
        if (btns.length === 36) {
            div.setAttribute('data-maki-grid', '1');
            return true;
        }
    }
    return false;
}'''

_AURA_JS = r'''() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
        if (node.textContent.trim() !== 'AURA') continue;
        let el = node.parentElement;
        for (let i = 0; i < 5; i++) {
            if (!el) break;
            const text = el.innerText || el.textContent || '';
            const m = text.match(/(\d+)/);
            if (m) return parseInt(m[1], 10);
            el = el.parentElement;
        }
    }
    return null;
}'''

_POSSIBLE_MOVES_JS = r'''() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
        const m = node.textContent.trim().match(/^Possible Moves:\s*(\d+)$/);
        if (m) return parseInt(m[1], 10);
    }
    return null;
}'''

_COINS_JS = r'''() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
        const text = node.textContent.trim();
        if (/^\d{1,3}(,\d{3})+$/.test(text)) {
            return parseInt(text.replace(/,/g, ''), 10);
        }
    }
    return null;
}'''

_CHECK_DISABLE_AUDIO_JS = r'''() => {
    const media = [...document.querySelectorAll('audio, video')];
    const wasEnabled = media.some(el => !el.muted);
    media.forEach(el => { el.muted = true; });
    return wasEnabled;
}'''


# ── Game helpers ──────────────────────────────────────────────────────────────

def login(page, username, password):
    page.goto("https://makichat.com/")
    page.get_by_placeholder("me@example.com").fill(username)
    time.sleep(random.uniform(0.2, 0.5))
    page.get_by_placeholder("*********").click()
    page.get_by_placeholder("*********").fill(password)
    time.sleep(random.uniform(0.2, 0.5))
    page.get_by_role("checkbox").check()
    time.sleep(random.uniform(0.1, 0.3))
    page.get_by_role("button", name="Login").click()
    time.sleep(random.uniform(0.8, 1.2))
    page.get_by_label("Dismiss").click()
    time.sleep(random.uniform(0.3, 0.6))


def get_aura_level(page):
    try:
        val = page.evaluate(_AURA_JS)
        return val if val is not None else 0
    except Exception:
        return 0


def get_possible_moves(page):
    try:
        return page.evaluate(_POSSIBLE_MOVES_JS)
    except Exception:
        return None


def get_coin_count(page):
    try:
        return page.evaluate(_COINS_JS)
    except Exception:
        return None


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def print_cycle_stats(cycles, run_start):
    n = len(cycles)
    last_coins, last_secs = cycles[-1]
    total_coins = sum(c for c, _ in cycles)
    total_secs  = time.time() - run_start
    avg_coins   = total_coins / n
    avg_secs    = sum(s for _, s in cycles) / n
    print(
        f"\n── Cycle {n} complete ──────────────────"
        f"\nCoins this cycle:        {last_coins:,}"
        f"\nTime this cycle:         {fmt_time(last_secs)}"
        f"\nAverage coins per cycle: {avg_coins:,.0f}"
        f"\nAverage time per cycle:  {fmt_time(avg_secs)}"
        f"\nTotal coins this run:    {total_coins:,}"
        f"\nTotal time this run:     {fmt_time(total_secs)}\n"
    )


def disable_audio_if_enabled(page):
    try:
        was_enabled = page.evaluate(_CHECK_DISABLE_AUDIO_JS)
        if was_enabled:
            print("[Audio was enabled — muted]")
    except Exception:
        pass


def switch_mode(page, mode):
    try:
        btn = page.get_by_role("button", name=mode).first
        if btn.is_visible(timeout=500):
            btn.click()
            time.sleep(random.uniform(0.3, 0.6))
    except Exception:
        pass


def read_board(page):
    try:
        board = page.evaluate(_READ_BOARD_JS)
        return board if board and len(board) == 36 else []
    except Exception:
        return []


def read_stable_board(page):
    prev = None
    for _ in range(8):
        board = read_board(page)
        if board and board == prev and all(t != '' for t in board):
            return board
        prev = board
        time.sleep(0.25)
    return board or []


def click_tile(page, index):
    page.evaluate(_TAG_GRID_JS)
    page.locator('[data-maki-grid="1"] button').nth(index).click()


# ── Match-3 solver ────────────────────────────────────────────────────────────

def count_matches(board):
    score = 0
    for r in range(ROWS):
        c = 0
        while c < COLS:
            val = board[r * COLS + c]
            run = 1
            while c + run < COLS and board[r * COLS + c + run] == val and val:
                run += 1
            if run >= 3:
                score += run
            c += run
    for c in range(COLS):
        r = 0
        while r < ROWS:
            val = board[r * COLS + c]
            run = 1
            while r + run < ROWS and board[(r + run) * COLS + c] == val and val:
                run += 1
            if run >= 3:
                score += run
            r += run
    return score


def find_best_move(board):
    best_move  = None
    best_score = 0
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in [(0, 1), (1, 0)]:
                r2, c2 = r + dr, c + dc
                if r2 >= ROWS or c2 >= COLS:
                    continue
                if board[r * COLS + c] == board[r2 * COLS + c2]:
                    continue
                sim = board[:]
                sim[r * COLS + c], sim[r2 * COLS + c2] = sim[r2 * COLS + c2], sim[r * COLS + c]
                score = count_matches(sim)
                if score > best_score:
                    best_score = score
                    best_move  = (r, c, r2, c2)
    return best_move


# ── Main game loop ────────────────────────────────────────────────────────────

def play_tile_match(page, state):
    page.locator("div").filter(has_text=re.compile(r"^AURA\d+$")).nth(2).click()
    time.sleep(random.uniform(1.0, 1.5))
    disable_audio_if_enabled(page)

    switch_mode(page, "Coins" if (state["collect_coins"] and state["in_coins_mode"]) else "Aura")
    no_move_streak = 0

    while not state["stop_event"].is_set():
        aura           = get_aura_level(page)
        aura_threshold = state["aura_switch_to_coins"]

        if state["collect_coins"] and not state["in_coins_mode"] and aura >= aura_threshold:
            state["coins_at_coins_start"] = get_coin_count(page)
            switch_mode(page, "Coins")
            state["in_coins_mode"] = True

        elif state["collect_coins"] and state["in_coins_mode"] and aura <= AURA_SWITCH_TO_AURA:
            coins_now = get_coin_count(page)
            if state["coins_at_coins_start"] is not None and coins_now is not None:
                state["cycles"].append(
                    (coins_now - state["coins_at_coins_start"], time.time() - state["cycle_start"])
                )
                print_cycle_stats(state["cycles"], state["run_start"])
            switch_mode(page, "Aura")
            state["in_coins_mode"]        = False
            state["coins_at_coins_start"] = None
            state["cycle_start"]          = time.time()

        possible = get_possible_moves(page)
        if possible is not None and possible == 0:
            switch_mode(page, "Coins" if (state["collect_coins"] and state["in_coins_mode"]) else "Aura")
            time.sleep(1.0)
            continue

        board = read_stable_board(page)
        if not board or all(t == '' for t in board):
            time.sleep(0.5)
            continue

        move = find_best_move(board)
        if move is None:
            no_move_streak += 1
            print(f"[No move found — streak {no_move_streak}/10]")
            if no_move_streak >= 10:
                print("[No valid moves for 10 consecutive reads — triggering board reset]")
                switch_mode(page, "Coins" if (state["collect_coins"] and state["in_coins_mode"]) else "Aura")
                no_move_streak = 0
            time.sleep(1.0)
            continue

        no_move_streak = 0
        r1, c1, r2, c2 = move
        click_tile(page, r1 * COLS + c1)
        time.sleep(random.uniform(0.15, 0.35))
        click_tile(page, r2 * COLS + c2)
        time.sleep(random.uniform(0.9, 1.3))


def run_bot(playwright: Playwright, username, password, collect_coins, aura_threshold, stop_event) -> None:
    browser = playwright.chromium.launch(headless=False, args=["--mute-audio"])
    context = browser.new_context()
    page    = context.new_page()

    state = {
        "run_start":            time.time(),
        "cycles":               [],
        "in_coins_mode":        False,
        "coins_at_coins_start": None,
        "cycle_start":          time.time(),
        "collect_coins":        collect_coins,
        "aura_switch_to_coins": aura_threshold,
        "stop_event":           stop_event,
    }

    while not stop_event.is_set():
        try:
            login(page, username, password)
            play_tile_match(page, state)
        except KeyboardInterrupt:
            break
        except Exception as e:
            if stop_event.is_set():
                break
            print(f"\n[Session dropped: {e}]\nReconnecting in 15s...")
            for _ in range(15):
                if stop_event.is_set():
                    break
                time.sleep(1)
            if stop_event.is_set():
                break
            try:
                page.reload(timeout=15000)
            except Exception:
                try:
                    context.close()
                except Exception:
                    pass
                context = browser.new_context()
                page    = context.new_page()
            print("Reconnected. Resuming...")

    context.close()
    browser.close()
    print("[Bot stopped cleanly]")


# ── Queue writer — redirects print() to the shared log ───────────────────────

class QueueWriter:
    def __init__(self, log_fn):
        self.log_fn = log_fn
        self.buf    = ""

    def write(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self.log_fn(line)

    def flush(self):
        if self.buf:
            self.log_fn(self.buf)
            self.buf = ""


# ── Tab UI ────────────────────────────────────────────────────────────────────

class TileGameTab:
    def __init__(self, frame, log_fn):
        self.frame      = frame
        self.log_fn     = log_fn
        self._stop_event = threading.Event()
        self._bot_thread = None
        self._accounts   = self._load_accounts()
        self._build_ui()

    def _build_ui(self):
        pad = dict(padx=10, pady=5)

        # ── Credentials ──────────────────────────────────────────────────────
        cred = ttk.LabelFrame(self.frame, text="Credentials")
        cred.grid(row=0, column=0, sticky="ew", **pad)

        ttk.Label(cred, text="Email:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.email_var   = tk.StringVar()
        self.email_combo = ttk.Combobox(cred, textvariable=self.email_var, width=30,
                                        values=list(self._accounts.keys()))
        self.email_combo.grid(row=0, column=1, padx=6, pady=4)
        self.email_combo.bind("<<ComboboxSelected>>", self._on_account_selected)

        ttk.Label(cred, text="Password:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.password_var = tk.StringVar()
        ttk.Entry(cred, textvariable=self.password_var, show="*", width=32).grid(
            row=1, column=1, padx=6, pady=4
        )

        # ── Settings ─────────────────────────────────────────────────────────
        settings = ttk.LabelFrame(self.frame, text="Settings")
        settings.grid(row=1, column=0, sticky="ew", **pad)

        self.collect_coins_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text="Collect Coins",
                        variable=self.collect_coins_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )

        ttk.Label(settings, text="Aura before switching to Coins:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.aura_var = tk.IntVar(value=5)
        ttk.Spinbox(settings, from_=1, to=999, textvariable=self.aura_var, width=6).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        # ── Controls ─────────────────────────────────────────────────────────
        ctrl = ttk.Frame(self.frame)
        ctrl.grid(row=2, column=0, pady=6)

        self.start_btn = ttk.Button(ctrl, text="Start", width=12, command=self._start)
        self.start_btn.grid(row=0, column=0, padx=6)

        self.stop_btn = ttk.Button(ctrl, text="Stop", width=12,
                                   command=self._stop, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=6)

    # ── Account persistence ───────────────────────────────────────────────────

    def _load_accounts(self):
        try:
            with open(ACCOUNTS_FILE) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_accounts(self, email, password):
        self._accounts[email] = password
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(self._accounts, f, indent=2)
        self.email_combo.config(values=list(self._accounts.keys()))

    def _on_account_selected(self, _event=None):
        email = self.email_var.get()
        if email in self._accounts:
            self.password_var.set(self._accounts[email])

    # ── Bot control ───────────────────────────────────────────────────────────

    def _start(self):
        email    = self.email_var.get().strip()
        password = self.password_var.get().strip()
        if not email or not password:
            self.log_fn("[Error] Please enter email and password.")
            return

        self._save_accounts(email, password)
        self._stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        collect_coins  = self.collect_coins_var.get()
        aura_threshold = self.aura_var.get()
        self.log_fn(f"[Tile Game] Starting — aura threshold: {aura_threshold}, "
                    f"coins: {'on' if collect_coins else 'off'}")

        self._bot_thread = threading.Thread(
            target=self._run_bot,
            args=(email, password, collect_coins, aura_threshold),
            daemon=True,
        )
        self._bot_thread.start()

    def _stop(self):
        self._stop_event.set()
        self.log_fn("[Tile Game] Stop requested — finishing current move...")
        self.stop_btn.config(state="disabled")

    def _run_bot(self, username, password, collect_coins, aura_threshold):
        original_stdout = sys.stdout
        sys.stdout = QueueWriter(self.log_fn)
        try:
            with sync_playwright() as playwright:
                run_bot(playwright, username, password, collect_coins, aura_threshold, self._stop_event)
        except Exception as e:
            self.log_fn(f"[Tile Game] Fatal error: {e}")
        finally:
            sys.stdout = original_stdout
            self.frame.after(0, self._on_bot_done)

    def _on_bot_done(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.log_fn("[Tile Game] Bot stopped")


# ── Plugin entry point ────────────────────────────────────────────────────────

def build_tab(frame, log_fn):
    TileGameTab(frame, log_fn)
