from datetime import date

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def fecha_corta(iso):
    """'2026-10-19' -> 'Lun 19/10/2026'"""
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d:%d/%m/%Y}"