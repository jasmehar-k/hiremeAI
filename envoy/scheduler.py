"""APScheduler daily trigger for automated job application runs."""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from envoy import config
from envoy.graph import run_cycle


def run_job():
    """Run the job application cycle."""
    print("\n" + "=" * 50)
    print("Starting scheduled job application cycle")
    print("=" * 50 + "\n")

    try:
        results = run_cycle()
        print(f"\nScheduled cycle completed. Processed {len(results)} jobs.")
    except Exception as e:
        print(f"Error in scheduled cycle: {e}")


def setup_scheduler() -> BlockingScheduler:
    """Set up the APScheduler with daily trigger."""
    scheduler = BlockingScheduler()

    # Daily trigger at configured time
    trigger = CronTrigger(
        hour=config.SCHEDULER_RUN_HOUR,
        minute=config.SCHEDULER_RUN_MINUTE,
    )

    scheduler.add_job(
        run_job,
        trigger=trigger,
        id="daily_job_search",
        name="Daily job search and application",
        replace_existing=True,
    )

    return scheduler


def main():
    """CLI entry point to start the scheduler."""
    print("Starting envoy scheduler...")
    print(f"Daily run scheduled at {config.SCHEDULER_RUN_HOUR:02d}:{config.SCHEDULER_RUN_MINUTE:02d}")

    scheduler = setup_scheduler()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()