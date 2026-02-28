# local_translator.py
# Offline tarjima: UZB <-> RUS <-> ENG (MarianMT / OPUS)
# Birinchi ishga tushganda modellar yuklanadi (internet kerak).
# Keyin cache'dan ishlaydi.

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

import torch
from transformers import MarianMTModel, MarianTokenizer


@dataclass
class _ModelPack:
    tokenizer: MarianTokenizer
    model: MarianMTModel


class LocalTranslator:
    """
    UZ/RU/EN o'rtasida offline tarjima.
    Supported routes (default):
      uz->ru, ru->uz,
      ru->en, en->ru,
      en->ru->uz (en->uz orqali),
      uz->ru->en (uz->en orqali)
    """

    def __init__(self, device: str | None = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # Eng ishonchli OPUS-MT yo'nalishlari:
        # (src, dst) -> HF model name
        self.model_map: Dict[Tuple[str, str], str] = {
            ("uz", "ru"): "Helsinki-NLP/opus-mt-uz-ru",
            ("ru", "uz"): "Helsinki-NLP/opus-mt-ru-uz",
            ("ru", "en"): "Helsinki-NLP/opus-mt-ru-en",
            ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
        }

        self._cache: Dict[Tuple[str, str], _ModelPack] = {}

    def _get_pack(self, src: str, dst: str) -> _ModelPack:
        key = (src, dst)
        if key in self._cache:
            return self._cache[key]

        if key not in self.model_map:
            raise ValueError(f"Route not supported: {src}->{dst}")

        name = self.model_map[key]
        tok = MarianTokenizer.from_pretrained(name)
        mdl = MarianMTModel.from_pretrained(name).to(self.device)
        mdl.eval()

        pack = _ModelPack(tokenizer=tok, model=mdl)
        self._cache[key] = pack
        return pack

    @torch.inference_mode()
    def _translate_one_step(self, text: str, src: str, dst: str) -> str:
        pack = self._get_pack(src, dst)
        batch = pack.tokenizer([text], return_tensors="pt", truncation=True, max_length=512).to(self.device)

        gen = pack.model.generate(
            **batch,
            max_new_tokens=256,
            num_beams=4,
            early_stopping=True
        )
        out = pack.tokenizer.batch_decode(gen, skip_special_tokens=True)[0]
        return out

    def translate(self, text: str, src: str, dst: str) -> str:
        src = src.lower().strip()
        dst = dst.lower().strip()

        if src == dst:
            return text

        # 1-qadam: to'g'ridan-to'g'ri bo'lsa
        if (src, dst) in self.model_map:
            return self._translate_one_step(text, src, dst)

        # 2-qadam: yo'l topish (pivot)
        # en<->uz uchun: en->ru->uz yoki uz->ru->en
        if src == "en" and dst == "uz":
            ru = self._translate_one_step(text, "en", "ru")
            uz = self._translate_one_step(ru, "ru", "uz")
            return uz

        if src == "uz" and dst == "en":
            ru = self._translate_one_step(text, "uz", "ru")
            en = self._translate_one_step(ru, "ru", "en")
            return en

        raise ValueError(f"Route not supported: {src}->{dst}")
