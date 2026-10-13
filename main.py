"""
Entry point: loads the .env file, then starts the Tkinter chat window.

This file only handles the GUI (drawing the window, reacting to clicks
and key presses, and rendering chat bubbles). All the actual thinking
happens in chatbot.py.
"""

import tkinter as tk
from datetime import datetime

from dotenv import load_dotenv

from chatbot import Chatbot

load_dotenv()  # reads GEMINI_API_KEY (and optional GEMINI_MODEL) from .env

# --- Color theme -----------------------------------------------------------
BG = "#fff5f8"
HEADER_BG = "#ec4899"
HEADER_FG = "#ffffff"
HEADER_SUBTITLE_FG = "#ffe0ef"

USER_BUBBLE_BG = "#ec4899"
USER_BUBBLE_FG = "#ffffff"
BOT_BUBBLE_BG = "#ffffff"
BOT_BUBBLE_FG = "#3b2430"
BOT_BUBBLE_BORDER = "#f6c6de"
SYSTEM_FG = "#b97ca0"
TIMESTAMP_FG = "#c998b4"

INPUT_BG = "#ffffff"
INPUT_BORDER = "#f3c9dc"
INPUT_BORDER_FOCUS = "#ec4899"

SEND_BG = "#ec4899"
SEND_BG_HOVER = "#db2777"
SEND_FG = "#ffffff"

SECONDARY_BG = "#fde2ef"
SECONDARY_BG_HOVER = "#fbd0e4"
SECONDARY_FG = "#9d174d"

