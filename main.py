#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests>=2.31.0",
#     "python-dotenv>=1.0.0",
#     "python-dateutil>=2.8.2",
#     "click>=8.1.0",
#     "rich>=13.0.0",
# ]
# ///
"""YNAB-PayPal Transaction Matcher.

Matches PayPal transactions with YNAB bank transactions to identify original merchants.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from src.config import Config
from src.ynab_client import YNABClient
from src.paypal_csv import PayPalCSVParser
from src.paypal_api import PayPalAPIClient
from src.matcher import TransactionMatcher

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--days",
    default=90,
    type=int,
    help="Number of days to look back for transactions",
    show_default=True,
)
@click.option(
    "--use-api",
    is_flag=True,
    help="Use PayPal API instead of CSV (requires Business account)",
)
@click.option(
    "--csv",
    type=click.Path(exists=True),
    help="Path to PayPal CSV file (overrides .env setting)",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Save output to file instead of printing to console",
)
@click.option(
    "--update",
    is_flag=True,
    help="Update YNAB transaction memos with matched merchant names",
)
@click.option(
    "--confidence",
    type=click.Choice(["high", "medium", "low"], case_sensitive=False),
    default="high",
    help="Minimum confidence level for updates",
    show_default=True,
)
@click.option(
    "--env",
    type=click.Path(exists=True),
    default=".env",
    help="Path to .env file",
    show_default=True,
)
def cli(ctx, days, use_api, csv, output, update, confidence, env):
    """Match YNAB PayPal transactions with PayPal merchant details.

    This tool intelligently matches PayPal transactions from your bank
    (imported into YNAB) with the actual PayPal transaction details to
    identify the original merchant/retailer.

    Examples:

        # Match transactions from last 30 days
        uv run main.py --days 30

        # Use PayPal API (Business accounts)
        uv run main.py --use-api --days 30

        # Save output to file
        uv run main.py --days 30 --output matches.txt

        # Update YNAB with high confidence matches
        uv run main.py --days 30 --update --confidence high
    """
    if ctx.invoked_subcommand is None:
        run_matcher(days, use_api, csv, output, update, confidence, env)


@cli.command()
@click.option(
    "--env",
    type=click.Path(exists=True),
    default=".env",
    help="Path to .env file",
    show_default=True,
)
def test(env):
    """Test API connections."""
    console.print("\n[bold cyan]Testing API Connections[/bold cyan]\n")

    config = Config(env)

    # Test YNAB
    if not config.validate_ynab():
        console.print("[red]✗ YNAB configuration invalid[/red]")
        console.print("Please set up your YNAB credentials in .env file")
        sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Testing YNAB API...", total=None)
        ynab_client = YNABClient(config.ynab_token, config.ynab_budget_id)

        if ynab_client.test_connection():
            progress.stop()
            console.print("[green]✓ YNAB API connection successful[/green]")
        else:
            progress.stop()
            console.print("[red]✗ YNAB API connection failed[/red]")
            sys.exit(1)

    # Test PayPal API if configured
    if config.validate_paypal_api():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Testing PayPal API...", total=None)
            paypal_client = PayPalAPIClient(
                config.paypal_client_id, config.paypal_client_secret, config.paypal_mode
            )

            if paypal_client.test_connection():
                progress.stop()
                console.print("[green]✓ PayPal API connection successful[/green]")
            else:
                progress.stop()
                console.print("[red]✗ PayPal API connection failed[/red]")
                sys.exit(1)
    else:
        console.print("[yellow]PayPal API not configured (will use CSV mode)[/yellow]")

    console.print("\n[bold green]✓ All configured connections successful![/bold green]\n")


def run_matcher(days, use_api, csv, output, update, confidence, env):
    """Run the transaction matching process."""
    # Load configuration
    config = Config(env)

    # Validate YNAB configuration
    if not config.validate_ynab():
        console.print("[red]Error: YNAB configuration invalid[/red]")
        console.print("Please set up your YNAB credentials in .env file")
        console.print("See .env.example for reference")
        sys.exit(1)

    # Initialize YNAB client
    ynab_client = YNABClient(config.ynab_token, config.ynab_budget_id)

    # Determine date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    console.print(
        f"\n[cyan]Fetching transactions from {start_date.strftime('%Y-%m-%d')} "
        f"to {end_date.strftime('%Y-%m-%d')}[/cyan]\n"
    )

    # Fetch YNAB transactions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching YNAB transactions...", total=None)

        try:
            ynab_paypal_transactions = ynab_client.find_paypal_transactions(
                paypal_keywords=config.paypal_keywords, since_date=start_date
            )
            progress.stop()
            console.print(
                f"[green]✓ Found {len(ynab_paypal_transactions)} PayPal transactions in YNAB[/green]"
            )
        except Exception as e:
            progress.stop()
            console.print(f"[red]Error fetching YNAB transactions: {e}[/red]")
            sys.exit(1)

    if not ynab_paypal_transactions:
        console.print(
            "\n[yellow]No PayPal transactions found in YNAB for the specified date range.[/yellow]"
        )
        console.print(f"Keywords used: {', '.join(config.paypal_keywords)}")
        sys.exit(0)

    # Fetch PayPal transactions
    paypal_transactions = []

    if use_api:
        if not config.validate_paypal_api():
            console.print("[red]Error: PayPal API credentials not configured[/red]")
            console.print("Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")
            sys.exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching PayPal transactions via API...", total=None)

            try:
                paypal_client = PayPalAPIClient(
                    config.paypal_client_id,
                    config.paypal_client_secret,
                    config.paypal_mode,
                )
                paypal_transactions = paypal_client.get_transactions_for_range(
                    start_date, end_date
                )
                progress.stop()
                console.print(
                    f"[green]✓ Found {len(paypal_transactions)} PayPal transactions[/green]"
                )
            except Exception as e:
                progress.stop()
                console.print(f"[red]Error fetching PayPal transactions: {e}[/red]")
                sys.exit(1)
    else:
        # Use CSV
        csv_path = csv or config.paypal_csv_path

        if not Path(csv_path).exists():
            console.print(f"[red]Error: PayPal CSV file not found: {csv_path}[/red]")
            console.print("\n[yellow]To export PayPal transactions:[/yellow]")
            console.print("1. Log into PayPal")
            console.print("2. Go to Activity > Download")
            console.print("3. Select date range and CSV format")
            console.print(f"4. Save as: {csv_path}")
            sys.exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Parsing PayPal CSV: {csv_path}...", total=None)

            try:
                parser = PayPalCSVParser(csv_path, config.paypal_date_format)
                all_paypal = parser.parse_transactions()

                # Filter by date range
                paypal_transactions = parser.filter_by_date_range(
                    all_paypal, start_date, end_date
                )
                progress.stop()
                console.print(
                    f"[green]✓ Found {len(paypal_transactions)} PayPal transactions in CSV[/green]"
                )
            except Exception as e:
                progress.stop()
                console.print(f"[red]Error parsing PayPal CSV: {e}[/red]")
                sys.exit(1)

    if not paypal_transactions:
        console.print(
            "\n[yellow]No PayPal transactions found for the specified date range.[/yellow]"
        )
        sys.exit(0)

    # Match transactions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Matching transactions...", total=None)

        matcher = TransactionMatcher(
            date_tolerance_days=config.date_tolerance_days,
            amount_tolerance_percent=config.amount_tolerance_percent,
        )

        matches = matcher.match_transactions(
            ynab_paypal_transactions, paypal_transactions
        )
        progress.stop()

    # Display results with rich formatting
    display_matches(matches, output)

    # Apply updates if requested
    if update:
        apply_updates(ynab_client, matcher, matches, confidence)


def display_matches(matches, output_file=None):
    """Display transaction matches using rich formatting."""
    # Statistics
    total = len(matches)
    matched = sum(1 for m in matches if m["paypal"] is not None)

    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style="cyan")
    stats_table.add_column(style="bold")

    stats_table.add_row("Total YNAB PayPal transactions:", str(total))
    stats_table.add_row("Matched:", f"{matched} ({matched/total*100:.1f}%)")
    stats_table.add_row("Unmatched:", str(total - matched))

    console.print()
    console.print(
        Panel(stats_table, title="[bold cyan]Match Statistics[/bold cyan]", border_style="cyan")
    )
    console.print()

    # Categorize matches
    high_conf = [m for m in matches if m["confidence"] == "high"]
    med_conf = [m for m in matches if m["confidence"] == "medium"]
    low_conf = [m for m in matches if m["confidence"] in ["low", "very_low"]]
    unmatched = [m for m in matches if m["paypal"] is None]

    # Display each category
    if high_conf:
        console.print(f"[bold green]HIGH CONFIDENCE MATCHES ({len(high_conf)})[/bold green]")
        display_match_table(high_conf)
        console.print()

    if med_conf:
        console.print(f"[bold yellow]MEDIUM CONFIDENCE MATCHES ({len(med_conf)})[/bold yellow]")
        display_match_table(med_conf)
        console.print()

    if low_conf:
        console.print(f"[bold red]LOW CONFIDENCE MATCHES ({len(low_conf)})[/bold red]")
        display_match_table(low_conf)
        console.print()

    if unmatched:
        console.print(f"[bold dim]UNMATCHED TRANSACTIONS ({len(unmatched)})[/bold dim]")
        display_unmatched_table(unmatched)
        console.print()

    # Save to file if requested
    if output_file:
        # Fall back to plain text for file output
        from src.matcher import TransactionMatcher

        output_text = TransactionMatcher.format_match_output(matches, show_unmatched=True)
        Path(output_file).write_text(output_text)
        console.print(f"[green]✓ Results saved to: {output_file}[/green]")


def display_match_table(matches):
    """Display a table of matched transactions."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("YNAB Date", style="cyan")
    table.add_column("Amount", justify="right", style="cyan")
    table.add_column("PayPal Date", style="green")
    table.add_column("Merchant", style="green")
    table.add_column("Score", justify="right", style="yellow")
    table.add_column("Days", justify="right", style="dim")

    for match in matches[:20]:  # Limit to first 20 for readability
        ynab = match["ynab"]
        paypal = match["paypal"]

        if paypal:
            days_diff = (
                datetime.strptime(ynab["date"], "%Y-%m-%d")
                - datetime.strptime(paypal["date"], "%Y-%m-%d")
            ).days

            currency_display = (
                f"{paypal['currency']} " if paypal["currency"] != "GBP" else "£"
            )
            amount_str = f"£{abs(ynab['amount']):.2f}"
            merchant = paypal["merchant_name"]
            if paypal.get("item_title"):
                merchant += f" ({paypal['item_title'][:30]}...)" if len(
                    paypal.get("item_title", "")
                ) > 30 else f" ({paypal.get('item_title', '')})"

            table.add_row(
                ynab["date"],
                amount_str,
                paypal["date"],
                merchant,
                f"{match['score']:.2f}",
                str(days_diff),
            )

    if len(matches) > 20:
        console.print(table)
        console.print(f"[dim]... and {len(matches) - 20} more matches[/dim]")
    else:
        console.print(table)


