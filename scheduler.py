"""スケジュール実行モジュール"""

import time
import logging

import schedule

logger = logging.getLogger(__name__)


def run_scheduled(job_func, run_time: str = "09:00"):
    """指定時刻に毎日ジョブを実行する

    Args:
        job_func: 実行する関数
        run_time: 実行時刻 (HH:MM形式)
    """
    schedule.every().day.at(run_time).do(job_func)
    logger.info(f"スケジュール設定完了: 毎日 {run_time} に実行")
    print(f"スケジュール実行モード: 毎日 {run_time} に取得を実行します")
    print("停止するには Ctrl+C を押してください")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nスケジュール実行を停止しました")
