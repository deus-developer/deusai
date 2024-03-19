from typing import Dict, List, Tuple, Set

from src.wasteland_wars.enums import Fraction

chat_id = 430930191

raid_kms: Set[int] = {5, 9, 12, 16, 20, 24, 28, 32, 38, 46, 53, 54, 57, 63}
raid_kms_tz: Set[int] = {24, 28, 32, 38, 53, 57, 63}


KEY_STAT_ICON_BY_NAME: Dict[str, str] = {
    "hp": "❤️",
    "power": "💪",
    "accuracy": "🎯",
    "oratory": "🗣",
    "agility": "🤸🏽️",
}
KEY_STAT_BASE_CAP_BY_NAME: Dict[str, int] = {
    "hp": 1550,
    "power": 1300,
    "accuracy": 1300,
    "oratory": 1200,
    "agility": 1200,
}

KEY_STATS: Dict[str, str] = {
    "hp": "❤️Здоровье",
    "power": "💪Сила",
    "accuracy": "🎯Меткость",
    "oratory": "🗣Харизма",
    "agility": "🤸🏽️Ловкость",
}

COLOR_BY_KEY_STAT: Dict[str, str] = {
    "hp": "rgb(214, 14, 0)",
    "power": "rgb(245, 139, 17)",
    "accuracy": "rgb(2, 224, 6)",
    "oratory": "rgb(2, 34, 179)",
    "agility": "rgb(17, 242, 238)",
}

group_type_translate: Dict[str, str] = {
    "gang": "Банда",
    "goat": "Козёл",
    "squad": "Отряд",
}

group_type_icon: Dict[str, str] = {
    "gang": "🤘",
    "goat": "🐐",
    "squad": "🔰",
}

raid_locations: Dict[str, Tuple[str, int]] = {
    "Старая фабрика": ("📦", 5),
    'Завод "Ядер-Кола"': ("🕳", 9),
    "Тюрьма": ("💊", 12),
    "Склады": ("🍗", 16),
    "Датацентр": ("🔹", 20),
    "🚷Госпиталь": ("❤️", 24),
    '🚷Завод "Электрон"': ("💡", 28),
    "🚷Офисное здание": ("💾", 32),
    "🚷Иридиевая шахта": ("🔩", 38),
    "Склад металла": ("🔗", 46),
    "🚷Радиостанция": ("🔗", 53),
    "Водохранилище": ("🥃", 54),
    "🚷Реактор": ("🔗", 57),
    "🚷Институт": ("🔸", 63),
}
raid_locations_by_km: Dict[int, Tuple[str, str]] = {
    5: ("Старая фабрика", "📦"),
    9: ('Завод "Ядер-Кола"', "🕳"),
    12: ("Тюрьма", "💊"),
    16: ("Склады", "🍗"),
    20: ("Датацентр", "🔹"),
    24: ("Госпиталь", "❤️"),
    28: ('Завод "Электрон"', "💡"),
    32: ("Офисное здание", "💾"),
    38: ("Иридиевая шахта", "🔩"),
    46: ("Склад металла", "🔗"),
    53: ("Радиостанция", "🔗"),
    54: ("Водохранилище", "🥃"),
    57: ("Реактор", "🔗"),
    63: ("Институт", "🔸"),
}

raid_kms_by_league: Dict[str, List[int]] = {
    "🥇Савант-лига": [20, 38, 54, 57, 63],
    "🥈Вторая лига": [16, 28, 46, 53],
    "🥉Детская лига": [5, 9, 12, 24, 32],
}

raid_kms_price: Dict[int, float] = {
    5: 4.2,
    9: 8.4,
    12: 11.2,
    16: 14,
    20: 18.2,
    24: 22.4,
    28: 25.2,
    32: 29.4,
    38: 35,
    46: 42,
    53: 49,
    54: 50.4,
    57: 53.2,
    63: 53.8,
}
raid_kms_weight: Dict[int, int] = {
    5: 15,
    9: 15,
    12: 15,
    16: 15,
    20: 15,
    24: 20,
    28: 20,
    32: 20,
    38: 20,
    46: 15,
    53: 20,
    54: 15,
    57: 20,
    63: 20,
}


fractions: Dict[Fraction, str] = {
    Fraction.REPUBLIC: "⚛️Республика",
    Fraction.THUNGS: "🔪Головорезы",
    Fraction.VAULT4: "⚙️Убежище 4",
    Fraction.MEGATON: "💣Мегатонна",
    Fraction.CITADEL: "👁‍🗨Цитадель",
    Fraction.CONCORD: "🔰Конкорд",
}
fraction_icons: Dict[Fraction, str] = {
    Fraction.REPUBLIC: "⚛️",
    Fraction.THUNGS: "🔪",
    Fraction.VAULT4: "⚙️",
    Fraction.MEGATON: "💣",
    Fraction.CITADEL: "👁‍🗨",
    Fraction.CONCORD: "🔰",
}
fractions_by_name: Dict[str, Fraction] = {
    "⚙️Убежище 6": Fraction.REPUBLIC,
    "⚛️Республика": Fraction.REPUBLIC,
    "🔪Головорезы": Fraction.THUNGS,
    "⚙️Убежище 4": Fraction.VAULT4,
    "💣Мегатонна": Fraction.MEGATON,
    "⚙️Убежище 11": Fraction.CITADEL,
    "👁‍🗨Цитадель": Fraction.CITADEL,
    "🔰Конкорд": Fraction.CONCORD,
}
fractions_by_icon: Dict[str, Fraction] = {
    "⚛️": Fraction.REPUBLIC,
    "🔪": Fraction.THUNGS,
    "⚙️": Fraction.VAULT4,
    "💣": Fraction.MEGATON,
    "👁‍🗨": Fraction.CITADEL,
    "🔰": Fraction.CONCORD,
}
