"""帮派仓库与物资管理系统"""
import time
from dataclasses import dataclass, field

RANKS = ("leader", "vice_leader", "elite", "member")
RANK_LEVEL = {rank: level for level, rank in enumerate(reversed(RANKS))}

CATEGORIES = ("material", "equipment", "consumable")

# 各权限等级可取出的物品稀有度上限
WITHDRAW_RARITY_LIMIT = {
    "leader": {"common", "uncommon", "rare", "epic", "legendary"},
    "vice_leader": {"common", "uncommon", "rare", "epic"},
    "elite": {"common", "uncommon", "rare"},
    "member": {"common", "uncommon"},
}

RARE_KEYWORDS = ("legendary", "epic", "rare")

DEFAULT_STACK_LIMIT = 999
BASE_CAPACITY = 100
CAPACITY_PER_LEVEL = 20
WITHDRAW_COOLDOWN_SECONDS = 30.0
DAILY_WITHDRAW_LIMIT = 20
DAILY_DEPOSIT_LIMIT = 50


@dataclass
class WarehouseItem:
    iid: str
    name: str
    quantity: int = 1
    category: str = "material"
    rarity: str = "common"

    def __post_init__(self):
        if self.category not in CATEGORIES:
            self.category = "material"


class WarehouseSystem:
    def __init__(self, guild_level: int = 1):
        self.guild_level = guild_level
        self.items: list[WarehouseItem] = []
        self.logs: list[dict] = []
        self.access_log: list[dict] = self.logs  # 同一日志的两个视图
        self.capacity: int = self.get_capacity(guild_level)
        self._last_withdraw_at: dict[str, float] = {}
        self._daily_counts: dict[str, dict[str, int]] = {}

    # ---------- bug1: 权限控制 ----------
    def can_withdraw(self, member_rank: str, item: str) -> bool:
        if member_rank not in WITHDRAW_RARITY_LIMIT:
            return False
        rarity = self._rarity_of(item)
        return rarity in WITHDRAW_RARITY_LIMIT[member_rank]

    def can_deposit(self, member_rank: str) -> bool:
        return member_rank in RANK_LEVEL

    def can_manage(self, member_rank: str) -> bool:
        """整理/分类/调整仓库仅副会长及以上可操作"""
        return RANK_LEVEL.get(member_rank, -1) >= RANK_LEVEL["vice_leader"]

    @staticmethod
    def _rarity_of(item: str) -> str:
        lowered = item.lower()
        for keyword in RARE_KEYWORDS:
            if keyword in lowered:
                return keyword
        return "common"

    # ---------- bug2: 操作日志 ----------
    def record_action(self, member: str, action: str, item: str, qty: int):
        self.logs.append({
            "member": member,
            "action": action,
            "item": item,
            "quantity": qty,
            "timestamp": time.time(),
        })

    # ---------- bug3: 容量随帮派等级成长 ----------
    def get_capacity(self, guild_level: int) -> int:
        level = max(1, int(guild_level))
        return BASE_CAPACITY + (level - 1) * CAPACITY_PER_LEVEL

    def set_guild_level(self, guild_level: int):
        self.guild_level = max(1, int(guild_level))
        self.capacity = self.get_capacity(self.guild_level)

    # ---------- bug4: 堆叠上限 ----------
    def get_stack_limit(self, item: str) -> int:
        return DEFAULT_STACK_LIMIT

    def _used_slots(self) -> int:
        limit = DEFAULT_STACK_LIMIT
        return sum(-(-item.quantity // limit) for item in self.items)

    def deposit(self, member: str, member_rank: str, item: WarehouseItem) -> bool:
        if not self.can_deposit(member_rank):
            return False
        if not self._check_daily_limit(member, "deposit", DAILY_DEPOSIT_LIMIT):
            return False
        limit = self.get_stack_limit(item.name)
        needed = -(-item.quantity // limit)
        if self._used_slots() + needed > self.capacity:
            return False
        remaining = item.quantity
        for existing in self.items:
            if existing.name == item.name and existing.category == item.category:
                room = limit - existing.quantity
                take = min(room, remaining)
                existing.quantity += take
                remaining -= take
                if remaining == 0:
                    break
        while remaining > 0:
            take = min(limit, remaining)
            self.items.append(WarehouseItem(
                iid=item.iid, name=item.name, quantity=take,
                category=item.category, rarity=item.rarity,
            ))
            remaining -= take
        self.record_action(member, "deposit", item.name, item.quantity)
        return True

    # ---------- bug5: 冷却与每日次数 ----------
    def get_withdraw_cooldown(self, member: str) -> float:
        last = self._last_withdraw_at.get(member)
        if last is None:
            return WITHDRAW_COOLDOWN_SECONDS
        remaining = WITHDRAW_COOLDOWN_SECONDS - (time.time() - last)
        return max(remaining, 0.0) if remaining > 0 else WITHDRAW_COOLDOWN_SECONDS

    def _check_daily_limit(self, member: str, action: str, limit: int) -> bool:
        today = time.strftime("%Y-%m-%d")
        key = f"{member}:{today}"
        counts = self._daily_counts.setdefault(key, {"deposit": 0, "withdraw": 0})
        if counts[action] >= limit:
            return False
        counts[action] += 1
        return True

    def withdraw(self, member: str, member_rank: str, item_name: str, qty: int) -> bool:
        if not self.can_withdraw(member_rank, item_name):
            return False
        if self._last_withdraw_at.get(member, 0) + WITHDRAW_COOLDOWN_SECONDS > time.time():
            return False
        if not self._check_daily_limit(member, "withdraw", DAILY_WITHDRAW_LIMIT):
            return False
        remaining = qty
        for existing in list(self.items):
            if existing.name != item_name:
                continue
            take = min(existing.quantity, remaining)
            existing.quantity -= take
            remaining -= take
            if existing.quantity == 0:
                self.items.remove(existing)
            if remaining == 0:
                break
        if remaining > 0:
            return False
        self._last_withdraw_at[member] = time.time()
        self.record_action(member, "withdraw", item_name, qty)
        return True

    # ---------- bug6: 分类 ----------
    def get_categories(self) -> list:
        return list(CATEGORIES)

    def get_items_by_category(self, category: str) -> list[WarehouseItem]:
        return [item for item in self.items if item.category == category]

    # ---------- bug7: 解散返还 ----------
    def dissolve_guild(self, guild_id: str, members: list) -> dict:
        returned: dict[str, list[dict]] = {}
        total_contribution = sum(max(0, m.get("contribution", 0)) for m in members)
        if not members:
            self.items.clear()
            return {"guild_id": guild_id, "returned": returned}

        # 每个成员按贡献比例分得每样物资的数量
        allocations: dict[str, dict[str, int]] = {m["id"]: {} for m in members}
        for item in self.items:
            left = item.quantity
            for index, member in enumerate(members):
                if index == len(members) - 1:
                    share = left
                elif total_contribution > 0:
                    share = item.quantity * max(0, member.get("contribution", 0)) // total_contribution
                else:
                    share = item.quantity // len(members)
                share = min(share, left)
                left -= share
                if share > 0:
                    key = f"{item.name}|{item.category}"
                    allocations[member["id"]][key] = allocations[member["id"]].get(key, 0) + share

        for member in members:
            bundle = [
                {"item": key.rsplit("|", 1)[0], "category": key.rsplit("|", 1)[1], "quantity": qty}
                for key, qty in allocations[member["id"]].items()
            ]
            if bundle:
                returned[member["id"]] = bundle
                self.record_action(member["id"], "dissolve_return", guild_id,
                                   sum(entry["quantity"] for entry in bundle))

        self.items.clear()
        return {"guild_id": guild_id, "returned": returned}
