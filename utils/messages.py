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
        "Ready when you are!",
        "Done!",
        "Nailed it!",
        "Crushed it!",
        "Finished!",
        "Complete!",
        "All clear!",
        "Job's done!",
        "That'll do it!",
        "Sorted!",
        "Handled!",
        "Locked in!",
        "Mission complete!",
        "Task done!",
        "Boom! Done!",
        "Check!",
        "Got it done!",
        "Wrapped!",
        "Delivered!",
        "Signed, sealed, delivered!",
        # Portal/GLaDOS
        "You will be baked, and then there will be cake.",
        "Well done. The Enrichment Center reminds you that the task is complete.",
        "The task is finished. Any contact with the chamber floor will result in an unsatisfactory mark on your official testing record, followed by death.",
        # Metal Gear
        "Mission complete! Awaiting orders.",
        # Classic Gaming
        "All your tasks are belong to us!",
        # Hitchhiker's Guide
        "Completed. The answer is 42.",
        # Movie Classics
        "Groovy, baby!",
        "As you wish.",
        "Hello. My name is Inigo Montoya. You killed my father. Prepare to die.",
        "What is this? A task for ants?",
        "I'm kind of a big deal.",
        "Hasta la vista, baby!",
        # Taulia
        "We get shit done!"
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
