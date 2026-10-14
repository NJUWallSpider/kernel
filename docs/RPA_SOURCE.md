# 可读 RPA 源码（RPA-S 1）

RPA-S 是给人和 Agent 阅读、编写与审查的证明源码。它把命名别名、数学表达式、
注释与确定性数组展开编译成完整 `Certificate`，再编码为现有 RPX；内核验证规则、
独立 caller request，以及已经冻结的 MCM 1、RPX/RPA V1–V10 都不变。
原来的 JSON RPA 继续可用，语法见 [RPA.md](RPA.md)。

```text
RPA-S 源码 → 完整 Certificate → RPX → 内核验证
```

源码首行必须是精确的 `RPA-S 1\n`，随后是可选的 `models`、`let` 声明与一个
`certificate { ... }`。建议使用 `.rpas` 扩展名；assembler 依据文件内容的头部
识别语法，不依据扩展名。源码版本 1 与 RPX 能力版本是两件事：同样的源码头可以
表达 V1–V10 的证书，assembler 根据实际内容选择最低所需 RPX 版本。

## 先运行一个完整例子

两份模型均只有一个整数坐标，范围为 `[0,1]`，没有模型行，目标恒为零。
下面的完整源码证明一个方向的恒等映射、整数性、目标相等与坐标投影；它没有声明
反方向或双射。

```text
RPA-S 1
// 名称是明确编号的别名，不是从模型自动查找变量。
let coordinate = x0;
let floor = lower(coordinate);
let ceiling = upper(coordinate);
let whole = integer(coordinate);

certificate {
  claims: [
    {
      reverse: false,
      input_integers: true,
      output_integers: true,
      objective: Equal,
      projection: [[0, 0]],
      inverse: null,
    },
  ],
  blocks: [
    {
      steps: [],
      end: Return {
        map: [expr(coordinate)],
        checks: [
          floor,   // 输出坐标的下界
          ceiling, // 输出坐标的上界
          whole,   // 输出坐标的整数性
          exact,   // 目标差恒为零
          exact,   // 请求的坐标投影恒等式
        ],
      },
    },
  ],
}
```

独立 `request.json` 必须声明与源码相同的完整 contract。源码不能替调用者选择
较弱的要求；assembler 也不会补写没有提供的证明。

仓库提供三份可直接组装和验证的完整实例，每份 `.rpas` 都表达同目录原有
`proof.rpa` 的同一个证书：

| 例子 | 可读源码 | 数学内容 |
|---|---|---|
| 冗余行删除 | [redundant/proof.rpas](rpx/examples/redundant/proof.rpas) | 两个恒等映射；显式推出被删的上界行 |
| 等式消元 | [elimination/proof.rpas](rpx/examples/elimination/proof.rpas) | 保留 `x1`，用 `1 - x1` 恢复 `x0`；完整目标与逆映射证明 |
| 分段映射 | [piecewise/proof.rpas](rpx/examples/piecewise/proof.rpas) | 两个完整分支证明绝对值映射 |

从仓库根目录执行：

```sh
cargo build -p kernel-core --release --locked
mkdir -p /tmp/rpa-source-example
target/release/rpx canonical docs/rpx/examples/elimination/source.lp /tmp/rpa-source-example/source.mcm
target/release/rpx canonical docs/rpx/examples/elimination/target.lp /tmp/rpa-source-example/target.mcm
target/release/rpx assemble docs/rpx/examples/elimination/proof.rpas /tmp/rpa-source-example/proof.rpx
target/release/rpx verify /tmp/rpa-source-example/source.mcm /tmp/rpa-source-example/target.mcm /tmp/rpa-source-example/proof.rpx docs/rpx/examples/elimination/request.json
target/release/rpx disassemble-source /tmp/rpa-source-example/proof.rpx /tmp/rpa-source-example/recovered.rpas
```