def display_unmatched_table(unmatched):
    """Display a table of unmatched transactions."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Date", style="cyan")
    table.add_column("Amount", justify="right", style="cyan")
    table.add_column("Payee", style="yellow")
    table.add_column("Memo", style="dim")

    for match in unmatched[:20]:  # Limit to first 20
        ynab = match["ynab"]
        table.add_row(
            ynab["date"],
            f"£{abs(ynab['amount']):.2f}",
            ynab.get("payee_name") or "",
            (ynab.get("memo") or "")[:50],
        )

    if len(unmatched) > 20:
        console.print(table)
        console.print(f"[dim]... and {len(unmatched) - 20} more unmatched[/dim]")
    else:
        console.print(table)


def apply_updates(ynab_client, matcher, matches, confidence):
    """Apply updates to YNAB transactions."""
    console.print(
        f"\n[cyan]Generating updates for {confidence} confidence matches...[/cyan]"
    )
    updates = matcher.generate_update_script(matches, min_confidence=confidence)

    if not updates:
        console.print("[yellow]No transactions to update[/yellow]")
        return

    console.print(f"\n[bold]Found {len(updates)} transactions to update[/bold]")
    console.print("\n[bold]Preview of updates:[/bold]")

    preview_table = Table(show_header=True, header_style="bold")
    preview_table.add_column("Merchant", style="green")
    preview_table.add_column("New Memo", style="cyan")
    preview_table.add_column("Confidence", style="yellow")

    for update in updates[:5]:
        preview_table.add_row(
            update["merchant_name"], update["new_memo"][:60], update["confidence"].upper()
        )

    console.print(preview_table)

    if len(updates) > 5:
        console.print(f"[dim]... and {len(updates) - 5} more[/dim]")

    # Confirm before applying
    if not click.confirm("\nApply these updates to YNAB?", default=False):
        console.print("[yellow]Updates cancelled[/yellow]")
        return

    # Apply updates
    console.print("\n[cyan]Applying updates...[/cyan]\n")
    success_count = 0

    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Updating transactions...", total=len(updates))

        for update in updates:
            if ynab_client.update_transaction_memo(
                update["transaction_id"], update["new_memo"]
            ):
                success_count += 1
                console.print(f"[green]✓ Updated: {update['merchant_name']}[/green]")
            else:
                console.print(f"[red]✗ Failed: {update['merchant_name']}[/red]")

            progress.advance(task)

    console.print(
        f"\n[bold green]Successfully updated {success_count}/{len(updates)} transactions[/bold green]\n"
    )


if __name__ == "__main__":
    cli()
