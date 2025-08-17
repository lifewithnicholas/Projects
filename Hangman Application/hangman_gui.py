#!/usr/bin/env python3
"""
Hangman (GUI Edition) - Tkinter
- Pure Python 3 standard library (uses tkinter).
- Cross-platform: Windows, macOS, Linux.
- No external dependencies.

How to run:
    python hangman_gui.py
"""

import random
import string
import tkinter as tk
from tkinter import messagebox

WORDS = [
    "python","hangman","variable","function","loop","condition","string","integer","boolean",
    "list","tuple","dictionary","set","module","package","object","class","inheritance","polymorphism",
    "encapsulation","algorithm","binary","recursion","iterator","generator","comprehension","exception",
    "syntax","runtime","debugger","keyword","operator","parameter","argument","namespace","attribute",
    "virtual","environment","library","framework","testing","assertion","protocol","network","socket",
    "encryption","database","transaction","cursor","query","index","schema","backup","restore","commit",
    "rollback","frontend","backend","server","client","request","response","cache","cookie","session",
    "thread","process","concurrency","parallel","performance","optimize","compile","interpreter"
]

class HangmanGame:
    def __init__(self, root):
        self.root = root
        root.title("Hangman")
        root.geometry("560x640")
        root.minsize(520, 600)

        self.frame_top = tk.Frame(root)
        self.frame_top.pack(pady=8)

        self.diff_var = tk.StringVar(value="medium")
        for label, val in [("Easy","easy"),("Medium","medium"),("Hard","hard")]:
            tk.Radiobutton(self.frame_top, text=label, variable=self.diff_var, value=val).pack(side=tk.LEFT, padx=4)

        self.btn_new = tk.Button(self.frame_top, text="New Game", command=self.new_game)
        self.btn_new.pack(side=tk.LEFT, padx=10)

        self.canvas = tk.Canvas(root, width=420, height=320, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.canvas.pack(pady=10)

        self.word_var = tk.StringVar(value="")
        self.lbl_word = tk.Label(root, textvariable=self.word_var, font=("Consolas", 28))
        self.lbl_word.pack(pady=8)

        self.info_var = tk.StringVar(value="Click a letter to guess")
        self.lbl_info = tk.Label(root, textvariable=self.info_var, font=("Arial", 12))
        self.lbl_info.pack(pady=2)

        self.kb_frame = tk.Frame(root)
        self.kb_frame.pack(pady=6)

        self.buttons = {}
        rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
        for r, letters in enumerate(rows):
            rowf = tk.Frame(self.kb_frame)
            rowf.pack()
            for ch in letters:
                b = tk.Button(rowf, text=ch.upper(), width=3, command=lambda c=ch: self.guess_letter(c))
                b.pack(side=tk.LEFT, padx=2, pady=2)
                self.buttons[ch] = b

        self.status_var = tk.StringVar(value="")
        self.lbl_status = tk.Label(root, textvariable=self.status_var, font=("Arial", 11))
        self.lbl_status.pack(pady=4)

        self.score_wins = 0
        self.score_losses = 0

        self.secret = ""
        self.guessed = set()
        self.lives = 6

        self.new_game()

    def choose_word(self, difficulty):
        if difficulty == "easy":
            pool = [w for w in WORDS if 4 <= len(w) <= 6]
        elif difficulty == "hard":
            pool = [w for w in WORDS if len(w) >= 9]
        else:
            pool = [w for w in WORDS if 6 <= len(w) <= 8]
        return random.choice(pool if pool else WORDS)

    def new_game(self):
        self.secret = self.choose_word(self.diff_var.get())
        self.guessed = set()
        self.lives = 6
        for ch, btn in self.buttons.items():
            btn.config(state=tk.NORMAL)
        self.update_word_label()
        self.info_var.set("Click a letter to guess")
        self.status_var.set(f"Wins: {self.score_wins}   Losses: {self.score_losses}")
        self.draw_gallows(stage=0)

    def update_word_label(self):
        display = " ".join([c.upper() if c in self.guessed else "_" for c in self.secret])
        self.word_var.set(display)

    def guess_letter(self, ch):
        if ch in self.guessed:
            return
        self.guessed.add(ch)
        self.buttons[ch].config(state=tk.DISABLED)
        if ch in self.secret:
            self.info_var.set(f"Nice! '{ch.upper()}' is in the word.")
            self.update_word_label()
            if all(c in self.guessed for c in set(self.secret)):
                self.end_game(win=True)
        else:
            self.lives -= 1
            self.info_var.set(f"Sorry, '{ch.upper()}' is not in the word.")
            self.draw_gallows(stage=6 - self.lives)
            if self.lives <= 0:
                self.end_game(win=False)

    def end_game(self, win):
        for btn in self.buttons.values():
            btn.config(state=tk.DISABLED)
        if win:
            self.score_wins += 1
            messagebox.showinfo("You win!", f"You revealed the word '{self.secret.upper()}' 🎉")
        else:
            self.score_losses += 1
            messagebox.showinfo("You lost", f"The word was '{self.secret.upper()}' 💀")
        self.status_var.set(f"Wins: {self.score_wins}   Losses: {self.score_losses}")

    def draw_gallows(self, stage):
        # clear
        self.canvas.delete("all")
        w, h = 420, 320
        # base
        self.canvas.create_line(40, 280, 200, 280, width=4)
        self.canvas.create_line(80, 280, 80, 50, width=4)
        self.canvas.create_line(80, 50, 200, 50, width=4)
        self.canvas.create_line(200, 50, 200, 80, width=4)

        # Draw parts based on stage (0..6)
        # 1: head, 2: body, 3: left arm, 4: right arm, 5: left leg, 6: right leg
        if stage >= 1:
            self.canvas.create_oval(175, 80, 225, 130, width=3)  # head
        if stage >= 2:
            self.canvas.create_line(200, 130, 200, 200, width=3)  # body
        if stage >= 3:
            self.canvas.create_line(200, 150, 170, 180, width=3)  # left arm
        if stage >= 4:
            self.canvas.create_line(200, 150, 230, 180, width=3)  # right arm
        if stage >= 5:
            self.canvas.create_line(200, 200, 175, 240, width=3)  # left leg
        if stage >= 6:
            self.canvas.create_line(200, 200, 225, 240, width=3)  # right leg

def main():
    root = tk.Tk()
    HangmanGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()
