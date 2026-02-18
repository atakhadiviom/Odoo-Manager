"""
TUI (Terminal User Interface) command for Odoo Manager.
"""

import click

from odoo_manager.utils.output import info


@click.command(name="ui")
@click.pass_context
def tui_cli(ctx):
    """Launch the Terminal UI (panel-style interface).

    Example: odoo-manager ui
    """
    try:
        from odoo_manager.tui import launch_tui

        info("Launching Odoo Manager Terminal UI...")
        info("Press 'q' to quit, 'tab' to navigate between panels")
        launch_tui()

    except ImportError:
        from odoo_manager.utils.output import error

        error(
            "Textual is not installed. Install it with: pip install textual>=0.44.0"
        )
        ctx.exit(1)
    except Exception as e:
        from odoo_manager.utils.output import error

        error(f"Failed to launch TUI: {e}")
        ctx.exit(1)
