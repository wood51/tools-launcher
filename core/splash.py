import threading
import tkinter as tk

from core.theme import ACCENT, BG, MUTED, SURFACE_2, TEXT


def run_with_splash(message, task):
    """Affiche une fenêtre d'attente pendant que task(set_status) s'exécute, puis renvoie son résultat.

    set_status(texte) change le message affiché ; il peut être appelé depuis task.
    """
    result = {}

    def set_status(text):
        root.after(0, status.config, {"text": text})

    def worker():
        try:
            result["value"] = task(set_status)
        except Exception as exc:
            result["error"] = exc
        root.after(0, root.destroy)

    root = tk.Tk()
    root.title("Mes outils")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.overrideredirect(True)  # pas de barre de titre
    root.attributes("-topmost", True)

    width, height = 380, 110
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg=BG, highlightthickness=1, highlightbackground=SURFACE_2)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Mes outils", bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(
        pady=(18, 2)
    )
    status = tk.Label(frame, text=message, bg=BG, fg=MUTED, font=("Segoe UI", 10))
    status.pack()

    bar_width, bar_height, block = 320, 4, 90
    bar = tk.Canvas(frame, width=bar_width, height=bar_height, bg=SURFACE_2, highlightthickness=0)
    bar.pack(pady=14)
    cursor = bar.create_rectangle(-block, 0, 0, bar_height, fill=ACCENT, width=0)

    def animate():
        bar.move(cursor, 4, 0)
        if bar.coords(cursor)[0] >= bar_width:
            bar.coords(cursor, -block, 0, 0, bar_height)
        root.after(12, animate)

    animate()

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()

    if "error" in result:
        raise result["error"]
    return result.get("value")
