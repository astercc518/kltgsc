"""CLI: 从客户主号历史抽取案例并打印候选 JSON。

用法:
  cd backend && python scripts/extract_case_studies_from_history.py --customer-id 1

输出 JSON 数组到 stdout, admin 可手动 review 后用 curl 批量 POST。
"""
import argparse
import asyncio
import json
import sys

from sqlmodel import Session
from app.core.database import engine
from app.services.case_study_extractor import extract_cases_for_customer


async def main():
    parser = argparse.ArgumentParser(
        description="从客户主号聊天历史 LLM 抽取成交案例候选"
    )
    parser.add_argument("--customer-id", type=int, required=True,
                        help="目标客户 ID")
    parser.add_argument("--max-history", type=int, default=100,
                        help="最多拉取最近 N 条聊天历史 (default: 100)")
    args = parser.parse_args()

    with Session(engine) as session:
        cases = await extract_cases_for_customer(
            session=session,
            customer_id=args.customer_id,
            max_history=args.max_history,
        )

    print(json.dumps(cases, ensure_ascii=False, indent=2))
    if not cases:
        print("(no cases extracted)", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
