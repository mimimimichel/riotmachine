"""Erreurs destinées à Michael : en français, elles disent ce qui se passe et quoi faire."""


class RiotError(Exception):
    """Erreur lisible : le message dit ce qui se passe et ce qu'on peut faire."""


class Refused(RiotError):
    """Écriture refusée : l'auteur n'a pas le droit d'écrire ce champ (R-A3, R-A4)."""
