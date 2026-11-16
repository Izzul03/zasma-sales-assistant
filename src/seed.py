"""FICTIONAL demo enquiries. No real customer data is used.

Messages are generated from templates and then passed through the same reader
as live enquiries, so the dashboard reflects what the system actually extracted.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .db import STAGES, LeadDB
from .enquiry import assess, draft_reply, read_enquiry

NAMES = ["Aminah", "Hafiz", "Nurul", "Faizal", "Siti", "Azman", "Farah", "Ikhwan", "Zulaikha", "Rashid", "Aisyah",
         "Hakim", "Mira", "Syafiq", "Liyana", "Imran", "Najwa", "Khairul", "Hidayah", "Amir"]
PLACES = ["Kota Bharu", "Pasir Mas", "Tumpat", "Bachok", "Pasir Puteh", "Machang", "Tanah Merah", "Kuala Krai",
          "Besut", "Setiu", "Gua Musang", "Jeli", "Kuala Terengganu", "Kota Bharu", "Pasir Mas", "Bachok"]
JOBS = ["cikgu", "polis", "jururawat kerajaan", "kerja swasta", "kerja kilang", "engineer oil and gas",
        "berniaga kedai runcit", "usahawan online", "askar", "kerja bank"]
TEMPLATES = [
    "Assalamualaikum, nama saya {name}. Saya {job}, ada tanah sendiri di {place}. Nak bina rumah {storey} "
    "{sqft} kps, {bed} bilik. Bajet RM{budget}k. Boleh mohon pinjaman?",
    "salam, saya {job}. tanah ayah di {place}. berapa harga rumah {storey} {sqft} sqft?",
    "Hi, boleh bina rumah di {place}? bajet {budget} ribu, nak {bed} bilik",
    "Assalamualaikum, saya {name} dari KL tapi tanah keluarga di {place}. Nak tengok katalog reka bentuk rumah "
    "{bed} bilik.",
    "Berapa lama tempoh siap rumah {storey}? Tanah di {place}. Saya {job}.",
    "salam tuan, saya {job}, apa dokumen perlu untuk loan? nak buat rumah di {place}",
]


def seed_demo(db: LeadDB, n: int = 42, seed: int = 11, now: datetime = None) -> int:
    rng = random.Random(seed)
    now = now or datetime.now()
    for _ in range(n):
        msg = rng.choice(TEMPLATES).format(
            name=rng.choice(NAMES), job=rng.choice(JOBS), place=rng.choice(PLACES),
            storey=rng.choice(["setingkat", "setingkat", "2 tingkat"]), sqft=rng.choice([1200, 1500, 1500, 1800, 2000, 2400]),
            bed=rng.choice([3, 4, 4, 5]), budget=rng.choice([180, 200, 230, 250, 280, 320, 400]))
        info = read_enquiry(msg)
        a = assess(info)
        created = now - timedelta(days=rng.randint(0, 100), hours=rng.randint(0, 23))
        age = (now - created).days
        if a["coverage"]["status"] == "not_covered":
            stage = "Tidak berminat"
        elif age < 3:
            stage = "Baru"
        else:
            stage = rng.choices(STAGES, weights=[1, 5, 3, 2, 2])[0]
        due = (now + timedelta(days=rng.choice([-4, -2, -1, 1, 2, 3, 5, 7, 10, 14]))).date().isoformat()
        db.add_lead(msg, info.to_dict(), a["coverage"]["status"], a["estimate"].price if a["estimate"] else None,
                    draft_reply(info, a), created_at=created, stage=stage, synthetic=True, follow_up_due=due)
    return n
