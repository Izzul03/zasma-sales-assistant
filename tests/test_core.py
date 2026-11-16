import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import business_rules as br  # noqa: E402
from src.db import LeadDB  # noqa: E402
from src.enquiry import assess, draft_reply, read_enquiry, read_enquiry_llm  # noqa: E402
from src.llm import LLM  # noqa: E402
from src.seed import seed_demo  # noqa: E402


def test_price_matches_public_faq_example():
    # FAQ: 1,500 sq ft standard is about RM232k
    est = br.estimate_price(1500, "standard", 1)
    assert est.price == 232_500
    assert (est.months_min, est.months_max) == (10, 12)
    assert br.estimate_price(2000, "premium", 2).price == 330_000
    assert br.estimate_price(2000, "premium", 2).months_text == "12–14 bulan"


def test_invalid_inputs():
    with pytest.raises(ValueError):
        br.estimate_price(0)
    with pytest.raises(ValueError):
        br.estimate_price(1000, "gold")


def test_monthly_instalment():
    assert br.monthly_instalment(0, 4, 30) == 0
    assert round(br.monthly_instalment(120_000, 0, 10)) == 1000
    assert round(br.monthly_instalment(200_000, 4.0, 30), 2) == 954.83


def test_coverage():
    assert br.coverage("Pasir Mas")["status"] == "covered"
    assert br.coverage("Besut")["status"] == "covered"
    assert br.coverage("Kuala Terengganu")["status"] == "not_covered"
    assert br.coverage("Ipoh")["status"] == "unknown"
    assert br.coverage(None)["status"] == "unknown"


def test_read_full_enquiry():
    i = read_enquiry("Assalamualaikum, nama saya Aminah. Saya cikgu, ada tanah sendiri di Pasir Mas. Nak bina "
                     "rumah setingkat 1500 kps, 4 bilik. Bajet RM220k. Boleh mohon LPPSA?")
    assert (i.name, i.place, i.segment, i.budget, i.sqft, i.bedrooms, i.storeys, i.has_land) == \
        ("Aminah", "Pasir Mas", "kerajaan", 220_000, 1500, 4, 1, True)
    assert "pinjaman" in i.intents


def test_land_location_beats_workplace():
    i = read_enquiry("saya kerja kilang di KL tapi tanah ayah di Machang, nak rumah 2 tingkat 2400 sqft premium")
    assert i.place == "Machang" and i.storeys == 2 and i.spec == "premium" and i.segment == "swasta"


def test_budget_formats():
    assert read_enquiry("bajet 300 ribu").budget == 300_000
    assert read_enquiry("bajet RM 250,000").budget == 250_000
    assert read_enquiry("budget 280k").budget == 280_000


def test_budget_check_and_draft():
    i = read_enquiry("Saya cikgu, tanah di Bachok, rumah setingkat 1500 kps, bajet RM220k")
    a = assess(i)
    assert a["budget_check"]["fits"] is False
    reply = draft_reply(i, a)
    assert "RM232,500" in reply and "1,419 kps" in reply and "Penyata kewangan bank 1 bulan" in reply


def test_not_covered_and_no_land():
    a = assess(read_enquiry("boleh bina di Kuala Terengganu?"))
    assert "di luar kawasan liputan" in draft_reply(read_enquiry("boleh bina di Kuala Terengganu?"), a)
    i = read_enquiry("takde tanah lagi, boleh carikan tanah?")
    assert i.has_land is False and "tidak menyediakan khidmat mencari tanah" in draft_reply(i, assess(i))


class _Fake:
    def __init__(self, payload):
        self.payload = payload
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kw):
        msg = type("M", (), {"content": json.dumps(self.payload)})()
        return type("R", (), {"choices": [type("Ch", (), {"message": msg})()]})()


def test_llm_reader_validates_output():
    llm = LLM(_client=_Fake({"name": "Ali", "place": "Tumpat", "segment": "hacker", "budget": "abc",
                              "sqft": 1800, "storeys": 2, "has_land": "yes", "intents": ["harga", "bogus"]}))
    i = read_enquiry_llm("whatever", llm)
    assert i.segment is None and i.budget is None and i.sqft == 1800 and i.has_land is None
    assert i.intents == ["harga"] and i.method == "llm"
    # price still comes from Python, not the LLM
    assert assess(i)["estimate"].price == 1800 * 155


def test_db_flow(tmp_path):
    db = LeadDB(tmp_path / "l.db")
    i = read_enquiry("Saya Hafiz, tanah di Tumpat, bajet 250k")
    a = assess(i)
    lid = db.add_lead("msg", i.to_dict(), a["coverage"]["status"], None, draft_reply(i, a))
    db.mark_replied(lid, "jawapan akhir", "Demo Jurujual A")
    lead = db.lead(lid)
    assert lead["stage"] == "Sudah dihubungi" and lead["replied_by"] == "Demo Jurujual A"
    db.set_stage(lid, "Temu janji", "Demo Jurujual A")
    assert [x["action"] for x in db.log(lid)] == ["DICIPTA", "JAWAPAN_DIHANTAR", "PERINGKAT"]
    with pytest.raises(ValueError):
        db.set_stage(lid, "Hacked", "x")
    assert seed_demo(db, n=10) == 10 and db.count() == 11
