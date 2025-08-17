
import tkinter as tk
from tkinter import ttk
import ast

APP_TITLE = "Python Calculator"
APP_WIDTH = 320
APP_HEIGHT = 460

ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.FloorDiv, ast.Call, ast.Name
)

SAFE_FUNCS = {
    "abs": abs,
    "round": round
}

def safe_eval(expr: str):
    """
    Safely evaluate a mathematical expression using Python's AST.
    Supports +, -, *, /, //, %, **, parentheses, unary +/-, and a few safe funcs.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError("Invalid syntax")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS:
                raise ValueError("Function not allowed")
        elif isinstance(node, ast.Name):
            if node.id not in SAFE_FUNCS:
                raise ValueError("Name not allowed")
        elif not isinstance(node, ALLOWED_NODES):
            raise ValueError("Operation not allowed")

    return eval(compile(tree, "<ast>", "eval"), {"__builtins__": {}}, SAFE_FUNCS)

class Calculator(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.master = master
        self.expr = tk.StringVar(value="")
        self.create_widgets()
        self.bind_keys()

    def create_widgets(self):
        self.master.title(APP_TITLE)
        self.master.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.master.minsize(280, 400)

        # Use a Tk themed style
        style = ttk.Style()
        try:
            self.master.tk.call("source", "sun-valley.tcl")  # optional if available
            style.theme_use("sun-valley-dark")
        except Exception:
            # fallback to default theme
            pass

        self.pack(fill="both", expand=True)

        display = ttk.Entry(self, textvariable=self.expr, justify="right", font=("SF Pro", 26))
        display.pack(fill="x", pady=(0, 10))
        display.focus_set()

        btns = [
            ("C", 1, 1), ("(", 1, 1), (")", 1, 1), ("⌫", 1, 1),
            ("7", 1, 1), ("8", 1, 1), ("9", 1, 1), ("/", 1, 1),
            ("4", 1, 1), ("5", 1, 1), ("6", 1, 1), ("*", 1, 1),
            ("1", 1, 1), ("2", 1, 1), ("3", 1, 1), ("-", 1, 1),
            ("0", 1, 1), (".", 1, 1), ("%", 1, 1), ("+", 1, 1),
            ("//", 1, 1), ("**", 1, 1), ("±", 1, 1), ("=", 2, 1),
        ]

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)

        # Configure responsive grid
        for i in range(6):
            grid.rowconfigure(i, weight=1)
        for j in range(4):
            grid.columnconfigure(j, weight=1)

        row = 0
        col = 0
        for text, colspan, rowspan in btns:
            btn = ttk.Button(grid, text=text, command=lambda t=text: self.on_button(t))
            btn.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan, sticky="nsew", padx=4, pady=4)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def bind_keys(self):
        self.master.bind("<Key>", self.on_key)
        self.master.bind("<Return>", lambda e: self.on_button("="))
        self.master.bind("<KP_Enter>", lambda e: self.on_button("="))
        self.master.bind("<BackSpace>", lambda e: self.on_button("⌫"))
        self.master.bind("<Escape>", lambda e: self.on_button("C"))

    def on_key(self, event):
        ch = event.char
        allowed = "0123456789.+-*/()%"
        if ch in allowed:
            self.expr.set(self.expr.get() + ch)

    def on_button(self, label):
        if label == "C":
            self.expr.set("")
        elif label == "⌫":
            self.expr.set(self.expr.get()[:-1])
        elif label == "±":
            self.toggle_sign()
        elif label == "=":
            self.calculate()
        else:
            # insert with spacing for readability around operators (optional)
            if label in {"+", "-", "*", "/", "%", "//", "**"}:
                self.expr.set(self.expr.get() + label)
            else:
                self.expr.set(self.expr.get() + label)

    def toggle_sign(self):
        s = self.expr.get().strip()
        if not s:
            self.expr.set("-")
            return
        # If it's a single number
        try:
            val = safe_eval(s)
            if isinstance(val, (int, float)):
                if str(s).startswith("-"):
                    self.expr.set(s[1:])
                else:
                    self.expr.set("-" + s)
                return
        except Exception:
            pass
        # Otherwise, wrap last number with -( )
        i = len(s) - 1
        while i >= 0 and (s[i].isdigit() or s[i] == "."):
            i -= 1
        i += 1
        if i < len(s):
            self.expr.set(s[:i] + "-(" + s[i:] + ")")

    def calculate(self):
        s = self.expr.get()
        if not s.strip():
            return
        try:
            result = safe_eval(s)
            # Normalize floats that are nearly integers
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.expr.set(str(result))
        except Exception as e:
            self.flash_error(str(e))

    def flash_error(self, message="Error"):
        orig = self.expr.get()
        self.expr.set(message)
        self.after(800, lambda: self.expr.set(orig))

def main():
    root = tk.Tk()
    Calculator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
