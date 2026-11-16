"""Business rules taken from ZASMA HOME's PUBLIC website (accessed 16 Nov 2026).

Source: https://zasmahome.com/soalan-lazim/
* Standard spec RM155 per sq ft, premium spec RM165 per sq ft
* Example: 1,500 sq ft (4 bedrooms, 3 bathrooms) about RM232k
* Build time: 10-12 months (1 storey), 12-14 months (2 storeys)
* Coverage: all of Kelantan; in Terengganu only Besut, Jertih and Setiu
* Loan documents differ for private-sector staff, civil servants and business owners
* ZASMA builds only on land the customer already owns

These values are hard-coded here as a demonstration. In a real deployment they
would be maintained by ZASMA staff, because prices change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

SOURCE_URL = "https://zasmahome.com/soalan-lazim/"

RATES_PER_SQFT = {"standard": 155.0, "premium": 165.0}
SPEC_LABELS = {"standard": "Standard (RM155/kps)", "premium": "Premium (RM165/kps)"}
BUILD_MONTHS = {1: (10, 12), 2: (12, 14)}

KELANTAN_DISTRICTS = [
    "Kota Bharu", "Pasir Mas", "Tumpat", "Pasir Puteh", "Bachok", "Kuala Krai", "Machang",
    "Tanah Merah", "Jeli", "Gua Musang", "Lojing",
]
TERENGGANU_COVERED = ["Besut", "Jertih", "Setiu"]
TERENGGANU_NOT_COVERED = ["Kuala Terengganu", "Dungun", "Kemaman", "Marang", "Hulu Terengganu", "Kuala Nerus"]
OTHER_PLACES = ["Kuala Lumpur", "Selangor", "Johor", "Pahang", "Kedah", "Perak", "Pulau Pinang", "Melaka",
                "Negeri Sembilan", "Perlis", "Sabah", "Sarawak", "Putrajaya"]

# Documents listed publicly per customer segment.
LOAN_DOCUMENTS: Dict[str, Dict] = {
    "kerajaan": {
        "label": "Penjawat awam (LPPSA)",
        "financing": "Pinjaman LPPSA (anggaran kelulusan 2 hingga 3 bulan)",
        "documents": ["Penyata kewangan bank 1 bulan"],
    },
    "swasta": {
        "label": "Pekerja swasta (pinjaman bank)",
        "financing": "Pinjaman bank (anggaran proses dokumen 1 hingga 2 bulan)",
        "documents": ["Slip gaji 3 bulan terkini", "Senarai komitmen bulanan dengan bank"],
    },
    "peniaga": {
        "label": "Pemilik perniagaan",
        "financing": "Pinjaman bank / SJKP (Bank Muamalat)",
        "documents": ["Penyata kewangan 6 bulan", "Pendaftaran SSM lebih setahun",
                      "Dokumen pinjaman SJKP (Bank Muamalat), jika berkaitan"],
    },
}
# Commonly needed for any house build. NOT listed on the ZASMA FAQ, so marked as "to confirm".
COMMON_DOCUMENTS_TO_CONFIRM = ["Salinan kad pengenalan", "Salinan geran / hak milik tanah"]


@dataclass
class Estimate:
    sqft: float
    spec: str
    storeys: int
    rate: float
    price: float
    months_min: int
    months_max: int

    @property
    def months_text(self) -> str:
        return f"{self.months_min}–{self.months_max} bulan"


def estimate_price(sqft: float, spec: str = "standard", storeys: int = 1) -> Estimate:
    if sqft is None or sqft <= 0:
        raise ValueError("Keluasan mesti lebih daripada 0 kps.")
    if spec not in RATES_PER_SQFT:
        raise ValueError(f"Spesifikasi tidak dikenali: {spec}")
    storeys = 2 if storeys and storeys >= 2 else 1
    rate = RATES_PER_SQFT[spec]
    lo, hi = BUILD_MONTHS[storeys]
    return Estimate(sqft=float(sqft), spec=spec, storeys=storeys, rate=rate, price=round(sqft * rate, 2),
                    months_min=lo, months_max=hi)


def max_sqft_for_budget(budget: float, spec: str = "standard") -> float:
    return budget / RATES_PER_SQFT[spec]


def monthly_instalment(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard amortised loan payment. Rate and tenure are user assumptions, not bank offers."""
    if principal <= 0:
        return 0.0
    n = int(years) * 12
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def coverage(place: Optional[str]) -> Dict:
    """Return whether ZASMA covers a place, based on the public FAQ."""
    if not place:
        return {"status": "unknown", "message": "Lokasi tanah belum dinyatakan."}
    p = place.strip().lower()
    for d in KELANTAN_DISTRICTS:
        if d.lower() == p:
            return {"status": "covered", "message": f"{d}, Kelantan berada dalam kawasan liputan ZASMA."}
    for d in TERENGGANU_COVERED:
        if d.lower() == p:
            return {"status": "covered", "message": f"{d}, Terengganu berada dalam kawasan liputan ZASMA."}
    for d in TERENGGANU_NOT_COVERED + OTHER_PLACES:
        if d.lower() == p:
            return {"status": "not_covered",
                    "message": f"{d} di luar kawasan liputan. ZASMA meliputi seluruh Kelantan, serta Besut, "
                               "Jertih dan Setiu di Terengganu."}
    return {"status": "unknown", "message": f"Lokasi '{place}' perlu disahkan oleh jurujual."}


def all_places() -> List[str]:
    return KELANTAN_DISTRICTS + TERENGGANU_COVERED + TERENGGANU_NOT_COVERED + OTHER_PLACES
