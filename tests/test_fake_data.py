from __future__ import annotations

import re

from stressbot.fake_data import (
    FakeUser,
    _luhn_checksum,
    fake_card,
    fake_email,
    saudi_phone,
)


def _pan_passes_luhn(pan: str) -> bool:
    digits = [int(c) for c in pan]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def test_saudi_phone_format() -> None:
    for _ in range(50):
        phone = saudi_phone()
        assert re.fullmatch(r"05\d{8}", phone), phone


def test_fake_email_unique_and_domain() -> None:
    a = fake_email()
    b = fake_email()
    assert a != b
    assert "@" in a
    assert a.split("@")[1] in ("gmail.com", "hotmail.com", "outlook.sa", "yahoo.com", "icloud.com")


def test_luhn_checksum_completes_valid_pan() -> None:
    partial = "7992739871"
    check = _luhn_checksum(partial + "0")
    pan = partial + str(check)
    assert _pan_passes_luhn(pan)


def test_fake_card_luhn_valid_and_length() -> None:
    for _ in range(30):
        card = fake_card()
        assert len(card.number) == 16
        assert card.number.isdigit()
        assert _pan_passes_luhn(card.number)
        assert card.cvv.isdigit() and len(card.cvv) == 3
        assert "/" in card.expiry


def test_fake_user_generate() -> None:
    user = FakeUser.generate()
    assert user.name.strip()
    assert re.fullmatch(r"05\d{8}", user.phone)
    assert user.card.number.isdigit()
