"""Funções pequenas usadas em várias partes do sistema."""

from datetime import datetime


def agora():
    """Data e hora local (usada em todos os registros novos)."""
    return datetime.now()


def numero(texto, minimo=None, maximo=None):
    """Converte '12,5' ou '12.5' em float. Devolve None se inválido."""
    try:
        valor = float(str(texto).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None

    if valor != valor:  # NaN
        return None

    if minimo is not None and valor < minimo:
        return None

    if maximo is not None and valor > maximo:
        return None

    return valor
