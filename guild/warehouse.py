"""帮派仓库与物资管理系统 - 修复版"""
import time
from dataclasses import dataclass, field

# bug1 修复: 权限等级
RANKS = ("member", "elite", "vice_leader", "leader")
RANK_LEVEL = {rank: idx for idx, rank in enumerate(RANKS)}
# 各操作所需最低权限
ACTION_MIN_RANK = {
    "deposit": "member",
    "withdraw": "elite",
    "withdraw_rare": "vice_leader",
    "manage": "leader",
}
RARE_KEYWORDS = ("legendary", "epic", "rare")

# bug3 修复: 容量随帮派等级增长
BASE_CAPACITY = 100
CAPACITY_PER_LEVEL = 20

# bug4 修复: 堆叠上限
DEFAULT_STACK_LIMIT = 999

# bug5 修复: 冷却与每日次数限制
WITHDRAW_COOLDOWN_SECONDS = 60.0
DAILY_WITHDRAW_LIMIT = 20

# bug6 修复: 分类
CATEGORIES = ("material", "equipment", "consumable")


@dataclass
class WarehouseItem:
    iid: str
    name: str
    quantity: int = 1
    category: str = "material"


class WarehouseSystem:
    def __init__(self, guild_level: int = 1):
        self.items: list[WarehouseItem] = []
        self.logs: list[dict] = []
        self.access_log: list[dict] = []
        self.guild_level = guild_level
        self.capacity: int = self.get_capacity(guild_level)
        self._last_action_time: dict[str, float] = {}
        self._daily_counts: dict[str, tuple[str, int]] = {}  # member -> (date, count)

    # ---- bug1: 权限控制 ----
    def can_withdraw(self, member_rank: str, item: str) -> bool:
        if member_rank not in RANK_LEVEL:
            return False
        if any(k in item for k in RARE_KEYWORDS):
            return RANK_LEVEL[member_rank] >= RANK_LEVEL[ACTION_MIN_RANK["withdraw_rare"]]
        return RANK_LEVEL[member_rank] >= RANK_LEVEL[ACTION_MIN_RANK["withdraw"]]

    def can_deposit(self, member_rank: str) -> bool:
        return member_rank in RANK_LEVEL

    # ---- bug2: 操作日志 ----
    def record_action(self, member: str, action: str, item: str, qty: int):
        entry = {
            "member": member,
            "action": action,
            "item": item,
            "quantity": qty,
            "timestamp": time.time(),
        }
        self.logs.append(entry)
        self.access_log.append(entry)

    # ---- bug3: 容量随等级升级 ----
    def get_capacity(self, guild_level: int) -> int:
        return BASE_CAPACITY + max(0, guild_level - 1) * CAPACITY_PER_LEVEL

    # ---- bug4: 堆叠上限 ----
    def get_stack_limit(self, item: str) -> int:
        return DEFAULT_STACK_LIMIT

    def _used_slots(self) -> int:
        return len(self.items)

    def deposit(self, member: str, member_rank: str, item: WarehouseItem) -> bool:
        """存入: 检查权限/冷却/每日次数/容量, 超过堆叠上限自动分格。"""
        if not self.can_deposit(member_rank):
            return False
        if not self._check_rate_limit(member):
            return False
        limit = self.get_stack_limit(item.name)
        remaining = item.quantity
        slots_needed = 0
        for existing in self.items:
            if existing.iid == item.iid and existing.name == item.name and existing.quantity < limit:
                take = min(remaining, limit - existing.quantity)
                remaining -= take
        slots_needed = -(-remaining // limit) if remaining > 0 else 0
        if self._used_slots() + slots_needed > self.capacity:
            return False
        remaining = item.quantity
        for existing in self.items:
            if remaining <= 0:
                break
            if existing.iid == item.iid and existing.name == item.name and existing.quantity < limit:
                take = min(remaining, limit - existing.quantity)
                existing.quantity += take
                remaining -= take
        while remaining > 0:
            take = min(remaining, limit)
            self.items.append(WarehouseItem(item.iid, item.name, take, item.category))
            remaining -= take
        self._commit_rate_limit(member)
        self.record_action(member, "deposit", item.name, item.quantity)
        return True

    def withdraw(self, member: str, member_rank: str, item_name: str, qty: int) -> int:
        """取出: 检查权限/冷却/每日次数, 返回实际取出数量。"""
        if not self.can_withdraw(member_rank, item_name):
            return 0
        if not self._check_rate_limit(member):
            return 0
        taken = 0
        for existing in list(self.items):
            if taken >= qty:
                break
            if existing.name != item_name:
                continue
            take = min(existing.quantity, qty - taken)
            existing.quantity -= take
            taken += take
            if existing.quantity <= 0:
                self.items.remove(existing)
        if taken > 0:
            self._commit_rate_limit(member)
            self.record_action(member, "withdraw", item_name, taken)
        return taken

    # ---- bug5: 冷却与每日次数 ----
    def get_withdraw_cooldown(self, member: str) -> float:
        return WITHDRAW_COOLDOWN_SECONDS

    def get_daily_limit(self, member_rank: str = "member") -> int:
        return DAILY_WITHDRAW_LIMIT

    def _check_rate_limit(self, member: str) -> bool:
        now = time.time()
        last = self._last_action_time.get(member)
        if last is not None and now - last < WITHDRAW_COOLDOWN_SECONDS:
            return False
        today = time.strftime("%Y-%m-%d")
        date, count = self._daily_counts.get(member, (today, 0))
        if date == today and count >= DAILY_WITHDRAW_LIMIT:
            return False
        return True

    def _commit_rate_limit(self, member: str):
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        self._last_action_time[member] = now
        date, count = self._daily_counts.get(member, (today, 0))
        self._daily_counts[member] = (today, count + 1 if date == today else 1)

    # ---- bug6: 分类 ----
    def get_categories(self) -> list:
        return list(CATEGORIES)

    def get_items_by_category(self, category: str) -> list[WarehouseItem]:
        return [item for item in self.items if item.category == category]

    # ---- bug7: 解散按贡献返还 ----
    def dissolve_guild(self, guild_id: str, members: list) -> dict:
        total_contribution = sum(max(0, m.get("contribution", 0)) for m in members)
        returned: dict[str, list[dict]] = {m["id"]: [] for m in members}
        for item in self.items:
            remaining = item.quantity
            for idx, member in enumerate(members):
                if idx == len(members) - 1:
                    share = remaining  # 最后一人拿走余数, 保证物资不丢失
                elif total_contribution > 0:
                    share = int(item.quantity * max(0, member.get("contribution", 0)) / total_contribution)
                else:
                    share = item.quantity // len(members)
                share = min(share, remaining)
                if share > 0:
                    returned[member["id"]].append(
                        {"iid": item.iid, "name": item.name, "quantity": share}
                    )
                    remaining -= share
        self.record_action("system", "dissolve", guild_id, len(self.items))
        self.items = []
        return {"returned": returned}
