from pathlib import Path
from typing import Iterable
from typing import List
from typing import Union

import g2p_en
from typeguard import check_argument_types

from espnet2.text.abs_tokenizer import AbsTokenizer


def pyopenjtalk_g2p(text) -> List[str]:
    import pyopenjtalk

    # phones is a str object separated by space
    phones = pyopenjtalk.g2p(text, kana=False)
    phones = phones.split(" ")
    return phones


def pyopenjtalk_g2p_kana(text) -> List[str]:
    import pyopenjtalk

    kanas = pyopenjtalk.g2p(text, kana=True)
    return list(kanas)


def pypinyin_g2p(text) -> List[str]:
    from pypinyin import pinyin
    from pypinyin import Style

    phones = [phone[0] for phone in pinyin(text, style=Style.TONE3)]
    return phones


def pypinyin_g2p_phone(text) -> List[str]:
    from pypinyin import pinyin
    from pypinyin import Style
    from pypinyin.style._utils import get_finals
    from pypinyin.style._utils import get_initials

    phones = [
        p
        for phone in pinyin(text, style=Style.TONE3)
        for p in [
            get_initials(phone[0], strict=True),
            get_finals(phone[0], strict=True),
        ]
        if len(p) != 0
    ]
    return phones

class espeak_g2p:
    def __init__(self, lang: str = 'en', arpabet: bool = False):
        self.lang = lang
        self.arpabet = arpabet

    def __call__(self, text) -> List[str]: 
        import subprocess
        proc = subprocess.run(['espeak-ng', '-xqv', self.lang, 'espeak', '--sep=_', '--ipa' if self.arpabet else ''], input=text, capture_output=True)
        if proc.returncode != 0:
            raise
        phones = proc.stdout
        if self.arpabet:
            from ipapy.arpabetmapper import ARPABETMapper
            phones = ARPABETMapper().map_unicode_string(proc.stdout, ignore=True, return_as_list=True) 
            return phones
        return phones.replace(' ', '_').split('_')


class G2p_en:
    """On behalf of g2p_en.G2p.

    g2p_en.G2p isn't pickalable and it can't be copied to the other processes
    via multiprocessing module.
    As a workaround, g2p_en.G2p is instantiated upon calling this class.

    """

    def __init__(self, no_space: bool = False):
        self.no_space = no_space
        self.g2p = None

    def __call__(self, text) -> List[str]:
        if self.g2p is None:
            self.g2p = g2p_en.G2p()

        phones = self.g2p(text)
        if self.no_space:
            # remove space which represents word serapater
            phones = list(filter(lambda s: s != " ", phones))
        return phones


class PhonemeTokenizer(AbsTokenizer):
    def __init__(
        self,
        g2p_type: str,
        non_linguistic_symbols: Union[Path, str, Iterable[str]] = None,
        space_symbol: str = "<space>",
        remove_non_linguistic_symbols: bool = False,
    ):
        assert check_argument_types()
        if g2p_type == "g2p_en":
            self.g2p = G2p_en(no_space=False)
        elif g2p_type == "g2p_en_no_space":
            self.g2p = G2p_en(no_space=True)
        elif g2p_type == "pyopenjtalk":
            self.g2p = pyopenjtalk_g2p
        elif g2p_type == "pyopenjtalk_kana":
            self.g2p = pyopenjtalk_g2p_kana
        elif g2p_type == "pypinyin_g2p":
            self.g2p = pypinyin_g2p
        elif g2p_type == "pypinyin_g2p_phone":
            self.g2p = pypinyin_g2p_phone
        elif g2p_type.startswith('espeak_arpabet'):
            lang = g2p_type.split('_')[2] if len(g2p_type.split('_')) > 2 else 'fr-fr'
            self.g2p = espeak_g2p(arpabet=True, lang=lang)
        elif g2p_type.startswith('espeak'):
            lang = g2p_type.split('_')[1] if '_' in g2p_type else 'fr-fr'
            self.g2p = espeak_g2p(lang=lang)
        else:
            raise NotImplementedError(f"Not supported: g2p_type={g2p_type}")

        self.g2p_type = g2p_type
        self.space_symbol = space_symbol
        if non_linguistic_symbols is None:
            self.non_linguistic_symbols = set()
        elif isinstance(non_linguistic_symbols, (Path, str)):
            non_linguistic_symbols = Path(non_linguistic_symbols)
            with non_linguistic_symbols.open("r", encoding="utf-8") as f:
                self.non_linguistic_symbols = set(line.rstrip() for line in f)
        else:
            self.non_linguistic_symbols = set(non_linguistic_symbols)
        self.remove_non_linguistic_symbols = remove_non_linguistic_symbols

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f'g2p_type="{self.g2p_type}", '
            f'space_symbol="{self.space_symbol}", '
            f'non_linguistic_symbols="{self.non_linguistic_symbols}"'
            f")"
        )

    def text2tokens(self, line: str) -> List[str]:
        tokens = []
        while len(line) != 0:
            for w in self.non_linguistic_symbols:
                if line.startswith(w):
                    if not self.remove_non_linguistic_symbols:
                        tokens.append(line[: len(w)])
                    line = line[len(w) :]
                    break
            else:
                t = line[0]
                tokens.append(t)
                line = line[1:]

        line = "".join(tokens)
        tokens = self.g2p(line)
        return tokens

    def tokens2text(self, tokens: Iterable[str]) -> str:
        # phoneme type is not invertible
        return "".join(tokens)
