"""
TUI (Terminal User Interface) command for Odoo Manager.
"""

import click
import traceback

from odoo_manager.utils.output import info, error


@click.command(name="ui")
@click.pass_context
def tui_cli(ctx):
    """Launch the Terminal UI (panel-style interface).

    Example: odoo-manager ui
    """
    try:
        # First verify textual is available
        try:
            import textual
        except ImportError:
            error("Textual is not installed. Install it with: pip install textual")
            ctx.exit(1)

        from odoo_manager.tui.app import OdooManagerTUI

        app = OdooManagerTUI()
        app.run()

    except Exception as e:
        error(f"Failed to launch TUI: {e}")
        if "--verbose" in ctx.args or "-v" in ctx.args:
            error(traceback.format_exc())
        ctx.exit(1)
