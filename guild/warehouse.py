"""帮派仓库与物资管理系统 - 含7个bug"""
from dataclasses import dataclass, field

@dataclass
class WarehouseItem:
    iid: str
    name: str
    quantity: int = 1
    category: str = "material"  # bug6: 无分类

class WarehouseSystem:
    def __init__(self):
        self.items: list[WarehouseItem] = []
        self.logs: list = []  # bug2: 无记录
        self.capacity: int = 100  # bug3: 固定
        self.access_log: list = []  # bug2

    def can_withdraw(self, member_rank: str, item: str) -> bool:
        # bug1: 无权限控制
        return True

    def record_action(self, member: str, action: str, item: str, qty: int):
        # bug2: 不记录
        pass

    def get_capacity(self, guild_level: int) -> int:
        # bug3: 固定容量
        return 100

    def get_stack_limit(self, item: str) -> int:
        # bug4: 无堆叠上限
        return 99999

    def get_withdraw_cooldown(self, member: str) -> float:
        # bug5: 无冷却
        return 0.0

    def get_categories(self) -> list:
        # bug6: 无分类
        return ["all"]

    def dissolve_guild(self, guild_id: str, members: list) -> dict:
        # bug7: 物资消失
        return {"returned": {}}
