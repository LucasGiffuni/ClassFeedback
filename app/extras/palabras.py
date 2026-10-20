import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

from app.extras.stopwords_es import STOPWORDS


TOP_PALABRAS = 20
LARGO_MINIMO = 2

# Letras Unicode (incluye tildes y ñ); excluye dígitos y guiones bajos.
_PALABRA = re.compile(r"[^\W\d_]+")
# Solo tilde aguda y diéresis: la ñ se conserva para no confundir "uña" con "una".
_DIACRITICOS = {"́", "̈"}


def sin_tildes(palabra: str) -> str:
    descompuesta = unicodedata.normalize("NFD", palabra)
    return unicodedata.normalize("NFC", "".join(c for c in descompuesta if c not in _DIACRITICOS))


def palabras_frecuentes(textos: Iterable[str], limite: int = TOP_PALABRAS) -> list[tuple[str, int]]:
    conteo = Counter()
    for texto in textos:
        for palabra in _PALABRA.findall(unicodedata.normalize("NFC", texto).lower()):
            if len(palabra) >= LARGO_MINIMO and sin_tildes(palabra) not in STOPWORDS:
                conteo[palabra] += 1
    # Desempate alfabético para un resultado estable.
    return sorted(conteo.items(), key=lambda item: (-item[1], item[0]))[:limite]
