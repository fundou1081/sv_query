#!/usr/bin/env python3
"""Add missing handlers in batches."""

import re
import sys

sys.path.insert(0, '/Users/fundou/miniconda3/lib/python3.11/site-packages')
from pyslang import SyntaxKind

# Missing handlers from validation script
missing_handlers = [
    'AnsiPortList', 'AnsiUdpPortList', 'ArgumentList', 'AttributeInstance',
    'AttributeSpec', 'BeginKeywordsDirective', 'CellConfigRule', 'CellDefineDirective',
    'ChargeStrength', 'CompilationUnit', 'ConditionalPredicate', 'ConfigCellIdentifier',
    'ConfigInstanceIdentifier', 'ConfigLiblist', 'ConstructorName', 'CycleDelay',
    'DPIExport', 'DPIImport', 'DefParam', 'DefParamAssignment', 'DefaultConfigRule',
    'DefaultDecayTimeDirective', 'DefaultDistItem', 'DefaultNetTypeDirective',
    'DefaultSkewItem', 'DefaultTriregStrengthDirective', 'DeferredAssertion',
    'DefineDirective', 'Delay3', 'DelayModeDistributedDirective', 'DelayModePathDirective',
    'DelayModeUnitDirective', 'DelayModeZeroDirective', 'DisableIff', 'DistItem',
    'DriveStrength', 'EdgeControlSpecifier', 'EdgeDescriptor', 'EdgeSensitivePathSuffix',
    'ElementSelect', 'ElsIfDirective', 'ElseDirective', 'EmptyIdentifierName',
    'EmptyMember', 'EmptyNonAnsiPort', 'EmptyPortConnection', 'EmptyTimingCheckArg',
    'EndCellDefineDirective', 'EndIfDirective', 'EndKeywordsDirective', 'EndProtectDirective',
    'EndProtectedDirective', 'EnumType', 'ExplicitAnsiPort', 'ExplicitNonAnsiPort',
    'ExternUdpDecl', 'FilePathSpec', 'ForeachLoopList', 'ForwardTypeRestriction',
    'HierarchyInstantiation', 'IdentifierSelectName', 'IfDefDirective', 'IfNDefDirective',
    'ImmediateAssertionMember', 'ImplicitType', 'IncludeDirective', 'InstanceConfigRule',
    'InstanceName', 'LibraryIncludeStatement', 'LibraryMap', 'LineDirective',
    'LocalScope', 'MacroActualArgument', 'MacroActualArgumentList', 'MacroArgumentDefault',
    'MacroFormalArgument', 'MacroFormalArgumentList', 'MacroUsage', 'NamedArgument',
    'NamedConditionalDirectiveExpression', 'NamedLabel', 'NamedParamAssignment',
    'NamedPortConnection', 'NamedStructurePatternMember', 'NetAlias', 'NetPortHeader',
    'NoUnconnectedDriveDirective', 'NonAnsiPortList', 'NonAnsiUdpPortList', 'OneStepDelay',
    'OrderedArgument', 'OrderedParamAssignment', 'OrderedPortConnection',
    'OrderedStructurePatternMember', 'ParameterPortList', 'ParameterValueAssignment',
    'ParenthesizedPattern', 'PathDescription', 'PortConcatenation', 'PortReference',
    'PragmaDirective', 'PrimitiveInstantiation', 'Production', 'ProtectDirective',
    'ProtectedDirective', 'PullStrength', 'QueueDimensionSpecifier',
    'RangeCoverageBinInitializer', 'RangeDimensionSpecifier', 'RangeList', 'RealTimeType',
    'ResetAllDirective', 'RootScope', 'RsIfElse', 'RsProdItem', 'RsRepeat', 'RsRule',
    'SimplePathSuffix', 'SimpleRangeSelect', 'SpecparamDeclarator', 'StructType',
    'StructUnionMember', 'SuperHandle', 'SystemName', 'SystemTimingCheck',
    'ThisHandle', 'TimeScaleDirective', 'TimeType', 'TokenList',
    'TransListCoverageBinInitializer', 'TransRange', 'TransRepeatRange', 'TransSet',
    'TypeAssignment', 'UdpBody', 'UdpEdgeField', 'UdpEntry', 'UdpInitialStmt',
    'UdpInputPortDecl', 'UdpOutputPortDecl', 'UdpSimpleField', 'UnconnectedDriveDirective',
    'UndefDirective', 'UndefineAllDirective', 'UnionType', 'UnitScope', 'Unknown',
    'Untyped', 'VariablePortHeader', 'WildcardDimensionSpecifier', 'WildcardPortConnection',
    'WildcardPortList', 'WildcardUdpPortList'
]

def make_handler(name):
    """Generate a handler stub for the given name."""
    return f'''
    @on('{name}')
    def extract_{name.lower().replace(' ', '_').replace('_', '')}(self, node) -> SignalResult:
        """{name}: {name.replace(' ', ' ').title()}"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result
'''

def main():
    handler_file = 'src/trace/core/visitors/signal_expression_visitor.py'
    
    with open(handler_file, 'r') as f:
        content = f.read()
    
    # Verify all names exist in pyslang
    for name in missing_handlers:
        if not hasattr(SyntaxKind, name):
            print(f"WARNING: {name} not in pyslang SyntaxKind")
    
    # Find insertion point (after VirtualInterfaceType handler)
    pattern = r"(@on\('VirtualInterfaceType'\).*?return SignalResult\(\)\n)"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("ERROR: Could not find insertion point")
        sys.exit(1)
    
    insert_pos = match.end()
    
    # Generate handlers in batches
    batch_size = 20
    total = len(missing_handlers)
    
    print(f"Adding {total} missing handlers in batches of {batch_size}")
    
    new_handlers = ''
    for i, name in enumerate(missing_handlers):
        new_handlers += make_handler(name)
        if (i + 1) % batch_size == 0 or i == total - 1:
            # Insert this batch
            new_content = content[:insert_pos] + new_handlers + content[insert_pos:]
            
            with open(handler_file, 'w') as f:
                f.write(new_content)
            
            print(f"Batch {i // batch_size + 1}: Added {i + 1}/{total} handlers")
            
            # Reset for next batch (but keep appending)
            new_handlers = ''
            content = new_content  # Continue from new position
    
    # Verify
    import py_compile
    try:
        py_compile.compile(handler_file, doraise=True)
        print(f"\n✓ File compiles successfully")
    except py_compile.PyCompileError as e:
        print(f"\n✗ Compile error: {e}")

if __name__ == '__main__':
    main()