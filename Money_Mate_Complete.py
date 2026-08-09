# ============================================================
# MONEY MATE - COMPLETE EDITION 
# Features: Income Tracking, Date Filters, Budget Alerts, Charts,
# Custom Categories, All-Time Totals, Scrollable Budgets
# ============================================================

import json
import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# ---- Charts ke liye matplotlib (agar installed ho to) ----
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# ============================================================
# STEP 1: DATA FILE SETUP
# ============================================================

FILE_NAME = "money_mate_data.json"
# NEW FEATURE: hamesha pichli successful save ki ek copy rakhi jati hai. Agar
# kabhi main file crash/corrupt ho jaye (e.g. app beech mein band ho jaye
# save karte waqt), to app khud is backup se recover kar leta hai.
BACKUP_FILE_NAME = "money_mate_data.backup.json"

DEFAULT_EXPENSE_CATEGORIES = ["Food", "Transport", "Shopping", "Education", "Health", "Entertainment", "Bills", "Other"]
DEFAULT_INCOME_CATEGORIES = ["Salary", "Freelance", "Business", "Investment", "Gift", "Other Income"]

# NEW FEATURE: Budget limits ab per-month "history" ki tarah save hote hain.
# Jis mahine jo limit set karo wahi us mahine se lagu ho jati hai aur aage
# (jab tak dobara change na ho) carry-forward hoti rehti hai — purane mahine
# untouched rehte hain. Sab se purana "epoch" key (BUDGET_EPOCH) hamesha
# maujood rehti hai taake har mahine ke liye koi na koi baseline mil jaye.
BUDGET_EPOCH = "2000-01"

# ---- Default data structure ----
def get_default_data():
    default_budgets = {
        "Food": 10000,
        "Transport": 5000,
        "Shopping": 8000,
        "Education": 5000,
        "Health": 5000,
        "Entertainment": 3000,
        "Bills": 10000,
        "Other": 2000
    }
    return {
        "transactions": [],
        # budget_history: { "YYYY-MM": {category: limit, ...}, ... }
        "budget_history": {
            BUDGET_EPOCH: default_budgets
        },
        # FIX (Issue 1): categories ab data file mein save hoti hain
        # taake user ki khud banayi hui (custom) categories bhi persist rahein
        "categories": {
            "expense": list(DEFAULT_EXPENSE_CATEGORIES),
            "income": list(DEFAULT_INCOME_CATEGORIES)
        }
    }

def get_budgets_for_month(data, month_date):
    """Diye gaye mahine (month_date, koi bhi date usi month ki) ke liye
    'effective' budget limits nikalta hai — yani sab se qareeb wala pichla
    saved snapshot (isi mahine ya us se pehle), taake carry-forward sahi
    kaam kare aur purane mahine apni asli limit par hi rahein."""
    target_key = month_date.strftime("%Y-%m")
    history = data.get("budget_history", {})
    applicable_keys = sorted(k for k in history.keys() if k <= target_key)
    if not applicable_keys:
        return {}
    return dict(history[applicable_keys[-1]])

def set_budgets_for_month(data, month_date, new_values):
    """Diye gaye mahine ke liye budget snapshot save karta hai. Baqi (na-badli
    hui) categories ki purani effective value bhi is snapshot mein carry
    hoti hai, taake future carry-forward theek se chalta rahe."""
    target_key = month_date.strftime("%Y-%m")
    effective = get_budgets_for_month(data, month_date)
    effective.update(new_values)
    data.setdefault("budget_history", {})[target_key] = effective

