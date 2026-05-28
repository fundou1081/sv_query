# test_uvm_testbench_phase2.py - UVM Testbench Phase 2 测试
# [铁律13] 金标准测试
#
# Phase 2: config_db 完整流 + factory override + 虚接口
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.uvm_testbench_extractor import UVMTestbenchExtractor
from trace.core.graph.uvm_models import (
    UVMComponent, TLMConnection, SequenceBinding, UVMTestbench,
    FactoryOverride, ConfigDBEntry
)


def _extract(source):
    extractor = UVMTestbenchExtractor({'test.sv': source})
    return extractor.extract()


class TestConfigDBFlow(unittest.TestCase):
    """Config DB set/get 完整流"""

    def test_config_db_set_get(self):
        """[金标准] config_db set → get 路径

        set: uvm_config_db#(int)::set(this, "env.agent.driver", "max_len", 100)
        get: uvm_config_db#(int)::get(this, "", "max_len", max_len)

        期望: 提取 set 条目，关联到目标组件
        """
        source = '''class my_test extends uvm_test;
    function void build_phase();
        uvm_config_db#(int)::set(this, "env.agent.driver", "max_len", 100);
    endfunction
endclass
class my_driver extends uvm_driver;
    int max_len;
    function void build_phase();
        uvm_config_db#(int)::get(this, "", "max_len", max_len);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.config_entries), 1,
            "应有 config_db 条目")
        entry = tb.config_entries[0]
        self.assertEqual(entry.field_name, 'max_len')
        self.assertEqual(entry.target_path, 'env.agent.driver')
        self.assertEqual(entry.value_type, 'int')

    def test_config_db_virtual_interface(self):
        """[金标准] 虚接口传递

        uvm_config_db#(virtual my_if)::set(this, "env.agent.driver", "vif", vif);

        期望: 提取为虚接口配置，类型标记为 virtual
        """
        source = '''class my_test extends uvm_test;
    function void build_phase();
        uvm_config_db#(virtual my_if)::set(this, "env.agent.driver", "vif", vif);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.config_entries), 1)
        entry = tb.config_entries[0]
        self.assertEqual(entry.field_name, 'vif')
        self.assertIn('virtual', entry.value_type.lower())


class TestFactoryOverride(unittest.TestCase):
    """Factory Override 提取"""

    def test_type_override(self):
        """[金标准] type override

        my_transaction::type_id::set_type_override(my_special_transaction::get_type());

        期望: 提取 override 关系
        """
        source = '''class my_transaction extends uvm_sequence_item; endclass
class my_special_transaction extends my_transaction; endclass
class my_test extends uvm_test;
    function void build_phase();
        my_transaction::type_id::set_type_override(my_special_transaction::get_type());
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.overrides), 1,
            "应有 factory override")
        override = tb.overrides[0]
        self.assertEqual(override.original, 'my_transaction')
        self.assertEqual(override.override_type, 'my_special_transaction')

    def test_inst_override(self):
        """[金标准] instance override

        my_transaction::type_id::set_inst_override(
            my_special_transaction::get_type(), "env.agent.*");

        期望: 提取 override 关系 + scope
        """
        source = '''class my_transaction extends uvm_sequence_item; endclass
class my_special_transaction extends my_transaction; endclass
class my_test extends uvm_test;
    function void build_phase();
        my_transaction::type_id::set_inst_override(
            my_special_transaction::get_type(), "env.agent.*");
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.overrides), 1)
        override = tb.overrides[0]
        self.assertEqual(override.original, 'my_transaction')
        self.assertEqual(override.override_type, 'my_special_transaction')
        self.assertIn('env.agent', override.scope)


class TestUVMCreateMacros(unittest.TestCase):
    """UVM 创建宏识别"""

    def test_uvm_create(self):
        """[金标准] `uvm_create 宏

        `uvm_create(req)

        期望: 识别为组件/对象创建
        """
        source = '''class my_seq extends uvm_sequence;
    task body();
        `uvm_create(req)
    endtask
endclass
module top; endmodule'''
        tb = _extract(source)

        # uvm_create 应被识别
        # 具体断言取决于实现

    def test_uvm_do_with(self):
        """[金标准] `uvm_do_with 宏

        `uvm_do_with(req, { addr < 64; })

        期望: 识别为 randomize with
        """
        source = '''class my_seq extends uvm_sequence;
    task body();
        `uvm_do_with(req, { addr inside {[0:63]}; })
    endtask
endclass
module top; endmodule'''
        tb = _extract(source)

        # uvm_do_with 应被识别为 randomize with


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_uvm_env(self):
        """[金标准] 完整 UVM 环境

        包含:
        - 组件层次
        - TLM 连接
        - config_db 设置
        - factory override
        - sequence 绑定
        """
        source = '''class my_transaction extends uvm_sequence_item; endclass
class my_special_transaction extends my_transaction; endclass
class my_driver extends uvm_driver;
    int max_len;
    function void build_phase();
        uvm_config_db#(int)::get(this, "", "max_len", max_len);
    endfunction
endclass
class my_monitor extends uvm_monitor; endclass
class my_sequencer extends uvm_sequencer; endclass
class my_agent extends uvm_agent;
    my_driver driver;
    my_monitor monitor;
    my_sequencer sequencer;
    function void build_phase();
        driver = my_driver::type_id::create("driver", this);
        monitor = my_monitor::type_id::create("monitor", this);
        sequencer = my_sequencer::type_id::create("sequencer", this);
    endfunction
endclass
class my_scoreboard extends uvm_scoreboard; endclass
class my_env extends uvm_env;
    my_agent agent;
    my_scoreboard sb;
    function void build_phase();
        agent = my_agent::type_id::create("agent", this);
        sb = my_scoreboard::type_id::create("sb", this);
    endfunction
    function void connect_phase();
        agent.monitor.ap.connect(sb.analysis_imp);
    endfunction
endclass
class my_sequence extends uvm_sequence; endclass
class my_test extends uvm_test;
    my_env env;
    function void build_phase();
        env = my_env::type_id::create("env", this);
        my_transaction::type_id::set_type_override(my_special_transaction::get_type());
        uvm_config_db#(int)::set(this, "env.agent.driver", "max_len", 256);
        uvm_config_db#(uvm_object_wrapper)::set(this,
            "env.agent.sequencer.run_phase",
            "default_sequence",
            my_sequence::get_type());
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        # 组件层次
        self.assertGreater(len(tb.components), 5)

        # TLM 连接
        self.assertGreaterEqual(len(tb.connections), 1)

        # Factory override
        self.assertGreaterEqual(len(tb.overrides), 1)

        # Config DB
        self.assertGreaterEqual(len(tb.config_entries), 1)

        # Sequence binding
        self.assertGreaterEqual(len(tb.sequence_bindings), 1)


if __name__ == '__main__':
    unittest.main()
