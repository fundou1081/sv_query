# test_uvm_testbench.py - UVM Testbench 静态骨架提取金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.uvm_testbench_extractor import UVMTestbenchExtractor
from trace.core.graph.uvm_models import (
    UVMComponent, TLMConnection, SequenceBinding, UVMTestbench
)


def _extract(source):
    extractor = UVMTestbenchExtractor({'test.sv': source})
    return extractor.extract()


class TestComponentHierarchy(unittest.TestCase):
    """组件层次提取"""

    def test_type_id_create(self):
        """[金标准] type_id::create 建立父子关系

        class my_env extends uvm_env;
            my_agent agent;
            function void build_phase(uvm_phase phase);
                agent = my_agent::type_id::create("agent", this);
            endfunction
        endclass

        期望: my_env 包含 my_agent (实例名 agent)
        """
        source = '''class my_agent extends uvm_agent; endclass
class my_env extends uvm_env;
    my_agent agent;
    function void build_phase();
        agent = my_agent::type_id::create("agent", this);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        env = tb.get_component('my_env')
        self.assertIsNotNone(env, "my_env 应存在")
        self.assertEqual(env.component_type, 'env')

        agent = tb.get_component('agent')
        self.assertIsNotNone(agent, "agent 应存在")
        self.assertEqual(agent.class_name, 'my_agent')
        self.assertEqual(agent.parent, 'my_env')

    def test_new_creation(self):
        """[金标准] new() 创建组件

        class my_env extends uvm_env;
            my_agent agent;
            function void build_phase();
                agent = new("agent", this);
            endfunction
        endclass
        """
        source = '''class my_agent extends uvm_agent; endclass
class my_env extends uvm_env;
    my_agent agent;
    function void build_phase();
        agent = new("agent", this);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        agent = tb.get_component('agent')
        self.assertIsNotNone(agent, "new() 创建的组件应被识别")
        self.assertEqual(agent.parent, 'my_env')

    def test_nested_hierarchy(self):
        """[金标准] 多层嵌套

        my_test
        └── my_env
            ├── my_agent
            │   ├── my_driver
            │   ├── my_monitor
            │   └── my_sequencer
            └── my_scoreboard
        """
        source = '''class my_driver extends uvm_driver; endclass
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
endclass
class my_test extends uvm_test;
    my_env env;
    function void build_phase();
        env = my_env::type_id::create("env", this);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        # 检查层次
        self.assertEqual(tb.get_component('my_test').component_type, 'test')
        self.assertEqual(tb.get_component('env').parent, 'my_test')
        self.assertEqual(tb.get_component('agent').parent, 'my_env')
        self.assertEqual(tb.get_component('driver').parent, 'my_agent')
        self.assertEqual(tb.get_component('monitor').parent, 'my_agent')
        self.assertEqual(tb.get_component('sequencer').parent, 'my_agent')
        self.assertEqual(tb.get_component('sb').parent, 'my_env')


class TestTLMConnection(unittest.TestCase):
    """TLM 连接提取"""

    def test_analysis_port_connect(self):
        """[金标准] analysis_port.connect

        class my_env extends uvm_env;
            function void connect_phase();
                agent.monitor.ap.connect(sb.analysis_imp);
            endfunction
        endclass

        期望: agent.monitor.ap → sb.analysis_imp (analysis 类型)
        """
        source = '''class my_monitor extends uvm_monitor; endclass
class my_agent extends uvm_agent;
    my_monitor monitor;
    function void build_phase();
        monitor = my_monitor::type_id::create("monitor", this);
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
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.connections), 1, "应有 TLM 连接")
        conn = tb.connections[0]
        self.assertEqual(conn.source_port, 'agent.monitor.ap')
        self.assertEqual(conn.target_port, 'sb.analysis_imp')
        self.assertEqual(conn.port_type, 'analysis')

    def test_put_port_connect(self):
        """[金标准] put_port.connect (单向)

        put_port.connect(target_put_export) → 单向 push
        """
        source = '''class my_agent extends uvm_agent; endclass
class my_env extends uvm_env;
    my_agent agent;
    function void build_phase();
        agent = my_agent::type_id::create("agent", this);
    endfunction
    function void connect_phase();
        agent.put_port.connect(agent.target_export);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.connections), 1)
        conn = tb.connections[0]
        self.assertEqual(conn.port_type, 'put')


class TestSequenceBinding(unittest.TestCase):
    """Sequence → Sequencer 绑定"""

    def test_default_sequence_config(self):
        """[金标准] uvm_config_db 设置 default_sequence

        uvm_config_db#(uvm_object_wrapper)::set(
            this, "env.agent.sequencer.run_phase",
            "default_sequence",
            my_sequence::get_type()
        );

        期望: my_sequence → env.agent.sequencer
        """
        source = '''class my_sequence extends uvm_sequence; endclass
