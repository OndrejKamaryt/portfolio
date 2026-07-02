"""Log vysvětlených pojmů (glossary.md) — aby edukativní sekce neopakovala stále totéž."""
import pathlib

PATH = pathlib.Path("glossary.md")
HEADER = "# Vysvětlené pojmy\n\nAutomaticky vedený seznam (viz sekce „Pojem k tématu“ v briefinzích).\n\n"


def recent(n=15):
    """Posledních n vysvětlených pojmů jako čárkami oddělený text pro prompt."""
    if not PATH.exists():
        return ""
    terms = [line.split(": ", 1)[1].strip() for line in PATH.read_text(encoding="utf-8").splitlines()
             if line.startswith("- ") and ": " in line]
    return ", ".join(terms[-n:])


def append(date, term):
    if not term:
        return
    is_new = not PATH.exists()
    with PATH.open("a", encoding="utf-8") as f:
        if is_new:
            f.write(HEADER)
        f.write(f"- {date.isoformat()}: {term}\n")
