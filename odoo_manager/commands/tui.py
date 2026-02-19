"""
TUI (Terminal User Interface) command for Odoo Manager.
"""

import click

from odoo_manager.utils.output import error


@click.command(name="ui")
@click.pass_context
def tui_cli(ctx):
    """Launch the Terminal UI (simple numbered menu).

    Example: odoo-manager ui
    """
    try:
        from odoo_manager.tui.app import launch_tui
        launch_tui()
    except Exception as e:
        error(f"Failed to launch TUI: {e}")
        ctx.exit(1)