class my_test extends uvm_test;
    function void build_phase();
        uvm_config_db#(uvm_object_wrapper)::set(
            this,
            "env.agent.sequencer.run_phase",
            "default_sequence",
            my_sequence::get_type()
        );
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)

        self.assertGreaterEqual(len(tb.sequence_bindings), 1)
        binding = tb.sequence_bindings[0]
        self.assertEqual(binding.sequence_class, 'my_sequence')
        self.assertIn('sequencer', binding.sequencer_path)


class TestComponentTypeInference(unittest.TestCase):
    """组件类型推断"""

    def test_uvm_driver_type(self):
        """[金标准] uvm_driver → driver"""
        source = '''class my_driver extends uvm_driver#(my_transaction); endclass
module top; endmodule'''
        tb = _extract(source)
        comp = tb.get_component_by_class('my_driver')
        self.assertIsNotNone(comp)
        self.assertEqual(comp.component_type, 'driver')

    def test_uvm_monitor_type(self):
        """[金标准] uvm_monitor → monitor"""
        source = '''class my_monitor extends uvm_monitor; endclass
module top; endmodule'''
        tb = _extract(source)
        comp = tb.get_component_by_class('my_monitor')
        self.assertEqual(comp.component_type, 'monitor')

    def test_uvm_sequencer_type(self):
        """[金标准] uvm_sequencer → sequencer"""
        source = '''class my_sequencer extends uvm_sequencer; endclass
module top; endmodule'''
        tb = _extract(source)
        comp = tb.get_component_by_class('my_sequencer')
        self.assertEqual(comp.component_type, 'sequencer')

    def test_uvm_scoreboard_type(self):
        """[金标准] uvm_scoreboard → scoreboard"""
        source = '''class my_scoreboard extends uvm_scoreboard; endclass
module top; endmodule'''
        tb = _extract(source)
        comp = tb.get_component_by_class('my_scoreboard')
        self.assertEqual(comp.component_type, 'scoreboard')


class TestOutputFormat(unittest.TestCase):
    """输出格式"""

    def test_dot_output(self):
        """[金标准] DOT 格式输出"""
        source = '''class my_agent extends uvm_agent; endclass
class my_env extends uvm_env;
    my_agent agent;
    function void build_phase();
        agent = my_agent::type_id::create("agent", this);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)
        dot = tb.to_dot()

        self.assertIn('digraph', dot)
        self.assertIn('my_env', dot)
        self.assertIn('agent', dot)
        self.assertIn('->', dot)

    def test_mermaid_output(self):
        """[金标准] Mermaid 格式输出"""
        source = '''class my_agent extends uvm_agent; endclass
class my_env extends uvm_env;
    my_agent agent;
    function void build_phase();
        agent = my_agent::type_id::create("agent", this);
    endfunction
endclass
module top; endmodule'''
        tb = _extract(source)
        mermaid = tb.to_mermaid()

        self.assertIn('graph TD', mermaid)
        self.assertIn('my_env', mermaid)
        self.assertIn('agent', mermaid)

    def test_dot_with_tlm_connection(self):
        """[金标准] DOT 输出包含 TLM 连接"""
        source = '''class my_monitor extends uvm_monitor; endclass
class my_agent extends uvm_agent;
    my_monitor monitor;
    function void build_phase();
        monitor = my_monitor::type_id::create("monitor", this);
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
module top; endmodule'''
        tb = _extract(source)
        dot = tb.to_dot()

        # TLM 连接应显示为虚线
        self.assertIn('dashed', dot, "TLM 连接应为虚线")
        self.assertIn('ap', dot)
        self.assertIn('analysis_imp', dot)


if __name__ == '__main__':
    unittest.main()