三个实例的 `models { source: "source.lp", target: "target.lp" }` 声明让 CLI 读取
同目录的实际模型，按名称核对证明义务。相对模型路径以源码文件所在目录为基准，
与命令执行目录无关。模型可以是 LP、MPS 或 MCM。文件路径用于加载模型，不授予数学事实。

`assemble` 支持两种文本入口。`disassemble-source` 输出确定性的 RPA-S；原有
`disassemble proof.rpx proof.rpa` 继续输出 JSON RPA。反汇编不会恢复作者的别名、
注释或排版。表达式与证据引用使用明确的 `xN`、`fN` 编号；提供实际模型时，检查项
使用实际变量、行的名称。没有提供模型时保留位置数组。

```sh
target/release/rpx disassemble-source --models /tmp/rpa-source-example/source.mcm /tmp/rpa-source-example/target.mcm /tmp/rpa-source-example/proof.rpx /tmp/rpa-source-example/named.rpas
```

这条命令输出命名检查，并写入模型文件的绝对路径声明；输出文件可以直接交给
`assemble`。没有 `models` 声明的命名源码也可用
`assemble --models source.mcm target.mcm proof.rpas proof.rpx`；显式参数优先于文件声明。

## 记录、枚举与注释

普通记录使用未加引号的字段名：`{ steps: [], end: ... }`。标签记录写为
`Return { map: ..., checks: ... }`、`Split { ... }` 或 `IntervalLift { ... }`。
有单个值的标签写为 `Witness(f0)`、`Absurd(f0)`、`Constant(q(1/3))`；
普通 block 的反证终点仍是 `Absurd { fact: f0 }`，两种上下文的结构不同。
无载荷枚举使用 `Equal`、`NonIncreasing`、`None`、`Le`、`Eq`、`Int`。

