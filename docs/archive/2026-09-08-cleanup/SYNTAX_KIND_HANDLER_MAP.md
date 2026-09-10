# Pyslang SyntaxKind to Handler Mapping

Total handlers: 976

| SyntaxKind | Handler Method | Description |
|------------|----------------|-------------|
| AbbreviatedRangeDimension | extract_abbreviated_range_dimension | AbbreviatedRangeDimension: abbreviated range dimension |
| AbortAssertExpression | extract_abort_assert_expr | AbortAssertExpression: abort assertion expression |
| AbsoluteToleranceValueRange | extract_absolute_tolerance_value_range | AbsoluteToleranceValueRange: absolute tolerance value range |
| AcceptConditionExpression | extract_accept_condition_expression | AcceptConditionExpression: accept condition expression |
| AcceptOnPropertyExpr | extract_accept_on_property_expr | AcceptOnPropertyExpr: accept_on property expression |
| AcceptStatement | extract_accept_statement | AcceptStatement: accept statement |
| ActionBlock | extract_action_block | ActionBlock: action block |
| AddAssignmentExpression | extract_add_assignment_expression | AddAssignmentExpression: add assignment += |
| AddExpr | extract_add_expr_stmt | AddExpr: add expression + |
| AddExpression | extract_add_expression | AddExpression: addition expression |
| AliasStatement | extract_alias_statement | AliasStatement: alias statement |
| AlwaysBlock | extract_always_block | AlwaysBlock: always block |
| AlwaysCombBlock | extract_always_comb_block | AlwaysCombBlock: always_comb block |
| AlwaysCombProceduralBlock | extract_always_comb_procedural_block | AlwaysCombProceduralBlock: always_comb block |
| AlwaysFFBlock | extract_always_ff_block | AlwaysFFBlock: always_ff block |
| AlwaysFFProceduralBlock | extract_always_ff_procedural_block | AlwaysFFProceduralBlock: always_ff block |
| AlwaysLatchBlock | extract_always_latch_block | AlwaysLatchBlock: always_latch block |
| AlwaysLatchProceduralBlock | extract_always_latch_procedural_block | AlwaysLatchProceduralBlock: always_latch block |
| AlwaysProceduralBlock | extract_always_procedural_block | AlwaysProceduralBlock: always block |
| AndAssignmentExpression | extract_and_assignment_expression | AndAssignmentExpression: and assignment &= |
| AndPropertyExpr | extract_and_property_expr | AndPropertyExpr: and property expression |
| AndSequenceExpr | extract_and_sequence_expr | AndSequenceExpr: and sequence expression |
| AndSequenceExpr | extract_and_sequence_expr_stmt | AndSequenceExpr: and sequence expression |
| AnonymousProgram | extract_anonymous_program | AnonymousProgram: anonymous program |
| ArbitrarySymbol | extract_arbitrary_symbol | ArbitrarySymbol: 未解析的符号 |
| ArithmeticLeftShiftAssignmentExpression | extract_arithmetic_left_shift_assignment | ArithmeticLeftShiftAssignmentExpression: <<<= |
| ArithmeticLeftShiftExpr | extract_arithmetic_left_shift_expr | ArithmeticLeftShiftExpr: arithmetic left shift <<< |
| ArithmeticRightShiftAssignmentExpression | extract_arithmetic_right_shift_assignment | ArithmeticRightShiftAssignmentExpression: >>>= |
| ArithmeticRightShiftExpr | extract_arithmetic_right_shift_expr | ArithmeticRightShiftExpr: arithmetic right shift >>> |
| ArithmeticShiftLeftExpression | extract_arithmetic_shift_left_expression | ArithmeticShiftLeftExpression: arithmetic shift left <<< |
| ArithmeticShiftRightExpression | extract_arithmetic_shift_right_expression | ArithmeticShiftRightExpression: arithmetic shift right >>> |
| ArrayAndMethod | extract_array_and_method | ArrayAndMethod: array.and() method |
| ArrayAndMethodExpr | extract_array_and_method_expr | ArrayAndMethodExpr: array.and() method expression |
| ArrayAndMethodExpr | extract_array_and_method_expr_stmt | ArrayAndMethodExpr: array.and() method expression |
| ArrayMethodExpr | extract_array_method_expr | ArrayMethodExpr: array method expression |
| ArrayOrMethod | extract_array_or_method | ArrayOrMethod: array.or() method |
| ArrayOrMethodExpr | extract_array_or_method_expr | ArrayOrMethodExpr: array.or() method expression |
| ArrayOrMethodExpr | extract_array_or_method_expr_stmt | ArrayOrMethodExpr: array.or() method expression |
| ArrayOrRandomizeMethodExpr | extract_array_or_randomize_method_expr | ArrayOrRandomizeMethodExpr: array.or_randomize() method e... |
| ArrayOrRandomizeMethodExpression | extract_array_randomize_method_expr | ArrayOrRandomizeMethodExpression: array.randomize() with ... |
| ArrayUniqueMethod | extract_array_unique_method | ArrayUniqueMethod: array.unique() method |
| ArrayUniqueMethodExpr | extract_array_unique_method_expr | ArrayUniqueMethodExpr: array.unique() method expression |
| ArrayUniqueMethodExpr | extract_array_unique_method_expr_stmt | ArrayUniqueMethodExpr: array.unique() method expression |
| ArrayXorMethod | extract_array_xor_method | ArrayXorMethod: array.xor() method |
| ArrayXorMethodExpr | extract_array_xor_method_expr | ArrayXorMethodExpr: array.xor() method expression |
| ArrayXorMethodExpr | extract_array_xor_method_expr_stmt | ArrayXorMethodExpr: array.xor() method expression |
| AscendingRangeSelect | extract_ascending_range_select | AscendingRangeSelect: ascending range select |
| AscendingRangeSelectExpr | extract_ascending_range_select_expr | AscendingRangeSelectExpr: ascending range select [a:b] |
| AssertExpression | extract_assert_expression | AssertExpression: assert expression |
| AssertPropertyExpression | extract_assert_property_expression | AssertPropertyExpression: assert property |
| AssertPropertyStatement | extract_assert_property_statement | AssertPropertyStatement: assert property statement |
| AssertStatement | extract_assert_statement_stmt | AssertStatement: assert statement |
| AssertionInstance | extract_assertion_instance | AssertionInstance: assert property |
| AssertionItemPort | extract_assertion_item_port | AssertionItemPort: assertion item port |
| AssertionItemPortList | extract_assertion_item_port_list | AssertionItemPortList: assertion item port list |
| AssertionStatementExpression | extract_assertion_statement_expression | AssertionStatementExpression: assert statement expression |
| AssignmentExpression | extract_assignment_expression | AssignmentExpression: a = b |
| AssignmentOperatorExpr | extract_assignment_operator_expr | AssignmentOperatorExpr: assignment operator expression |
| AssignmentPatternExpression | extract_assignment_pattern | AssignmentPatternExpression: '{a, b, c} |
| AssignmentPatternExpression | extract_assignment_pattern_expr | AssignmentPatternExpression: pattern expression |
| AssignmentPatternItem | extract_assignment_pattern_item | AssignmentPatternItem: assignment pattern item |
| AssociativeArrayExpression | extract_associative_array_expression | AssociativeArrayExpression: associative array expression |
| AssociativeArrayLiteral | extract_associative_array_literal | AssociativeArrayLiteral: '{key: value, ...} |
| AssociativeDimension | extract_associative_dimension | AssociativeDimension: associative dimension |
| AssumeExpression | extract_assume_expression | AssumeExpression: assume expression |
| AssumePropertyExpression | extract_assume_property | AssumePropertyExpression: assume property |
| AssumePropertyExpression | extract_assume_property_expression | AssumePropertyExpression: assume property |
| AssumePropertyStatement | extract_assume_property_statement | AssumePropertyStatement: assume property statement |
| AssumeStatement | extract_assume_statement_stmt | AssumeStatement: assume statement |
| AsyncAcceptSequenceExpr | extract_async_accept_sequence_expr | AsyncAcceptSequenceExpr: async accept sequence expression |
| AsyncRejectSequenceExpr | extract_async_reject_sequence_expr | AsyncRejectSequenceExpr: async reject sequence expression |
| AsyncRejectWeakSequenceExpr | extract_async_reject_weak_sequence_expr | AsyncRejectWeakSequenceExpr: async reject weak sequence e... |
| BadExpression | extract_bad_expression | BadExpression: bad expression |
| BeginStatementExpression | extract_begin_stmt_expression | BeginStatementExpression: begin end block |
| BinSelectWithFilterExpr | extract_bin_select_with_filter_expr | BinSelectWithFilterExpr: bin select with filter expression |
| BinaryAndExpr | extract_binary_and_expr | BinaryAndExpr: binary and expression & |
| BinaryAndExpression | extract_binary_and_expression | BinaryAndExpression: binary and expression |
| BinaryAssertExpression | extract_binary_assert_expression | BinaryAssertExpression: binary assertion expression |
| BinaryBinsSelectExpr | extract_binary_bins_select_expr | BinaryBinsSelectExpr: binary bins select expression |
| BinaryBinsSelectExpr | extract_binary_bins_select_expr_stmt | BinaryBinsSelectExpr: binary bins select expression |
| BinaryBlockEventExpr | extract_binary_block_event_expr | BinaryBlockEventExpr: binary block event expression |
| BinaryBlockEventExpression | extract_binary_block_event_expression | BinaryBlockEventExpression: binary block event expression |
| BinaryConditionalDirectiveExpression | extract_binary_conditional_directive_expr | BinaryConditionalDirectiveExpression: binary conditional ... |
| BinaryEventExpression | extract_binary_event_expression | BinaryEventExpression: binary event expression |
| BinaryExpression | extract_binary_expression | BinaryExpression: a + b, a & b 等二元表达式                  递归... |
| BinaryNandExpr | extract_binary_nand_expr | BinaryNandExpr: binary nand expression ~& |
| BinaryNorExpr | extract_binary_nor_expr | BinaryNorExpr: binary nor expression ~| |
| BinaryOperator | extract_binary_operator | BinaryOperator: 二元运算符 |
| BinaryOrExpr | extract_binary_or_expr | BinaryOrExpr: binary or expression | |
| BinaryOrExpression | extract_binary_or_expression | BinaryOrExpression: binary or expression |
| BinaryPropertyExpr | extract_binary_property_expr | BinaryPropertyExpr: binary property expression |
| BinaryXnorExpr | extract_binary_xnor_expr_stmt | BinaryXnorExpr: binary xnor expression ^~ |
| BinaryXnorExpression | extract_binary_xnor_expression | BinaryXnorExpression: binary xnor expression |
| BinaryXorExpr | extract_binary_xor_expr | BinaryXorExpr: binary xor expression ^ |
| BinaryXorExpression | extract_binary_xor_expression | BinaryXorExpression: binary xor expression |
| BindDirective | extract_bind_directive | BindDirective: bind directive |
| BindTargetList | extract_bind_target_list | BindTargetList: bind target list |
| BinsSelectConditionExpr | extract_bins_select_condition_expr | BinsSelectConditionExpr: bins select condition expression |
| BinsSelection | extract_bins_selection | BinsSelection: bins selection |
| BitSelect | extract_bit_select | BitSelect: bit select |
| BitSelectExpr | extract_bit_select_expr | BitSelectExpr: bit select expression |
| BitStreamCastExpr | extract_bit_stream_cast_expr | BitStreamCastExpr: bit stream cast expression |
| BitType | extract_bit_type | BitType: bit type |
| BitVectorExpr | extract_bit_vector_expr | BitVectorExpr: bit vector expression |
| BitVectorType | extract_bit_vector_type | BitVectorType: bit vector type |
| BitstreamCastConversion | extract_bitstream_cast_conversion | BitstreamCastConversion: bitstream cast conversion |
| BlockCommentTrivia | extract_block_comment_trivia | BlockCommentTrivia: block comment trivia |
| BlockCoverageEvent | extract_block_coverage_event | BlockCoverageEvent: block coverage event |
| BlockEventListTimingControl | extract_block_event_list_timing_control | BlockEventListTimingControl: block event list timing control |
| BlockStatement | extract_block_statement | BlockStatement: block statement |
| BlockingAssignmentStatement | extract_blocking_assignment_stmt | BlockingAssignmentStatement: blocking assignment |
| BlockingAssignmentStatement | extract_blocking_assignment_stmt_stmt | BlockingAssignmentStatement: blocking assignment statement |
| BlockingEventTriggerStatement | extract_blocking_event_trigger_statement | BlockingEventTriggerStatement: blocking event trigger |
| BothEdges | extract_both_edges | BothEdges: both edges |
| BreakStatement | extract_break_statement | BreakStatement: break statement |
| BreakStatementExpression | extract_break_stmt_expression | BreakStatementExpression: break |
| ByteType | extract_byte_type | ByteType: byte type |
| CHandleType | extract_chandle_type | CHandleType: chandle type |
| CallExpression | extract_call | CallExpression: 函数调用参数 |
| CallableExpression | extract_callable_expression | CallableExpression: callable expression |
| CaseAssertExpression | extract_case_assert_expr | CaseAssertExpression: case assertion expression |
| CaseEqualityExpr | extract_case_equality_expr | CaseEqualityExpr: case equality expression === |
| CaseEqualityExpression | extract_case_equality_expression | CaseEqualityExpression: case equality expression === |
| CaseExpression | extract_case_expression | CaseExpression: case expression |
| CaseGenerate | extract_case_generate | CaseGenerate: case generate construct |
| CaseInequalityExpr | extract_case_inequality_expr | CaseInequalityExpr: case inequality expression !== |
| CaseInequalityExpression | extract_case_inequality_expression | CaseInequalityExpression: case inequality expression !== |
| CaseItemExpression | extract_case_item_expression | CaseItemExpression: case item |
| CaseItemStatementExpression | extract_case_item_stmt_expression | CaseItemStatementExpression: case item statement |
| CasePropertyExpr | extract_case_property_expr | CasePropertyExpr: case property expression |
| CasePropertyExpression | extract_case_property_expression | CasePropertyExpression: case property expression |
| CaseSequenceExpr | extract_case_sequence_expr | CaseSequenceExpr: case sequence expression |
| CaseStatement | extract_case_statement_stmt | CaseStatement: case statement |
| CaseStatementExpression | extract_case_stmt_expression | CaseStatementExpression: case statement expression |
| CastExpr | extract_cast_expr_stmt | CastExpr: cast expression |
| CastExpression | extract_cast_expression | CastExpression: type'(expr) |
| CastToBitBaseExpr | extract_cast_to_bit_base_expr | CastToBitBaseExpr: cast to bit base expression |
| CastToBitExpr | extract_cast_to_bit_expr | CastToBitExpr: cast to bit expression |
| CastToByteExpr | extract_cast_to_byte_expr | CastToByteExpr: cast to byte expression |
| CastToIntExpr | extract_cast_to_int_expr | CastToIntExpr: cast to int expression |
| CastToLongIntExpr | extract_cast_to_long_int_expr | CastToLongIntExpr: cast to long int expression |
| CastToRealExpr | extract_cast_to_real_expr | CastToRealExpr: cast to real expression |
| CastToShortIntExpr | extract_cast_to_short_int_expr | CastToShortIntExpr: cast to short int expression |
| CheckerDataDeclaration | extract_checker_data_declaration | CheckerDataDeclaration: checker data declaration |
| CheckerDeclaration | extract_checker_declaration | CheckerDeclaration: checker declaration |
| CheckerInstanceStatement | extract_checker_instance_statement | CheckerInstanceStatement: checker instance statement |
| CheckerInstantiation | extract_checker_instantiation | CheckerInstantiation: checker instantiation |
| CheckerInstantiationStatement | extract_checker_instantiation_statement | CheckerInstantiationStatement: checker instantiation stat... |
| ClassDeclaration | extract_class_declaration | ClassDeclaration: class declaration |
| ClassMethodDeclaration | extract_class_method_declaration | ClassMethodDeclaration: class method declaration |
| ClassMethodPrototype | extract_class_method_prototype | ClassMethodPrototype: class method prototype |
| ClassName | extract_class_name | ClassName: class name |
| ClassPropertyDeclaration | extract_class_property_declaration | ClassPropertyDeclaration: class property declaration |
| ClassScopeExpr | extract_class_scope_expr | ClassScopeExpr: class scope expression |
| ClassSpecifier | extract_class_specifier | ClassSpecifier: class specifier |
| ClockingAssertExpression | extract_clocking_assert_expr | ClockingAssertExpression: clocking assertion expression |
| ClockingBlock | extract_clocking_block | ClockingBlock: clocking block |
| ClockingBlockEvent | extract_clocking_block_event | ClockingBlockEvent: clocking block event |
| ClockingBlockEventExpr | extract_clocking_block_event_expr | ClockingBlockEventExpr: clocking block event expression |
| ClockingBlockEventExpr | extract_clocking_block_event_expr_stmt | ClockingBlockEventExpr: clocking block event expression |
| ClockingBlockExpr | extract_clocking_block_expr | ClockingBlockExpr: clocking block expression |
| ClockingBlockExpr | extract_clocking_block_expr_stmt | ClockingBlockExpr: clocking block expression |
| ClockingBlockPropertyExpr | extract_clocking_block_property_expr | ClockingBlockPropertyExpr: clocking block property expres... |
| ClockingBlockPropertyExpr | extract_clocking_block_property_expr_stmt | ClockingBlockPropertyExpr: clocking block property expres... |
| ClockingBlockSequenceExpr | extract_clocking_block_sequence_expr | ClockingBlockSequenceExpr: clocking block sequence expres... |
| ClockingBlockSequenceExpr | extract_clocking_block_sequence_expr_stmt | ClockingBlockSequenceExpr: clocking block sequence expres... |
| ClockingDeclaration | extract_clocking_declaration | ClockingDeclaration: clocking block declaration |
| ClockingDirection | extract_clocking_direction | ClockingDirection: clocking direction |
| ClockingDrive | extract_clocking_drive | ClockingDrive: clocking drive |
| ClockingEvent | extract_clock_event | ClockingEvent: @clk, @(posedge clk) |
| ClockingItem | extract_clocking_item | ClockingItem: clocking item |
| ClockingPropertyExpr | extract_clocking_property_expr | ClockingPropertyExpr: property with clock |
| ClockingPropertyExpr | extract_clocking_property_expr_stmt | ClockingPropertyExpr: clocking property expression |
| ClockingSequenceExpr | extract_clocking_sequence_expr | ClockingSequenceExpr: clocking sequence expression |
| ClockingSkew | extract_clocking_skew | ClockingSkew: clocking skew |
| ColonExpressionClause | extract_colon_expression_clause | ColonExpressionClause: colon expression clause |
| CompoundStatementExpression | extract_compound_stmt_expression | CompoundStatementExpression: compound statement |
| ConcatenationExpr | extract_concatenation_expr | ConcatenationExpr: concatenation expression |
| ConcatenationExpression | extract_concatenation | ConcatenationExpression: {a, b, c} |
| ConcurrentAssertStatement | extract_concurrent_assert_statement | ConcurrentAssertStatement: concurrent assert statement |
| ConcurrentAssertionMember | extract_concurrent_assertion_member | ConcurrentAssertionMember: concurrent assertion member |
| ConcurrentAssertionStatement | extract_concurrent_assertion | ConcurrentAssertionStatement: concurrent assertion |
| ConditionBinsSelectExpr | extract_condition_bins_select_expr | ConditionBinsSelectExpr: condition bins select expression |
| ConditionalAssertExpression | extract_conditional_assert_expr | ConditionalAssertExpression: conditional assertion |
| ConditionalConstraint | extract_conditional_constraint | ConditionalConstraint: conditional constraint |
| ConditionalDirectiveExpression | extract_conditional_directive_expression | ConditionalDirectiveExpression: conditional directive exp... |
| ConditionalExpr | extract_conditional_expr | ConditionalExpr: conditional expression cond ? expr1 : expr2 |
| ConditionalExpression | extract_conditional_expression | ConditionalExpression: cond ? expr1 : expr2 |
| ConditionalOp | extract_conditional_op | ConditionalOp: 三元运算符 sel ? a : b |
| ConditionalPathDeclaration | extract_conditional_path_declaration | ConditionalPathDeclaration: conditional path declaration |
| ConditionalPattern | extract_conditional_pattern | ConditionalPattern: pattern if cond |
| ConditionalPattern | extract_conditional_pattern_stmt | ConditionalPattern: conditional pattern |
| ConditionalPropertyExpr | extract_conditional_property_expr | ConditionalPropertyExpr: conditional property expression |
| ConditionalStatement | extract_conditional_statement | ConditionalStatement: conditional statement |
| ConfigDeclaration | extract_config_declaration | ConfigDeclaration: config declaration |
| ConfigUseClause | extract_config_use_clause | ConfigUseClause: config use clause |
| ConstantCastExpr | extract_constant_cast_expr | ConstantCastExpr: constant cast expression |
| ConstantExpression | extract_constant_expression | ConstantExpression: constant expression |
| ConstantPattern | extract_constant_pattern | ConstantPattern: constant pattern |
| ConstantPatternExpr | extract_constant_pattern_expr | ConstantPatternExpr: constant pattern expression |
| ConstraintBlock | extract_constraint_block | ConstraintBlock: constraint block |
| ConstraintConditional | extract_constraint_conditional | ConstraintConditional: conditional constraint |
| ConstraintDeclaration | extract_constraint_declaration | ConstraintDeclaration: constraint declaration |
| ConstraintDisableSoft | extract_constraint_disable_soft | ConstraintDisableSoft: disable soft constraint |
| ConstraintExpression | extract_constraint_expression | ConstraintExpression: expression constraint |
| ConstraintExpression | extract_constraint_expression | ConstraintExpression: expression constraint |
| ConstraintForeach | extract_constraint_foreach | ConstraintForeach: foreach constraint |
| ConstraintImplication | extract_constraint_implication | ConstraintImplication: implication constraint |
| ConstraintList | extract_constraint_list | ConstraintList: constraint list |
| ConstraintListExpr | extract_constraint_list_expr | ConstraintListExpr: constraint list expression |
| ConstraintPrototype | extract_constraint_prototype | ConstraintPrototype: constraint prototype |
| ConstraintSolveBefore | extract_constraint_solve_before | ConstraintSolveBefore: solve before constraint |
| ConstraintUniqueness | extract_constraint_uniqueness | ConstraintUniqueness: uniqueness constraint |
| ContinueStatement | extract_continue_statement | ContinueStatement: continue statement |
| ContinueStatementExpression | extract_continue_stmt_expression | ContinueStatementExpression: continue |
| ContinuousAssign | extract_continuous_assign | ContinuousAssign: continuous assignment |
| CopyClassExpression | extract_copy_class | CopyClassExpression: class.copy() |
| CopyClassExpression | extract_copy_class_expression | CopyClassExpression: copy class expression |
| CoverCross | extract_cover_cross | CoverCross: cover cross |
| CoverCrossExpr | extract_cover_cross_expr | CoverCrossExpr: cover cross expression |
| CoverCrossItemExpr | extract_cover_cross_item_expr | CoverCrossItemExpr: cover cross item expression |
| CoverPropertyExpression | extract_cover_property | CoverPropertyExpression: cover property |
| CoverPropertyExpression | extract_cover_property_expr | CoverPropertyExpression: cover property expression |
| CoverPropertyExpression | extract_cover_property_expression | CoverPropertyExpression: cover property |
| CoverPropertyStatement | extract_cover_property_statement | CoverPropertyStatement: cover property statement |
| CoverSequenceExpression | extract_cover_sequence | CoverSequenceExpression: cover sequence |
| CoverSequenceExpression | extract_cover_sequence_expr | CoverSequenceExpression: cover sequence expression |
| CoverSequenceStatement | extract_cover_sequence_statement | CoverSequenceStatement: cover sequence statement |
| CoverStatement | extract_cover_statement_stmt | CoverStatement: cover statement |
| CoverageBins | extract_coverage_bins | CoverageBins: coverage bins |
| CoverageBinsArraySize | extract_coverage_bins_array_size | CoverageBinsArraySize: coverage bins array size |
| CoverageIffClause | extract_coverage_iff_clause | CoverageIffClause: coverage iff clause |
| CoverageOption | extract_coverage_option | CoverageOption: coverage option |
| CoverageStatementExpression | extract_coverage_stmt_expression | CoverageStatementExpression: coverage statement |
| CovergroupDeclaration | extract_covergroup_declaration | CovergroupDeclaration: covergroup declaration |
| Coverpoint | extract_coverpoint | Coverpoint: coverpoint |
| CoverpointBinExpr | extract_coverpoint_bin_expr | CoverpointBinExpr: coverpoint bin expression |
| CoverpointExpr | extract_coverpoint_expr | CoverpointExpr: coverpoint expression |
| CoverpointValueBinExpr | extract_coverpoint_value_bin_expr | CoverpointValueBinExpr: coverpoint value bin expression |
| CoverpointWildcardBinExpr | extract_coverpoint_wildcard_bin_expr | CoverpointWildcardBinExpr: coverpoint wildcard bin expres... |
| CrossIdBinsSelectExpr | extract_cross_id_bins_select_expr | CrossIdBinsSelectExpr: cross id bins select expression |
| CycleDelayControl | extract_cycle_delay_control | CycleDelayControl: ##1 cycle delay |
| CycleDelayControlStatement | extract_cycle_delay_control_statement | CycleDelayControlStatement: cycle delay control statement |
| CycleDelayExpr | extract_cycle_delay_expr | CycleDelayExpr: cycle delay expression ## |
| CycleDelayExpression | extract_cycle_delay_expression | CycleDelayExpression: cycle delay expression ## |
| CycleDelayTimingControl | extract_cycle_delay_timing_control | CycleDelayTimingControl: cycle delay ##N |
| DPIOpenArrayDimension | extract_dpi_open_array_dimension | DPIOpenArrayDimension: DPI open array dimension |
| DataDeclaration | extract_data_declaration | DataDeclaration: data declaration (variables, nets) |
| DataType | extract_data_type | DataType: 数据类型 |
| DeassignStatement | extract_deassign_stmt | DeassignStatement: deassign |
| DecrementAssignmentExpr | extract_decrement_assignment_expr | DecrementAssignmentExpr: decrement assignment expression |
| DefaultCaseItem | extract_default_case_item | DefaultCaseItem: default case item |
| DefaultClockingReference | extract_default_clocking_reference | DefaultClockingReference: default clocking reference |
| DefaultCoverageBinInitializer | extract_default_coverage_bin_initializer | DefaultCoverageBinInitializer: default coverage bin initi... |
| DefaultDisableDeclaration | extract_default_disable_declaration | DefaultDisableDeclaration: default disable declaration |
| DefaultExtendsClauseArg | extract_default_extends_clause_arg | DefaultExtendsClauseArg: default extends clause arg |
| DefaultFunctionPort | extract_default_function_port | DefaultFunctionPort: default function port |
| DefaultPattern | extract_default_pattern | DefaultPattern: default pattern |
| DefaultPatternExpression | extract_default_pattern_expr | DefaultPatternExpression: default pattern |
| DefaultPatternKeyExpression | extract_default_pattern_key_expression | DefaultPatternKeyExpression: default pattern key expression |
| DefaultPropertyCaseItem | extract_default_property_case_item | DefaultPropertyCaseItem: default property case item |
| DefaultRsCaseItem | extract_default_rs_case_item | DefaultRsCaseItem: default randsequence case item |
| DeferredAssertStatementExpression | extract_deferred_assert_stmt_expr | DeferredAssertStatementExpression: deferred assert |
| DeferredAssumeStatementExpression | extract_deferred_assume_stmt_expr | DeferredAssumeStatementExpression: deferred assume |
| DeferredCoverStatementExpression | extract_deferred_cover_stmt_expr | DeferredCoverStatementExpression: deferred cover |
| DeferredImmediateAssertionStatement | extract_deferred_immediate_assertion | DeferredImmediateAssertionStatement: #0 assert |
| Delay3TimingControl | extract_delay3_timing_control | Delay3TimingControl: delay3 timing control |
| DelayControl | extract_delay_control | DelayControl: #1delay |
| DelayControl | extract_delay_control | DelayControl: #1delay |
| DelayControlExpr | extract_delay_control_expr | DelayControlExpr: delay control expression |
| DelayControlExpression | extract_delay_control_expression | DelayControlExpression: delay control expression |
| DelayControlStatement | extract_delay_control_statement | DelayControlStatement: delay control statement |
| DelayOrEventControl | extract_delay_or_event_control | DelayOrEventControl: #1 or @event |
| DelayTimingControl | extract_delay_timing_control | DelayTimingControl: #delay timing control |
| DelayedSequenceElement | extract_delayed_sequence_element | DelayedSequenceElement: delayed sequence element |
| DelayedSequenceExpr | extract_delayed_sequence_expr | DelayedSequenceExpr: delayed sequence expression |
| DescendingRangeSelect | extract_descending_range_select | DescendingRangeSelect: descending range select |
| DescendingRangeSelectExpr | extract_descending_range_select_expr | DescendingRangeSelectExpr: descending range select [a:b] |
| DirectiveTrivia | extract_directive_trivia | DirectiveTrivia: directive trivia |
| DisableConstraint | extract_disable_constraint | DisableConstraint: disable constraint |
| DisableConstraint | extract_disable_constraint_stmt | DisableConstraint: disable constraint |
| DisableForkStatement | extract_disable_fork_statement | DisableForkStatement: disable fork statement |
| DisableForkStatementExpression | extract_disable_fork_expression | DisableForkStatementExpression: disable fork |
| DisableIffAssertExpression | extract_disable_iff_assert_expr | DisableIffAssertExpression: disable iff assertion |
| DisableStatement | extract_disable_statement | DisableStatement: disable statement |
| DisableStatementExpression | extract_disable_stmt_expression | DisableStatementExpression: disable statement |
| DisabledTextTrivia | extract_disabled_text_trivia | DisabledTextTrivia: disabled text trivia |
| DistConstraintExpr | extract_dist_constraint_expr | DistConstraintExpr: dist constraint expression |
| DistConstraintList | extract_dist_constraint_list | DistConstraintList: dist constraint list |
| DistExpression | extract_dist | DistExpression: a dist {[/=]:1, [:=]:2} |
| DistWeight | extract_dist_weight | DistWeight: dist weight |
| DistributionConstraint | extract_distribution_constraint | DistributionConstraint: dist constraint |
| DivideAssignmentExpression | extract_divide_assignment_expression | DivideAssignmentExpression: /= |
| DivideExpr | extract_divide_expr_stmt | DivideExpr: divide expression / |
| DivideExpression | extract_divide_expression | DivideExpression: division expression |
| DividerClause | extract_divider_clause | DividerClause: divider clause |
| DoWhileLoopStatement | extract_do_while_loop_statement | DoWhileLoopStatement: do while loop statement |
| DoWhileStatement | extract_do_while_statement | DoWhileStatement: do-while statement |
| DoWhileStatementExpression | extract_do_while_expression | DoWhileStatementExpression: do while expression |
| DotMemberClause | extract_dot_member_clause | DotMemberClause: dot member clause |
| DynamicArrayCastExpr | extract_dynamic_array_cast_expr | DynamicArrayCastExpr: dynamic array cast expression |
| DynamicDimension | extract_dynamic_dimension | DynamicDimension: dynamic dimension |
| ElabSystemTask | extract_elab_system_task | ElabSystemTask: elaboration system task |
| ElementSelectExpression | extract_element_select | ElementSelectExpression: data[5] |
| ElseClause | extract_else_clause | ElseClause: else clause |
| ElseConstraint | extract_else_constraint | ElseConstraint: else constraint |
| ElseConstraintClause | extract_else_constraint_clause | ElseConstraintClause: else constraint clause |
| ElsePropertyClause | extract_else_property_clause | ElsePropertyClause: else property clause |
| EmptyArgument | extract_empty_argument | EmptyArgument: 函数参数占位 |
| EmptyExpression | extract_empty_expression | EmptyExpression: empty expression |
| EmptyProperty | extract_empty_property | EmptyProperty: empty property |
| EmptyQueueExpression | extract_empty_queue_expression | EmptyQueueExpression: empty queue expression {} |
| EmptySequence | extract_empty_sequence | EmptySequence: empty sequence |
| EmptyStatement | extract_empty_statement | EmptyStatement: empty statement |
| EmptyStatement | extract_empty_statement_stmt | EmptyStatement: empty statement |
| EmptyStatementExpression | extract_empty_stmt_expression | EmptyStatementExpression: empty statement |
| EndOfLineTrivia | extract_end_of_line_trivia | EndOfLineTrivia: end of line trivia |
| EqualityExpr | extract_equality_expr | EqualityExpr: equality expression == |
| EqualityExpression | extract_equality_expression | EqualityExpression: equality expression == |
| EqualsAssertionArgClause | extract_equals_assertion_arg_clause | EqualsAssertionArgClause: equals assertion arg clause |
| EqualsTypeClause | extract_equals_type_clause | EqualsTypeClause: equals type clause |
| EqualsValueClause | extract_equals_value_clause | EqualsValueClause: equals value clause |
| ErrorElabSystemTask | extract_error_elab_system_task | ErrorElabSystemTask: error elaboration system task |
| EventControl | extract_event_control | EventControl: @event |
| EventControl | extract_event_control_stmt | EventControl: @event |
| EventControlExpr | extract_event_control_expr | EventControlExpr: event control expression |
| EventControlExpression | extract_event_control_expression | EventControlExpression: event control expression |
| EventControlStatement | extract_event_control_statement | EventControlStatement: event control statement |
| EventControlWithExpression | extract_event_control_with_expression | EventControlWithExpression: event control with expression |
| EventExpression | extract_event_expression | EventExpression: event expression |
| EventListTimingControl | extract_event_list_timing_control | EventListTimingControl: event list timing control |
| EventStatementExpression | extract_event_statement_expression | EventStatementExpression: event statement |
| EventTriggerExpression | extract_event_trigger | EventTriggerExpression: ->event |
| EventTriggerStatement | extract_event_trigger_statement | EventTriggerStatement: event trigger |
| EventType | extract_event_type | EventType: event type |
| ExpectExpression | extract_expect_expression | ExpectExpression: expect expression |
| ExpectPropertyExpression | extract_expect_property | ExpectPropertyExpression: expect property |
| ExpectPropertyStatement | extract_expect_property_statement | ExpectPropertyStatement: expect property statement |
| ExpectPropertyStatement | extract_expect_property_statement_stmt | ExpectPropertyStatement: expect property statement |
| ExpectStatementExpression | extract_expect_stmt_expression | ExpectStatementExpression: expect statement |
| ExplicitConversion | extract_explicit_conversion | ExplicitConversion: explicit conversion |
| ExpressionConstraint | extract_expression_constraint | ExpressionConstraint: expression constraint |
| ExpressionConstraint | extract_expression_constraint_stmt | ExpressionConstraint: expression constraint |
| ExpressionCoverageBinInitializer | extract_expression_coverage_bin_initializer | ExpressionCoverageBinInitializer: expression coverage bin... |
| ExpressionOrCondItem | extract_expression_or_cond_item | ExpressionOrCondItem: expression or condition item |
| ExpressionOrDist | extract_expression_or_dist | ExpressionOrDist: expression or dist expression |
| ExpressionOrStatement | extract_expression_or_statement | ExpressionOrStatement: expression or statement |
| ExpressionPattern | extract_expression_pattern | ExpressionPattern: expression pattern |
| ExpressionStatement | extract_expression_statement_stmt | ExpressionStatement: expression statement |
| ExpressionStatement | extract_expression_statement_stmt | ExpressionStatement: expression statement |
| ExpressionStatement | extract_expression_stmt | ExpressionStatement: expression statement |
| ExpressionTimingCheckArg | extract_expression_timing_check_arg | ExpressionTimingCheckArg: expression timing check arg |
| ExtendsClause | extract_extends_clause | ExtendsClause: extends clause |
| ExternFunctionDeclaration | extract_extern_function_declaration | ExternFunctionDeclaration: extern function declaration |
| ExternInterfaceMethod | extract_extern_interface_method | ExternInterfaceMethod: extern interface method |
| ExternModuleDecl | extract_extern_module_decl | ExternModuleDecl: extern module declaration |
| ExternTaskDeclaration | extract_extern_task_declaration | ExternTaskDeclaration: extern task declaration |
| FatalElabSystemTask | extract_fatal_elab_system_task | FatalElabSystemTask: fatal elaboration system task |
| FinalBlock | extract_final_block | FinalBlock: final block |
| FinalDeferredAssertStatement | extract_final_deferred_assert_statement | FinalDeferredAssertStatement: final deferred assert state... |
| FinalDeferredImmediateAssertionStatement | extract_final_deferred_assertion | FinalDeferredImmediateAssertionStatement: final #0 assert |
| FinalProceduralBlock | extract_final_procedural_block | FinalProceduralBlock: final block |
| FinalStatement | extract_final_statement | FinalStatement: final statement |
| FirstMatchAssertExpression | extract_first_match_assert_expr | FirstMatchAssertExpression: first_match assertion |
| FirstMatchSequenceExpr | extract_first_match_sequence_expr | FirstMatchSequenceExpr: first_match sequence expression |
| FollowedByPropertyExpr | extract_followed_by_property_expr | FollowedByPropertyExpr: followed_by property expression |
| FollowedBySequenceExpr | extract_followed_by_sequence_expr | FollowedBySequenceExpr: followed by #=# |
| ForGenerate | extract_for_generate | ForGenerate: for generate construct |
| ForLoopStatement | extract_for_loop_statement | ForLoopStatement: for loop statement |
| ForLoopStatementExpression | extract_for_loop_expression | ForLoopStatementExpression: for loop expression |
| ForVariableDeclaration | extract_for_variable_declaration | ForVariableDeclaration: for loop variable declaration |
| ForceStatement | extract_force_statement | ForceStatement: force statement |
| ForeachConstraint | extract_foreach_constraint | ForeachConstraint: foreach constraint |
| ForeachConstraintExpr | extract_foreach_constraint_expr | ForeachConstraintExpr: foreach constraint expression |
| ForeachLoopStatement | extract_foreach_loop_statement | ForeachLoopStatement: foreach loop statement |
| ForeachLoopStatementExpression | extract_foreach_loop_expression | ForeachLoopStatementExpression: foreach loop |
| ForeverLoopStatement | extract_forever_loop_statement | ForeverLoopStatement: forever loop |
| ForeverLoopStatement | extract_forever_loop_statement_stmt | ForeverLoopStatement: forever loop statement |
| ForeverStatement | extract_forever_statement | ForeverStatement: forever statement |
| ForkStatement | extract_fork_statement | ForkStatement: fork statement |
| ForkStatementExpression | extract_fork_stmt_expression | ForkStatementExpression: fork join |
| ForwardTypedefDeclaration | extract_forward_typedef_declaration | ForwardTypedefDeclaration: forward typedef declaration |
| FullSkewTimingCheck | extract_full_skew_timing_check | FullSkewTimingCheck: full skew timing check |
| FunctionDeclaration | extract_function_declaration | FunctionDeclaration: function declaration |
| FunctionPort | extract_function_port | FunctionPort: function port |
| FunctionPortList | extract_function_port_list | FunctionPortList: function port list |
| FunctionPrototype | extract_function_prototype | FunctionPrototype: function prototype |
| FunctionReturnType | extract_function_return_type | FunctionReturnType: function return type |
| FunctionSubroutine | extract_function_subroutine | FunctionSubroutine: function subroutine |
| GenerateBlock | extract_generate_block | GenerateBlock: generate block |
| GenerateRegion | extract_generate_region | GenerateRegion: generate region |
| GenvarDeclaration | extract_genvar_declaration | GenvarDeclaration: genvar declaration |
| GreaterThanEqualExpression | extract_greater_than_equal_expression | GreaterThanEqualExpression: >= expression |
| GreaterThanExpr | extract_greater_than_expr_stmt | GreaterThanExpr: greater than expression > |
| GreaterThanExpression | extract_greater_than_expression | GreaterThanExpression: greater than expression > |
| GreaterThanOrEqualExpr | extract_greater_than_or_equal_expr_stmt | GreaterThanOrEqualExpr: greater than or equal expression >= |
| GreaterThanOrEqualExpression | extract_greater_than_or_equal_expression | GreaterThanOrEqualExpression: greater than or equal expre... |
| HierarchicalValueExpression | extract_hierarchical_value | HierarchicalValueExpression: ifc.data |
| HoldTimingCheck | extract_hold_timing_check | HoldTimingCheck: hold timing check |
| IdWithExprCoverageBinInitializer | extract_id_with_expr_coverage_bin_initializer | IdWithExprCoverageBinInitializer: id with expr coverage b... |
| IdentifierName | extract_identifier_name | IdentifierName: 简单信号名 |
| IdentifierSelect | extract_identifier_select | IdentifierSelect: data[3] 等带位选的标识符 |
| IfConstraint | extract_if_constraint | IfConstraint: if (cond) constraint |
| IfElseConditionItem | extract_if_else_condition_item | IfElseConditionItem: if else condition item |
| IfElseConstraintExpr | extract_if_else_constraint_expr | IfElseConstraintExpr: if-else constraint expression |
| IfElseStatementExpression | extract_if_else_stmt_expression | IfElseStatementExpression: if else statement |
| IfGenerate | extract_if_generate | IfGenerate: if generate construct |
| IfNonePathDeclaration | extract_if_none_path_declaration | IfNonePathDeclaration: ifnone path declaration |
| IfPropertyExpr | extract_if_property_expr_stmt | IfPropertyExpr: if property expression |
| IfPropertyExpression | extract_if_property_expression | IfPropertyExpression: if property |
| IfStatementExpression | extract_if_stmt_expression | IfStatementExpression: if statement expression |
| IffEventClause | extract_iff_event_clause | IffEventClause: iff event clause |
| IffPropertyExpr | extract_iff_property_expr | IffPropertyExpr: property iff expression |
| ImmediateAssertStatement | extract_immediate_assert_statement | ImmediateAssertStatement: immediate assert statement |
| ImmediateAssertStatementExpression | extract_immediate_assert_stmt_expr | ImmediateAssertStatementExpression: immediate assert |
| ImmediateAssertionStatement | extract_immediate_assertion | ImmediateAssertionStatement: immediate assertion |
| ImmediateAssumeStatement | extract_immediate_assume_statement | ImmediateAssumeStatement: immediate assume statement |
| ImmediateAssumeStatementExpression | extract_immediate_assume_stmt_expr | ImmediateAssumeStatementExpression: immediate assume |
| ImmediateCoverStatement | extract_immediate_cover_statement | ImmediateCoverStatement: immediate cover statement |
| ImmediateCoverStatementExpression | extract_immediate_cover_stmt_expr | ImmediateCoverStatementExpression: immediate cover |
| ImplementsClause | extract_implements_clause | ImplementsClause: implements clause |
| Implication | extract_implication | Implication: sequence implication |
| ImplicationConstraint | extract_implication_constraint | ImplicationConstraint: implication constraint |
| ImplicationConstraintExpr | extract_implication_constraint_expr | ImplicationConstraintExpr: implication constraint expression |
| ImplicationExpression | extract_implication_expression | ImplicationExpression: implication expression |
| ImplicationPropertyExpr | extract_implication_property_expr | ImplicationPropertyExpr: implication property expression |
| ImplicationSequenceExpr | extract_implication_sequence_expr | ImplicationSequenceExpr: implication sequence => or -> |
| ImplicationWindow | extract_implication_window | ImplicationWindow: implication window |
| ImplicitConversion | extract_implicit_conversion | ImplicitConversion: implicit conversion |
| ImplicitEventControl | extract_implicit_event_control | ImplicitEventControl: @@ |
| ImplicitEventTimingControl | extract_implicit_event_timing_control | ImplicitEventTimingControl: implicit event timing control |
| ImpliesPropertyExpr | extract_implies_property_expr_stmt | ImpliesPropertyExpr: implies property expression |
| ImportExportExpr | extract_import_export_expr | ImportExportExpr: import export expression |
| ImportPackageDeclaration | extract_import_package_declaration | ImportPackageDeclaration: import package declaration |
| IncrementAssignmentExpr | extract_increment_assignment_expr | IncrementAssignmentExpr: increment assignment expression |
| IndexedDownRangeSelection | extract_indexed_down_range_selection | IndexedDownRangeSelection: indexed down range selection |
| IndexedUpRangeSelection | extract_indexed_up_range_selection | IndexedUpRangeSelection: indexed up range selection |
| InequalityExpr | extract_inequality_expr | InequalityExpr: inequality expression != |
| InequalityExpression | extract_inequality_expression | InequalityExpression: inequality expression != |
| InfoElabSystemTask | extract_info_elab_system_task | InfoElabSystemTask: info elaboration system task |
| InitialBlock | extract_initial_block | InitialBlock: initial block |
| InitialProceduralBlock | extract_initial_procedural_block | InitialProceduralBlock: initial block |
| InitialStatement | extract_initial_statement | InitialStatement: initial statement |
| InsideExpr | extract_inside_expr | InsideExpr: inside expression |
| InsideExpression | extract_inside | InsideExpression: expr inside {a, b, c} |
| IntType | extract_int_type | IntType: int type |
| IntegerLiteral | extract_integer_literal | IntegerLiteral: 整数字面量 |
| IntegerLiteralExpr | extract_integer_literal_expr | IntegerLiteralExpr: integer literal expression |
| IntegerLiteralExpression | extract_integer_literal_expression_stmt | IntegerLiteralExpression: integer literal expression |
| IntegerType | extract_integer_type | IntegerType: integer type |
| IntegerVectorExpression | extract_integer_vector | IntegerVectorExpression: 带位宽的字面量 |
| InterfaceDeclaration | extract_interface_declaration | InterfaceDeclaration: interface declaration |
| InterfaceDefinition | extract_interface_definition | InterfaceDefinition: interface definition |
| InterfaceHandleExpr | extract_interface_handle_expr | InterfaceHandleExpr: interface handle expression |
| InterfaceHeader | extract_interface_header_stmt | InterfaceHeader: interface header |
| InterfaceInstantiation | extract_interface_instantiation | InterfaceInstantiation: interface instantiation |
| InterfacePortHeader | extract_interface_port_header | InterfacePortHeader: interface port header |
| IntersectClause | extract_intersect_clause | IntersectClause: intersect clause |
| IntersectSequenceExpr | extract_intersect_sequence_expr | IntersectSequenceExpr: intersect sequence expression |
| Invalid | extract_invalid | Invalid: 无效节点 |
| InvalidBinsSelectExpr | extract_invalid_bins_select_expr | InvalidBinsSelectExpr: invalid bins select expression |
| InvalidExpression | extract_invalid_expression | InvalidExpression: invalid expression |
| InvalidPort | extract_invalid_port | InvalidPort: invalid port |
| InvalidTimingControl | extract_invalid_timing_control | InvalidTimingControl: invalid timing control |
| InvocationExpression | extract_invocation_expression | InvocationExpression: invocation expression |
| JoinAllStatementBlock | extract_join_all_statement_block | JoinAllStatementBlock: join all statement block |
| JoinAnyStatement | extract_join_any_statement_stmt | JoinAnyStatement: join any statement |
| JoinAnyStatementBlock | extract_join_any_statement_block | JoinAnyStatementBlock: join any statement block |
| JoinAnyStatementExpression | extract_join_any_expression | JoinAnyStatementExpression: join any |
| JoinNoneStatement | extract_join_none_statement_stmt | JoinNoneStatement: join none statement |
| JoinNoneStatementBlock | extract_join_none_statement_block | JoinNoneStatementBlock: join none statement block |
| JoinNoneStatementExpression | extract_join_none_expression | JoinNoneStatementExpression: join none |
| JoinStatement | extract_join_statement | JoinStatement: join statement |
| JumpStatement | extract_jump_statement | JumpStatement: break, continue, return, disable statements |
| JumpStatementExpression | extract_jump_statement_expression | JumpStatementExpression: jump statement |
| LValueReference | extract_l_value_reference | LValueReference: 左值引用 |
| LeftShiftExpr | extract_left_shift_expr | LeftShiftExpr: left shift expression << |
| LessThanEqualExpression | extract_less_than_equal_expression | LessThanEqualExpression: <= expression |
| LessThanExpr | extract_less_than_expr_stmt | LessThanExpr: less than expression < |
| LessThanExpression | extract_less_than_expression | LessThanExpression: less than expression < |
| LessThanOrEqualExpr | extract_less_than_or_equal_expr_stmt | LessThanOrEqualExpr: less than or equal expression <= |
| LessThanOrEqualExpression | extract_less_than_or_equal_expression | LessThanOrEqualExpression: less than or equal expression <= |
| LetDeclaration | extract_let_declaration | LetDeclaration: let declaration |
| LetExpression | extract_let_expression | LetExpression: let expression |
| LetExpression | extract_let_expression_stmt | LetExpression: let expression |
| LetStatementExpression | extract_let_stmt_expression | LetStatementExpression: let statement |
| LibraryDeclaration | extract_library_declaration | LibraryDeclaration: library declaration |
| LibraryIncDirClause | extract_library_inc_dir_clause | LibraryIncDirClause: library include directory clause |
| LineCommentTrivia | extract_line_comment_trivia | LineCommentTrivia: line comment trivia |
| ListStatement | extract_list_statement | ListStatement: list of statements |
| LocalParameterDeclaration | extract_local_parameter_declaration | LocalParameterDeclaration: local parameter declaration |
| LocalVariableDeclaration | extract_local_variable_declaration | LocalVariableDeclaration: local variable declaration |
| LogicType | extract_logic_type | LogicType: logic type |
| LogicalAndExpr | extract_logical_and_expr | LogicalAndExpr: logical and expression && |
| LogicalAndExpression | extract_logical_and_expression_stmt | LogicalAndExpression: && expression |
| LogicalEquivalenceExpression | extract_logical_equivalence_expression | LogicalEquivalenceExpression: <-> expression |
| LogicalImplicationExpression | extract_logical_implication_expression | LogicalImplicationExpression: -> expression |
| LogicalLeftShiftAssignmentExpression | extract_logical_left_shift_assignment | LogicalLeftShiftAssignmentExpression: <<= |
| LogicalLeftShiftExpression | extract_logical_left_shift_expression | LogicalLeftShiftExpression: logical left shift << |
| LogicalOrExpr | extract_logical_or_expr | LogicalOrExpr: logical or expression || |
| LogicalOrExpression | extract_logical_or_expression_stmt | LogicalOrExpression: || expression |
| LogicalRightShiftAssignmentExpression | extract_logical_right_shift_assignment | LogicalRightShiftAssignmentExpression: >>= |
| LogicalRightShiftExpression | extract_logical_right_shift_expression | LogicalRightShiftExpression: logical right shift >> |
| LogicalShiftLeftExpression | extract_logical_shift_left_expression | LogicalShiftLeftExpression: << expression |
| LogicalShiftRightExpression | extract_logical_shift_right_expression | LogicalShiftRightExpression: >> expression |
| LogicalXnorExpr | extract_logical_xnor_expr | LogicalXnorExpr: logical xnor expression ^~ |
| LogicalXorExpr | extract_logical_xor_expr | LogicalXorExpr: logical xor expression ^ |
| LongIntType | extract_long_int_type | LongIntType: longint type |
| LoopConstraint | extract_loop_constraint_stmt | LoopConstraint: loop constraint |
| LoopGenerate | extract_loop_generate | LoopGenerate: loop generate construct |
| LoopStatement | extract_loop_statement | LoopStatement: loop statement (for, while, do-while, repe... |
| LoopStatementExpression | extract_loop_statement_expression | LoopStatementExpression: loop statement expression |
| MatchedExpr | extract_matched_expr | MatchedExpr: matched expression |
| MatchedExpr | extract_matched_expr_stmt | MatchedExpr: matched expression |
| MatchedMultipleSequences | extract_matched_multiple_sequences | MatchedMultipleSequences: matched sequences |
| MatchedProperty | extract_matched_property | MatchedProperty: matched property |
| MatchedSequence | extract_matched_sequence | MatchedSequence: matched sequence |
| MatchesClause | extract_matches_clause | MatchesClause: matches clause |
| MemberAccessExpression | extract_member_access | MemberAccessExpression: obj.member |
| MethodCallExpression | extract_method_call_expression_stmt | MethodCallExpression: method call expression |
| MinTypMaxExpr | extract_min_typ_max_expr_stmt | MinTypMaxExpr: min typ max expression |
| MinTypMaxExpression | extract_min_typ_max | MinTypMaxExpression: min:typ:max |
| MinusBitSelectExpr | extract_minus_bit_select_expr | MinusBitSelectExpr: minus bit select expression |
| MinusRangeSelectExpr | extract_minus_range_select_expr | MinusRangeSelectExpr: minus range select [a-:b] |
| ModAssignmentExpression | extract_mod_assignment_expression | ModAssignmentExpression: mod assignment expression |
| ModExpression | extract_mod_expression_stmt | ModExpression: mod expression % |
| ModportClockingItem | extract_modport_clocking_item | ModportClockingItem: modport clocking item |
| ModportClockingPort | extract_modport_clocking_port | ModportClockingPort: modport clocking port |
| ModportDeclaration | extract_modport_declaration | ModportDeclaration: modport declaration |
| ModportExplicitPort | extract_modport_explicit_port | ModportExplicitPort: modport explicit port |
| ModportItem | extract_modport_item | ModportItem: modport item |
| ModportNamedPort | extract_modport_named_port | ModportNamedPort: modport named port |
| ModportSimplePortDecl | extract_modport_simple_port_decl | ModportSimplePortDecl: modport simple port declaration |
| ModportSimplePortList | extract_modport_simple_port_list | ModportSimplePortList: modport simple port list |
| ModportSubroutinePort | extract_modport_subroutine_port | ModportSubroutinePort: modport subroutine port |
| ModportSubroutinePortDecl | extract_modport_subroutine_port_decl | ModportSubroutinePortDecl: modport subroutine port declar... |
| ModportSubroutinePortList | extract_modport_subroutine_port_list | ModportSubroutinePortList: modport subroutine port list |
| ModuleDeclaration | extract_module_declaration | ModuleDeclaration: module declaration |
| ModuleDefinition | extract_module_definition | ModuleDefinition: module definition |
| ModuleHeader | extract_module_header | ModuleHeader: module header |
| ModuloAssignmentExpression | extract_modulo_assignment_expression | ModuloAssignmentExpression: %= |
| ModuloExpr | extract_modulo_expr | ModuloExpr: modulo expression % |
| ModuloExpression | extract_modulo_expression | ModuloExpression: modulo expression |
| MultiPattern | extract_multi_pattern | MultiPattern: multiple patterns |
| MulticastExpression | extract_multicast_expression | MulticastExpression: multicast expression |
| MultipleConcatenationExpression | extract_multiple_concatenation | MultipleConcatenationExpression: {{n{expr}} |
| MultiplyAssignmentExpression | extract_multiply_assignment_expression | MultiplyAssignmentExpression: *= |
| MultiplyExpr | extract_multiply_expr_stmt | MultiplyExpr: multiply expression * |
| MultiplyExpression | extract_multiply_expression | MultiplyExpression: multiplication expression |
| NameValuePragmaExpression | extract_name_value_pragma_expression | NameValuePragmaExpression: name value pragma expression |
| NamedBlockClause | extract_named_block_clause | NamedBlockClause: named block clause |
| NamedValue | extract_named_value | NamedValue: 单一信号引用                  SignalResult 返回: prim... |
| NegEdge | extract_neg_edge | NegEdge: negative edge |
| NetDeclaration | extract_net_declaration | NetDeclaration: net declaration |
| NetTypeDeclaration | extract_net_type_declaration | NetTypeDeclaration: net type declaration |
| NewArrayExpression | extract_new_array | NewArrayExpression: new[size] |
| NewArrayExpression | extract_new_array_expression_stmt | NewArrayExpression: new array expression |
| NewClassExpression | extract_new_class | NewClassExpression: new() |
| NewClassExpression | extract_new_class_expression_stmt | NewClassExpression: new class expression |
| NewCovergroupExpression | extract_new_covergroup | NewCovergroupExpression: covergroup |
| NewCovergroupExpression | extract_new_covergroup_expression_stmt | NewCovergroupExpression: new covergroup expression |
| NoChangeTimingCheck | extract_no_change_timing_check | NoChangeTimingCheck: nochange timing check |
| NoEdge | extract_no_edge | NoEdge: no edge |
| NoShowCancelledPulseStyle | extract_no_show_cancelled_pulse_style | NoShowCancelledPulseStyle: no_show_cancelled pulse style |
| NonBlockingAssignmentStatement | extract_non_blocking_assignment_stmt | NonBlockingAssignmentStatement: non-blocking assignment s... |
| NonBlockingAssignmentStatement | extract_nonblocking_assignment_stmt | NonBlockingAssignmentStatement: non-blocking assignment |
| NonNullMethodCallSequence | extract_non_null_method_call_seq | NonNullMethodCallSequence: non null method call |
| NonOverlappingFollowedBySequenceExpr | extract_non_overlapping_followed_by_seq | NonOverlappingFollowedBySequenceExpr: non-overlapping fol... |
| NonblockingAssignmentExpression | extract_nonblocking_assignment_expression | NonblockingAssignmentExpression: nonblocking assignment e... |
| NonblockingEventTriggerStatement | extract_nonblocking_event_trigger_statement | NonblockingEventTriggerStatement: nonblocking event trigg... |
| NotPropertyExpr | extract_not_property_expr | NotPropertyExpr: not property expression |
| NullCheckExpression | extract_null_check | NullCheckExpression: null check |
| NullExpression | extract_null_expression | NullExpression: null expression |
| NullLiteral | extract_null_literal | NullLiteralExpression: null |
| NullLiteralExpression | extract_null_literal_expression | NullLiteralExpression: null literal expression |
| NullOtherControl | extract_null_other_control | NullOtherControl: null or other control |
| NumberPragmaExpression | extract_number_pragma_expression | NumberPragmaExpression: number pragma expression |
| OnDetectPulseStyle | extract_on_detect_pulse_style | OnDetectPulseStyle: on_detect pulse style |
| OnEventPulseStyle | extract_on_event_pulse_style | OnEventPulseStyle: on_event pulse style |
| OneStepDelayTimingControl | extract_one_step_delay_timing_control | OneStepDelayTimingControl: one step delay |
| OpenRangeExpression | extract_open_range | OpenRangeExpression: open range |
| OpenRangeExpression | extract_open_range_expression | OpenRangeExpression: open range expression |
| OrAssignmentExpression | extract_or_assignment_expression | OrAssignmentExpression: or assignment |= |
| OrPropertyExpr | extract_or_property_expr | OrPropertyExpr: or property expression |
| OrSequenceExpr | extract_or_sequence_expr | OrSequenceExpr: or sequence expression |
| OrSequenceExpr | extract_or_sequence_expr_stmt | OrSequenceExpr: or sequence expression |
| OverlappingFollowedBySequenceExpr | extract_overlapping_followed_by_seq | OverlappingFollowedBySequenceExpr: overlapping followed b... |
| PackageDeclaration | extract_package_declaration | PackageDeclaration: package declaration |
| PackageExportAllDeclaration | extract_package_export_all_declaration | PackageExportAllDeclaration: package export all declaration |
| PackageExportDeclaration | extract_package_export_declaration | PackageExportDeclaration: package export declaration |
| PackageExpression | extract_package_expression | PackageExpression: package expression |
| PackageHeader | extract_package_header | PackageHeader: package header |
| PackageImportDeclaration | extract_package_import_declaration | PackageImportDeclaration: package import declaration |
| PackageImportItem | extract_package_import_item | PackageImportItem: package import item |
| ParallelBlockStatement | extract_parallel_block_statement | ParallelBlockStatement: parallel block statement |
| ParallelStatementExpression | extract_parallel_stmt_expression | ParallelStatementExpression: parallel statement |
| ParameterDeclaration | extract_parameter_declaration | ParameterDeclaration: parameter declaration |
| ParameterDeclarationStatement | extract_parameter_declaration_statement | ParameterDeclarationStatement: parameter declaration stat... |
| ParameterizedPropertyExpression | extract_parameterized_property | ParameterizedPropertyExpression: parameterized property |
| ParenConstantExpression | extract_paren_constant_expression | ParenConstantExpression: (constant) |
| ParenExpressionList | extract_paren_expression_list | ParenExpressionList: parenthesized expression list |
| ParenPragmaExpression | extract_paren_pragma_expression | ParenPragmaExpression: parenthesized pragma expression |
| ParenthesisExpression | extract_parenthesis_expression | ParenthesisExpression: (expr) |
| ParenthesizedBinsSelectExpr | extract_parenthesized_bins_select_expr | ParenthesizedBinsSelectExpr: parenthesized bins select ex... |
| ParenthesizedConditionalDirectiveExpression | extract_parenthesized_conditional_directive_expression | ParenthesizedConditionalDirectiveExpression: parenthesize... |
| ParenthesizedEventExpression | extract_parenthesized_event_expression | ParenthesizedEventExpression: parenthesized event expression |
| ParenthesizedExpression | extract_parenthesized_expression | ParenthesizedExpression: parenthesized expression |
| ParenthesizedPropertyExpr | extract_parenthesized_property_expr | ParenthesizedPropertyExpr: parenthesized property expression |
| ParenthesizedSequenceExpr | extract_parenthesized_sequence_expr | ParenthesizedSequenceExpr: parenthesized sequence expression |
| PathDeclaration | extract_path_declaration | PathDeclaration: path declaration |
| PatternBinding | extract_pattern_binding | PatternBinding: pattern binding |
| PatternCaseItem | extract_pattern_case_item | PatternCaseItem: pattern case item |
| PatternStatementExpression | extract_pattern_stmt_expression | PatternStatementExpression: pattern statement |
| PeriodTimingCheck | extract_period_timing_check | PeriodTimingCheck: period timing check |
| PlusBitSelectExpr | extract_plus_bit_select_expr | PlusBitSelectExpr: plus bit select expression |
| PlusRangeSelectExpr | extract_plus_range_select_expr | PlusRangeSelectExpr: plus range select [a+:b] |
| PortDeclaration | extract_port_declaration | PortDeclaration: port declaration |
| PosEdge | extract_pos_edge | PosEdge: positive edge |
| PostDecrementExpr | extract_post_decrement_expr_stmt | PostDecrementExpr: post decrement expression expr-- |
| PostDecrementExpression | extract_post_decrement_expression | PostDecrementExpression: post decrement expression i-- |
| PostIncrementExpr | extract_post_increment_expr_stmt | PostIncrementExpr: post increment expression expr++ |
| PostIncrementExpression | extract_post_increment_expression | PostIncrementExpression: post increment expression i++ |
| PostdecrementExpression | extract_postdecrement_expression_stmt | PostdecrementExpression: post-decrement expression expr-- |
| PostincrementExpression | extract_postincrement_expression_stmt | PostincrementExpression: post-increment expression expr++ |
| PostrandomizeMethodExpr | extract_postrandomize_method_expr | PostrandomizeMethodExpr: post_randomize() method expression |
| PowerExpr | extract_power_expr | PowerExpr: power expression ** |
| PowerExpression | extract_power_expression | PowerExpression: power expression ** |
| PreDecrementExpr | extract_pre_decrement_expr | PreDecrementExpr: pre decrement expression --expr |
| PreDecrementExpression | extract_pre_decrement_expression | PreDecrementExpression: pre decrement expression --i |
| PreIncrementExpr | extract_pre_increment_expr | PreIncrementExpr: pre increment expression ++expr |
| PreIncrementExpression | extract_pre_increment_expression | PreIncrementExpression: pre increment expression ++i |
| PrerandomizeMethodExpr | extract_prerandomize_method_expr | PrerandomizeMethodExpr: pre_randomize() method expression |
| PrimaryBlockEventExpression | extract_primary_block_event_expression | PrimaryBlockEventExpression: primary block event expression |
| PrimaryExpression | extract_primary_expression_stmt | PrimaryExpression: primary expression |
| ProceduralAssignStatement | extract_procedural_assign_statement | ProceduralAssignStatement: procedural assign |
| ProceduralAssignStatement | extract_procedural_assign_statement_stmt | ProceduralAssignStatement: procedural assign statement |
| ProceduralAssignStatement | extract_procedural_assign_stmt | ProceduralAssignStatement: procedural assign |
| ProceduralCheckerStatement | extract_procedural_checker_statement | ProceduralCheckerStatement: procedural checker |
| ProceduralDeassignStatement | extract_procedural_deassign_statement | ProceduralDeassignStatement: procedural deassign |
| ProceduralDeassignStatement | extract_procedural_deassign_statement_stmt | ProceduralDeassignStatement: procedural deassign statement |
| ProceduralForceStatement | extract_procedural_force_stmt | ProceduralForceStatement: procedural force |
| ProceduralReleaseStatement | extract_procedural_release_statement | ProceduralReleaseStatement: procedural release statement |
| ProceduralTimingControl | extract_procedural_timing_control | ProceduralTimingControl: procedural timing control |
| ProceduralTimingControlStatement | extract_procedural_timing_control_stmt | ProceduralTimingControlStatement: procedural timing contr... |
| ProgramDeclaration | extract_program_declaration_stmt | ProgramDeclaration: program declaration |
| ProgramDefinition | extract_program_definition | ProgramDefinition: program definition |
| ProgramHeader | extract_program_header | ProgramHeader: program header |
| ProgramInstantiation | extract_program_instantiation | ProgramInstantiation: program instantiation |
| PropagatedConversion | extract_propagated_conversion | PropagatedConversion: propagated conversion |
| PropertyActualArgument | extract_property_actual_argument | PropertyActualArgument: property argument |
| PropertyAnd | extract_property_and | PropertyAnd: property and |
| PropertyAndExpr | extract_property_and_expr_stmt | PropertyAndExpr: property and expression |
| PropertyAndSequence | extract_property_and_sequence | PropertyAndSequence: property and sequence |
| PropertyClocked | extract_property_clocked | PropertyClocked: property with clock |
| PropertyDeclaration | extract_property_declaration_stmt | PropertyDeclaration: property declaration |
| PropertyDisableIff | extract_property_disable | PropertyDisableIff: disable iff |
| PropertyExpr | extract_property_expr | PropertyExpr: property expression |
| PropertyExprItem | extract_property_expr_item | PropertyExprItem: property expression item |
| PropertyIfExpr | extract_property_if_expr | PropertyIfExpr: property if expression |
| PropertyImplication | extract_property_implication | PropertyImplication: property implication |
| PropertyImplicationExpr | extract_property_implication_expr | PropertyImplicationExpr: property implication expression |
| PropertyInstance | extract_property_instance | PropertyInstance: property call |
| PropertyListExpression | extract_property_list_expression | PropertyListExpression: property list expression |
| PropertyMatched | extract_property_matched | PropertyMatched: matched property |
| PropertyNot | extract_property_not | PropertyNot: not property |
| PropertyNotExpr | extract_property_not_expr_stmt | PropertyNotExpr: property not expression |
| PropertyOr | extract_property_or | PropertyOr: property or |
| PropertyOrExpr | extract_property_or_expr_stmt | PropertyOrExpr: property or expression |
| PropertyOrSequence | extract_property_or_sequence | PropertyOrSequence: property or sequence |
| PropertySequence | extract_property_sequence | PropertySequence: sequence expression |
| PropertySpec | extract_property_spec | PropertySpec: property spec |
| PropertySpecExpression | extract_property_spec_expression | PropertySpecExpression: property spec expression |
| PropertyType | extract_property_type | PropertyType: property type |
| PulseStyleDeclaration | extract_pulse_style_declaration | PulseStyleDeclaration: pulse style declaration |
| QueueDimension | extract_queue_dimension | QueueDimension: queue dimension |
| QueueExpression | extract_queue_expression | QueueExpression: queue expression |
| QueueLiteral | extract_queue_literal | QueueLiteral: '{...} |
| RandCaseItem | extract_rand_case_item | RandCaseItem: rand case item |
| RandCaseItem | extract_rand_case_item_stmt | RandCaseItem: rand case item |
| RandCaseStatement | extract_rand_case_statement | RandCaseStatement: rand case |
| RandCaseStatement | extract_rand_case_statement_stmt | RandCaseStatement: rand case statement |
| RandJoinClause | extract_rand_join_clause | RandJoinClause: rand join clause |
| RandSequenceBodyExpr | extract_rand_sequence_body_expr | RandSequenceBodyExpr: rand sequence body expression |
| RandSequenceExpression | extract_rand_sequence_expression | RandSequenceExpression: rand sequence expression |
| RandSequenceItemExpr | extract_rand_sequence_item_expr | RandSequenceItemExpr: rand sequence item expression |
| RandSequenceRepeatExpr | extract_rand_sequence_repeat_expr | RandSequenceRepeatExpr: rand sequence repeat expression |
| RandSequenceStatement | extract_rand_sequence_statement | RandSequenceStatement: rand sequence statement |
| RandSequenceWhenExpr | extract_rand_sequence_when_expr | RandSequenceWhenExpr: rand sequence when expression |
| RandomizeMethodExpr | extract_randomize_method_expr | RandomizeMethodExpr: randomize() method expression |
| RandomizeSequence | extract_randomize_sequence | RandomizeSequence: randomize with sequence |
| RandomizeWithExpression | extract_randomize_with_expression | RandomizeWithExpression: randomize with expression |
| RangeConstraint | extract_range_constraint | RangeConstraint: range constraint |
| RangeDimension | extract_range_dimension | RangeDimension: range dimension |
| RangeSelectExpression | extract_range_select | RangeSelectExpression: data[3:0] |
| RealLiteral | extract_real_literal | RealLiteralExpression: 实数字面量 |
| RealLiteralExpr | extract_real_literal_expr | RealLiteralExpr: real literal expression |
| RealLiteralExpression | extract_real_literal_expression_stmt | RealLiteralExpression: real literal expression |
| RealType | extract_real_type | RealType: real type |
| RecRemTimingCheck | extract_rec_rem_timing_check | RecRemTimingCheck: recrem timing check |
| RecoveryTimingCheck | extract_recovery_timing_check | RecoveryTimingCheck: recovery timing check |
| RefVariableExpression | extract_ref_variable | RefVariableExpression: ref variable |
| RegType | extract_reg_type | RegType: reg type |
| RejectConditionExpression | extract_reject_condition_expression | RejectConditionExpression: reject condition expression |
| RejectStatement | extract_reject_statement | RejectStatement: reject statement |
| RelativeToleranceValueRange | extract_relative_tolerance_value_range | RelativeToleranceValueRange: relative tolerance value range |
| ReleaseStatement | extract_release_statement | ReleaseStatement: release statement |
| ReleaseStatement | extract_release_stmt | ReleaseStatement: release |
| RemovalTimingCheck | extract_removal_timing_check | RemovalTimingCheck: removal timing check |
| RepeatLoopStatement | extract_repeat_loop_statement | RepeatLoopStatement: repeat loop |
| RepeatLoopStatement | extract_repeat_loop_statement_stmt | RepeatLoopStatement: repeat loop statement |
| RepeatedEventControl | extract_repeated_event_control | RepeatedEventControl: repeated event control |
| RepeatedEventTimingControl | extract_repeated_event_timing_control | RepeatedEventTimingControl: repeated event timing control |
| RepeatedPattern | extract_repeated_pattern | RepeatedPattern: repeated pattern |
| ReplicatedAssignmentPattern | extract_replicated_assignment_pattern | ReplicatedAssignmentPattern: '{n{a, b, c}} |
| ReplicatedPatternExpr | extract_replicated_pattern_expr | ReplicatedPatternExpr: replicated pattern expression |
| ReplicationExpr | extract_replication_expr | ReplicationExpr: replication expression {N{expr}} |
| ReplicationExpression | extract_replication | ReplicationExpression: {N{signal}} |
| RestrictExpression | extract_restrict_expression | RestrictExpression: restrict expression |
| RestrictPropertyExpression | extract_restrict_property | RestrictPropertyExpression: restrict property |
| RestrictPropertyStatement | extract_restrict_property_statement | RestrictPropertyStatement: restrict property statement |
| ReturnMethodCallSequence | extract_return_method_call_seq | ReturnMethodCallSequence: return method call sequence |
| ReturnStatement | extract_return_statement | ReturnStatement: return statement |
| ReturnStatement | extract_return_statement | ReturnStatement: return statement |
| ReturnStatementExpression | extract_return_expression | ReturnStatementExpression: return expression |
| ReturnStatementExpression | extract_return_stmt_expression | ReturnStatementExpression: return expression |
| RightShiftExpr | extract_right_shift_expr | RightShiftExpr: right shift expression >> |
| RsCase | extract_rs_case | RsCase: randsequence case |
| RsCodeBlock | extract_rs_code_block | RsCodeBlock: randsequence code block |
| RsElseClause | extract_rs_else_clause | RsElseClause: randsequence else clause |
| RsWeightClause | extract_rs_weight_clause | RsWeightClause: randsequence weight clause |
| SUntilPropertyExpr | extract_s_until_property_expr | SUntilPropertyExpr: s_until property expression |
| SUntilWithPropertyExpr | extract_s_until_with_property_expr | SUntilWithPropertyExpr: s_until_with property expression |
| ScopedName | extract_scoped_name | ScopedName: 点分路径 p.sub.data |
| SequenceAbbrevMaybe | extract_sequence_abbrev_maybe | SequenceAbbrevMaybe: maybe ##? |
| SequenceAbbrevMaybeExpr | extract_sequence_abbrev_maybe_expr | SequenceAbbrevMaybeExpr: sequence abbreviation maybe ##? |
| SequenceAbbrevPlus | extract_sequence_abbrev_plus | SequenceAbbrevPlus: plus ##+ |
| SequenceAbbrevPlusExpr | extract_sequence_abbrev_plus_expr | SequenceAbbrevPlusExpr: sequence abbreviation plus ##+ |
| SequenceAbbrevStar | extract_sequence_abbrev_star | SequenceAbbrevStar: star ##* |
| SequenceAbbrevStarExpr | extract_sequence_abbrev_star_expr | SequenceAbbrevStarExpr: sequence abbreviation star ##* |
| SequenceAbortExpr | extract_sequence_abort_expr | SequenceAbortExpr: sequence abort expression |
| SequenceActualArgument | extract_sequence_actual_argument | SequenceActualArgument: sequence argument |
| SequenceAnd | extract_sequence_and | SequenceAnd: sequence and |
| SequenceAndExpr | extract_sequence_and_expr_stmt | SequenceAndExpr: sequence and expression |
| SequenceClocked | extract_sequence_clocked | SequenceClocked: sequence with clock |
| SequenceClocking | extract_sequence_clock | SequenceClocking: sequence with clock |
| SequenceClockingExpr | extract_sequence_clocking_expr_stmt | SequenceClockingExpr: sequence clocking expression |
| SequenceConcat | extract_sequence_concat | SequenceConcat: sequence concatenation |
| SequenceConcatExpr | extract_sequence_concat_expr | SequenceConcatExpr: sequence concatenation expression |
| SequenceConcatExpr | extract_sequence_concat_expr_stmt | SequenceConcatExpr: sequence concat expression |
| SequenceConcatExpression | extract_sequence_concat_expr | SequenceConcatExpression: sequence concat expression |
| SequenceConjunction | extract_sequence_conjunction | SequenceConjunction: seq1 and seq2 |
| SequenceConjunctionItem | extract_sequence_conjunction_item | SequenceConjunctionItem: sequence conjunction item |
| SequenceDeclaration | extract_sequence_declaration_stmt | SequenceDeclaration: sequence declaration |
| SequenceDelay | extract_sequence_delay | SequenceDelay: ##1 seq |
| SequenceDelayExpr | extract_sequence_delay_expr | SequenceDelayExpr: sequence delay expression ## |
| SequenceEventControl | extract_sequence_event_control | SequenceEventControl: sequence event control |
| SequenceExpr | extract_sequence_expr | SequenceExpr: sequence expression |
| SequenceFirstMatch | extract_sequence_first_match | SequenceFirstMatch: sequence first_match |
| SequenceFirstMatchExpr | extract_sequence_first_match_expr_stmt | SequenceFirstMatchExpr: sequence first_match expression |
| SequenceInstance | extract_sequence_instance | SequenceInstance: sequence call |
| SequenceInstersection | extract_sequence_intersection | SequenceInstersection: sequence intersection |
| SequenceIntersectExpr | extract_sequence_intersect_expr | SequenceIntersectExpr: sequence intersect expression |
| SequenceMatchExpr | extract_sequence_match_expr | SequenceMatchExpr: sequence match expression |
| SequenceMatchFunction | extract_sequence_match_function | SequenceMatchFunction: match function |
| SequenceMatchItem | extract_sequence_match_item | SequenceMatchItem: sequence match item |
| SequenceMatchList | extract_sequence_match_list | SequenceMatchList: sequence match list |
| SequenceMatched | extract_sequence_matched | SequenceMatched: matched sequence |
| SequenceMultiplicationExpr | extract_sequence_multiplication_expr | SequenceMultiplicationExpr: sequence multiplication expre... |
| SequenceNotExpr | extract_sequence_not_expr | SequenceNotExpr: sequence not expression |
| SequenceOr | extract_sequence_or | SequenceOr: sequence or |
| SequenceOrExpr | extract_sequence_or_expr_stmt | SequenceOrExpr: sequence or expression |
| SequencePropertyExpr | extract_sequence_property_expr | SequencePropertyExpr: sequence with clock |
| SequenceRepetition | extract_sequence_repetition | SequenceRepetition: seq[*1:3] |
| SequenceType | extract_sequence_type | SequenceType: sequence type |
| SequenceUnionExpr | extract_sequence_union_expr | SequenceUnionExpr: sequence union expression |
| SequenceWindow | extract_sequence_window | SequenceWindow: sequence window |
| SequenceWithMatchExpression | extract_sequence_with_match_expr | SequenceWithMatchExpression: sequence with match |
| SequentialBlockStatement | extract_sequential_block_statement | SequentialBlockStatement: sequential block statement |
| SequentialStatementBlock | extract_sequential_statement_block | SequentialStatementBlock: sequential statement block |
| SetBinsSelectExpr | extract_set_bins_select_expr | SetBinsSelectExpr: set bins select expression |
| SetupHoldTimingCheck | extract_setup_hold_timing_check | SetupHoldTimingCheck: setup hold timing check |
| SetupTimingCheck | extract_setup_timing_check | SetupTimingCheck: setup timing check |
| ShortIntType | extract_short_int_type | ShortIntType: shortint type |
| ShortRealType | extract_short_real_type | ShortRealType: shortreal type |
| ShowCancelledPulseStyle | extract_show_cancelled_pulse_style | ShowCancelledPulseStyle: show_cancelled pulse style |
| SignalEventExpression | extract_signal_event_expression | SignalEventExpression: signal event expression |
| SignalEventTimingControl | extract_signal_event_timing_control | SignalEventTimingControl: signal event timing control |
| SignallerEventControl | extract_signaller_event_control | SignallerEventControl: signaller event control |
| SignatureExpression | extract_signature_expression | SignatureExpression: signature expression |
| SignedCastExpression | extract_signed_cast_expression | SignedCastExpression: signed cast expression |
| SimpleAssertExpression | extract_simple_assert_expression | SimpleAssertExpression: simple assertion expression |
| SimpleAssignmentPattern | extract_simple_assignment_pattern | SimpleAssignmentPattern: 简单赋值模式 |
| SimpleBinsSelectExpr | extract_simple_bins_select_expr | SimpleBinsSelectExpr: simple bins select expression |
| SimpleDeferredAssertStatement | extract_simple_deferred_assert_statement | SimpleDeferredAssertStatement: simple deferred assert sta... |
| SimpleDeferredImmediateAssertionStatement | extract_simple_deferred_assertion | SimpleDeferredImmediateAssertionStatement: #0 assert |
| SimpleExpression | extract_simple_expression | SimpleExpression: simple expression |
| SimplePragmaExpression | extract_simple_pragma_expression | SimplePragmaExpression: simple pragma expression |
| SimplePropertyExpr | extract_simple_property_expr | SimplePropertyExpr: simple property expression |
| SimpleRangeSelection | extract_simple_range_selection | SimpleRangeSelection: simple range selection |
| SimpleSequenceExpr | extract_simple_sequence_expr | SimpleSequenceExpr: simple sequence expression |
| SimpleValueRange | extract_simple_value_range | SimpleValueRange: simple value range |
| SkewTimingCheck | extract_skew_timing_check | SkewTimingCheck: skew timing check |
| SkippedSyntaxTrivia | extract_skipped_syntax_trivia | SkippedSyntaxTrivia: skipped syntax trivia |
| SkippedTokensTrivia | extract_skipped_tokens_trivia | SkippedTokensTrivia: skipped tokens trivia |
| SolveBeforeConstraint | extract_solve_before_constraint | SolveBeforeConstraint: solve before constraint |
| SolveBeforeConstraintExpr | extract_solve_before_constraint_expr | SolveBeforeConstraintExpr: solve_before constraint expres... |
| SpecifyBlock | extract_specify_block | SpecifyBlock: specify block |
| SpecparamDeclaration | extract_specparam_declaration | SpecparamDeclaration: specparam declaration |
| StandardCaseItem | extract_standard_case_item | StandardCaseItem: standard case item |
| StandardPropertyCaseItem | extract_standard_property_case_item | StandardPropertyCaseItem: standard property case item |
| StandardRsCaseItem | extract_standard_rs_case_item | StandardRsCaseItem: standard randsequence case item |
| StatementOrExpression | extract_statement_or_expression | StatementOrExpression: statement or expression |
| StaticAssertElabSystemTask | extract_static_assert_elab_system_task | StaticAssertElabSystemTask: static assert elaboration sys... |
| StaticCastExpr | extract_static_cast_expr | StaticCastExpr: static cast expression |
| StreamExpression | extract_stream_expression | StreamExpression: {>>[type]{expr}} or {<<[type]{expr}} |
| StreamExpression | extract_stream_expression_stmt | StreamExpression: stream expression |
| StreamExpressionWithRange | extract_stream_expression_with_range | StreamExpressionWithRange: stream expression with range |
| StreamingConcatConversion | extract_streaming_concat_conversion | StreamingConcatConversion: streaming concat conversion |
| StreamingConcatenationExpr | extract_streaming_concatenation_expr | StreamingConcatenationExpr: streaming concatenation expre... |
| StreamingConcatenationExpression | extract_streaming_concatenation_expression | StreamingConcatenationExpression: streaming concatenation... |
| StreamingExpression | extract_streaming | StreamingExpression: {>>[a:b]} or {<<[a:b]} |
| StreamingReplicationExpr | extract_streaming_replication_expr | StreamingReplicationExpr: streaming replication expression |
| StringLiteral | extract_string_literal | StringLiteralExpression: \"string\ |
| StringLiteralExpr | extract_string_literal_expr | StringLiteralExpr: string literal expression |
| StringLiteralExpression | extract_string_literal_expression_stmt | StringLiteralExpression: string literal expression |
| StringType | extract_string_type | StringType: string type |
| StrongParenthesizedProperty | extract_strong_parenthesized_property | StrongParenthesizedProperty: strong(property) |
| StrongWeakAssertExpression | extract_strong_weak_assert_expr | StrongWeakAssertExpression: strong/weak assertion |
| StrongWeakPropertyExpr | extract_strong_weak_property_expr | StrongWeakPropertyExpr: strong/weak property expression |
| StructurePattern | extract_structure_pattern | StructurePattern: structure pattern |
| StructurePatternExpr | extract_structure_pattern_expr | StructurePatternExpr: structure pattern expression |
| StructuredAssignmentPattern | extract_structured_assignment_pattern | StructuredAssignmentPattern: 结构化赋值模式 |
| SubtractAssignmentExpression | extract_subtract_assignment_expression | SubtractAssignmentExpression: subtract assignment -= |
| SubtractExpr | extract_subtract_expr_stmt | SubtractExpr: subtract expression - |
| SubtractExpression | extract_subtract_expression | SubtractExpression: subtraction expression |
| SuperExpression | extract_super_expression | SuperExpression: super expression |
| SuperNewDefaultedArgsExpression | extract_super_new_defaulted_args_expression | SuperNewDefaultedArgsExpression: super.new with defaulted... |
| SyncAcceptSequenceExpr | extract_sync_accept_sequence_expr | SyncAcceptSequenceExpr: sync accept sequence expression |
| SyncQuickBell | extract_sync_quick_bell | SyncQuickBell: sync @bell |
| SyncRejectSequenceExpr | extract_sync_reject_sequence_expr | SyncRejectSequenceExpr: sync reject sequence expression |
| SyncRejectWeakSequenceExpr | extract_sync_reject_weak_sequence_expr | SyncRejectWeakSequenceExpr: sync reject weak sequence exp... |
| SyncSequenceExpr | extract_sync_sequence_expr | SyncSequenceExpr: sync sequence expression |
| SyncSharpBell | extract_sync_sharp_bell | SyncSharpBell: sync ##bell |
| SystemMethodCallExpression | extract_system_method_call_expression | SystemMethodCallExpression: system method call expression |
| TaggedPattern | extract_tagged_pattern | TaggedPattern: tagged pattern |
| TaggedPatternExpr | extract_tagged_pattern_expr | TaggedPatternExpr: tagged pattern expression |
| TaggedPatternExpression | extract_tagged_pattern_expr | TaggedPatternExpression: tagged pattern expression |
| TaggedPatternKind | extract_tagged_pattern_kind | TaggedPatternKind: tagged pattern |
| TaggedUnionExpr | extract_tagged_union_expr | TaggedUnionExpr: tagged union expression |
| TaggedUnionExpression | extract_tagged_union_expression | TaggedUnionExpression: tag'(expr) |
| TaskDeclaration | extract_task_declaration | TaskDeclaration: task declaration |
| TaskPrototype | extract_task_prototype | TaskPrototype: task prototype |
| TaskSubroutine | extract_task_subroutine | TaskSubroutine: task subroutine |
| ThisExpression | extract_this_expression | ThisExpression: this expression |
| ThroughoutFirstMatchSequenceExpr | extract_throughout_first_match_seq_expr | ThroughoutFirstMatchSequenceExpr: throughout first_match ... |
| ThroughoutSequenceExpr | extract_throughout_sequence_expr | ThroughoutSequenceExpr: throughout sequence expression |
| TimeLiteral | extract_time_literal | TimeLiteralExpression: 时间字面量 |
| TimeLiteralExpr | extract_time_literal_expr | TimeLiteralExpr: time literal expression |
| TimeLiteralExpression | extract_time_literal_expression_stmt | TimeLiteralExpression: time literal expression |
| TimeSkewTimingCheck | extract_time_skew_timing_check | TimeSkewTimingCheck: time skew timing check |
| TimeUnitsDeclaration | extract_time_units_declaration | TimeUnitsDeclaration: time units declaration |
| TimedStatement | extract_timed_statement | TimedStatement: timed statement |
| TimingCheckEventArg | extract_timing_check_event_arg | TimingCheckEventArg: timing check event arg |
| TimingCheckEventCondition | extract_timing_check_event_condition | TimingCheckEventCondition: timing check event condition |
| TimingControlEvent | extract_timing_control_event | TimingControlEvent: timing control event |
| TimingControlExpression | extract_timing_control_expression | TimingControlExpression: timing control expression |
| TimingControlSequence | extract_timing_control_sequence | TimingControlSequence: timing control sequence |
| TimingControlStatement | extract_timing_control_statement | TimingControlStatement: timing control statement |
| TimingControlStatementExpression | extract_timing_control_stmt_expression | TimingControlStatementExpression: timing control statement |
| TimingControlWithExpression | extract_timing_control_with_expression | TimingControlWithExpression: timing control with expression |
| TimingDeclarationStatement | extract_timing_decl_stmt | TimingDeclarationStatement: timing declaration |
| TypeOptionExpression | extract_type_option | TypeOptionExpression: type_option expression |
| TypeParameterDeclaration | extract_type_parameter_declaration | TypeParameterDeclaration: type parameter declaration |
| TypeReference | extract_type_reference | TypeReference: 类型引用 |
| TypeType | extract_type_type | TypeType: type type |
| TypedPortDeclaration | extract_typed_port_declaration | TypedPortDeclaration: typed port declaration |
| TypedVariableDeclaration | extract_typed_variable_declaration | TypedVariableDeclaration: typed variable declaration |
| TypedefDeclaration | extract_typedef_declaration_stmt | TypedefDeclaration: typedef declaration |
| TypedefExpression | extract_typedef_expression | TypedefExpression: typedef expression |
| UdpDeclaration | extract_udp_declaration | UdpDeclaration: UDP declaration (Verilog primitive) |
| UnaryAndExpr | extract_unary_and_expr | UnaryAndExpr: unary and expression & |
| UnaryAndExpression | extract_unary_and_expression | UnaryAndExpression: unary and expression & |
| UnaryAssertExpression | extract_unary_assert_expression | UnaryAssertExpression: unary assertion expression |
| UnaryBinsSelectExpr | extract_unary_bins_select_expr | UnaryBinsSelectExpr: unary bins select expression |
| UnaryBitwiseAndExpression | extract_unary_bitwise_and_expression | UnaryBitwiseAndExpression: unary bitwise and expression & |
| UnaryBitwiseNandExpression | extract_unary_bitwise_nand_expression | UnaryBitwiseNandExpression: unary bitwise nand expression ~& |
| UnaryBitwiseNorExpression | extract_unary_bitwise_nor_expression | UnaryBitwiseNorExpression: unary bitwise nor expression ~| |
| UnaryBitwiseNotExpression | extract_unary_bitwise_not_expression | UnaryBitwiseNotExpression: unary bitwise not expression ~ |
| UnaryBitwiseOrExpression | extract_unary_bitwise_or_expression | UnaryBitwiseOrExpression: unary bitwise or expression | |
| UnaryBitwiseXnorExpression | extract_unary_bitwise_xnor_expression | UnaryBitwiseXnorExpression: unary bitwise xnor expression ^~ |
| UnaryBitwiseXorExpression | extract_unary_bitwise_xor_expression | UnaryBitwiseXorExpression: unary bitwise xor expression ^ |
| UnaryConditionalDirectiveExpression | extract_unary_conditional_directive_expression | UnaryConditionalDirectiveExpression: unary conditional di... |
| UnaryExpression | extract_unary | UnaryExpression: ~a, -a, !a 等 |
| UnaryLogicalNotExpression | extract_unary_logical_not_expression | UnaryLogicalNotExpression: unary logical not expression ! |
| UnaryMinusExpr | extract_unary_minus_expr | UnaryMinusExpr: unary minus expression - |
| UnaryMinusExpression | extract_unary_minus_expression_stmt | UnaryMinusExpression: unary minus expression - |
| UnaryNandExpr | extract_unary_nand_expr | UnaryNandExpr: unary nand expression ~& |
| UnaryNandExpression | extract_unary_nand_expression | UnaryNandExpression: unary nand expression ~& |
| UnaryNorExpr | extract_unary_nor_expr | UnaryNorExpr: unary nor expression ~| |
| UnaryNorExpression | extract_unary_nor_expression | UnaryNorExpression: unary nor expression ~| |
| UnaryNotExpr | extract_unary_not_expr | UnaryNotExpr: unary not expression ! |
| UnaryOperator | extract_unary_operator | UnaryOperator: 一元运算符 |
| UnaryOrExpr | extract_unary_or_expr | UnaryOrExpr: unary or expression | |
| UnaryOrExpression | extract_unary_or_expression | UnaryOrExpression: unary or expression | |
| UnaryPlusExpr | extract_unary_plus_expr | UnaryPlusExpr: unary plus expression + |
| UnaryPlusExpression | extract_unary_plus_expression_stmt | UnaryPlusExpression: unary plus expression + |
| UnaryPredecrementExpression | extract_unary_predecrement_expression | UnaryPredecrementExpression: pre-decrement expression --expr |
| UnaryPreincrementExpression | extract_unary_preincrement_expression | UnaryPreincrementExpression: pre-increment expression ++expr |
| UnaryPropertyExpr | extract_unary_property_expr_stmt | UnaryPropertyExpr: unary property expression |
| UnaryPropertyExpression | extract_unary_property_expression | UnaryPropertyExpression: unary property |
| UnarySelectPropertyExpr | extract_unary_select_property_expr | UnarySelectPropertyExpr: unary select property expression |
| UnaryTildeExpr | extract_unary_tilde_expr | UnaryTildeExpr: unary tilde expression ~ |
| UnaryXnorExpr | extract_unary_xnor_expr | UnaryXnorExpr: unary xnor expression ^~ |
| UnaryXnorExpression | extract_unary_xnor_expression | UnaryXnorExpression: unary xnor expression ^~ |
| UnaryXorExpr | extract_unary_xor_expr | UnaryXorExpr: unary xor expression ^ |
| UnaryXorExpression | extract_unary_xor_expression | UnaryXorExpression: unary xor expression ^ |
| UnbasedUnsizedLiteral | extract_unbased_unsized_literal | UnbasedUnsizedLiteralExpression: '0, '1, 'x, 'z |
| UnbasedUnsizedLiteralExpr | extract_unbased_unsized_literal_expr | UnbasedUnsizedLiteralExpr: unbased unsized literal expres... |
| UnbasedUnsizedLiteralExpression | extract_unbased_unsized_literal_expression_stmt | UnbasedUnsizedLiteralExpression: unbased unsized literal ... |
| UnboundedExpression | extract_unbounded_expression | UnboundedExpression: unbounded expression $ |
| UnboundedLiteral | extract_unbounded_literal | UnboundedLiteralExpression: $ |
| UniqueConstraint | extract_unique_constraint | UniqueConstraint: unique constraint |
| UniquenessConstraint | extract_uniqueness_constraint | UniquenessConstraint: uniqueness constraint |
| UniquenessConstraintExpr | extract_uniqueness_constraint_expr | UniquenessConstraintExpr: uniqueness constraint expression |
| UnknownDimension | extract_unknown_dimension | UnknownDimension: unknown dimension |
| UnknownTrivia | extract_unknown_trivia | UnknownTrivia: unknown trivia |
| UntilPropertyExpr | extract_until_property_expr | UntilPropertyExpr: until property expression |
| UntilWithPropertyExpr | extract_until_with_property_expr | UntilWithPropertyExpr: until_with property expression |
| UntypedType | extract_untyped_type | UntypedType: untyped type |
| UserDefinedNetDeclaration | extract_user_defined_net_declaration | UserDefinedNetDeclaration: user defined net declaration |
| ValueRangeExpression | extract_value_range | ValueRangeExpression: [a:b] or [a..b] |
| VariableDeclarationExpression | extract_variable_declaration_expression | VariableDeclarationExpression: variable declaration |
| VariableDeclarationStatement | extract_variable_declaration_statement | VariableDeclarationStatement: variable declaration statement |
| VariableDeclarationStatement | extract_variable_declaration_stmt | VariableDeclarationStatement: variable declaration |
| VariablePattern | extract_variable_pattern | VariablePattern: variable pattern |
| VariablePatternBinding | extract_variable_pattern_binding | VariablePatternBinding: variable pattern binding |
| VariablePatternExpr | extract_variable_pattern_expr | VariablePatternExpr: variable pattern expression |
| VirtualInterfaceType | extract_virtual_interface_type | VirtualInterfaceType: virtual interface type |
| VoidCastedCallStatement | extract_void_casted_call_statement | VoidCastedCallStatement: void casted call statement |
| VoidCastedVarianceExpression | extract_void_casted_variance | VoidCastedVarianceExpression: variance cast |
| VoidExpression | extract_void_expression | VoidExpression: void expression |
| VoidMethodCallSequence | extract_void_method_call_seq | VoidMethodCallSequence: void method call |
| VoidType | extract_void_type | VoidType: void type |
| WaitForkExpression | extract_wait_fork_expression | WaitForkExpression: wait fork expression |
| WaitForkStatement | extract_wait_fork_statement | WaitForkStatement: wait fork |
| WaitForkStatementExpression | extract_wait_fork_expression | WaitForkStatementExpression: wait fork |
| WaitOrderStatement | extract_wait_order_statement | WaitOrderStatement: wait order |
| WaitOrderStatement | extract_wait_order_statement_stmt | WaitOrderStatement: wait order statement |
| WaitStatement | extract_wait_statement | WaitStatement: wait statement |
| WaitStatement | extract_wait_statement_stmt | WaitStatement: wait statement |
| WaitStatementExpression | extract_wait_statement_expression | WaitStatementExpression: wait statement |
| WarningElabSystemTask | extract_warning_elab_system_task | WarningElabSystemTask: warning elaboration system task |
| WeakParenthesizedProperty | extract_weak_parenthesized_property | WeakParenthesizedProperty: property |
| WhileLoopStatement | extract_while_loop_statement | WhileLoopStatement: while loop statement |
| WhileLoopStatementExpression | extract_while_loop_expression | WhileLoopStatementExpression: while loop expression |
| WhitespaceTrivia | extract_whitespace_trivia | WhitespaceTrivia: whitespace trivia |
| WidthTimingCheck | extract_width_timing_check | WidthTimingCheck: width timing check |
| WildcardEqualityExpression | extract_wildcard_equality_expression | WildcardEqualityExpression: wildcard equality expression ==? |
| WildcardExpression | extract_wildcard_expression | WildcardExpression: wildcard expression |
| WildcardInequalityExpression | extract_wildcard_inequality_expression | WildcardInequalityExpression: wildcard inequality express... |
| WildcardLiteral | extract_wildcard_literal | WildcardLiteral: * |
| WildcardLiteralExpression | extract_wildcard_literal_expression | WildcardLiteralExpression: wildcard literal expression |
| WildcardPattern | extract_wildcard_pattern | WildcardPattern: wildcard pattern |
| WildcardPatternExpr | extract_wildcard_pattern_expr | WildcardPatternExpr: wildcard pattern expression |
| WildcardPatternExpression | extract_wildcard_pattern_expr | WildcardPatternExpression: wildcard pattern expression |
| WildcardPatternExpression | extract_wildcard_pattern_expr | WildcardPatternExpression: wildcard pattern expression |
| WildcardPatternKind | extract_wildcard_pattern_kind | WildcardPatternKind: wildcard pattern |
| WithClause | extract_with_clause | WithClause: with clause |
| WithExpression | extract_with_expression_stmt | WithExpression: with expression |
| WithFilterBinsSelectExpr | extract_with_filter_bins_select_expr | WithFilterBinsSelectExpr: with filter bins select expression |
| WithFunctionClause | extract_with_function_clause | WithFunctionClause: with function clause |
| WithFunctionSample | extract_with_function_sample | WithFunctionSample: with function sample |
| WithinFirstMatchSequenceExpr | extract_within_first_match_seq_expr | WithinFirstMatchSequenceExpr: within first_match sequence |
| WithinSequenceExpr | extract_within_sequence_expr | WithinSequenceExpr: within sequence expression |
| XorAssignmentExpression | extract_xor_assignment_expression | XorAssignmentExpression: xor assignment ^= |
| YieldStatementExpression | extract_yield_expression | YieldStatementExpression: yield expression |
