"""帮派仓库与物资管理系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guild.warehouse import WarehouseSystem, WarehouseItem

class TestPermission:
    def test_normal_member_cannot_withdraw_rare_item(self):
        ws = WarehouseSystem()
        assert ws.can_withdraw("member", "legendary_item") == False
        assert ws.can_withdraw("leader", "legendary_item") == True

class TestActionLog:
    def test_withdraw_is_recorded(self):
        ws = WarehouseSystem()
        ws.record_action("p1", "withdraw", "sword", 1)
        assert len(ws.logs) > 0 or len(ws.access_log) > 0

class TestCapacityByLevel:
    def test_higher_guild_level_more_capacity(self):
        ws = WarehouseSystem()
        c1 = ws.get_capacity(1)
        c10 = ws.get_capacity(10)
        assert c10 > c1

class TestStackLimit:
    def test_items_have_stack_limit(self):
        ws = WarehouseSystem()
        limit = ws.get_stack_limit("potion")
        assert limit < 10000

class TestWithdrawCooldown:
    def test_withdraw_has_cooldown(self):
        ws = WarehouseSystem()
        cd = ws.get_withdraw_cooldown("p1")
        assert cd > 0

class TestCategories:
    def test_warehouse_has_multiple_categories(self):
        ws = WarehouseSystem()
        cats = ws.get_categories()
        assert len(cats) > 1

class TestGuildDissolveReturn:
    def test_members_get_items_on_dissolve(self):
        ws = WarehouseSystem()
        ws.items = [WarehouseItem("i1", "sword", 10)]
        members = [{"id": "p1", "contribution": 100}, {"id": "p2", "contribution": 50}]
        result = ws.dissolve_guild("g1", members)
        assert result["returned"] != {}
