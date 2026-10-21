from datetime import date, datetime, timedelta, timezone

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
HORA_PERU = timezone(timedelta(hours=-5))  # Perú no usa horario de verano


def fecha_corta(iso):
    """'2026-10-19' -> 'Lun 19/10/2026'"""
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d:%d/%m/%Y}"


def ahora(**desfase):
    """Fecha y hora de Perú como texto ordenable: '2026-10-21 09:30:00'.
    ahora(minutes=-15) da la hora de hace 15 minutos."""
    return (datetime.now(HORA_PERU) + timedelta(**desfase)).strftime("%Y-%m-%d %H:%M:%S")


def fecha_hora(texto):
    """'2026-10-21 09:30:00' -> '21/10/2026 09:30'"""
    if not texto:
        return "—"
    d = datetime.fromisoformat(texto)
    return f"{d:%d/%m/%Y %H:%M}"
