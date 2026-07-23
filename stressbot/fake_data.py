from __future__ import annotations

import random
import string
import threading
import uuid
from dataclasses import dataclass


FIRST_NAMES = [
    "أم فاطمة",
    "أبو محمد",
    "أم مريم",
    "أبو عبدالله",
    "أم سارة",
    "أبو خالد",
    "أم هدى",
    "أبو فهد",
    "أم نورة",
    "أبو ناصر",
    "أم ريم",
    "أبو سلطان",
    "أم جواهر",
    "أبو راشد",
    "أم سلمى",
    "أبو عيسى",
    "أم عائشة",
    "أبو حمد",
    "أم حصة",
    "أبو بدر",
]

FAMILY_NAMES = [
    "العنزي",
    "آل فهد",
    "آل سعود",
    "البلوشي",
    "آل نهيان",
    "آل مكتوم",
    "آل راشد",
    "آل سعيد",
    "آل زايد",
    "آل خليفة",
    "آل مشاري",
    "آل حمد",
    "آل جابر",
    "آل خالد",
]

_counter_lock = threading.Lock()
_counter = 0


def _next_suffix() -> str:
    global _counter
    with _counter_lock:
        _counter += 1
        return f"{_counter:06d}{uuid.uuid4().hex[:6]}"


def arabic_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(FAMILY_NAMES)}"


def saudi_phone() -> str:
    """Local Saudi mobile format 05XXXXXXXX."""
    return "05" + "".join(random.choices(string.digits, k=8))


def fake_email() -> str:
    return f"stress.{_next_suffix()}@example.invalid"


def random_otp(length: int | None = None) -> str:
    n = length or random.randint(4, 6)
    return "".join(random.choices(string.digits, k=n))


def _luhn_checksum(digits: str) -> int:
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - (total % 10)) % 10


def _is_repeated_digits(digits: str) -> bool:
    return len(digits) > 0 and len(set(digits)) == 1


def _is_sequential_digits(digits: str) -> bool:
    if len(digits) < 6:
        return False
    asc = all(int(digits[i]) == (int(digits[i - 1]) + 1) % 10 for i in range(1, len(digits)))
    desc = all(int(digits[i]) == (int(digits[i - 1]) - 1) % 10 for i in range(1, len(digits)))
    return asc or desc


def _generate_pan(prefix: str, length: int) -> str:
    body_len = length - len(prefix) - 1
    for _ in range(100):
        body = "".join(random.choices(string.digits, k=body_len))
        partial = prefix + body
        check = _luhn_checksum(partial + "0")
        pan = partial + str(check)
        if not _is_repeated_digits(pan) and not _is_sequential_digits(pan):
            return pan
    return prefix + "0" * body_len + str(_luhn_checksum(prefix + "0" * body_len + "0"))


@dataclass
class FakeCard:
    number: str
    expiry: str
    cvv: str
    brand: str


def fake_card() -> FakeCard:
    brand = random.choice(["visa", "mastercard", "mada"])
    if brand == "visa":
        number = _generate_pan("4", 16)
        cvv_len = 3
    elif brand == "mastercard":
        number = _generate_pan("51", 16)
        cvv_len = 3
    else:
        number = _generate_pan("6", 16)
        cvv_len = 3

    month = random.randint(1, 12)
    year = random.randint(28, 32)
    expiry = f"{month:02d}/{year:02d}"
    cvv = "".join(random.choices(string.digits, k=cvv_len))
    return FakeCard(number=number, expiry=expiry, cvv=cvv, brand=brand)


@dataclass
class FakeUser:
    name: str
    email: str
    phone: str
    card: FakeCard

    @classmethod
    def generate(cls) -> FakeUser:
        return cls(
            name=arabic_name(),
            email=fake_email(),
            phone=saudi_phone(),
            card=fake_card(),
        )
