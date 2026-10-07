"""Günlükleme: Windows konsolunda (cp1254) emoji içeren mesaj UnicodeEncodeError yığını basmamalı (2026-10-08)."""
import io
import logging

from app.logging_setup import hatasiz_akis


def _cp1254_akisi():
    ham = io.BytesIO()
    return ham, io.TextIOWrapper(ham, encoding="cp1254", errors="strict", write_through=True)


def test_cp1254_konsolda_emoji_hata_vermez(capsys):
    ham, akis = _cp1254_akisi()
    isleyici = logging.StreamHandler(hatasiz_akis(akis))
    kayitci = logging.getLogger("test.gunlukleme.emoji")
    kayitci.addHandler(isleyici)
    kayitci.propagate = False
    try:
        kayitci.warning("✅ Scheduler kuruldu: 6 job tanımlandı")
    finally:
        kayitci.removeHandler(isleyici)
    cikti = ham.getvalue().decode("cp1254")
    assert "\\u2705 Scheduler kuruldu: 6 job tanımlandı" in cikti, "emoji kaçışlanır, Türkçe karakter korunur"
    assert "Logging error" not in capsys.readouterr().err


def test_duzeltme_olmadan_hata_veriyordu():
    """Düzeltmenin neyi önlediğini belgeler: katı cp1254 akışı emojide UnicodeEncodeError fırlatır."""
    _, akis = _cp1254_akisi()
    try:
        akis.write("✅")
    except UnicodeEncodeError:
        return
    raise AssertionError("cp1254 katı akış emojiyi kabul etmemeliydi")


def test_reconfigure_olmayan_akis_sorun_cikarmaz():
    class Akis:
        def write(self, s):
            pass
    a = Akis()
    assert hatasiz_akis(a) is a
