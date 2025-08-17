#!/usr/bin/env python3
"""
Hangman (Console Edition)
- Pure Python 3, runs in a terminal/command prompt.
- Cross-platform: Windows, macOS, Linux.

How to run:
    python hangman_console.py
"""

import random
import string
import sys

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

HANGMAN_PICS = [
    """
     +---+
     |   |
         |
         |
         |
         |
    =========""",
    """
     +---+
     |   |
     O   |
         |
         |
         |
    =========""",
    """
     +---+
     |   |
     O   |
     |   |
         |
         |
    =========""",
    """
     +---+
     |   |
     O   |
    /|   |
         |
         |
    =========""",
    """
     +---+
     |   |
     O   |
    /|\\  |
         |
         |
    =========""",
    """
     +---+
     |   |
     O   |
    /|\\  |
    /    |
         |
    =========""",
    """
     +---+
     |   |
     O   |
    /|\\  |
    / \\  |
         |
    ========="""
]

def choose_word(difficulty: str) -> str:
    difficulty = difficulty.lower()
    if difficulty == "easy":
        candidates = [w for w in WORDS if 4 <= len(w) <= 6]
    elif difficulty == "hard":
        candidates = [w for w in WORDS if len(w) >= 9]
    else:
        candidates = [w for w in WORDS if 6 <= len(w) <= 8]
    return random.choice(candidates) if candidates else random.choice(WORDS)

def prompt_difficulty() -> str:
    print("Choose difficulty: [E]asy, [M]edium, [H]ard")
    while True:
        choice = input("Your choice: ").strip().lower()
        if choice in {"e","easy"}: return "easy"
        if choice in {"m","medium"}: return "medium"
        if choice in {"h","hard"}: return "hard"
        print("Please type E, M, or H.")

def print_state(secret, guessed, lives):
    display = " ".join([c if c in guessed else "_" for c in secret])
    print(HANGMAN_PICS[len(HANGMAN_PICS)-1 - lives])
    print(f"\nWord: {display}")
    print(f"Guessed: {' '.join(sorted(guessed)) if guessed else '(none)'}")
    print(f"Lives: {lives}\n")

def get_letter(already):
    while True:
        s = input("Guess a letter (or type ! to guess the whole word): ").strip().lower()
        if s == "!":
            return "!"
        if len(s) != 1 or s not in string.ascii_lowercase:
            print("Please enter a single letter a-z.")
            continue
        if s in already:
            print("You already tried that letter.")
            continue
        return s

def play_round():
    difficulty = prompt_difficulty()
    secret = choose_word(difficulty)
    lives = 6
    guessed = set()
    correct = set()
    print("\nLet's play Hangman!\n")
    while lives > 0:
        print_state(secret, guessed, lives)
        letter = get_letter(guessed)
        if letter == "!":
            attempt = input("Enter your full word guess: ").strip().lower()
            if attempt == secret:
                print(f"🎉 Correct! The word was '{secret}'. You win!")
                return True
            else:
                print("Nope! That's not the word. You lose 2 lives.")
                lives -= 2
                continue
        guessed.add(letter)
        if letter in secret:
            print("Nice! That letter is in the word.")
            correct.add(letter)
            if all(c in guessed for c in set(secret)):
                print_state(secret, guessed, lives)
                print(f"🎉 You revealed the word '{secret}'! You win!")
                return True
        else:
            print("Sorry, not in the word.")
            lives -= 1
    print_state(secret, guessed, 0)
    print(f"💀 Out of lives. The word was '{secret}'. Better luck next time!")
    return False

def main():
    wins = 0
    losses = 0
    print("== HANGMAN (Console) ==")
    while True:
        result = play_round()
        wins += int(result)
        losses += int(not result)
        print(f"\nScore: {wins} wins / {losses} losses")
        again = input("Play again? [Y/n]: ").strip().lower()
        if again in {"n","no"}:
            print("Thanks for playing!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