字段与标签沿用 [完整证书 schema](FORMAT.md#rpa-text-and-independent-request-schema)，
包括 points、bijections、improvements 与所有 lift。没有另外一套数学语义。
已有可选字段采用同样的默认值：可选数组为空，可选值为 `null`；必需字段仍须
提供。重复字段、未知字段与未知枚举拒绝。

允许 `//` 行注释、`/* ... */` 块注释、通常的空白，以及数组和记录末尾的逗号。
头部本身不接受 BOM、CRLF、额外空格或注释。名称与标签区分大小写。

## 精确数学表达式

`q(1/3)` 表示精确有理数，用于 capacity、point values、objective level 等 scalar
字段。整数编号写成普通整数；不能把数学 scalar 字段的 `q(...)` 与编号混淆。
数值沿用 `model::parse_q` 的精确规范化，零分母拒绝，反汇编输出规范整数或分数。
文本数值的 numerator/denominator 各有 4096 位十进制数字上限，十进制指数也有
4096 的绝对值上限；中间有理数的 numerator/denominator 各有 65,536 bit 上限。
算术展开后的最终 scalar 仍通过现有 `parse_q`，不能用分块算术绕过文本数字预算。
程序直接构造的 `Certificate` 如果含有超出文本数字预算的 scalar，源码反汇编会
返回 `RESOURCE_LIMIT`。RPX 的独立有理数 magnitude 预算仍按冻结 codec 执行。

`expr(1 - 2*x0 + x3/7)` 表示仿射表达式。支持常数、坐标、加减、正负号、括号、
乘以 scalar 与除以非零 scalar；坐标之间的乘法和除以含坐标的表达式拒绝。
编译会合并同坐标项、去掉零系数并按编号排序，因此 `expr(x2 - x2 + x0)`
得到与 `expr(x0)` 相同的规范表达式。计算始终精确，不使用浮点近似。

名称用顶层 `let name = value;` 显式绑定。可以给坐标、引用、表达式或记录取名，
后续声明和证书使用该值。重复名称、未定义名称拒绝。别名不会自动分配变量或
fact ID，也不会从 MPS/LP 变量名、行名或 `coordinate_index.json` 推断编号。
不同方向中的同一个 `x0` 仍按该方向的当前输入 scope 解释。
名称由 ASCII 字母、数字与下划线组成，不能以数字开头；内建构造、枚举与
`xN`/`fN` 形式的名称是保留名称，不能重新定义。

## 引用与证明步骤

| 源码引用 | 证书含义 |
|---|---|
| `lower(x3)` / `upper(x3)` | 当前输入变量 3 的下界 / 上界事实 |
| `integer(x3)` | 当前输入变量 3 的整数性事实 |
| `row_lower(2)` / `row_upper(2)` / `row_eq(2)` | 当前输入模型行 2 的相应事实 |
| `f7` 或 `local(7)` | 当前分支中的局部 fact 7 |
| `assumption(0)` | 当前路径的第一个假设 |
| `exact` | 精确恒真表达式检查 |

可读步骤将数学计算放在同一处：

```text
lin.eq(f0, -row_eq(0))
lin.le(f1, 2*upper(x0) - 1/3)
lin.int(f2, integer(x0) + 1)
round(f3, f1, f2)
drop(f0, f1)
```

`lin.eq`、`lin.le`、`lin.int` 的第一个参数是显式 fact ID，其余部分是
“常数 + 各引用的有理数倍”。例如 `lin.le(f0, row_upper(0) - 1)` 完整编码为
常数 `-1`、引用 `RowUpper(0)` 的系数 `1`。这三个缩写分别产生 `Lin` 的
`Eq`、`Le`、`Int` kind；它们没有自动选择可用证明的逻辑。
`round` 与 `drop` 分别产生 `Round` 与 `Drop`。

其他步骤可以直接用标签记录，例如下面与等式消元示例里的第一步等价：

```text
Lin { id: 0, kind: Eq, constant: q(0), terms: [[row_eq(0), q(-1)]] }
```

引用的可用性、线性组合系数的规则、Round 的条件、DROP 后的失效以及分支作用域
都由原内核检查。给 `f7` 取一个名称不意味着它已经被证明；必须先在当前路径中
定义它。完整引用语义见 [SEMANTICS.md](SEMANTICS.md) 与
[FORMAT.md](FORMAT.md#facts-references-and-scopes)。

## 确定性数组展开

下面四个构造生成数组；放在数组内时展开成连续元素，不执行循环体、模型查询或证明搜索。
参数的 start/count 均为明确的非负整数。

| 构造 | 展开结果 |
|---|---|
| `[repeat(3, exact)]` | `[exact, exact, exact]` |
| `[identity(2, 3)]` | `[expr(x2), expr(x3), expr(x4)]` |
| `[range(2, 3)]` | `[2, 3, 4]` |
| `[pairs(2, 5, 3)]` | `[[2, 5], [3, 6], [4, 7]]` |

可以与普通元素混用，例如 `map: [expr(1 - x0), identity(1, 3)]` 完整产生四个
输出坐标。`checks: [repeat(4, exact)]` 提供四条显式证据，是否恰好匹配真实的
四项义务仍须由内核判断。构造没有提供省略证明的语义；每一项都实际展开进
`Certificate`。也可以直接作为整个数组字段的值，例如 `map: identity(0, 4)`。
数组别名表示一个普通数组值：`let mapping = identity(0, 4);` 后使用
`map: mapping`；写成 `map: [mapping]` 会产生嵌套数组，不会隐式展开别名。

## 写出每项义务，再验证

推荐用命名检查直接写出每条证据的用途。例如消元实例的正向 Return：

```text
checks {
  variable["y"].lower: lower(x1),
  variable["y"].upper: upper(x1),
  objective.equal: f0,
  projection[0]: exact,
  inverse.coordinate["x0"]: f0,
  inverse.coordinate["x1"]: exact,
}
```

左边是**待证明的义务**，右边是**使用的输入事实或局部证据**。
`variable["y"].lower` 指实际输出变量 y 的下界；`lower(x1)` 指当前输入坐标 1
已有的下界事实。两者角色不同。`inverse.coordinate["x0"]` 指恢复当前输入模型的
变量 x0，不是重新分配一个证据寄存器。

条目可以任意排序。编译器根据完整模型与 claim 生成义务清单，核对每个名称，
然后排成内核需要的数组。缺失、重复、越界、错误名称或不适用的义务都会拒绝；
例如 LP 输出没有整数性义务时，不能额外写 `variable[0].integer`。
同一义务同时写编号和名称也算重复。只有名称正确仍不足以证明它，证据的数学内容
继续由原内核验证。

| 命名义务 | 含义 |
|---|---|
| `variable[0].lower` / `.upper` / `.integer` | 实际输出变量的有限边界与请求的整数性；可用 `variable["y"]` 指定实际名字 |
| `row[0].equal` / `.lower` / `.upper` | 实际输出模型行；等式只接受 `.equal`，可用 `row["balance"]` |
| `objective.equal` / `objective.non_increasing` | 当前 claim 请求的目标关系 |
| `projection[0]` / `affine_projection[0]` | 当前 claim 的第 0 个坐标/仿射观察，索引对应请求条目 |
| `inverse.coordinate[0]` | 逆映射恢复当前输入坐标 0，也可以指定输入变量名 |
| `inverse.objective_level` | 映射结果属于对向 claim 请求的目标水平域 |
| `input.objective_lower` | 当前 claim 请求的输入目标下界 |
| `bijection[0].coordinate[0]` | 第 0 个双射契约要求的组合恒等式；只出现在对应反向 claim 中 |
| `injectivity.coordinate[0]` | `bijections[].injectivity.checks` 中的单射性等式 |
| `objective.improve` | `ImproveReturn` 中含显式 margin 的目标改进义务 |

命名形式适用于方向证明里的 Return（包括分支和 lift 内的 Return）、改进证明的
ImproveReturn，以及双射的 injectivity 检查。lift 自身的前提检查仍按其现有结构提供。
Rust 的纯文本接口不会读取 `models` 文件声明：命名源码必须通过
`assemble_with_models` 提供两个实际 `Model`；没有模型的 `assemble` 明确拒绝命名检查。

`Return.map` 必须完整覆盖实际输出模型的每个坐标。兼容的 `checks: [...]` 按内核生成
的完整义务顺序排列：变量的有限下界、有限上界与所需整数性；模型行；请求的目标
关系；坐标与仿射观察；逆映射；其他已声明的 contract 条件。准确规则见
[Return obligation order](FORMAT.md#return-obligation-order)。

命名形式让义务成为编译器会核对的源码。注释仍只供读者使用，不会改写 obligation。
每个分支都有自己的完整 Return 或反证；
不能把不同分支、不同 existential tuple 的事实拼成一个缺失检查的结果。

assembler 成功表示源码可以编码，不表示证明成立。源/目标模型与独立 request
仍必须传给 `verify`；只有 `VERIFIED` 建立所请求的关系。`INVALID`、
`RESOURCE_LIMIT` 和 `IO_ERROR` 都不是该数学关系不成立的结论。

## API 与资源边界

Rust 文本接口是 `kernel_core::rpa_source::assemble(&str)` 与
`disassemble(&Certificate)`；命名形式使用 `assemble_with_models(text, source, target)`
与 `disassemble_with_models(certificate, source, target)`。`parse` 返回 `ParsedSource`，
供路径接口查看模型声明后加载模型，避免重复解析源码。
路径接口使用 `api::assemble_paths`、`disassemble_source_paths` 及对应的
`*_with_models` 入口，见 [API.md](API.md)。
源码 parser 的输入与展开后 JSON 均有 256 MiB 上限，源码及展开结构的嵌套上限是 128 层，
展开节点预算为 16,000,000（包括别名复制与重复结构），超限返回
`RESOURCE_LIMIT`。展开后的证书仍受现有编码与内核预算约束；紧凑源码
不会绕过完整验证的工作量限制。
