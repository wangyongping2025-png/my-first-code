#!/usr/bin/env python3
"""简单记账小脚本

推荐用法（交互模式）：
    python3 jizhang.py        进入记账模式，然后直接输入“金额 备注”记账，
                              例如输入: 30 晚饭
                              输入 list 看全部，today 看今天，total 看总计，q 退出

也支持单条命令：
    python3 jizhang.py add 金额 [备注]   记一笔账
    python3 jizhang.py list             查看所有账目
    python3 jizhang.py today            查看今天花了多少钱
    python3 jizhang.py total            查看总共花了多少钱

账目保存在脚本同目录下的 jizhang.json 文件里。
"""

import json
import sys
from datetime import date
from pathlib import Path

# 账本文件和脚本放在同一个目录下
DATA_FILE = Path(__file__).parent / "jizhang.json"


def load_records():
    """读取账本，文件不存在时返回空列表"""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def save_records(records):
    """把账目写回账本文件"""
    DATA_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add(amount, note):
    records = load_records()
    records.append({
        "date": date.today().isoformat(),
        "amount": amount,
        "note": note,
    })
    save_records(records)
    print(f"已记账：{date.today()} 花了 {amount:.2f} 元（{note or '无备注'}）")


def show_list():
    records = load_records()
    if not records:
        print("账本还是空的，先用 add 记一笔吧！")
        return
    print(f"{'日期':<12}{'金额(元)':>10}  备注")
    print("-" * 32)
    for r in records:
        print(f"{r['date']:<12}{r['amount']:>10.2f}  {r['note'] or ''}")
    print("-" * 32)
    print(f"共 {len(records)} 笔，合计 {sum(r['amount'] for r in records):.2f} 元")


def show_today():
    today = date.today().isoformat()
    todays = [r for r in load_records() if r["date"] == today]
    total = sum(r["amount"] for r in todays)
    print(f"今天（{today}）共花了 {total:.2f} 元，共 {len(todays)} 笔")
    for r in todays:
        print(f"  - {r['amount']:.2f} 元  {r['note'] or ''}")


def show_total():
    records = load_records()
    print(f"总共花了 {sum(r['amount'] for r in records):.2f} 元，共 {len(records)} 笔")


def interactive():
    """交互记账模式：进来之后一行记一笔，不用每次敲 python3 jizhang.py"""
    print("=" * 40)
    print("  欢迎使用记账小助手！")
    print("  直接输入“金额 备注”记一笔，例如: 30 晚饭")
    print("  list(全部)  today(今天)  total(总计)  q(退出)")
    print("=" * 40)
    while True:
        try:
            line = input("\n记账> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        if line in ("q", "quit", "exit", "退出"):
            print("再见，明天也记得来记账哦！")
            break
        if line in ("list", "全部"):
            show_list()
        elif line in ("today", "今天"):
            show_today()
        elif line in ("total", "总计"):
            show_total()
        elif line in ("help", "帮助", "?"):
            print("输入“金额 备注”记账，如: 30 晚饭")
            print("list 看全部 / today 看今天 / total 看总计 / q 退出")
        else:
            parts = line.split(maxsplit=1)
            try:
                amount = float(parts[0])
            except ValueError:
                print(f"没看懂：{line}")
                print("记账请输入“金额 备注”，例如: 30 晚饭（输入 help 看说明）")
                continue
            note = parts[1] if len(parts) > 1 else ""
            add(amount, note)


def main():
    if len(sys.argv) < 2:
        interactive()
        return

    command = sys.argv[1]
    if command == "add":
        if len(sys.argv) < 3:
            print("请输入金额，例如: python3 jizhang.py add 25.5 午饭")
            return
        try:
            amount = float(sys.argv[2])
        except ValueError:
            print(f"金额格式不对：{sys.argv[2]}，请输入数字")
            return
        note = " ".join(sys.argv[3:])
        add(amount, note)
    elif command == "list":
        show_list()
    elif command == "today":
        show_today()
    elif command == "total":
        show_total()
    else:
        print(f"不认识的命令：{command}")
        print(__doc__)


if __name__ == "__main__":
    main()