FONT_FAMILY = "Segoe UI"


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Chatbot")
        self.root.geometry("540x660")
        self.root.minsize(420, 480)
        self.root.configure(bg=BG)

        self.bot = Chatbot()
        self._typing_row = None  # the temporary "Bot is typing..." bubble row, if shown

        self._build_widgets()
        self._show_system_message(
            "Chatbot ready. Say hello, ask about AI/Python, or just chat!"
        )

    # ------------------------------------------------------------------ UI --

    def _build_widgets(self):
        self._build_header()
        self._build_chat_area()
        self._build_input_area()

    def _build_header(self):
        header = tk.Frame(self.root, bg=HEADER_BG)
        header.pack(fill=tk.X)

        tk.Label(
            header, text="AI Chatbot", bg=HEADER_BG, fg=HEADER_FG,
            font=(FONT_FAMILY, 16, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 0))

        tk.Label(
            header, text="Ask about AI, Python, or just chat", bg=HEADER_BG,
            fg=HEADER_SUBTITLE_FG, font=(FONT_FAMILY, 9), anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(0, 12))

    def _build_chat_area(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.messages_frame = tk.Frame(self.canvas, bg=BG)
        self._frame_id = self.canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")

        self.messages_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._frame_id, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 40), "units")

    def _build_input_area(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill=tk.X, padx=12, pady=(0, 6))

        entry_border = tk.Frame(bar, bg=INPUT_BORDER, padx=1, pady=1)
        entry_border.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.input_entry = tk.Entry(
            entry_border, font=(FONT_FAMILY, 11), bg=INPUT_BG, fg=BOT_BUBBLE_FG,
            relief="flat", insertbackground=BOT_BUBBLE_FG,
        )
        self.input_entry.pack(fill=tk.X, padx=8, pady=8)
        self.input_entry.bind("<Return>", lambda event: self.on_send())
        self.input_entry.bind("<FocusIn>", lambda e: entry_border.configure(bg=INPUT_BORDER_FOCUS))
        self.input_entry.bind("<FocusOut>", lambda e: entry_border.configure(bg=INPUT_BORDER))
        self.input_entry.focus_set()

        self.send_button = self._make_button(bar, "Send", SEND_BG, SEND_BG_HOVER, SEND_FG, self.on_send)
        self.send_button.pack(side=tk.LEFT)

        button_frame = tk.Frame(self.root, bg=BG)
        button_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        new_chat_button = self._make_button(
            button_frame, "New Chat", SECONDARY_BG, SECONDARY_BG_HOVER, SECONDARY_FG, self.on_new_chat
        )
        new_chat_button.pack(side=tk.LEFT)

        exit_button = self._make_button(
            button_frame, "Exit", SECONDARY_BG, SECONDARY_BG_HOVER, SECONDARY_FG, self.root.quit
        )
        exit_button.pack(side=tk.RIGHT)

    @staticmethod
    def _make_button(parent, text, bg, hover_bg, fg, command):
        button = tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover_bg,
            activeforeground=fg, relief="flat", font=(FONT_FAMILY, 10, "bold"),
            padx=16, pady=8, cursor="hand2", bd=0,
        )
        button.bind("<Enter>", lambda e: button.configure(bg=hover_bg))
        button.bind("<Leave>", lambda e: button.configure(bg=bg))
        return button

    # ------------------------------------------------------------- actions --

    def on_send(self):
        user_text = self.input_entry.get()
        if not user_text.strip():
            return

        self.input_entry.delete(0, tk.END)
        self._add_bubble(user_text, align="right", bg=USER_BUBBLE_BG, fg=USER_BUBBLE_FG)

        self._show_typing_indicator()
        self.send_button.configure(state="disabled")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            bot_reply = self.bot.process_message(user_text)
        finally:
            self.root.config(cursor="")
            self.send_button.configure(state="normal")

        self._remove_typing_indicator()
        self._add_bubble(bot_reply, align="left", bg=BOT_BUBBLE_BG, fg=BOT_BUBBLE_FG, border=True)

    def on_new_chat(self):
        self.bot.new_chat()
        for row in self.messages_frame.winfo_children():
            row.destroy()
        self._typing_row = None
        self._show_system_message("Started a new chat. Previous context has been cleared.")

    # --------------------------------------------------------- bubble UI --

    def _add_bubble(self, text, align, bg, fg, border=False):
        row = tk.Frame(self.messages_frame, bg=BG)
        row.pack(fill=tk.X, pady=4, padx=6)

        side = tk.RIGHT if align == "right" else tk.LEFT
        anchor = "e" if align == "right" else "w"

        column = tk.Frame(row, bg=BG)
        column.pack(side=side, anchor=anchor)

        bubble_kwargs = dict(
            text=text, bg=bg, fg=fg, font=(FONT_FAMILY, 10), wraplength=340,
            justify="left", padx=12, pady=8, bd=0,
        )
        if border:
            # 1px colored frame behind the label fakes a clean border, since
            # Label's own relief/highlight options don't give a crisp color.
            wrapper = tk.Frame(column, bg=BOT_BUBBLE_BORDER)
            wrapper.pack(anchor=anchor)
            bubble = tk.Label(wrapper, **bubble_kwargs)
            bubble.pack(padx=1, pady=1)
        else:
            bubble = tk.Label(column, **bubble_kwargs)
            bubble.pack(anchor=anchor)

        tk.Label(
            column, text=datetime.now().strftime("%H:%M"), bg=BG, fg=TIMESTAMP_FG,
            font=(FONT_FAMILY, 8),
        ).pack(anchor=anchor, pady=(2, 0))

        self._scroll_to_bottom()
        return row

    def _show_system_message(self, text):
        row = tk.Frame(self.messages_frame, bg=BG)
        row.pack(fill=tk.X, pady=6)
        tk.Label(
            row, text=text, bg=BG, fg=SYSTEM_FG, font=(FONT_FAMILY, 9, "italic"),
            wraplength=380, justify="center",
        ).pack(anchor="center")
        self._scroll_to_bottom()

    def _show_typing_indicator(self):
        self._typing_row = self._add_bubble(
            "Bot is typing...", align="left", bg=BG, fg=SYSTEM_FG
        )

    def _remove_typing_indicator(self):
        if self._typing_row is not None:
            self._typing_row.destroy()
            self._typing_row = None

    def _scroll_to_bottom(self):
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)


def main():
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
