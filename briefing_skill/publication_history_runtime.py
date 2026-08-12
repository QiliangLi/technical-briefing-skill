from __future__ import annotations


def install_publication_history_runtime() -> None:
    """Repair/project legacy SENT history whenever a normal CLI context is opened.

    This keeps existing local databases safe on the first run after upgrade without
    making every briefing run depend on a network mailbox call. Agently mailbox sync
    remains an explicit `publication-sync` recovery command for historical/manual sends.
    """

    from . import cli
    from .publication_history import reconcile_local_history

    if getattr(cli, "_publication_history_runtime_installed", False):
        return

    original_context = cli._context

    def context(args):
        root, paths, config, db = original_context(args)
        reconcile_local_history(root, db)
        return root, paths, config, db

    cli._context = context
    cli._publication_history_runtime_installed = True
