import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import psutil
import json
import os
import sys
import threading
import ctypes

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
        self.log_entries = []

        self.load_config()
        self._build_ui()
        self._register_all_hotkeys()
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
            keyboard.add_hotkey(hotkey, self._kill_process, args=[proc, hotkey])
            self.shortcuts[hotkey] = proc
            self.kill_counts[hotkey] = 0
            self._refresh_tree()
            self._save_config()
            self._set_status(f"✅ 已新增  {hotkey}  →  {proc}", GREEN)
            self.proc_var.set("")
            self.hotkey_var.set("")
        except Exception as e:
            messagebox.showerror("快捷鍵錯誤", f"無法註冊快捷鍵:\n{e}\n\n請確認格式正確。")

    def _kill_process(self, process_name, hotkey):
        killed = 0
        errors = []
        target_name = process_name.lower()
        for proc in psutil.process_iter(["name", "pid"]):
            name = proc.info.get("name")
            if not name:
                continue
            try:
                if name.lower() == target_name:
                    proc.kill()
                    killed += 1
            except psutil.AccessDenied:
                errors.append("AccessDenied")
            except psutil.NoSuchProcess:
                pass
            except Exception as ex:
                errors.append(str(ex))

        self.kill_counts[hotkey] = self.kill_counts.get(hotkey, 0) + killed

        if killed > 0:
            msg = f"⚡ 已終止 {killed} 個「{process_name}」"
        elif errors:
            msg = f"🔒 無法終止「{process_name}」— 請以管理員身分執行"
        else:
            msg = f"🔍 找不到執行中的「{process_name}」"

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
            try:
                keyboard.remove_hotkey(hotkey)
            except Exception:
                pass
            self.shortcuts.pop(hotkey, None)
            self.kill_counts.pop(hotkey, None)
        self._refresh_tree()
        self._save_config()
        self._set_status("🗑 已刪除選取的快捷鍵", YELLOW)

    def _register_all_hotkeys(self):
        for hotkey, proc in self.shortcuts.items():
            try:
                keyboard.add_hotkey(hotkey, self._kill_process, args=[proc, hotkey])
            except Exception:
                pass

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
        for item in self.tree.get_children():
            self.tree.delete(item)
        for hotkey, proc in self.shortcuts.items():
            running = self._is_running(proc)
            status  = "🟢 執行中" if running else "⚫ 未執行"
            kills   = self.kill_counts.get(hotkey, 0)
            self.tree.insert("", tk.END, values=(proc, hotkey, status, kills))

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
            except Exception:
                self.shortcuts   = {}
                self.kill_counts = {}
        else:
            self.shortcuts   = {}
            self.kill_counts = {}

    def on_closing(self):
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook_all()
        except Exception:
            pass
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        if getattr(sys, "frozen", False):
            sys.exit(0)


# ── 主程式進入點 ───────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = ProcessKillerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
