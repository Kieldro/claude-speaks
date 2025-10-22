"""
Shared message definitions for Claude Code hooks.
This module provides centralized message lists to avoid duplication.
"""

import os


def get_notification_messages(include_personalized=True):
    """
    Get notification messages used when agent needs user input.

    Args:
        include_personalized: If True, includes personalized variant with engineer name

    Returns:
        list: Notification message strings
    """
    messages = ["Your agent needs your input"]

    if include_personalized:
        # Get engineer name if available, fallback to USER
        engineer_name = os.getenv('ENGINEER_NAME', '').strip()
        if not engineer_name:
            engineer_name = os.getenv('USER', '').strip()
        if engineer_name:
            messages.append(f"{engineer_name}, your agent needs your input")

    return messages


def get_completion_messages():
    """
    Get completion messages used when agent finishes a task.

    Returns:
        list: Completion message strings
    """
    return [
        "Work complete!",
        "All done!",
        "Task finished!",
        "Job complete!",
        "Ready for next task!",
        "Mission accomplished!",
        "Task complete!",
        "Finished successfully!",
        "All set!",
        "Done and dusted!",
        "Wrapped up!",
        "Job well done!",
        "That's a wrap!",
        "Successfully completed!",
        "All finished!",
        "Task accomplished!",
        "Good to go!",
        "Completed successfully!",
        "Everything's done!",
        "Ready when you are!"
    ]


def get_all_messages():
    """
    Get all static messages used in Claude hooks.
    Combines notification and completion messages.

    Returns:
        list: All message strings
    """
    messages = []
    messages.extend(get_notification_messages(include_personalized=True))
    messages.extend(get_completion_messages())
    return messages
