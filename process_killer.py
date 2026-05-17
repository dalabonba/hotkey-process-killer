import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import psutil
import json
import os
import sys
import threading
import ctypes
import time
from datetime import datetime

# 打包成 exe 後，__file__ 會指向暫存目錄；用 sys.executable 取得 exe 所在位置
if getattr(sys, "frozen", False):
    # 以 PyInstaller 打包後執行
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    # 一般 Python 腳本執行
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")

# ── 顏色主題 ──────────────────────────────────────────────
BG        = "#0f0f13"
BG2       = "#1a1a24"
BG3       = "#22222f"
ACCENT    = "#ff4d6d"
ACCENT2   = "#ff8fa3"
GREEN     = "#39d353"
YELLOW    = "#ffd166"
TEXT      = "#e8e8f0"
TEXT_DIM  = "#7070a0"
BORDER    = "#2e2e45"
FONT_MAIN = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")
FONT_TITLE= ("Consolas", 18, "bold")
FONT_SUB  = ("Consolas", 9)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


class ProcessKillerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Process Killer — 快捷鍵進程終結器")
        self.root.geometry("700x540")
        self.root.minsize(700, 540)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.shortcuts = {}       # hotkey -> process_name
        self.kill_counts = {}     # hotkey -> int
        self.hotkey_handlers = {} # hotkey -> handler id returned by keyboard.add_hotkey
        self.log_entries = []

        # Initialize logging
        self._log("\n" + "="*80)
        self._log(f"🚀 PROCESS KILLER INITIALIZED - Admin: {is_admin()}")
        self._log(f"   Base Dir: {_BASE_DIR}")
        self._log(f"   Config File: {CONFIG_FILE}")
        self._log("="*80)

        self.load_config()
        self._build_ui()
        self._register_all_hotkeys()
        # start watchdog to periodically refresh/re-register hotkeys
        threading.Thread(target=self._hotkey_watchdog_loop, daemon=True).start()
        self._update_process_status()

    # ── UI 建構 ────────────────────────────────────────────
    def _build_ui(self):
        # 頂部標題列
        header = tk.Frame(self.root, bg=BG, pady=12)
        header.pack(fill=tk.X, padx=20)

        tk.Label(header, text="⚡ PROCESS KILLER", font=FONT_TITLE,
                 fg=ACCENT, bg=BG).pack(side=tk.LEFT)

        admin_text = "🔑 管理員模式" if is_admin() else "⚠ 一般模式（部分進程可能無法終止）"
        admin_color = GREEN if is_admin() else YELLOW
        tk.Label(header, text=admin_text, font=FONT_SUB,
                 fg=admin_color, bg=BG).pack(side=tk.RIGHT, pady=4)

        # 分隔線
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        # 新增區塊
        add_frame = tk.Frame(self.root, bg=BG2, pady=12)
        add_frame.pack(fill=tk.X, padx=0)

        inner = tk.Frame(add_frame, bg=BG2)
        inner.pack(padx=20)

        tk.Label(inner, text="進程名稱", font=FONT_SUB, fg=TEXT_DIM, bg=BG2).grid(
            row=0, column=0, sticky="w", padx=(0, 4))
        tk.Label(inner, text="快捷鍵", font=FONT_SUB, fg=TEXT_DIM, bg=BG2).grid(
            row=0, column=2, sticky="w", padx=(16, 4))

        self.proc_var = tk.StringVar()
        proc_entry = tk.Entry(inner, textvariable=self.proc_var, width=22,
                              font=FONT_MAIN, bg=BG3, fg=TEXT,
                              insertbackground=ACCENT, relief=tk.FLAT,
                              highlightthickness=1, highlightcolor=ACCENT,
                              highlightbackground=BORDER)
        proc_entry.grid(row=1, column=0, ipady=6, padx=(0, 4))
        proc_entry.insert(0, "例: chrome.exe")
        proc_entry.bind("<FocusIn>",  lambda e: self._clear_placeholder(self.proc_var, "例: chrome.exe"))
        proc_entry.bind("<FocusOut>", lambda e: self._restore_placeholder(self.proc_var, "例: chrome.exe"))

        tk.Label(inner, text="→", font=FONT_BOLD, fg=ACCENT, bg=BG2).grid(row=1, column=1, padx=4)

        self.hotkey_var = tk.StringVar()
        hk_entry = tk.Entry(inner, textvariable=self.hotkey_var, width=22,
                            font=FONT_MAIN, bg=BG3, fg=TEXT,
                            insertbackground=ACCENT, relief=tk.FLAT,
                            highlightthickness=1, highlightcolor=ACCENT,
                            highlightbackground=BORDER)
        hk_entry.grid(row=1, column=2, ipady=6, padx=(16, 8))
        hk_entry.insert(0, "例: ctrl+shift+k")
        hk_entry.bind("<FocusIn>",  lambda e: self._clear_placeholder(self.hotkey_var, "例: ctrl+shift+k"))
        hk_entry.bind("<FocusOut>", lambda e: self._restore_placeholder(self.hotkey_var, "例: ctrl+shift+k"))
        hk_entry.bind("<Return>", lambda e: self._add_shortcut())

        add_btn = tk.Button(inner, text="＋ 新增", font=FONT_BOLD,
                            bg=ACCENT, fg="white", relief=tk.FLAT,
                            activebackground=ACCENT2, activeforeground="white",
                            cursor="hand2", padx=16, pady=6,
                            command=self._add_shortcut)
        add_btn.grid(row=1, column=3, padx=(4, 0))

        # 說明文字
        tk.Label(inner, text="快捷鍵格式: ctrl+shift+k  /  alt+F4  /  win+q",
                 font=FONT_SUB, fg=TEXT_DIM, bg=BG2).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        # 主列表
        list_frame = tk.Frame(self.root, bg=BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Kill.Treeview",
                         background=BG2, foreground=TEXT,
                         fieldbackground=BG2, font=FONT_MAIN,
                         rowheight=28, borderwidth=0)
        style.configure("Kill.Treeview.Heading",
                         background=BG3, foreground=TEXT_DIM,
                         font=FONT_BOLD, relief="flat")
        style.map("Kill.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

        cols = ("process", "hotkey", "running", "kills")
        self.tree = ttk.Treeview(list_frame, columns=cols,
                                  show="headings", style="Kill.Treeview",
                                  height=10)
        self.tree.heading("process", text="⬛  進程名稱")
        self.tree.heading("hotkey",  text="⌨  快捷鍵")
        self.tree.heading("running", text="狀態")
        self.tree.heading("kills",   text="已終止次數")
        self.tree.column("process", width=200, anchor="w")
        self.tree.column("hotkey",  width=200, anchor="w")
        self.tree.column("running", width=100, anchor="center")
        self.tree.column("kills",   width=100, anchor="center")

        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部按鈕列
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)
        btn_bar = tk.Frame(self.root, bg=BG, pady=10)
        btn_bar.pack(fill=tk.X, padx=20)

        def btn(parent, text, cmd, color):
            return tk.Button(parent, text=text, font=FONT_BOLD,
                             bg=color, fg="white", relief=tk.FLAT,
                             activebackground=color, activeforeground="white",
                             cursor="hand2", padx=14, pady=5, command=cmd)

        btn(btn_bar, "🗑  刪除選取", self._delete_shortcut, "#c0392b").pack(side=tk.LEFT, padx=(0, 8))
        btn(btn_bar, "⚡ 立刻手動終止", self._manual_kill, ACCENT).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="就緒 — 所有快捷鍵監聽中")
        self.status_label = tk.Label(btn_bar, textvariable=self.status_var, font=FONT_SUB,
                                     fg=GREEN, bg=BG, anchor="e")
        self.status_label.pack(side=tk.RIGHT)

        self._refresh_tree()
        self._tick_status()

    # ── 快捷鍵邏輯 ─────────────────────────────────────────
    def _add_shortcut(self):
        proc   = self.proc_var.get().strip()
        hotkey = self.hotkey_var.get().strip().lower()

        placeholders = {"例: chrome.exe", "例: ctrl+shift+k"}
        if not proc or proc in placeholders:
            messagebox.showwarning("缺少資料", "請輸入進程名稱（例: chrome.exe）")
            return
        if not hotkey or hotkey in placeholders:
            messagebox.showwarning("缺少資料", "請輸入快捷鍵（例: ctrl+shift+k）")
            return
        if hotkey in self.shortcuts:
            messagebox.showwarning("重複", f"快捷鍵「{hotkey}」已被使用，請換一個。")
            return

        try:
            self._log(f"➕ adding new shortcut: {hotkey} -> {proc}")
            handler = keyboard.add_hotkey(hotkey, self._kill_process, args=[proc, hotkey])
            self.shortcuts[hotkey] = proc
            self.kill_counts[hotkey] = 0
            # store handler so we can remove/refresh later
            self.hotkey_handlers[hotkey] = handler
            self._log(f"✅ successfully added {hotkey} -> {proc} (handler_id: {id(handler)})")
            self._refresh_tree()
            self._save_config()
            self._set_status(f"✅ 已新增  {hotkey}  →  {proc}", GREEN)
            self.proc_var.set("")
            self.hotkey_var.set("")
        except Exception as e:
            self._log(f"❌ failed to add shortcut {hotkey} -> {proc}: {type(e).__name__}: {e}")
            messagebox.showerror("快捷鍵錯誤", f"無法註冊快捷鍵:\n{e}\n\n請確認格式正確。")

    def _kill_process(self, process_name, hotkey):
        # log invocation with detailed info
        try:
            self._log(f"🔥 HOTKEY TRIGGERED: {hotkey} -> {process_name}")
        except Exception:
            pass
        killed = 0
        errors = []
        target_name = process_name.lower()
        matched_pids = []
        for proc in psutil.process_iter(["name", "pid"]):
            name = proc.info.get("name")
            pid = proc.info.get("pid")
            if not name:
                continue
            try:
                if name.lower() == target_name:
                    matched_pids.append(pid)
                    proc.kill()
                    killed += 1
                    self._log(f"  └─ killed process: {name} (PID: {pid})")
            except psutil.AccessDenied:
                errors.append(f"AccessDenied({pid})")
                self._log(f"  └─ AccessDenied: {name} (PID: {pid})")
            except psutil.NoSuchProcess:
                pass
            except Exception as ex:
                errors.append(str(ex))
                self._log(f"  └─ Exception: {name} (PID: {pid}) - {ex}")

        self.kill_counts[hotkey] = self.kill_counts.get(hotkey, 0) + killed

        if killed > 0:
            msg = f"⚡ 已終止 {killed} 個「{process_name}」"
            self._log(f"✅ SUCCESS: killed {killed} of {process_name} | PIDs: {matched_pids}")
        elif errors:
            msg = f"🔒 無法終止「{process_name}」— 請以管理員身分執行"
            self._log(f"❌ PERMISSION ERROR: {process_name} - errors: {errors}")
        else:
            msg = f"🔍 找不到執行中的「{process_name}」"
            self._log(f"⚠️  NOT FOUND: {process_name} is not running")

        color = GREEN if killed > 0 else (YELLOW if errors else TEXT_DIM)
        self.root.after(0, lambda: self._set_status(msg, color))
        self.root.after(0, self._refresh_tree)

    def _manual_kill(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "請先在列表中選取一個項目")
            return
        vals = self.tree.item(sel[0])["values"]
        proc, hotkey = vals[0], vals[1]
        threading.Thread(target=self._kill_process,
                         args=(proc, hotkey), daemon=True).start()

    def _delete_shortcut(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "請先選取要刪除的項目")
            return
        for item in sel:
            vals  = self.tree.item(item)["values"]
            hotkey = vals[1]
            self._log(f"🗑️  deleting shortcut: {hotkey}")
            try:
                # try to remove by stored handler first
                handler = self.hotkey_handlers.pop(hotkey, None)
                if handler is not None:
                    try:
                        keyboard.remove_hotkey(handler)
                        self._log(f"  ├─ removed handler for {hotkey}")
                    except Exception as e:
                        # fallback to removing by hotkey string
                        self._log(f"  ├─ handler removal failed, fallback to string remove: {e}")
                        keyboard.remove_hotkey(hotkey)
                else:
                    self._log(f"  ├─ no handler found, using string remove")
                    keyboard.remove_hotkey(hotkey)
            except Exception as e:
                self._log(f"  └─ failed to remove hotkey {hotkey}: {type(e).__name__}: {e}")
            self.shortcuts.pop(hotkey, None)
            self.kill_counts.pop(hotkey, None)
        self._refresh_tree()
        self._save_config()
        self._set_status("🗑 已刪除選取的快捷鍵", YELLOW)

    def _register_all_hotkeys(self):
        total = len(self.shortcuts)
        self._log(f"📋 registering {total} hotkeys from config...")
        for i, (hotkey, proc) in enumerate(self.shortcuts.items(), 1):
            try:
                # register and store handler id
                handler = keyboard.add_hotkey(hotkey, self._kill_process, args=[proc, hotkey])
                self.hotkey_handlers[hotkey] = handler
                self._log(f"  ✓ [{i}/{total}] registered {hotkey} -> {proc}")
            except Exception as e:
                self._log(f"  ✗ [{i}/{total}] FAILED to register {hotkey}: {type(e).__name__}: {e}")

    # ── 進程狀態輪詢 ───────────────────────────────────────
    def _update_process_status(self):
        self._refresh_tree()
        self.root.after(3000, self._update_process_status)

    def _is_running(self, name):
        name_lo = name.lower()
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"].lower() == name_lo:
                    return True
            except Exception:
                pass
        return False

    # ── 樹狀列表 ───────────────────────────────────────────
    def _refresh_tree(self):
        selected_hotkeys = []
        for item in self.tree.selection():
            try:
                vals = self.tree.item(item)["values"]
                if len(vals) > 1:
                    selected_hotkeys.append(vals[1])
            except Exception:
                pass

        for item in self.tree.get_children():
            self.tree.delete(item)

        selected_items = []
        for hotkey, proc in self.shortcuts.items():
            running = self._is_running(proc)
            status  = "● 執行中" if running else "○ 未執行"
            kills   = self.kill_counts.get(hotkey, 0)
            item_id = self.tree.insert("", tk.END, values=(proc, hotkey, status, kills))
            if hotkey in selected_hotkeys:
                selected_items.append(item_id)

        if selected_items:
            try:
                self.tree.selection_set(selected_items)
            except Exception:
                pass

    # ── 狀態列 ─────────────────────────────────────────────
    def _set_status(self, text, color=GREEN):
        self.status_var.set(text)
        self.status_label.configure(fg=color)
        def reset_status():
            self.status_var.set("就緒 — 所有快捷鍵監聽中")
            self.status_label.configure(fg=GREEN)
        self.root.after(4000, reset_status)

    def _tick_status(self):
        self.root.after(5000, self._tick_status)

    # ── 輸入框 placeholder ─────────────────────────────────
    def _clear_placeholder(self, var, placeholder):
        if var.get() == placeholder:
            var.set("")

    def _restore_placeholder(self, var, placeholder):
        if var.get().strip() == "":
            var.set(placeholder)

    def _log(self, msg: str):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # ms precision
            thread_id = threading.current_thread().name
            handlers_count = len(self.hotkey_handlers)
            fn = os.path.join(_BASE_DIR, "process_killer.log")
            with open(fn, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{thread_id}] [H:{handlers_count}] {msg}\n")
        except Exception:
            pass

    def _hotkey_watchdog_loop(self):
        # Periodically refresh hotkey registrations to recover from lost hooks
        self._log("🐕 WATCHDOG: started (60s interval)")
        cycle = 0
        while True:
            try:
                cycle += 1
                total = len(self.shortcuts)
                if total > 0:
                    self._log(f"🔄 WATCHDOG CYCLE {cycle}: checking {total} hotkeys...")
                for hotkey, proc in list(self.shortcuts.items()):
                    try:
                        # remove stale handler if any
                        handler = self.hotkey_handlers.get(hotkey)
                        if handler is not None:
                            try:
                                keyboard.remove_hotkey(handler)
                                self._log(f"  ├─ removed stale handler for {hotkey}")
                            except Exception as e:
                                self._log(f"  ├─ remove_hotkey failed for {hotkey}: {e}")
                        # re-register
                        new_handler = keyboard.add_hotkey(hotkey, self._kill_process, args=[proc, hotkey])
                        self.hotkey_handlers[hotkey] = new_handler
                        self._log(f"  └─ re-registered {hotkey} -> {proc} (handler_id: {id(new_handler)})")
                    except Exception as e:
                        self._log(f"  ❌ watchdog FAILED for {hotkey}: {type(e).__name__}: {e}")
                if total > 0:
                    self._log(f"🔄 WATCHDOG CYCLE {cycle}: completed")
                time.sleep(60)
            except Exception as e:
                self._log(f"❌ WATCHDOG LOOP FATAL ERROR: {type(e).__name__}: {e}")
                time.sleep(60)

    # ── 設定檔 ─────────────────────────────────────────────
    def _save_config(self):
        data = {"shortcuts": self.shortcuts, "kill_counts": self.kill_counts}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.shortcuts   = data.get("shortcuts", {})
                self.kill_counts = data.get("kill_counts", {})
                self._log(f"📂 loaded config: {len(self.shortcuts)} shortcuts, {sum(self.kill_counts.values())} total kills")
                for hk, proc in list(self.shortcuts.items())[:3]:
                    self._log(f"   - {hk} -> {proc}")
                if len(self.shortcuts) > 3:
                    self._log(f"   ... and {len(self.shortcuts) - 3} more")
            except Exception as e:
                self._log(f"⚠ failed to load config: {type(e).__name__}: {e}")
                self.shortcuts   = {}
                self.kill_counts = {}
        else:
            self._log(f"ℹ config file not found, starting fresh (expected: {CONFIG_FILE})")
            self.shortcuts   = {}
            self.kill_counts = {}

    def on_closing(self):
        self._log(f"🛑 SHUTTING DOWN - {len(self.shortcuts)} shortcuts, {len(self.kill_counts)} total kills")
        try:
            keyboard.unhook_all_hotkeys()
            self._log("   ✓ unhook_all_hotkeys() called")
        except Exception as e:
            self._log(f"   ⚠ unhook_all_hotkeys() error: {e}")
        try:
            keyboard.unhook_all()
            self._log("   ✓ unhook_all() called")
        except Exception as e:
            self._log(f"   ⚠ unhook_all() error: {e}")
        try:
            self.root.quit()
            self._log("   ✓ root.quit() called")
        except Exception as e:
            self._log(f"   ⚠ root.quit() error: {e}")
        try:
            self.root.destroy()
            self._log("   ✓ root.destroy() called")
        except Exception as e:
            self._log(f"   ⚠ root.destroy() error: {e}")
        self._log("🏁 SHUTDOWN COMPLETE\n")
        if getattr(sys, "frozen", False):
            sys.exit(0)


# ── 主程式進入點 ───────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = ProcessKillerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
