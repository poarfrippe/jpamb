#Bytecode instructions
| Mnemonic | Opcode Name |  Exists in |  Count |
| :---- | :---- | :----- | -----: |
| [iload_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iload_n) | [Load](utils/jvm/opcode.py?plain=1#L735) |  Arrays Dependent Fuzzer Loops Simple Tricky | 312 |
| [iconst_i](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iconst_i) | [Push](utils/jvm/opcode.py?plain=1#L102) |  Arrays Dependent Loops Simple Tricky | 229 |
| [if_cond](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.if_cond) | [Ifz](utils/jvm/opcode.py?plain=1#L903) |  Arrays Dependent Fuzzer Loops Simple Strings Tricky | 157 |
| [ldc](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ldc) | [Push](utils/jvm/opcode.py?plain=1#L102) |  Arrays Fuzzer Strings | 152 |
| [dup](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.dup) | [Dup](utils/jvm/opcode.py?plain=1#L258) |  Arrays Fuzzer Loops Simple Strings Tricky | 140 |
| [if_icmp_cond](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.if_icmp_cond) | [If](utils/jvm/opcode.py?plain=1#L774) |  Arrays Fuzzer Tricky | 138 |
| [return](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.return) | [Return](utils/jvm/opcode.py?plain=1#L1125) |  Arrays Calls Fuzzer Loops Strings Tricky | 134 |
| [getstatic](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.getstatic) | [Get](utils/jvm/opcode.py?plain=1#L841) |  Arrays Fuzzer Loops Simple Strings Tricky | 90 |
| [new](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.new) | [New](utils/jvm/opcode.py?plain=1#L973) |  Arrays Fuzzer Loops Simple Strings Tricky | 90 |
| [invokespecial](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.invokespecial) | [InvokeSpecial](utils/jvm/opcode.py?plain=1#L535) |  Arrays Fuzzer Loops Simple Strings Tricky | 90 |
| [athrow](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.athrow) | [Throw](utils/jvm/opcode.py?plain=1#L1015) |  Arrays Fuzzer Loops Simple Strings Tricky | 90 |
| [istore_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.istore_n) | [Store](utils/jvm/opcode.py?plain=1#L585) |  Arrays Fuzzer Loops Tricky | 78 |
| [aload_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.aload_n) | [Load](utils/jvm/opcode.py?plain=1#L735) |  Arrays Strings | 74 |
| [iastore](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iastore) | [ArrayStore](utils/jvm/opcode.py?plain=1#L293) |  Arrays | 59 |
| [ireturn](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ireturn) | [Return](utils/jvm/opcode.py?plain=1#L1125) |  Dependent Simple | 47 |
| [idiv](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.idiv) | [Binary](utils/jvm/opcode.py?plain=1#L698) |  Arrays Dependent Simple Tricky | 45 |
| [goto](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.goto) | [Goto](utils/jvm/opcode.py?plain=1#L1085) |  Arrays Loops Tricky | 34 |
| [iadd](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iadd) | [Binary](utils/jvm/opcode.py?plain=1#L698) |  Arrays Fuzzer Loops Tricky | 32 |
| [astore_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.astore_n) | [Store](utils/jvm/opcode.py?plain=1#L585) |  Arrays | 27 |
| [arraylength](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.arraylength) | [ArrayLength](utils/jvm/opcode.py?plain=1#L393) |  Arrays | 21 |
| [caload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.caload) | [ArrayLoad](utils/jvm/opcode.py?plain=1#L359) |  | 20 |
| [iaload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iaload) | [ArrayLoad](utils/jvm/opcode.py?plain=1#L359) |  Arrays | 17 |
| [isub](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.isub) | [Binary](utils/jvm/opcode.py?plain=1#L698) |  Arrays | 17 |
| [newarray](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.newarray) | [NewArray](utils/jvm/opcode.py?plain=1#L224) |  Arrays | 16 |
| [iload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iload) | [Load](utils/jvm/opcode.py?plain=1#L735) |  Arrays | 16 |
| [invokestatic](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.invokestatic) | [InvokeStatic](utils/jvm/opcode.py?plain=1#L462) |  Calls | 16 |
| [imul](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.imul) | [Binary](utils/jvm/opcode.py?plain=1#L698) |  Fuzzer Tricky | 15 |
| [iinc](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iinc) | [Incr](utils/jvm/opcode.py?plain=1#L1052) |  | 14 |
| [ineg](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ineg) | [Negate](utils/jvm/opcode.py?plain=1#L194) |  | 10 |
| [aconst_null](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.aconst_null) | [Push](utils/jvm/opcode.py?plain=1#L102) |  | 7 |
| [istore](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.istore) | [Store](utils/jvm/opcode.py?plain=1#L585) |  Arrays | 7 |
| [invokevirtual](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.invokevirtual) | [InvokeVirtual](utils/jvm/opcode.py?plain=1#L427) |  Strings | 7 |
| [irem](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.irem) | [Binary](utils/jvm/opcode.py?plain=1#L698) |  Tricky | 3 |
| [i2s](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.i2s) | [Cast](utils/jvm/opcode.py?plain=1#L325) |  Loops | 2 |
