"""Loc menu theo quyen (feature-gating) cho bot hostvn.

- Admin (chat_id trong ADMIN_IDS) -> get_user_features() = None -> thay TAT CA nhom.
- User duoc phep khac -> tap feature theo USER_FEATURES, mac dinh = tat ca nhom VIEW.
- BOT_MODE=notify: chan moi thao tac ghi (can_write=False) va gioi han o cac nhom VIEW.
- Chat khong nam trong ALLOWED_CHAT_IDS -> khong dung duoc bot.
"""
from __future__ import annotations

from typing import Optional

import config as C


def is_allowed(chat_id: int) -> bool:
    return chat_id in C.ALLOWED_CHAT_IDS


def is_admin(chat_id: int) -> bool:
    return chat_id in C.ADMIN_IDS


def can_write(chat_id: int) -> bool:
    """Che do notify -> chi xem. Che do menu -> admin moi duoc ghi."""
    return C.BOT_MODE != "notify" and is_admin(chat_id)


def get_user_features(chat_id: int) -> Optional[set[str]]:
    """None = thay tat ca (admin). Nguoc lai tra tap feature_key duoc phep."""
    if not is_allowed(chat_id):
        return set()
    if C.BOT_MODE == "notify":
        # Ai cung chi xem cac nhom VIEW.
        return set(C.VIEW_FEATURES)
    if is_admin(chat_id):
        return None
    return set(C.USER_FEATURES.get(chat_id, C.VIEW_FEATURES))


def can_see(feature_key: Optional[str], features: Optional[set[str]]) -> bool:
    """Admin (features=None) thay tat ca; nguoc lai chi thay nut co key trong tap."""
    return features is None or feature_key in features


def has_feature(chat_id: int, feature_key: str) -> bool:
    """Kiem tra lai quyen o phia handler (khong chi dua vao viec an nut)."""
    features = get_user_features(chat_id)
    return features is None or feature_key in features
