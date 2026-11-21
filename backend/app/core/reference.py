"""Static administrative reference data.

Tunisia has 24 governorates (wilayas). Codes are QATRA-internal slugs.
Other countries are accepted without governorate validation for now.
"""

TUNISIA_GOVERNORATES: dict[str, dict[str, str]] = {
    "ariana": {"en": "Ariana", "fr": "Ariana", "ar": "أريانة"},
    "beja": {"en": "Beja", "fr": "Béja", "ar": "باجة"},
    "ben_arous": {"en": "Ben Arous", "fr": "Ben Arous", "ar": "بن عروس"},
    "bizerte": {"en": "Bizerte", "fr": "Bizerte", "ar": "بنزرت"},
    "gabes": {"en": "Gabes", "fr": "Gabès", "ar": "قابس"},
    "gafsa": {"en": "Gafsa", "fr": "Gafsa", "ar": "قفصة"},
    "jendouba": {"en": "Jendouba", "fr": "Jendouba", "ar": "جندوبة"},
    "kairouan": {"en": "Kairouan", "fr": "Kairouan", "ar": "القيروان"},
    "kasserine": {"en": "Kasserine", "fr": "Kasserine", "ar": "القصرين"},
    "kebili": {"en": "Kebili", "fr": "Kébili", "ar": "قبلي"},
    "kef": {"en": "Kef", "fr": "Le Kef", "ar": "الكاف"},
    "mahdia": {"en": "Mahdia", "fr": "Mahdia", "ar": "المهدية"},
    "manouba": {"en": "Manouba", "fr": "La Manouba", "ar": "منوبة"},
    "medenine": {"en": "Medenine", "fr": "Médenine", "ar": "مدنين"},
    "monastir": {"en": "Monastir", "fr": "Monastir", "ar": "المنستير"},
    "nabeul": {"en": "Nabeul", "fr": "Nabeul", "ar": "نابل"},
    "sfax": {"en": "Sfax", "fr": "Sfax", "ar": "صفاقس"},
    "sidi_bouzid": {"en": "Sidi Bouzid", "fr": "Sidi Bouzid", "ar": "سيدي بوزيد"},
    "siliana": {"en": "Siliana", "fr": "Siliana", "ar": "سليانة"},
    "sousse": {"en": "Sousse", "fr": "Sousse", "ar": "سوسة"},
    "tataouine": {"en": "Tataouine", "fr": "Tataouine", "ar": "تطاوين"},
    "tozeur": {"en": "Tozeur", "fr": "Tozeur", "ar": "توزر"},
    "tunis": {"en": "Tunis", "fr": "Tunis", "ar": "تونس"},
    "zaghouan": {"en": "Zaghouan", "fr": "Zaghouan", "ar": "زغوان"},
}

assert len(TUNISIA_GOVERNORATES) == 24
