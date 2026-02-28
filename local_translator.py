# local_translator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

import torch
from transformers import MarianMTModel, MarianTokenizer


@dataclass
class _Pack:
    tok: MarianTokenizer
    mdl: MarianMTModel


class LocalTranslator:
    """
    Offline tarjima: UZ <-> RU <-> EN
    Direct: uz<->ru, ru<->en
    Pivot: uz<->en (ru orqali)
    """
    def __init__(self, device: str | None = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        self.model_map: Dict[Tuple[str, str], str] = {
            ("uz", "ru"): "Helsinki-NLP/opus-mt-uz-ru",
            ("ru", "uz"): "Helsinki-NLP/opus-mt-ru-uz",
            ("ru", "en"): "Helsinki-NLP/opus-mt-ru-en",
            ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
        }
        self.cache: Dict[Tuple[str, str], _Pack] = {}

    def _load(self, src: str, dst: str) -> _Pack:
        key = (src, dst)
        if key in self.cache:
            return self.cache[key]
        name = self.model_map[key]
        tok = MarianTokenizer.from_pretrained(name)
        mdl = MarianMTModel.from_pretrained(name).to(self.device)
        mdl.eval()
        pack = _Pack(tok=tok, mdl=mdl)
        self.cache[key] = pack
        return pack

    @torch.inference_mode()
    def _step(self, text: str, src: str, dst: str) -> str:
        pack = self._load(src, dst)
        batch = pack.tok([text], return_tensors="pt", truncation=True, max_length=512).to(self.device)
        out_ids = pack.mdl.generate(**batch, num_beams=4, max_new_tokens=256, early_stopping=True)
        return pack.tok.batch_decode(out_ids, skip_special_tokens=True)[0]

    def translate(self, text: str, src: str, dst: str) -> str:
        src, dst = src.lower().strip(), dst.lower().strip()
        if src == dst:
            return text

        if (src, dst) in self.model_map:
            return self._step(text, src, dst)

        # Pivot: uz<->en ru orqali
        if src == "uz" and dst == "en":
            ru = self._step(text, "uz", "ru")
            return self._step(ru, "ru", "en")

        if src == "en" and dst == "uz":
            ru = self._step(text, "en", "ru")
            return self._step(ru, "ru", "uz")

        raise ValueError(f"Route not supported: {src}->{dst}")