# ---- File load karna (purani format ko bhi support kare) ----
def load_data():
    if not os.path.exists(FILE_NAME):
        data = get_default_data()
        save_data(data)
        return data

    # FIX: pehle agar file corrupt (invalid JSON) ya beech mein truncated ho
    # jati (e.g. app crash hote waqt save ke dauran), to chup chaap saara data
    # khali kar diya jata tha (get_default_data() se overwrite). Ab pehle
    # automatically backup file se recover karne ki koshish hoti hai, aur agar
    # woh bhi na chale to purani (corrupt) file ko delete karne ki bajaye
    # ".corrupted" naam se mehfooz kar dete hain taake manually dekhi ja sake.
    try:
        with open(FILE_NAME, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        data = None
        if os.path.exists(BACKUP_FILE_NAME):
            try:
                with open(BACKUP_FILE_NAME, "r", encoding="utf-8") as file:
                    data = json.load(file)
                messagebox.showwarning(
                    "Data Recovered",
                    "Your main data file looked corrupted, so Money Mate restored "
                    "your most recent automatic backup instead.\n\n"
                    "Some very recent changes (since the last save) may be missing."
                )
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                data = None

        if data is None:
            try:
                shutil.copyfile(FILE_NAME, FILE_NAME + ".corrupted")
            except OSError:
                pass
            messagebox.showerror(
                "Data Error",
                "Both the main data file and its backup appear to be corrupted.\n\n"
                f"Starting with a fresh file. Your old file has been saved as "
                f"'{FILE_NAME}.corrupted' in case you want to inspect or recover it manually."
            )
            data = get_default_data()

    # Purani format (sirf list) ko new format mein convert karna
    if isinstance(data, list):
        new_data = get_default_data()
        for item in data:
            if "type" not in item:
                item["type"] = "expense"
            if "id" not in item:
                item["id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
            new_data["transactions"].append(item)
        save_data(new_data)
        return new_data

    # Migration: purani flat "budgets" dict ko budget_history mein convert karna
    if "budget_history" not in data:
        old_budgets = data.get("budgets", get_default_data()["budget_history"][BUDGET_EPOCH])
        data["budget_history"] = {BUDGET_EPOCH: dict(old_budgets)}
    data.pop("budgets", None)

    # Ensure categories exist (purani save files mein yeh key nahi hogi)
    if "categories" not in data:
        data["categories"] = {
            "expense": list(DEFAULT_EXPENSE_CATEGORIES),
            "income": list(DEFAULT_INCOME_CATEGORIES)
        }

    # Ensure all transactions have IDs, aur unki category bhi list mein shamil ho
    for t in data.get("transactions", []):
        if "id" not in t:
            t["id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
        if "type" not in t:
            t["type"] = "expense"
        cat_type = "income" if t["type"] == "income" else "expense"
        if t.get("category") and t["category"] not in data["categories"][cat_type]:
            data["categories"][cat_type].append(t["category"])

    return data

def save_data(data):
    # FIX: pehle seedha FILE_NAME par likha jata tha — agar app is dauran
    # crash ho jaye to file aadhi likhi hui (corrupt) reh sakti thi. Ab:
    # 1) pehle ek temp file mein poora data likhte hain,
    # 2) phir purani file ko backup ke tor par mehfooz karte hain,
    # 3) phir temp file ko atomically asal file ki jagah rename karte hain
    #    (os.replace ek hi step mein hota hai, isliye beech mein crash hone
    #    par bhi purani ya nayi file mukammal hi milegi, adhoori nahi).
    tmp_path = FILE_NAME + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    if os.path.exists(FILE_NAME):
        try:
            shutil.copyfile(FILE_NAME, BACKUP_FILE_NAME)
        except OSError:
            pass  # backup best-effort hai, save ko na roke

    os.replace(tmp_path, FILE_NAME)

def ensure_category(data, cat_type, cat_name):
    """Agar category naam list mein maujood nahi to naya add kar deta hai
    (Issue 1 fix: user apni marzi ki category likh kar bana sakta hai)"""
    cat_name = (cat_name or "").strip()
    if not cat_name:
        return
    lst = data["categories"][cat_type]
    if cat_name not in lst:
        lst.append(cat_name)

# ============================================================
# STEP 2: MAIN WINDOW
# ============================================================

root = tk.Tk()
root.title("Money Mate - Complete Edition")
root.geometry("1200x850")
root.configure(bg="#eef1f5")
root.minsize(1100, 700)

# ============================================================
# STEP 3: STYLES & CONSTANTS
# ============================================================

LABEL_FONT = ("Segoe UI", 11, "bold")
ENTRY_FONT = ("Segoe UI", 11)
CARD_FONT = ("Segoe UI", 10)
CARD_VALUE_FONT = ("Segoe UI", 16, "bold")

colors = {
    "primary": "#2c3e50",
    "success": "#27ae60",
    "danger": "#c0392b",
    "warning": "#f39c12",
    "info": "#2980b9",
    "purple": "#8e44ad",
    "grey": "#7f8c8d",
    "white": "#ffffff",
    "bg": "#eef1f5",
    "card_bg": "#ffffff",
    "income": "#27ae60",
    "expense": "#c0392b",
    "balance_pos": "#27ae60",
    "balance_neg": "#c0392b"
}

# In-memory lists, hamesha data file se sync rehti hain (sync_category_lists() call se)
expense_categories = list(DEFAULT_EXPENSE_CATEGORIES)
income_categories = list(DEFAULT_INCOME_CATEGORIES)

def sync_category_lists(data):
    """expense_categories / income_categories ko data file ke mutabiq update karta hai"""
    expense_categories[:] = data["categories"]["expense"]
    income_categories[:] = data["categories"]["income"]

# ============================================================
# STEP 4: HEADING
# ============================================================

heading = tk.Label(
    root, text="Money Mate", font=("Segoe UI", 24, "bold"),
    bg=colors["primary"], fg="white", pady=15
)
heading.pack(fill="x")

# ============================================================
# STEP 5: TOP SECTION - Input Form + Dashboard Cards
# ============================================================

top_frame = tk.Frame(root, bg=colors["bg"])
top_frame.pack(padx=20, pady=15, fill="x")

# ---- LEFT: Input Form ----
input_frame = tk.Frame(top_frame, bg="white", padx=20, pady=15, relief="solid", bd=1)
input_frame.pack(side="left", fill="y")

# Type (Income/Expense)
tk.Label(input_frame, text="Type", bg="white", font=LABEL_FONT).grid(row=0, column=0, padx=8, pady=6, sticky="w")
type_var = tk.StringVar(value="expense")
type_combo = ttk.Combobox(input_frame, textvariable=type_var, font=ENTRY_FONT, width=22, values=["expense", "income"], state="readonly")
type_combo.grid(row=0, column=1, padx=8, pady=6, sticky="w")

# Date
tk.Label(input_frame, text="Date", bg="white", font=LABEL_FONT).grid(row=1, column=0, padx=8, pady=6, sticky="w")
date_entry = tk.Entry(input_frame, font=ENTRY_FONT, width=24)
date_entry.grid(row=1, column=1, padx=8, pady=6, sticky="w")
date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

# Category
# FIX (Issue 1): state="normal" (readonly ki jagah) taake user dropdown se choose
# bhi kar sake AUR khud apni marzi ki nayi category type bhi kar sake.
tk.Label(input_frame, text="Category", bg="white", font=LABEL_FONT).grid(row=2, column=0, padx=8, pady=6, sticky="w")
category = ttk.Combobox(input_frame, font=ENTRY_FONT, width=22, values=expense_categories, state="normal")
category.grid(row=2, column=1, padx=8, pady=6, sticky="w")
category.set(expense_categories[0])

# Description
tk.Label(input_frame, text="Description", bg="white", font=LABEL_FONT).grid(row=3, column=0, padx=8, pady=6, sticky="w")
description = tk.Entry(input_frame, font=ENTRY_FONT, width=24)
description.grid(row=3, column=1, padx=8, pady=6, sticky="w")

# Amount
tk.Label(input_frame, text="Amount (Rs.)", bg="white", font=LABEL_FONT).grid(row=4, column=0, padx=8, pady=6, sticky="w")
amount = tk.Entry(input_frame, font=ENTRY_FONT, width=24)
amount.grid(row=4, column=1, padx=8, pady=6, sticky="w")

# Form ke end mein chota "Clear" button (sirf isi form ki fields reset karta hai)
# Neeche action-bar wala "Clear" ab poora record reset karega, isliye yeh alag rakha hai.
form_clear_btn = tk.Button(input_frame, text="Clear Form", command=lambda: clear_fields(),
                           bg=colors["grey"], fg="white", font=("Segoe UI", 9, "bold"),
                           padx=10, pady=3, relief="flat", cursor="hand2")
form_clear_btn.grid(row=5, column=1, padx=8, pady=(10, 0), sticky="e")

# ---- Category update on type change ----
def on_type_change(event=None):
    t = type_var.get()
    if t == "income":
        category.config(values=income_categories)
        if income_categories:
            category.set(income_categories[0])
    else:
        category.config(values=expense_categories)
        if expense_categories:
            category.set(expense_categories[0])

type_combo.bind("<<ComboboxSelected>>", on_type_change)

# ---- RIGHT: Dashboard Cards ----
dashboard_frame = tk.Frame(top_frame, bg=colors["bg"])
dashboard_frame.pack(side="right", fill="both", expand=True, padx=(15, 0))

# Card banane ka helper
def create_card(parent, title, value, color, row, col):
    card = tk.Frame(parent, bg="white", padx=20, pady=15, relief="solid", bd=1)
    card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
    tk.Label(card, text=title, bg="white", font=CARD_FONT, fg=colors["grey"]).pack(anchor="w")
    lbl = tk.Label(card, text=value, bg="white", font=CARD_VALUE_FONT, fg=color)
    lbl.pack(anchor="w", pady=(5, 0))
    return lbl

# Row 0: Summary Cards
dashboard_frame.columnconfigure(0, weight=1)
dashboard_frame.columnconfigure(1, weight=1)
dashboard_frame.columnconfigure(2, weight=1)

# Small label showing which period the 3 cards below currently reflect
# (FIX: cards ab Filter bar ke sath sync hain, isliye yahan clearly dikhta hai
# ke abhi kis period ka data dikh raha hai)
dashboard_period_label = tk.Label(dashboard_frame, text="Showing: All Time", bg=colors["bg"],
                                   font=("Segoe UI", 9, "italic"), fg=colors["grey"])
dashboard_period_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

balance_label = create_card(dashboard_frame, "BALANCE", "Rs. 0.00", colors["balance_pos"], 1, 0)
income_label = create_card(dashboard_frame, "TOTAL INCOME", "Rs. 0.00", colors["income"], 1, 1)
expense_label = create_card(dashboard_frame, "TOTAL EXPENSES", "Rs. 0.00", colors["expense"], 1, 2)

# Row 2: Budget Progress (Dynamic + Scrollable)
budget_frame = tk.Frame(dashboard_frame, bg="white", padx=15, pady=12, relief="solid", bd=1)
budget_frame.grid(row=2, column=0, columnspan=3, padx=8, pady=8, sticky="nsew")

# FIX: Budget Status ab apna independent month navigation rakhta hai (Filter bar
# se alag), kyunke budget ek monthly concept hai aur "Last 7 Days"/"This Year"
# jaisay filters ke sath match nahi karta. Ab koi bhi mahina browse kiya ja sakta hai.
budget_month_state = {"date": datetime.now().date().replace(day=1)}

def shift_month(date_obj, delta):
    total = date_obj.month - 1 + delta
    year = date_obj.year + total // 12
    month = total % 12 + 1
    return date_obj.replace(year=year, month=month, day=1)

budget_header = tk.Frame(budget_frame, bg="white")
budget_header.pack(fill="x")

tk.Label(budget_header, text="Monthly Budget Limits", bg="white", font=("Segoe UI", 12, "bold"), fg=colors["primary"]).pack(side="left")

budget_nav = tk.Frame(budget_header, bg="white")
budget_nav.pack(side="right")

def budget_prev_month():
    budget_month_state["date"] = shift_month(budget_month_state["date"], -1)
    refresh_budget_progress()

def budget_next_month():
    budget_month_state["date"] = shift_month(budget_month_state["date"], 1)
    refresh_budget_progress()

tk.Button(budget_nav, text="◀", command=budget_prev_month, bg="#ecf0f1", fg=colors["primary"],
          font=("Segoe UI", 10, "bold"), padx=8, pady=2, relief="flat", cursor="hand2").pack(side="left", padx=3)

budget_month_label = tk.Label(budget_nav, text=budget_month_state["date"].strftime("%B %Y"),
                              bg="white", font=("Segoe UI", 10, "bold"), fg=colors["primary"], width=14)
budget_month_label.pack(side="left", padx=3)

tk.Button(budget_nav, text="▶", command=budget_next_month, bg="#ecf0f1", fg=colors["primary"],
          font=("Segoe UI", 10, "bold"), padx=8, pady=2, relief="flat", cursor="hand2").pack(side="left", padx=3)

# FIX (Issue 3): pehle sirf top 4 categories dikhti thi aur baqi kahin nazar
# hi nahi aati thi. Ab Canvas + Scrollbar use kar ke SAARI budgeted
# categories yahan scroll kar ke dekhi ja sakti hain.
budget_scroll_wrap = tk.Frame(budget_frame, bg="white")
budget_scroll_wrap.pack(fill="both", expand=True, pady=(8, 0))

budget_canvas = tk.Canvas(budget_scroll_wrap, bg="white", highlightthickness=0, height=170)
budget_scrollbar = ttk.Scrollbar(budget_scroll_wrap, orient="vertical", command=budget_canvas.yview)
budget_progress_container = tk.Frame(budget_canvas, bg="white")

budget_progress_container.bind(
    "<Configure>",
    lambda e: budget_canvas.configure(scrollregion=budget_canvas.bbox("all"))
)
budget_canvas_window = budget_canvas.create_window((0, 0), window=budget_progress_container, anchor="nw")
budget_canvas.configure(yscrollcommand=budget_scrollbar.set)
budget_canvas.pack(side="left", fill="both", expand=True)
budget_scrollbar.pack(side="right", fill="y")

def _resize_budget_container(event):
    budget_canvas.itemconfig(budget_canvas_window, width=event.width)
budget_canvas.bind("<Configure>", _resize_budget_container)

def _on_budget_mousewheel(event):
    if event.num == 4:
        budget_canvas.yview_scroll(-1, "units")
    elif event.num == 5:
        budget_canvas.yview_scroll(1, "units")
    else:
        budget_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

budget_canvas.bind("<Enter>", lambda e: (
    budget_canvas.bind_all("<MouseWheel>", _on_budget_mousewheel),
    budget_canvas.bind_all("<Button-4>", _on_budget_mousewheel),
    budget_canvas.bind_all("<Button-5>", _on_budget_mousewheel)
))
budget_canvas.bind("<Leave>", lambda e: (
    budget_canvas.unbind_all("<MouseWheel>"),
    budget_canvas.unbind_all("<Button-4>"),
    budget_canvas.unbind_all("<Button-5>")
))

# ============================================================
# STEP 6: FILTER BAR
# ============================================================

filter_frame = tk.Frame(root, bg=colors["bg"])
filter_frame.pack(padx=20, pady=(0, 10), fill="x")

tk.Label(filter_frame, text="Filter:", bg=colors["bg"], font=LABEL_FONT).pack(side="left", padx=(0, 10))

filter_var = tk.StringVar(value="all")

filter_buttons = []

def create_filter_btn(text, value):
    btn = tk.Button(filter_frame, text=text, font=("Segoe UI", 10, "bold"),
                    padx=12, pady=4, relief="flat", cursor="hand2",
                    command=lambda v=value: set_filter(v))
    btn.pack(side="left", padx=3)
    filter_buttons.append((btn, value))
    return btn

create_filter_btn("All Time", "all")
create_filter_btn("This Month", "this_month")
create_filter_btn("This Year", "this_year")

# NEW FEATURE: "Last 7 Days" hata diya gaya hai. Iski jagah records ko bhi
# Budget Status jaisa ◀ Month ▶ navigator mil gaya hai, taake koi bhi mahina
# seedha browse kiya ja sake (sirf "This Month" tak mehdood nahi).
table_month_state = {"date": datetime.now().date().replace(day=1)}

table_nav_frame = tk.Frame(filter_frame, bg=colors["bg"])
table_nav_frame.pack(side="left", padx=(10, 0))

def table_prev_month():
    table_month_state["date"] = shift_month(table_month_state["date"], -1)
    filter_var.set("month_nav")
    highlight_filter_buttons()
    refresh_all()

def table_next_month():
    table_month_state["date"] = shift_month(table_month_state["date"], 1)
    filter_var.set("month_nav")
    highlight_filter_buttons()
    refresh_all()

table_prev_btn = tk.Button(table_nav_frame, text="◀", command=table_prev_month,
                          bg=colors["white"], fg=colors["primary"], font=("Segoe UI", 10, "bold"),
                          padx=8, pady=4, relief="flat", cursor="hand2")
table_prev_btn.pack(side="left", padx=2)

table_month_nav_label = tk.Label(table_nav_frame, text=table_month_state["date"].strftime("%b %Y"),
                                 bg=colors["white"], fg=colors["primary"], font=("Segoe UI", 10, "bold"),
                                 padx=8, pady=4, width=10)
table_month_nav_label.pack(side="left", padx=2)

table_next_btn = tk.Button(table_nav_frame, text="▶", command=table_next_month,
                          bg=colors["white"], fg=colors["primary"], font=("Segoe UI", 10, "bold"),
                          padx=8, pady=4, relief="flat", cursor="hand2")
table_next_btn.pack(side="left", padx=2)

# Custom Date Range
tk.Label(filter_frame, text="From:", bg=colors["bg"], font=ENTRY_FONT).pack(side="left", padx=(20, 5))
from_date = tk.Entry(filter_frame, font=ENTRY_FONT, width=12)
from_date.pack(side="left", padx=2)
from_date.insert(0, datetime.now().replace(day=1).strftime("%Y-%m-%d"))

tk.Label(filter_frame, text="To:", bg=colors["bg"], font=ENTRY_FONT).pack(side="left", padx=(10, 5))
to_date = tk.Entry(filter_frame, font=ENTRY_FONT, width=12)
to_date.pack(side="left", padx=2)
to_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

custom_filter_btn = tk.Button(filter_frame, text="Apply Range", font=("Segoe UI", 10, "bold"),
                               bg=colors["info"], fg="white", padx=12, pady=4, relief="flat", cursor="hand2",
                               command=lambda: set_filter("custom"))
custom_filter_btn.pack(side="left", padx=8)

# ============================================================
# STEP 7: ACTION BUTTONS + SEARCH
# ============================================================

action_frame = tk.Frame(root, bg=colors["bg"])
action_frame.pack(padx=20, pady=5, fill="x")

# Sab kuch ek hi row mein: action buttons + Search + Amount range + Toggle
# Charts — taake neeche table ke liye zyada jagah bache.
buttons_row = tk.Frame(action_frame, bg=colors["bg"])
buttons_row.pack(fill="x")

btn_add = tk.Button(buttons_row, text="Add", command=lambda: add_transaction(),
                    bg=colors["success"], fg="white", font=("Segoe UI", 11, "bold"),
                    padx=14, pady=7, relief="flat", cursor="hand2")
btn_add.pack(side="left", padx=(0, 4))

btn_update = tk.Button(buttons_row, text="Update", command=lambda: update_transaction(),
                       bg=colors["info"], fg="white", font=("Segoe UI", 11, "bold"),
                       padx=14, pady=7, relief="flat", cursor="hand2")
btn_update.pack(side="left", padx=4)

btn_delete = tk.Button(buttons_row, text="Delete", command=lambda: delete_transaction(),
                       bg=colors["danger"], fg="white", font=("Segoe UI", 11, "bold"),
                       padx=14, pady=7, relief="flat", cursor="hand2")
btn_delete.pack(side="left", padx=4)

# FIX: pehle "Clear" button sirf form ki fields (description/amount) reset karta tha,
# jo confusing tha kyunke button poore action-bar mein records ke sath tha.
# Ab yeh poora record/history reset karta hai (confirmation ke sath), aur form
# clear karne wala chota button ab form ke andar (Amount field ke neeche) hai.
btn_clear = tk.Button(buttons_row, text="Clear Shown", command=lambda: reset_all_data(),
                      bg="#922b21", fg="white", font=("Segoe UI", 11, "bold"),
                      padx=14, pady=7, relief="flat", cursor="hand2")
btn_clear.pack(side="left", padx=4)

# Budget Settings Button
btn_budget = tk.Button(buttons_row, text="Budget Settings", command=lambda: open_budget_window(),
                       bg=colors["purple"], fg="white", font=("Segoe UI", 11, "bold"),
                       padx=14, pady=7, relief="flat", cursor="hand2")
btn_budget.pack(side="left", padx=(12, 4))

# Toggle Charts Button
btn_toggle_charts = tk.Button(buttons_row, text="Toggle Charts", command=lambda: toggle_charts(),
                              bg=colors["warning"], fg="white", font=("Segoe UI", 11, "bold"),
                              padx=14, pady=7, relief="flat", cursor="hand2")
btn_toggle_charts.pack(side="left", padx=4)

# ---- Divider ----
tk.Frame(buttons_row, bg="#cfd4da", width=2).pack(side="left", fill="y", padx=14, pady=4)

# ---- Search ----
tk.Label(buttons_row, text="Search:", bg=colors["bg"], font=LABEL_FONT).pack(side="left", padx=(0, 5))
search_entry = tk.Entry(buttons_row, font=ENTRY_FONT, width=16, fg="grey")
search_entry.pack(side="left", padx=5)
search_entry.insert(0, "Search...")

def clear_placeholder(event):
    if search_entry.get() == "Search...":
        search_entry.delete(0, tk.END)
        search_entry.config(fg="black")

def restore_placeholder(event):
    if search_entry.get() == "":
        search_entry.insert(0, "Search...")
        search_entry.config(fg="grey")

search_entry.bind("<FocusIn>", clear_placeholder)
search_entry.bind("<FocusOut>", restore_placeholder)
search_entry.bind("<KeyRelease>", lambda e: refresh_all())

btn_search_clear = tk.Button(buttons_row, text="X", command=lambda: clear_search(),
                             bg=colors["grey"], fg="white", font=("Segoe UI", 10, "bold"),
                             padx=8, pady=7, relief="flat", cursor="hand2")
btn_search_clear.pack(side="left", padx=(3, 0))

# ---- Divider ----
tk.Frame(buttons_row, bg="#cfd4da", width=2).pack(side="left", fill="y", padx=14, pady=4)

# ---- Amount range (NEW FEATURE) ----
# Search box sirf text (category/date/description) match karta tha, amount
# ke liye koi tareeqa nahi tha.
tk.Label(buttons_row, text="Amount:", bg=colors["bg"], font=LABEL_FONT).pack(side="left", padx=(0, 5))
min_amount_entry = tk.Entry(buttons_row, font=ENTRY_FONT, width=7)
min_amount_entry.pack(side="left", padx=2)
tk.Label(buttons_row, text="to", bg=colors["bg"], font=ENTRY_FONT).pack(side="left", padx=4)
max_amount_entry = tk.Entry(buttons_row, font=ENTRY_FONT, width=7)
max_amount_entry.pack(side="left", padx=2)

min_amount_entry.bind("<KeyRelease>", lambda e: refresh_all())
max_amount_entry.bind("<KeyRelease>", lambda e: refresh_all())

def clear_amount_filter():
    min_amount_entry.delete(0, tk.END)
    max_amount_entry.delete(0, tk.END)
    refresh_all()

tk.Button(buttons_row, text="X", command=clear_amount_filter,
          bg=colors["grey"], fg="white", font=("Segoe UI", 9, "bold"),
          padx=8, pady=7, relief="flat", cursor="hand2").pack(side="left", padx=(3, 0))

# ============================================================
# STEP 8: CHARTS (own popup window)
# ============================================================
# FIX: Pehle charts ko main window ke andar hi squeeze kar ke dikhaya jata
# tha, jahan pehle se hi input form, dashboard cards, budget list, filter bar
# aur table sab jagah le chuke thay — isliye charts bohat chota/squeezed aur
# unclear dikhte thay (titles bhi overlap ho rahe thay kyunke chart ke andar
# ka title aur upar wala label dono ek sath dikh rahe thay).
# Ab "Toggle Charts" apni ek alag, generously sized window kholta hai jahan
# dono charts saaf aur bara dikhte hain.
charts_window_state = {"win": None}
chart_target_frames = {"pie": None, "bar": None}


# ============================================================
# STEP 9: TREEVIEW TABLE
# ============================================================

table_frame = tk.Frame(root)
table_frame.pack(padx=20, pady=10, fill="both", expand=True)

style = ttk.Style()
style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
style.configure("Treeview.Heading", font=("Segoe UI", 12, "bold"))

columns = ("type", "date", "category", "description", "amount")
expense_table = ttk.Treeview(table_frame, columns=columns, show="headings")

expense_table.heading("type", text="Type")
expense_table.heading("date", text="Date")
expense_table.heading("category", text="Category")
expense_table.heading("description", text="Description")
expense_table.heading("amount", text="Amount")

expense_table.column("type", width=80, anchor="center")
expense_table.column("date", width=110, anchor="center")
expense_table.column("category", width=130, anchor="center")
expense_table.column("description", width=350, anchor="w")
expense_table.column("amount", width=130, anchor="center")

expense_table.tag_configure("oddrow", background="#f4f6f9")
expense_table.tag_configure("evenrow", background="white")
expense_table.tag_configure("income_row", foreground=colors["income"])
expense_table.tag_configure("expense_row", foreground=colors["expense"])

scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=expense_table.yview)
expense_table.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
expense_table.pack(fill="both", expand=True)

# ============================================================
# STEP 10: BOTTOM SUMMARY
# ============================================================

summary_frame = tk.Frame(root, bg=colors["bg"])
summary_frame.pack(padx=20, pady=(0, 15), fill="x")

total_count_label = tk.Label(summary_frame, text="Showing: 0", font=("Segoe UI", 12, "bold"),
                             bg=colors["bg"], fg=colors["primary"])
total_count_label.pack(side="left", padx=10)

filtered_amount_label = tk.Label(summary_frame, text="Filtered Total: Rs. 0.00", font=("Segoe UI", 12, "bold"),
                                 bg=colors["bg"], fg=colors["info"])
filtered_amount_label.pack(side="right", padx=10)

# ============================================================
# STEP 11: HELPER FUNCTIONS
# ============================================================

def format_currency(value):
    return f"Rs. {value:,.2f}"

def get_budget_status(spent, budget):
    """Ek hi jagah se decide karta hai ke spending 'On Track', 'Near Limit',
    'At Limit' (bilkul barabar) ya 'Over Budget' hai — taake progress bar aur
    Budget Alert popup dono HAMESHA ek dusre se match karein (pehle bar
    'Near Limit' dikhata tha jab ke popup 'EXCEEDED' bol raha hota tha,
    khaas taur par jab spent aur budget bilkul barabar hote thay).
    Returns: (status_key, icon, label, color_key)"""
    if budget <= 0:
        return ("none", "", "", "grey")
    diff = spent - budget
    if diff > 0.009:  # thora sa tolerance float rounding ke liye
        return ("over", "\u26D4", "Over Budget", "danger")
    elif abs(diff) <= 0.009:  # spent == budget (bilkul limit par)
        return ("at_limit", "\u26D4", "Limit Reached", "danger")
    elif spent >= budget * 0.75:
        return ("near", "\u26A0", "Near Limit", "warning")
    else:
        return ("ok", "\u2713", "On Track", "success")

def parse_currency(text):
    return float(text.replace("Rs.", "").replace(",", "").strip())

def get_filter_dates():
    """Returns (start_date, end_date) based on current filter"""
    today = datetime.now().date()
    f = filter_var.get()

    if f == "all":
        return (None, None)
    elif f == "this_month":
        start = today.replace(day=1)
        return (start, today)
    elif f == "this_year":
        start = today.replace(month=1, day=1)
        return (start, today)
    elif f == "month_nav":
        start = table_month_state["date"]
        end = shift_month(start, 1) - timedelta(days=1)
        return (start, end)
    elif f == "custom":
        try:
            start = datetime.strptime(from_date.get(), "%Y-%m-%d").date()
            end = datetime.strptime(to_date.get(), "%Y-%m-%d").date()
            return (start, end)
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
            return (None, None)
    return (None, None)

def matches_filter(transaction):
    """Check if transaction matches current filter + search + amount range"""
    start, end = get_filter_dates()
    t_date = datetime.strptime(transaction["date"], "%Y-%m-%d").date()

    if start and end:
        if not (start <= t_date <= end):
            return False

    keyword = search_entry.get().lower().strip()
    if keyword and keyword != "search...":
        fields = f"{transaction.get('type','')} {transaction['date']} {transaction['category']} {transaction['description']}".lower()
        if keyword not in fields:
            return False

    # NEW FEATURE: amount-range filter
    min_text = min_amount_entry.get().strip()
    max_text = max_amount_entry.get().strip()
    if min_text:
        try:
            if transaction["amount"] < float(min_text):
                return False
        except ValueError:
            pass  # invalid number typed — ignore rather than hide everything
    if max_text:
        try:
            if transaction["amount"] > float(max_text):
                return False
        except ValueError:
            pass

    return True

def get_filtered_transactions():
    data = load_data()
    return [t for t in data["transactions"] if matches_filter(t)]

def get_date_filtered_transactions():
    """Same as get_filtered_transactions() but ignores the search box —
    used for the summary cards so typing in Search doesn't change Balance/
    Income/Expenses (only the Filter bar buttons/date-range should)."""
    data = load_data()
    start, end = get_filter_dates()
    if start is None:
        return data["transactions"]
    result = []
    for t in data["transactions"]:
        t_date = datetime.strptime(t["date"], "%Y-%m-%d").date()
        if start <= t_date <= end:
            result.append(t)
    return result

def get_filter_period_text():
    """Human readable text describing the currently selected Filter bar range"""
    f = filter_var.get()
    if f == "all":
        return "All Time"
    elif f == "this_month":
        return datetime.now().strftime("%B %Y")
    elif f == "this_year":
        return str(datetime.now().year)
    elif f == "month_nav":
        return table_month_state["date"].strftime("%B %Y")
    elif f == "custom":
        return f"{from_date.get()} to {to_date.get()}"
    return "All Time"

# ============================================================
# STEP 12: REFRESH FUNCTIONS
# ============================================================

def refresh_table():
    expense_table.delete(*expense_table.get_children())
    # NEW FEATURE: date ke hisaab se sort karte hain (jo date jitni pehle hai
    # wo sab se upar), pehle list jis order mein save hoti thi usi order mein
    # dikhti thi jo confusing tha.
    transactions = sorted(get_filtered_transactions(), key=lambda t: t["date"])

    for index, t in enumerate(transactions):
        tag = "evenrow" if index % 2 == 0 else "oddrow"
        type_tag = "income_row" if t["type"] == "income" else "expense_row"

        expense_table.insert("", tk.END, values=(
            t["type"].upper(),
            t["date"],
            t["category"],
            t["description"],
            format_currency(t["amount"])
        ), tags=(tag, type_tag))

    # Summary
    total_count_label.config(text=f"Showing: {len(transactions)}")
    total = sum(t["amount"] for t in transactions)
    filtered_amount_label.config(text=f"Filtered Total: {format_currency(total)}")

def refresh_dashboard():
    """FIX: Pehle yeh cards hamesha ALL-TIME (poori history) ka total dikhate
    thay, chahe Filter bar mein kuch bhi selected ho — is wajah se 'previous
    month + next month' sab mil kar ek hi total mein dikh raha tha aur user
    control nahi kar sakta tha ke konsa period dekhna hai.
    Ab yeh cards Filter bar (All Time / This Month / Last 7 Days / This Year /
    Custom Range) ke sath sync hain — jo period table ke liye select karo,
    wahi cards mein bhi calculate hoga. Neeche ek chota label bhi dikhata hai
    ke abhi kis period ka data show ho raha hai."""
    transactions = get_date_filtered_transactions()

    total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
    total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
    balance = total_income - total_expense

    income_label.config(text=format_currency(total_income))
    expense_label.config(text=format_currency(total_expense))
    balance_label.config(text=format_currency(balance))
    balance_label.config(fg=colors["balance_pos"] if balance >= 0 else colors["balance_neg"])

    dashboard_period_label.config(text=f"Showing: {get_filter_period_text()}")

def refresh_budget_progress():
    # Clear old widgets
    for widget in budget_progress_container.winfo_children():
        widget.destroy()

    data = load_data()
    transactions = data["transactions"]

    # FIX: pehle hamesha real "aaj" ke calendar month ka data calculate hota
    # tha, Filter bar ya kisi aur cheez se koi farq nahi parta tha — isliye
    # previous month dekhne ka koi tareeqa nahi tha. Ab apna month navigation
    # (◀ / ▶ buttons) hai jo budget_month_state["date"] update karta hai, aur
    # calculation isi selected month tak MEHDOOD hai (pehle upper bound bhi
    # missing thi, ab month_end bhi properly set kiya hai).
    month_start = budget_month_state["date"]
    month_end = shift_month(month_start, 1) - timedelta(days=1)
    budget_month_label.config(text=month_start.strftime("%B %Y"))

    # NEW FEATURE: budgets ab isi mahine ki "effective" values hain — agar July
    # mein Food=2000 set kiya tha aur August mein nahi chheda, to yahan wohi
    # 2000 carry-forward hoga; agar August mein khud 3000 set kiya ho to sirf
    # August (aur aage) 3000 dikhega, July hamesha 2000 par hi rahega.
    budgets = get_budgets_for_month(data, month_start)

    # Calculate selected month's expenses per category
    cat_spent = {}
    for t in transactions:
        if t["type"] == "expense":
            t_date = datetime.strptime(t["date"], "%Y-%m-%d").date()
            if month_start <= t_date <= month_end:
                cat_spent[t["category"]] = cat_spent.get(t["category"], 0) + t["amount"]

    # FIX (Issue 3): pehle sirf 4 categories dikhti thi, ab data['categories']['expense']
    # ki SAARI categories dikhengi (jinki budget > 0 ho), aur zaroorat par scroll ho jayega.
    # NEW FEATURE: jis category ki budget limit sabse zyada ho woh sabse upar (top) dikhegi,
    # taake usay dhoondna aasan ho.
    displayed = 0
    sorted_categories = sorted(data["categories"]["expense"], key=lambda c: budgets.get(c, 0), reverse=True)
    for cat in sorted_categories:
        budget = budgets.get(cat, 0)
        if budget <= 0:
            continue
        spent = cat_spent.get(cat, 0)
        # FIX: pehle "pct" hamesha 100 par capped tha aur usi se status decide
        # hota tha (90% par hi "Over Budget" likh diya jata tha). Ab ek shared
        # get_budget_status() function use karte hain jo Budget Alert popup
        # ke sath bhi consistent hai — khaas taur par jab spent == budget
        # (bilkul limit par) ho to ab "Limit Reached" dikhta hai, na ke
        # ghalati se "Near Limit" ya "Over Budget".
        raw_pct = (spent / budget) * 100 if budget > 0 else 0
        pct = min(raw_pct, 100)

        row = tk.Frame(budget_progress_container, bg="white")
        row.pack(fill="x", pady=4)

        _, status_icon, status_text, color_key = get_budget_status(spent, budget)
        bar_color = colors[color_key]

        header_row = tk.Frame(row, bg="white")
        header_row.pack(fill="x")

        tk.Label(header_row, text=f"{status_icon}  {cat}", bg="white",
                 font=("Segoe UI", 10, "bold"), fg=bar_color).pack(side="left")
        tk.Label(header_row, text=f"{format_currency(spent)} / {format_currency(budget)}  \u2022  {status_text}",
                 bg="white", font=("Segoe UI", 9), fg=colors["grey"]).pack(side="right")

        # Progress bar canvas
        bar = tk.Canvas(row, height=12, bg="#ecf0f1", highlightthickness=0)
        bar.pack(fill="x", pady=(4, 4))
        # FIX: pehle ek fixed 100ms timer se width nikali jati thi — pehli
        # dafa app open hote waqt window abhi apna final size le hi raha hota
        # tha, isliye "Over Budget" bar bhi poori nahi bharti thi (Filter
        # button click karte hi theek ho jati thi kyunke tab tak window ka
        # size settle ho chuka hota tha). Ab canvas ke apne <Configure> event
        # se judte hain — jab bhi widget ko uska asal size milta/badalta hai,
        # bar khud sahi width ke sath dobara draw ho jati hai.
        def draw_bar(event=None, b=bar, p=pct, c=bar_color):
            b.delete("all")
            w = b.winfo_width()
            if w > 1:
                fill_w = (w * p) / 100
                b.create_rectangle(0, 0, fill_w, 12, fill=c, outline="")
        bar.bind("<Configure>", draw_bar)

        displayed += 1

    if displayed == 0:
        tk.Label(budget_progress_container, text="No budgets set. Click 'Budget Settings' to configure.",
                 bg="white", font=("Segoe UI", 10), fg=colors["grey"]).pack(pady=5)

def build_charts():
    """Popup charts window ke andar dono charts banata hai. Sirf tab kaam
    karta hai jab window khuli ho (chart_target_frames set hon)."""
    if not MATPLOTLIB_AVAILABLE:
        return
    pie_frame = chart_target_frames["pie"]
    bar_frame = chart_target_frames["bar"]
    if pie_frame is None or bar_frame is None:
        return

    # Clear old charts
    for widget in pie_frame.winfo_children():
        widget.destroy()
    for widget in bar_frame.winfo_children():
        widget.destroy()

    data = load_data()
    transactions = get_filtered_transactions()

    # ---- PIE CHART: Category-wise Expenses ----
    cat_totals = {}
    for t in transactions:
        if t["type"] == "expense":
            cat_totals[t["category"]] = cat_totals.get(t["category"], 0) + t["amount"]

    if cat_totals:
        # FIX: pehle chart ke andar bhi apna title tha ("Expenses by Category")
        # jo upar wale tk.Label heading ke sath overlap ho kar mess kar raha
        # tha. Ab chart ke andar koi title nahi (heading Label hi kaafi hai),
        # aur figure size bhi bara kiya hai taake popup window mein saaf dikhe.
        fig1 = Figure(figsize=(5.2, 4.4), dpi=95, facecolor="white")
        ax1 = fig1.add_subplot(111)
        colors_list = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6",
                       "#16a085", "#d35400", "#34495e", "#c0392b"]
        ax1.pie(
            cat_totals.values(), labels=cat_totals.keys(), autopct="%1.1f%%",
            colors=(colors_list * ((len(cat_totals) // len(colors_list)) + 1))[:len(cat_totals)],
            startangle=90, textprops={"fontsize": 10}
        )
        fig1.tight_layout()

        canvas1 = FigureCanvasTkAgg(fig1, master=pie_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill="both", expand=True)
    else:
        tk.Label(pie_frame, text="No expense data for charts", bg="white", fg=colors["grey"],
                 font=("Segoe UI", 11)).pack(pady=50)

    # ---- BAR CHART: Monthly Income vs Expense ----
    monthly_data = {}
    for t in data["transactions"]:
        month_key = t["date"][:7]  # YYYY-MM
        if month_key not in monthly_data:
            monthly_data[month_key] = {"income": 0, "expense": 0}
        monthly_data[month_key][t["type"]] += t["amount"]

    if monthly_data:
        sorted_months = sorted(monthly_data.keys())[-6:]  # Last 6 months
        incomes = [monthly_data[m]["income"] for m in sorted_months]
        expenses = [monthly_data[m]["expense"] for m in sorted_months]

        fig2 = Figure(figsize=(5.2, 4.4), dpi=95, facecolor="white")
        ax2 = fig2.add_subplot(111)
        x = range(len(sorted_months))
        width = 0.35
        ax2.bar([i - width/2 for i in x], incomes, width, label="Income", color="#27ae60")
        ax2.bar([i + width/2 for i in x], expenses, width, label="Expense", color="#c0392b")
        ax2.set_xticks(x)
        ax2.set_xticklabels([m[-2:] for m in sorted_months])  # Show only month
        ax2.set_xlabel("Month", fontsize=10)
        ax2.set_ylabel("Amount (Rs.)", fontsize=10)
        ax2.legend(fontsize=9)
        fig2.tight_layout()

        canvas2 = FigureCanvasTkAgg(fig2, master=bar_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill="both", expand=True)
    else:
        tk.Label(bar_frame, text="No data for charts", bg="white", fg=colors["grey"],
                 font=("Segoe UI", 11)).pack(pady=50)

def refresh_all():
    data = load_data()
    sync_category_lists(data)
    on_type_change()  # dropdown suggestions ko naye/updated categories se refresh karo
    refresh_table()
    refresh_dashboard()
    refresh_budget_progress()
    build_charts()  # sirf tab kaam karta hai jab charts window khuli ho

# ============================================================
# STEP 13: FILTER SETUP
# ============================================================

def highlight_filter_buttons():
    """Filter bar ke buttons + month navigator label ko current filter_var
    ke mutabiq highlight karta hai (taake pata chale kaunsa filter active hai)"""
    value = filter_var.get()
    for btn, val in filter_buttons:
        if val == value:
            btn.config(bg=colors["primary"], fg="white")
        else:
            btn.config(bg=colors["white"], fg=colors["primary"])

    if value == "custom":
        custom_filter_btn.config(bg=colors["primary"])
    else:
        custom_filter_btn.config(bg=colors["info"])

    if value == "month_nav":
        table_month_nav_label.config(bg=colors["primary"], fg="white")
    else:
        table_month_nav_label.config(bg=colors["white"], fg=colors["primary"])
    table_month_nav_label.config(text=table_month_state["date"].strftime("%b %Y"))

def set_filter(value):
    filter_var.set(value)
    highlight_filter_buttons()
    refresh_all()

# ============================================================
# STEP 14: BUDGET SETTINGS WINDOW
# ============================================================

def open_budget_window():
    # NEW FEATURE: Budget Settings ab hamesha usi mahine ke liye hai jo
    # "Monthly Budget Status" navigator (◀ Month ▶) mein currently select hai.
    # Yahan set ki gayi limit sirf isi mahine se lagu hogi (aur aage carry-forward
    # hogi jab tak dobara change na ho) — pichle mahine untouched rehte hain.
    target_month = budget_month_state["date"]

    win = tk.Toplevel(root)
    win.title(f"Budget Settings - {target_month.strftime('%B %Y')}")
    win.geometry("460x600")
    win.configure(bg="white")
    win.transient(root)
    win.grab_set()

    tk.Label(win, text="Set Monthly Budget Limits", font=("Segoe UI", 14, "bold"),
             bg="white", fg=colors["primary"]).pack(pady=(15, 2))
    tk.Label(win, text=f"Editing limits for: {target_month.strftime('%B %Y')}",
             font=("Segoe UI", 10), bg="white", fg=colors["info"]).pack(pady=(0, 10))
    tk.Label(win, text="(Changes apply from this month onward; earlier months keep their own limits.)",
             font=("Segoe UI", 8), bg="white", fg=colors["grey"]).pack(pady=(0, 10))

    data = load_data()
    budgets = get_budgets_for_month(data, target_month)

    # FIX (Issue 3): categories ki list ab data se aati hai (custom categories
    # samet), aur agar list lambi ho to scroll ho jati hai taake sab fields
    # nazar aayein (pehle window mein sirf jitni fit hoti woh dikhti thi).
    scroll_wrap = tk.Frame(win, bg="white")
    scroll_wrap.pack(padx=20, pady=5, fill="both", expand=True)

    b_canvas = tk.Canvas(scroll_wrap, bg="white", highlightthickness=0)
    b_scroll = ttk.Scrollbar(scroll_wrap, orient="vertical", command=b_canvas.yview)
    container = tk.Frame(b_canvas, bg="white")

    container.bind("<Configure>", lambda e: b_canvas.configure(scrollregion=b_canvas.bbox("all")))
    b_canvas_window = b_canvas.create_window((0, 0), window=container, anchor="nw")
    b_canvas.configure(yscrollcommand=b_scroll.set)
    b_canvas.pack(side="left", fill="both", expand=True)
    b_scroll.pack(side="right", fill="y")

    def _resize(event):
        b_canvas.itemconfig(b_canvas_window, width=event.width)
    b_canvas.bind("<Configure>", _resize)

    def _mousewheel(event):
        if event.num == 4:
            b_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            b_canvas.yview_scroll(1, "units")
        else:
            b_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    b_canvas.bind("<Enter>", lambda e: (
        b_canvas.bind_all("<MouseWheel>", _mousewheel),
        b_canvas.bind_all("<Button-4>", _mousewheel),
        b_canvas.bind_all("<Button-5>", _mousewheel)
    ))
    b_canvas.bind("<Leave>", lambda e: (
        b_canvas.unbind_all("<MouseWheel>"),
        b_canvas.unbind_all("<Button-4>"),
        b_canvas.unbind_all("<Button-5>")
    ))

    entries = {}
    for i, cat in enumerate(data["categories"]["expense"]):
        tk.Label(container, text=cat, bg="white", font=LABEL_FONT).grid(row=i, column=0, padx=5, pady=5, sticky="w")
        ent = tk.Entry(container, font=ENTRY_FONT, width=15)
        ent.grid(row=i, column=1, padx=5, pady=5)
        ent.insert(0, str(budgets.get(cat, 0)))
        entries[cat] = ent

        # NEW FEATURE: delete this category from the budget list
        del_btn = tk.Button(container, text="\u2715", command=lambda c=cat: delete_category(c),
                            bg=colors["danger"], fg="white", font=("Segoe UI", 9, "bold"),
                            padx=6, pady=2, relief="flat", cursor="hand2")
        del_btn.grid(row=i, column=2, padx=(8, 5), pady=5)

    def delete_category(cat_name):
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete the category '{cat_name}'?\n\n"
            "It will be removed from the category dropdown and budget list. "
            "Past transactions that already used this category will keep their name unaffected."
        )
        if not confirm:
            return
        fresh = load_data()
        if cat_name in fresh["categories"]["expense"]:
            fresh["categories"]["expense"].remove(cat_name)

        # FIX: pehle category delete karne par uski purani budget_history
        # entries (har mahine ki snapshot mein) file mein reh jati thin —
        # harmless clutter, lekin file dheere dheere barhti rehti thi. Ab
        # category delete hote hi uski entry har mahine ki snapshot se bhi
        # nikal di jati hai.
        for month_key, snapshot in fresh.get("budget_history", {}).items():
            snapshot.pop(cat_name, None)

        save_data(fresh)
        sync_category_lists(fresh)
        win.destroy()
        refresh_all()
        open_budget_window()

    # ---- Add a brand-new category right from here ----
    sep = tk.Frame(win, bg="#e0e0e0", height=1)
    sep.pack(fill="x", padx=20, pady=(5, 10))

    add_cat_frame = tk.Frame(win, bg="white")
    add_cat_frame.pack(padx=20, fill="x")

    tk.Label(add_cat_frame, text="+ New Category", bg="white", font=("Segoe UI", 10, "bold"),
             fg=colors["purple"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    new_cat_name = tk.Entry(add_cat_frame, font=ENTRY_FONT, width=15)
    new_cat_name.grid(row=1, column=0, padx=(0, 5), pady=3, sticky="w")
    new_cat_budget = tk.Entry(add_cat_frame, font=ENTRY_FONT, width=12)
    new_cat_budget.grid(row=1, column=1, padx=5, pady=3, sticky="w")
    new_cat_budget.insert(0, "0")

    def add_new_category():
        name = new_cat_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a category name.")
            return
        budget_text = new_cat_budget.get().strip()
        # FIX (Issue 3): pehle invalid/non-numeric text silently 0 ban kar save ho jata
        # tha, ab yahan strictly validate karte hain aur ghalat input par error dikhate hain.
        try:
            b_amt = float(budget_text) if budget_text else 0
        except ValueError:
            messagebox.showerror("Error", "Budget amount must be a valid number.")
            return
        if b_amt < 0:
            messagebox.showerror("Error", "Budget amount cannot be negative.")
            return

        fresh = load_data()
        if name in fresh["categories"]["expense"]:
            messagebox.showwarning("Warning", "This category already exists.")
            return
        ensure_category(fresh, "expense", name)
        set_budgets_for_month(fresh, target_month, {name: b_amt})
        save_data(fresh)
        sync_category_lists(fresh)
        win.destroy()
        refresh_all()
        open_budget_window()

    tk.Button(add_cat_frame, text="Add Category", command=add_new_category,
              bg=colors["info"], fg="white", font=("Segoe UI", 9, "bold"),
              padx=10, pady=4, relief="flat", cursor="hand2").grid(row=1, column=2, padx=5)

    def save_budgets():
        # FIX (Issue 3): pehle invalid/non-numeric budget value ko chup chaap 0 kar
        # ke save kar diya jata tha. Ab har field strictly validate hoti hai; agar
        # koi field ghalat ho to clear error dikha kar save rok di jaati hai.
        fresh = load_data()
        new_values = {}
        invalid_categories = []

        for cat, ent in entries.items():
            text = ent.get().strip()
            try:
                num = float(text)
                if num < 0:
                    invalid_categories.append(cat)
                    continue
                new_values[cat] = num
            except ValueError:
                invalid_categories.append(cat)

        if invalid_categories:
            messagebox.showerror(
                "Error",
                "Invalid budget value for: " + ", ".join(invalid_categories) +
                ".\nPlease enter a valid, non-negative number for each category."
            )
            return

        # NEW FEATURE: yeh values sirf target_month (aur us se aage, jab tak
        # koi future month khud change na ho) ke liye lagu hongi. Pichle
        # mahine ki apni values mehfooz rehti hain.
        set_budgets_for_month(fresh, target_month, new_values)
        save_data(fresh)
        refresh_all()
        win.destroy()
        messagebox.showinfo("Success", "Budgets saved successfully!")

    tk.Button(win, text="Save Budgets", command=save_budgets,
              bg=colors["success"], fg="white", font=("Segoe UI", 12, "bold"),
              padx=20, pady=8, relief="flat", cursor="hand2").pack(pady=15)

# ============================================================
# STEP 15: CHARTS TOGGLE
# ============================================================

def toggle_charts():
    # FIX: pehle charts ko main window ke andar hi (table_frame se pehle)
    # squeeze kiya jata tha, jahan pehle se hi bohat sara UI already fit
    # kiya hua tha — is wajah se charts bohat chote/unclear dikhte thay aur
    # titles bhi overlap ho rahe thay. Ab yeh apni ek alag, bari popup window
    # kholta/band karta hai jahan dono charts saaf aur bade dikhte hain.
    win = charts_window_state["win"]
    if win is not None and win.winfo_exists():
        win.destroy()
        charts_window_state["win"] = None
        chart_target_frames["pie"] = None
        chart_target_frames["bar"] = None
        return

    if not MATPLOTLIB_AVAILABLE:
        messagebox.showinfo(
            "Charts Unavailable",
            "The 'matplotlib' library is not installed, so charts can't be shown.\n\n"
            "Install it with: pip install matplotlib"
        )
        return

    win = tk.Toplevel(root)
    win.title("Money Mate - Charts")
    win.geometry("1150x560")
    win.configure(bg="white")
    win.transient(root)

    def on_close():
        charts_window_state["win"] = None
        chart_target_frames["pie"] = None
        chart_target_frames["bar"] = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)

    charts_window_state["win"] = win

    inner = tk.Frame(win, bg="white", padx=15, pady=15)
    inner.pack(fill="both", expand=True)

    left = tk.Frame(inner, bg="white")
    left.pack(side="left", fill="both", expand=True, padx=10)

    right = tk.Frame(inner, bg="white")
    right.pack(side="left", fill="both", expand=True, padx=10)

    tk.Label(left, text="Category-wise Expenses", bg="white", font=("Segoe UI", 12, "bold"), fg=colors["primary"]).pack()
    tk.Label(right, text="Monthly Income vs Expense", bg="white", font=("Segoe UI", 12, "bold"), fg=colors["primary"]).pack()

    pie_holder = tk.Frame(left, bg="white")
    pie_holder.pack(fill="both", expand=True, pady=5)

    bar_holder = tk.Frame(right, bg="white")
    bar_holder.pack(fill="both", expand=True, pady=5)

    chart_target_frames["pie"] = pie_holder
    chart_target_frames["bar"] = bar_holder

    build_charts()

# ============================================================
# STEP 16: CRUD OPERATIONS
# ============================================================

selected_id = None

def clear_fields():
    type_var.set("expense")
    on_type_change()
    date_entry.delete(0, tk.END)
    date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
    description.delete(0, tk.END)
    amount.delete(0, tk.END)
    global selected_id
    selected_id = None

def validate_inputs():
    if date_entry.get() == "":
        messagebox.showerror("Error", "Please enter date.")
        return False
    try:
        datetime.strptime(date_entry.get(), "%Y-%m-%d")
    except ValueError:
        messagebox.showerror("Error", "Date must be in YYYY-MM-DD format.")
        return False
    if category.get().strip() == "":
        messagebox.showerror("Error", "Please select or type a category.")
        return False
    if description.get() == "":
        messagebox.showerror("Error", "Please enter description.")
        return False
    if amount.get() == "":
        messagebox.showerror("Error", "Please enter amount.")
        return False
    try:
        val = float(amount.get())
        if val <= 0:
            messagebox.showerror("Error", "Amount must be greater than 0.")
            return False
    except ValueError:
        messagebox.showerror("Error", "Amount must be a number.")
        return False
    return True

def add_transaction():
    if not validate_inputs():
        return

    data = load_data()
    cat_name = category.get().strip()
    cat_type = "income" if type_var.get() == "income" else "expense"

    # FIX (Issue 1): typed category agar naya hai to save ki jaa rahi list mein add ho jaye
    ensure_category(data, cat_type, cat_name)

    transaction = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "type": type_var.get(),
        "date": date_entry.get(),
        "category": cat_name,
        "description": description.get(),
        "amount": float(amount.get())
    }
    data["transactions"].append(transaction)
    save_data(data)
    sync_category_lists(data)

    # Budget alert check
    if transaction["type"] == "expense":
        check_budget_alert(transaction["category"], transaction["date"])

    refresh_all()
    clear_fields()
    messagebox.showinfo("Success", f"{transaction['type'].title()} added successfully!")

def check_budget_alert(category_name, transaction_date):
    data = load_data()

    # FIX: pehle hamesha real "aaj" ke month ka spend calculate hota tha, ab
    # us transaction ki apni date ke month ke hisaab se calculate hota hai
    # (taake backdated entries ka alert bhi sahi mahine ke against ho).
    t_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
    month_start = t_date.replace(day=1)
    month_end = shift_month(month_start, 1) - timedelta(days=1)

    # NEW FEATURE: is mahine ki "effective" (carry-forward) budget limit use karo
    budget = get_budgets_for_month(data, month_start).get(category_name, 0)
    if budget <= 0:
        return

    spent = sum(t["amount"] for t in data["transactions"]
                if t["type"] == "expense" and t["category"] == category_name
                and month_start <= datetime.strptime(t["date"], "%Y-%m-%d").date() <= month_end)

    pct = (spent / budget) * 100
    status_key, _, _, _ = get_budget_status(spent, budget)

    # FIX: pehle "spent == budget" (bilkul limit par) hone par bhi "EXCEEDED"
    # (over budget) wala message aata tha, jab ke limit abhi sirf REACH hui
    # thi, cross nahi hui thi. Ab teeno states (Over / At Limit / Near) ke
    # liye alag aur sahi messages hain, aur yeh progress bar ke status se
    # bhi hamesha match karte hain (get_budget_status() dono jagah use hota hai).
    if status_key == "over":
        messagebox.showwarning("Budget Alert!",
            f"You have EXCEEDED your budget for {category_name}!\n\n"
            f"Budget: {format_currency(budget)}\n"
            f"Spent: {format_currency(spent)}")
    elif status_key == "at_limit":
        messagebox.showwarning("Budget Alert!",
            f"You have REACHED your full budget limit for {category_name}!\n\n"
            f"Budget: {format_currency(budget)}\n"
            f"Spent: {format_currency(spent)}")
    elif status_key == "near":
        messagebox.showwarning("Budget Warning",
            f"You have used {pct:.1f}% of your {category_name} budget!\n\n"
            f"Budget: {format_currency(budget)}\n"
            f"Spent: {format_currency(spent)}")

def select_record(event):
    global selected_id
    selected = expense_table.focus()
    if not selected:
        return
    values = expense_table.item(selected, "values")
    if not values:
        return

    # Find transaction by values
    data = load_data()
    for t in data["transactions"]:
        if (t["date"] == values[1] and t["category"] == values[2] and
            t["description"] == values[3] and format_currency(t["amount"]) == values[4]):
            selected_id = t["id"]
            type_var.set(t["type"])
            on_type_change()
            date_entry.delete(0, tk.END)
            date_entry.insert(0, t["date"])
            category.set(t["category"])
            description.delete(0, tk.END)
            description.insert(0, t["description"])
            amount.delete(0, tk.END)
            amount.insert(0, str(t["amount"]))
            break

def update_transaction():
    global selected_id
    if selected_id is None:
        messagebox.showwarning("Warning", "Please select a transaction first.")
        return
    if not validate_inputs():
        return

    data = load_data()
    cat_name = category.get().strip()
    cat_type = "income" if type_var.get() == "income" else "expense"
    ensure_category(data, cat_type, cat_name)

    for i, t in enumerate(data["transactions"]):
        if t["id"] == selected_id:
            data["transactions"][i] = {
                "id": selected_id,
                "type": type_var.get(),
                "date": date_entry.get(),
                "category": cat_name,
                "description": description.get(),
                "amount": float(amount.get())
            }
            break

    save_data(data)
    sync_category_lists(data)

    # FIX: pehle sirf naya (Add) transaction par budget alert check hota tha,
    # Update karne par nahi — is wajah se update se limit exceed karne par
    # koi warning nahi aati thi. Ab yahan bhi check hota hai.
    if type_var.get() == "expense":
        check_budget_alert(cat_name, date_entry.get())

    refresh_all()
    clear_fields()
    messagebox.showinfo("Success", "Transaction updated successfully!")

def delete_transaction():
    global selected_id
    if selected_id is None:
        messagebox.showwarning("Warning", "Please select a transaction.")
        return

    confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this transaction?")
    if not confirm:
        return

    data = load_data()
    data["transactions"] = [t for t in data["transactions"] if t["id"] != selected_id]
    save_data(data)

    selected_id = None
    refresh_all()
    clear_fields()
    messagebox.showinfo("Success", "Transaction deleted successfully!")

def reset_all_data():
    """Action-bar wala 'Clear All' button.
    FIX: pehle yeh HAMESHA poori transaction history delete kar deta tha,
    chahe koi bhi filter active ho (jaise 'August 2026' ya '20 July se 30 July')
    — matlab agar sirf August dekh rahe ho aur Clear All dabao, to July ka
    data bhi ghalti se delete ho jata tha. Ab yeh SIRF wahi transactions
    delete karta hai jo abhi table mein show ho rahi hain (currently active
    Filter bar range + Search + Amount range ke mutabiq) — baqi records
    (jo filter se bahar hain) mehfooz rehte hain."""
    to_delete = get_filtered_transactions()
    if not to_delete:
        messagebox.showinfo("Nothing to Clear", "There are no transactions matching the current filter/search to delete.")
        return

    delete_ids = {t["id"] for t in to_delete}
    period_text = get_filter_period_text()

    confirm = messagebox.askyesno(
        "Confirm Reset",
        f"This will permanently delete {len(to_delete)} transaction(s) currently shown "
        f"(filter: {period_text})!\n\n"
        "Transactions outside this filter/search will be kept. "
        "Your budgets and categories will be preserved.\n\n"
        "Are you sure you want to delete these?"
    )
    if not confirm:
        return

    data = load_data()
    data["transactions"] = [t for t in data["transactions"] if t["id"] not in delete_ids]
    save_data(data)

    global selected_id
    selected_id = None
    refresh_all()
    clear_fields()
    messagebox.showinfo("Success", f"{len(delete_ids)} transaction(s) cleared!")

def clear_search():
    search_entry.delete(0, tk.END)
    search_entry.insert(0, "Search...")
    search_entry.config(fg="grey")
    refresh_all()

# ============================================================
# STEP 17: EVENT BINDINGS & INITIAL LOAD
# ============================================================

expense_table.bind("<<TreeviewSelect>>", select_record)

# Initial load - ALL functions defined above this line
_initial_data = load_data()
sync_category_lists(_initial_data)
on_type_change()
set_filter("all")

# ============================================================
# STEP 18: MAINLOOP
# ============================================================

root.mainloop()